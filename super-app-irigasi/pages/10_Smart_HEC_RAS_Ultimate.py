import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json
from scipy.optimize import newton
from scipy.interpolate import interp1d

# =========================================================
# 1. KONFIGURASI HALAMAN & THEME
# =========================================================
st.set_page_config(page_title="JIAT Smart HEC-RAS Ultimate", layout="wide")

st.markdown("""
    <style>
    .report-text { font-family: 'Arial'; font-size: 14px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 5px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 2. FUNGSI STANDARISASI & HIDROLIKA (KP-07)
# =========================================================
def clean_df(df):
    """Membersihkan nama kolom dari spasi dan mengubah ke UPPERCASE agar tidak KeyError."""
    df.columns = df.columns.str.strip().str.upper()
    return df

def solve_manning(Q, b, m, n, S):
    """Solver Manning untuk mencari Tinggi Air Normal (yn)."""
    if S <= 0.00001: return np.nan, 0.0, 0.0, "Genangan/Flat"
    def func(y):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P
        return (1/n) * A * (R**(2/3)) * (S**0.5) - Q
    try:
        yn = newton(func, x0=0.5, maxiter=100)
        A = (b + m * yn) * yn
        V = Q / A
        T = b + 2 * m * yn
        Fr = V / np.sqrt(9.81 * (A/T))
        status = "✅ Sub-Kritis (Aman)"
        if Fr >= 1.1: status = "⚠️ Super-Kritis (Bahaya)"
        elif 0.9 <= Fr < 1.1: status = "⚡ Kritis (Gelombang)"
        return yn, V, Fr, status
    except:
        return np.nan, np.nan, np.nan, "❌ Error Solver"

# =========================================================
# 3. GENERATOR SKRIP AUTOCAD (BWMS STANDARD)
# =========================================================
def generate_scr_long(df, s_hor, s_ver):
    """Membuat file .scr untuk Profil Memanjang."""
    scr = "._PLINE\n"
    for _, row in df.iterrows():
        x = row['STA']
        y = row['ELEV_DESAIN'] * (s_hor / s_ver)
        scr += f"{x},{y}\n"
    scr += "\n._ZOOM _E\n"
    return scr

def generate_scr_cross(b, h_total, m, z_dasar, s_hor, s_ver):
    """Membuat potongan melintang trapesium standar KP-07."""
    # Koordinat relatif dasar saluran (0,0)
    # Titik: Kiri Atas -> Kiri Bawah -> Kanan Bawah -> Kanan Atas
    y_atas = (z_dasar + h_total) * (s_hor / s_ver)
    y_bawah = z_dasar * (s_hor / s_ver)
    x_kiri_atas = -(b/2 + m * h_total)
    x_kiri_bawah = -b/2
    x_kanan_bawah = b/2
    x_kanan_atas = (b/2 + m * h_total)
    
    scr = "._PLINE\n"
    scr += f"{x_kiri_atas},{y_atas}\n{x_kiri_bawah},{y_bawah}\n"
    scr += f"{x_kanan_bawah},{y_bawah}\n{x_kanan_atas},{y_atas}\n\n"
    return scr

# =========================================================
# 4. SIDEBAR & BOUNDARY
# =========================================================
with st.sidebar:
    st.header("📂 Project & File")
    col_f1, col_f2 = st.columns(2)
    with col_f1: st.button("💾 Save")
    with col_f2: st.button("📂 Open")
    
    st.divider()
    st.header("⚙️ Boundary Condition")
    s_awal = st.number_input("STA Awal", value=0.0)
    e_awal = st.number_input("Elev Awal Dasar", value=320.0)
    s_akhir = st.number_input("STA Akhir", value=1150.0)
    e_akhir = st.number_input("Elev Akhir Dasar", value=310.0)
    
    # Hitung Target Slope Global
    L_total = s_akhir - s_awal
    if L_total > 0:
        slope_global = (e_awal - e_akhir) / L_total
        st.info(f"Target I-Global: {slope_global:.6f}")

    st.divider()
    st.header("📐 Skala Print (PDF/SCR)")
    scale_h = st.number_input("Skala Horizontal 1:", value=1000)
    scale_v = st.number_input("Skala Vertikal 1:", value=100)
    st.button("🖨️ Print Laporan (PDF)")

# =========================================================
# 5. MAIN LOGIC
# =========================================================
st.title("🌊 JIAT Smart HEC-RAS: Professional Design")

f_tanah = st.file_uploader("Upload Data Tanah (STA, Elev)", type=['xlsx', 'csv'])
f_terjun = st.file_uploader("Upload Data Terjunan (STA, Terjunan)", type=['xlsx', 'csv'])

if f_tanah and f_terjun:
    try:
        # Load & Clean Data
        df_g = clean_df(pd.read_excel(f_tanah) if f_tanah.name.endswith('xlsx') else pd.read_csv(f_tanah))
        df_t = clean_df(pd.read_excel(f_terjun) if f_terjun.name.endswith('xlsx') else pd.read_csv(f_terjun))

        # Analisa Engineering
        # (Menggunakan parameter dari baris pertama file tanah)
        Q = df_g.iloc[0].get('DEBIT Q (M3/S)', 0.17)
        b = df_g.iloc[0].get('LEBAR B (M)', 0.6)
        m = df_g.iloc[0].get('TALUD M', 1.0)
        n = df_g.iloc[0].get('KEKASARAN N', 0.017)
        
        # Interpolasi Tanah
        df_pts = pd.concat([
            df_g[['STA AWAL (M)', 'ELEV AWAL (M)']].rename(columns={'STA AWAL (M)':'STA', 'ELEV AWAL (M)':'Z'}),
            df_g[['STA AKHIR (M)', 'ELEV AKHIR (M)']].rename(columns={'STA AKHIR (M)':'STA', 'ELEV AKHIR (M)':'Z'})
        ]).drop_duplicates().sort_values('STA')
        get_z_ground = interp1d(df_pts['STA'], df_pts['Z'], kind='linear', fill_value="extrapolate")

        # Logic Perhitungan Segmen
        control_stas = sorted(list(set([s_awal] + df_t['STA'].tolist() + [s_akhir])))
        res_det = []
        curr_z = e_awal

        for i in range(len(control_stas)-1):
            s1, s2 = control_stas[i], control_stas[i+1]
            L = s2 - s1
            # Distribusi elevasi proporsional menuju e_akhir
            target_z2 = e_awal - ((e_awal - e_akhir) * (s2 - s_awal) / L_total)
            slope = (curr_z - target_z2) / L
            if slope < 0.0005: slope = 0.0005 # Min Slope Teknis
            
            yn, V, Fr, status = solve_manning(Q, b, m, n, slope)
            
            # Generate points per 25m
            for st_val in np.linspace(s1, s2, int(L/25)+2):
                z_d = curr_z - (slope * (st_val - s1))
                res_det.append({'STA': st_val, 'ELEV_TANAH': float(get_z_ground(st_val)), 
                                'ELEV_DESAIN': z_d, 'STATUS': status, 'FR': Fr})
            
            # Apply Drop di ujung segmen jika ada
            drop_val = df_t[df_t['STA'] == s2]['TERJUNAN (M)'].sum()
            curr_z = (curr_z - (slope * L)) - drop_val

        df_final = pd.DataFrame(res_det)
        st.success("✅ Perhitungan Selesai!")

        # TABS
        tab_grafik, tab_data, tab_export = st.tabs(["📊 Grafik Profil", "📑 Data Analisa", "💾 Export & AutoCAD"])
        
        with tab_grafik:
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(df_final['STA'], df_final['ELEV_TANAH'], 'brown', label='Tanah Asli')
            ax.plot(df_final['STA'], df_final['ELEV_DESAIN'], 'blue', linewidth=2, label='Dasar Saluran')
            ax.legend(); st.pyplot(fig)

        with tab_data:
            st.dataframe(df_final)
            if any(df_final['FR'] >= 0.9):
                st.warning("⚠️ **Rekomendasi Teknik:** Terdeteksi aliran kritis/superkritis. Perlu penambahan terjunan atau memperlebar dasar saluran (b) untuk menurunkan Froude Number.")

        with tab_export:
            # AutoCAD Section
            st.subheader("🚀 AutoCAD Script (BWMS/KP-07)")
            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                scr_long = generate_scr_long(df_final, scale_h, scale_v)
                st.download_button("📥 Download SCR Long Section", scr_long, "Long_Section.scr")
            with col_ex2:
                # Contoh Cross Section di STA 0
                scr_cross = generate_scr_cross(b, 1.5, m, e_awal, scale_h, scale_v)
                st.download_button("📥 Download SCR Cross (STA 0)", scr_cross, "Cross_Section.scr")

            # Excel Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name='DATA_DETAIL', index=False)
            st.download_button("💾 Download Full Data (Excel)", buffer.getvalue(), "Hasil_Desain.xlsx")

    except Exception as e:
        st.error(f"Terjadi Kesalahan: {e}")
        st.info("Pastikan nama kolom di file Terjunan adalah 'STA' dan 'TERJUNAN (M)'")
