import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import newton
from scipy.interpolate import interp1d
import io

# =========================================================
# 1. KONFIGURASI HALAMAN & STYLE
# =========================================================
st.set_page_config(page_title="Smart HEC-RAS Pro", layout="wide")
st.title("🌊 JIAT Smart HEC-RAS: Professional Design")
st.markdown("""
**Metode:** Boundary Control & Manual Drop Analysis.
Aplikasi ini menghitung hidrolika saluran berdasarkan lokasi terjunan yang ditentukan User.
""")

# =========================================================
# 2. CORE ENGINE: HIDROLIKA & FISIKA
# =========================================================
def solve_manning(Q, b, m, n, S):
    """
    Menghitung Depth (yn), Velocity (V), dan Froude (Fr)
    menggunakan Newton-Raphson Solver.
    """
    # Safety: Jika slope terlalu kecil/negatif, return flow sangat lambat
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
        if Fr >= 1.0: status = "⚠️ Super-Kritis (Bahaya)"
        if 0.9 <= Fr <= 1.1: status = "⚡ Kritis (Gelombang)"
        
        return yn, V, Fr, status
    except:
        return np.nan, np.nan, np.nan, "❌ Error Solver"

# =========================================================
# 3. DATA PROCESSOR (ANTI-ERROR)
# =========================================================
def clean_columns(df):
    """Membersihkan spasi di nama kolom agar tidak error."""
    df.columns = [c.strip() for c in df.columns]
    return df

def process_design(df_ground, df_drops):
    # --- A. Setup Interpolasi Tanah ---
    # Mengubah data segmen menjadi titik kontinyu
    pts = []
    # Ambil parameter desain dari baris pertama
    Q_des = df_ground.iloc[0].get('Debit Q (m3/s)', 0.17)
    b_des = df_ground.iloc[0].get('Lebar b (m)', 0.6)
    m_des = df_ground.iloc[0].get('Talud m', 1.0)
    n_des = df_ground.iloc[0].get('Kekasaran n', 0.017)
    
    # Buat array titik tanah
    for _, row in df_ground.iterrows():
        pts.append((row['STA Awal (m)'], row['Elev Awal (m)']))
    # Titik terakhir
    last = df_ground.iloc[-1]
    pts.append((last['STA Akhir (m)'], last['Elev Akhir (m)']))
    
    df_pts = pd.DataFrame(pts, columns=['STA', 'Z']).drop_duplicates('STA').sort_values('STA')
    get_z_ground = interp1d(df_pts['STA'], df_pts['Z'], kind='linear', fill_value="extrapolate")
    
    # --- B. Setup Control Points (Boundary) ---
    max_sta = df_pts['STA'].max()
    # Gabungkan STA 0, STA Terjunan, dan STA Akhir
    control_stas = sorted(list(set([0] + df_drops['STA'].tolist() + [max_sta])))
    
    results_detail = []
    results_segment = []
    
    # Parameter Galian
    CUT_IDEAL = 1.0  # Meter
    
    # Start Elevasi Desain (Tanah - Galian)
    current_z_des = get_z_ground(0) - CUT_IDEAL
    
    # --- C. Loop Perhitungan Per Segmen ---
    for i in range(len(control_stas) - 1):
        s_start = control_stas[i]
        s_end = control_stas[i+1]
        L = s_end - s_start
        
        if L <= 0: continue
        
        # 1. Cek Drop di Ujung Segmen
        drop_h = 0.0
        row_d = df_drops[df_drops['STA'] == s_end]
        if not row_d.empty:
            drop_h = row_d.iloc[0]['TERJUNAN (m)']
            
        # 2. Tentukan Target Elevasi (Sebelum Drop)
        z_end_target = get_z_ground(s_end) - CUT_IDEAL
        
        # 3. Hitung Slope (I)
        slope = (current_z_des - z_end_target) / L
        
        # Auto-Correction: Jika nanjak (slope negatif), set ke minimum teknis
        note = "Normal"
        if slope < 0.0005:
            slope = 0.0005
            note = "Slope Adjusted (Min)"
            # Recalculate target elevation
            z_end_target = current_z_des - (slope * L)
            
        # 4. Hitung Hidrolika
        yn, V, Fr, status = solve_manning(Q_des, b_des, m_des, n_des, slope)
        
        results_segment.append({
            'STA Awal': s_start,
            'STA Akhir': s_end,
            'Panjang (m)': L,
            'Drop (m)': drop_h,
            'Slope Desain': slope,
            'Kecepatan (m/s)': V,
            'Froude': Fr,
            'Status': status,
            'Note': note
        })
        
        # 5. Generate Detail Points (Untuk Grafik & AutoCAD)
        # Interval 25m
        stas = np.arange(s_start, s_end, 25.0)
        if stas[-1] != s_end: stas = np.append(stas, s_end)
        
        for st in stas:
            z_d = current_z_des - (slope * (st - s_start))
            z_g = get_z_ground(st)
            results_detail.append({
                'STA': st,
                'Elev Tanah': z_g,
                'Elev Desain': z_d,
                'Tinggi Galian': z_g - z_d,
                'Keterangan': 'Saluran'
            })
            
        # 6. Handle Drop (Garis Vertikal)
        z_after_drop = z_end_target - drop_h
        if drop_h > 0:
            results_detail.append({
                'STA': s_end,
                'Elev Tanah': get_z_ground(s_end),
                'Elev Desain': z_after_drop,
                'Tinggi Galian': get_z_ground(s_end) - z_after_drop,
                'Keterangan': f'Bottom Drop {drop_h}m'
            })
            
        # Update Start Elevasi untuk Loop berikutnya
        current_z_des = z_after_drop

    return pd.DataFrame(results_segment), pd.DataFrame(results_detail), Q_des

