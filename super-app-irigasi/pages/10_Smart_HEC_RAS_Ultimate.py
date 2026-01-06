import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json
from scipy.optimize import newton
from scipy.interpolate import interp1d

# =========================================================
# 1. KONFIGURASI HALAMAN
# =========================================================
st.set_page_config(page_title="Smart HEC-RAS Pro - KP 07 Standard", layout="wide")

# Custom CSS agar tampilan lebih bersih
st.markdown("""
    <style>
    .report-text { font-family: 'Courier New', Courier, monospace; font-size: 14px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px 5px 0 0; }
    .stTabs [aria-selected="true"] { background-color: #007BFF !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 2. CORE ENGINE: HIDROLIKA & FISIKA (KP 07)
# =========================================================
def solve_manning(Q, b, m, n, S):
    """Menghitung yn, V, dan Fr menggunakan kaidah teknis ketat."""
    if S <= 1e-6: 
        return np.nan, 0.0, 0.0, "Genangan/Flat"

    def func_manning(y):
        if y <= 0: return -Q
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P
        return (1/n) * A * (R**(2/3)) * (S**0.5) - Q

    try:
        yn = newton(func_manning, x0=0.5, maxiter=50)
        A = (b + m * yn) * yn
        V = Q / A
        T = b + 2 * m * yn
        D = A / T
        Fr = V / np.sqrt(9.81 * D)
        
        status = "✅ Sub-Kritis (Aman)"
        if Fr >= 1.1: status = "⚠️ Super-Kritis (Bahaya)"
        elif 0.9 <= Fr < 1.1: status = "⚡ Kritis (Gelombang)"
        
        return yn, V, Fr, status
    except:
        return np.nan, np.nan, np.nan, "❌ Error Solver"

def generate_autocad_script(df, type="long", scale_h=1000, scale_v=100):
    """Script AutoCAD SCR mengikuti standar plotting BWMS."""
    script = "._PLINE\n"
    for _, row in df.iterrows():
        # Skala Vertikal biasanya diperbesar (Ex: 1:100) dibanding Horizontal (1:1000)
        x = row['STA']
        y = row['Elev Desain'] * (scale_h / scale_v)
        script += f"{x},{y}\n"
    script += "\n._ZOOM _E\n"
    return script

# =========================================================
# 3. SIDEBAR: PROJECT MANAGEMENT & BOUNDARY
# =========================================================
with st.sidebar:
    st.header("📂 Project Management")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.button("💾 Save Project")
    with col_s2:
        st.button("📂 Open Project")

    st.divider()
    st.header("⚙️ Boundary Condition")
    st.caption("Gunakan data hasil survey lapangan (BM)")
    sta_awal_input = st.number_input("STA Awal (m)", value=0.0)
    elev_awal_input = st.number_input("Elev Awal Dasar (m)", value=319.0)
    sta_akhir_input = st.number_input("STA Akhir (m)", value=1000.0)
    
    st.divider()
    st.header("📐 Skala Profil (PDF/CAD)")
    s_hor = st.select_slider("Skala Horizontal 1:", options=[100, 200, 500, 1000, 2000], value=1000)
    s_ver = st.select_slider("Skala Vertikal 1:", options=[10, 20, 50, 100, 200], value=100)

# =========================================================
# 4. DATA PROCESSOR
# =========================================================
def clean_columns(df):
    df.columns = [c.strip() for c in df.columns]
    return df

def run_professional_analysis(df_ground, df_drops, s_start, z_start, s_end_limit):
    # Parameter Desain (Ambil dari baris 1)
    Q_des = df_ground.iloc[0].get('Debit Q (m3/s)', 0.17)
    b_des = df_ground.iloc[0].get('Lebar b (m)', 0.6)
    m_des = df_ground.iloc[0].get('Talud m', 1.0)
    n_des = df_ground.iloc[0].get('Kekasaran n', 0.017)

    # Setup Interpolasi Tanah
    pts = []
    for _, row in df_ground.iterrows():
        pts.append((row['STA Awal (m)'], row['Elev Awal (m)']))
    last = df_ground.iloc[-1]
    pts.append((last['STA Akhir (m)'], last['Elev Akhir (m)']))
    
    df_pts = pd.DataFrame(pts, columns=['STA', 'Z']).drop_duplicates('STA').sort_values('STA')
    get_z_ground = interp1d(df_pts['STA'], df_pts['Z'], kind='linear', fill_value="extrapolate")

    # Control Points (STA 0 + Drops + STA Akhir)
    control_stas = sorted(list(set([s_start] + df_drops['STA'].tolist() + [s_end_limit])))
    control_stas = [s for s in control_stas if s_start <= s <= s_end_limit]

    results_detail = []
    results_segment = []
    current_z_des = z_start

    for i in range(len(control_stas) - 1):
        s1, s2 = control_stas[i], control_stas[i+1]
        L = s2 - s1
        if L <= 0: continue

        # Hitung Slope Berdasarkan Target Tanah di ujung segmen (KP-07: Galian Min 1m)
        z_end_target = get_z_ground(s2) - 1.0
        slope = (current_z_des - z_end_target) / L
        
        note = "Normal"
        if slope < 0.0005:
            slope = 0.0005
            note = "Slope Adjusted (Min)"
            z_end_target = current_z_des - (slope * L)

        yn, V, Fr, status = solve_manning(Q_des, b_des, m_des, n_des, slope)
        
        results_segment.append({
            'STA Awal': s1, 'STA Akhir': s2, 'Panjang (m)': L,
            'Slope Desain': slope, 'Kecepatan (m/s)': V, 'Froude': Fr, 'Status': status, 'Note': note
        })

        # Detail STA per 25m
        stas = np.arange(s1, s2, 25.0)
        if stas[-1] != s2: stas = np.append(stas, s2)
        for st in stas:
            z_d = current_z_des - (slope * (st - s1))
            results_detail.append({
                'STA': st, 'Elev Tanah': get_z_ground(st), 'Elev Desain': z_d, 'Tinggi Galian': get_z_ground(st) - z_d
            })

        # Handle Drop
        drop_h = 0.0
        row_d = df_drops[df_drops['STA'] == s2]
        if not row_d.empty:
            drop_h = row_d.iloc[0]['TERJUNAN (m)']
            current_z_des = z_end_target - drop_h
            results_detail.append({
                'STA': s2, 'Elev Tanah': get_z_ground(s2), 'Elev Desain': current_z_des, 'Tinggi Galian': get_z_ground(s2) - current_z_des
            })
        else:
            current_z_des = z_end_target

    return pd.DataFrame(results_segment), pd.DataFrame(results_detail), Q_des

# =========================================================
# 5. UI MAIN CONTENT
# =========================================================
st.title("🌊 JIAT Smart HEC-RAS: Professional Design")

col1, col2 = st.columns(2)
with col1:
    f_ground = st.file_uploader("📂 Upload Data Tanah", type=['csv', 'xlsx'])
with col2:
    f_drops = st.file_uploader("📂 Upload Data Terjunan", type=['csv', 'xlsx'])

if f_ground and f_drops:
    try:
        df_g = clean_columns(pd.read_csv(f_ground) if f_ground.name.endswith('csv') else pd.read_excel(f_ground))
        df_d = clean_columns(pd.read_csv(f_drops) if f_drops.name.endswith('csv') else pd.read_excel(f_drops))
        
        df_segmen, df_detail, Q_val = run_professional_analysis(df_g, df_d, sta_awal_input, elev_awal_input, sta_akhir_input)
        
        st.success("✅ Perhitungan Selesai! Analisa Professional berhasil dijalankan.")

        tab1, tab2, tab3, tab4 = st.tabs(["📊 Grafik Profil", "📑 Data Analisa", "💾 Export Data", "🖨️ Output Print (AutoCAD)"])

        with tab1:
            st.subheader("Profil Memanjang (Long Section)")
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(df_detail['STA'], df_detail['Elev Tanah'], color='brown', linestyle='--', label='Tanah Asli', alpha=0.7)
            ax.plot(df_detail['STA'], df_detail['Elev Desain'], color='blue', linewidth=2, label='Dasar Saluran (Desain)')
            ax.set_xlabel("Stationing (STA)")
            ax.set_ylabel("Elevasi (m)")
            ax.legend()
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            
            # Tombol Print Browser
            st.button("🖨️ Print Halaman Ini (PDF)")

        with tab2:
            st.subheader("Evaluasi Teknis Per Segmen")
            st.dataframe(df_segmen.style.applymap(lambda v: 'color: red; font-weight: bold;' if 'Super' in str(v) else '', subset=['Status']))
            
            # Rekomendasi Otomatis
            for _, row in df_segmen.iterrows():
                if "Super-Kritis" in row['Status']:
                    st.error(f"⚠️ **Bahaya di STA {row['STA Awal']}-{row['STA Akhir']}:** Aliran Super-Kritis ($Fr > 1.1$). Rekomendasi: Pasang Kolam Olak (Energy Dissipator) atau perkecil slope.")

        with tab4:
            st.subheader("🚀 AutoCAD SCR Script Generator")
            scr_content = generate_autocad_script(df_detail, "long", s_hor, s_ver)
            st.code(scr_content, language="sql")
            st.download_button("📥 Download Long Section (.SCR)", data=scr_content, file_name="JIAT_LONG_SECTION.scr")
            st.info("Cara Pakai: Buka AutoCAD -> Ketik 'SCRIPT' -> Pilih file ini -> Selesai.")

    except Exception as e:
        st.error(f"Terjadi kesalahan data: {e}")