# =========================================================
# 4. USER INTERFACE (STREAMLIT)
# =========================================================
col1, col2 = st.columns(2)
with col1:
    f_ground = st.file_uploader("📂 Upload Data Tanah (CSV/Excel)", type=['csv', 'xlsx'])
with col2:
    f_drops = st.file_uploader("📂 Upload Data Terjunan Manual (CSV/Excel)", type=['csv', 'xlsx'])

if f_ground and f_drops:
    try:
        # Load Data
        df_g = pd.read_csv(f_ground) if f_ground.name.endswith('csv') else pd.read_excel(f_ground)
        df_d = pd.read_csv(f_drops) if f_drops.name.endswith('csv') else pd.read_excel(f_drops)
        
        # Clean Data
        df_g = clean_columns(df_g)
        df_d = clean_columns(df_d)
        
        # Pastikan kolom Drop positif
        if 'TERJUNAN (m)' in df_d.columns:
            df_d['TERJUNAN (m)'] = df_d['TERJUNAN (m)'].fillna(0).abs()
        
        # RUN CALCULATION
        with st.spinner('Sedang melakukan analisa hidrolika professional...'):
            df_segmen, df_detail, Q_val = process_design(df_g, df_d)
            
        st.success("✅ Perhitungan Selesai! Analisa Professional berhasil dijalankan.")
        
        # --- TAB OUTPUT ---
        tab1, tab2, tab3 = st.tabs(["📊 Grafik Profil", "📑 Data Analisa", "💾 Download Hasil"])
        
        with tab1:
            st.subheader("Profil Memanjang (Long Section)")
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Plot Tanah
            ax.plot(df_detail['STA'], df_detail['Elev Tanah'], 'g--', label='Tanah Asli', alpha=0.6)
            # Plot Desain
            ax.plot(df_detail['STA'], df_detail['Elev Desain'], 'b-', linewidth=2, label='Desain Saluran')
            
            # Plot Drops (Vertical Lines)
            drops_x = df_d['STA']
            for x in drops_x:
                ax.axvline(x, color='red', linestyle=':', alpha=0.3)
            
            ax.set_xlabel('Station (m)')
            ax.set_ylabel('Elevasi (m)')
            ax.set_title(f'Desain Saluran Irigasi (Q = {Q_val} m3/s)')
            ax.legend()
            ax.grid(True, which='both', linestyle='--', alpha=0.5)
            
            st.pyplot(fig)
            
            # Info Box
            st.info("💡 **Tips Membaca Grafik:** Garis Biru adalah dasar saluran. Garis patah vertikal (jika ada) menunjukkan lokasi terjunan.")

        with tab2:
            st.subheader("Ringkasan Analisa Per Segmen")
            # Highlight Status Bahaya
            st.dataframe(df_segmen.style.applymap(lambda v: 'color: red; font-weight: bold;' if isinstance(v, str) and 'Super' in v else None, subset=['Status']))
            
            st.subheader("Detail Data Per 25m")
            st.dataframe(df_detail)

        with tab3:
            st.subheader("Export Center")
            
            # Buat File Excel di Memory
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_segmen.to_excel(writer, sheet_name='ANALISA_HIDROLIKA', index=False)
                df_detail.to_excel(writer, sheet_name='DETAIL_STA_25', index=False)
                
                # Sheet AutoCAD (Format Khusus X,Y)
                df_acad = df_detail[['STA', 'Elev Desain']].copy()
                df_acad.columns = ['X', 'Y']
                df_acad.to_excel(writer, sheet_name='DATA_AUTOCAD', index=False)
                
            buffer.seek(0)
            
            st.download_button(
                label="📥 Download Laporan Lengkap (.xlsx)",
                data=buffer,
                file_name="HASIL_DESAIN_PROFESIONAL.xlsx",
                mime="application/vnd.ms-excel"
            )
            st.markdown("*File ini berisi sheet khusus **DATA_AUTOCAD** untuk plotting otomatis.*")

    except Exception as e:
        st.error(f"Terjadi Kesalahan: {e}")
        st.warning("Pastikan nama kolom di Excel sudah benar: 'STA Awal (m)', 'Elev Awal (m)', 'STA', 'TERJUNAN (m)'.")

else:
    st.info("👋 Silakan upload file **Data Tanah** dan **Data Terjunan** untuk memulai.")
