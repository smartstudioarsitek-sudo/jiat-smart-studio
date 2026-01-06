import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from scipy.optimize import newton
from scipy.interpolate import interp1d

# =========================================================
# 1. KONFIGURASI HALAMAN
# =========================================================
st.set_page_config(page_title="Smart HEC-RAS Pro - KP 07 Standard", layout="wide")

# =========================================================
# 2. CORE ENGINE: HIDROLIKA
# =========================================================
def solve_manning(Q, b, m, n, S):
    if S <= 1e-6: return np.nan, 0.0, 0.0, "Genangan/Flat"
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
        status = "✅ Sub-Kritis"
        if Fr >= 1.1: status = "⚠️ Super-Kritis"
        elif 0.9 <= Fr < 1.1: status = "⚡ Kritis"
        return yn, V, Fr, status
    except:
        return np.nan, np.nan, np.nan, "❌ Error"

# =========================================================
# 3. SIDEBAR: BOUNDARY & PROJECT
# =========================================================
with st.sidebar:
    st.header("📂 Project Management")
    st.button("💾 Save Project")
    st.button("📂 Open Project")

    st.divider()
    st.header("⚙️ Boundary Condition")
    sta_awal = st.number_input("STA Awal (m)", value=0.0)
    elev_awal = st.number_input("Elev Awal Dasar (m)", value=319.0)
    sta_akhir = st.number_input("STA Akhir (m)", value=1000.0)
    elev_akhir = st.number_input("Elev Akhir Dasar (m)", value=315.0) # Permintaan User

    # Hitung Kemiringan Total
    dist_total = sta_akhir - sta_awal
    if dist_total > 0:
        slope_total = (elev_awal - elev_akhir) / dist_total
        st.info(f"**Target Kemiringan Total:** {slope_total:.6f}")
    
    st.divider()
    st.header("📐 Skala Profil")
    s_hor = st.select_slider("Horizontal 1:", options=[500, 1000, 2000], value=1000)
    s_ver = st.select_slider("Vertikal 1:", options=[50, 100, 200], value=100)

# =========================================================
# 4. DATA PROCESSOR
# =========================================================
def run_analysis(df_g, df_d, s_start, z_start, s_end, z_end):
    # Parameter dari baris pertama
    Q = df_g.iloc[0].get('Debit Q (m3/s)', 0.17)
    b = df_g.iloc[0].get('Lebar b (m)', 0.6)
    m = df_g.iloc[0].get('Talud m', 1.0)
    n = df_g.iloc[0].get('Kekasaran n', 0.017)

    # Interpolasi Tanah
    pts = []
    for _, r in df_g.iterrows(): pts.append((r['STA Awal (m)'], r['Elev Awal (m)']))
    last = df_g.iloc[-1]
    pts.append((last['STA Akhir (m)'], last['Elev Akhir (m)']))
    df_pts = pd.DataFrame(pts, columns=['STA', 'Z']).drop_duplicates('STA').sort_values('STA')
    get_z_ground = interp1d(df_pts['STA'], df_pts['Z'], kind='linear', fill_value="extrapolate")

    # Jalur STA
    control_stas = sorted(list(set([s_start] + df_d['STA'].tolist() + [s_end])))
    control_stas = [s for s in control_stas if s_start <= s <= s_end]

    res_seg = []
    res_det = []
    curr_z = z_start

    for i in range(len(control_stas) - 1):
        s1, s2 = control_stas[i], control_stas[i+1]
        L = s2 - s1
        
        # Penentuan slope segmen: menuju target elevasi akhir secara proporsional atau mengikuti profil tanah
        target_z_end = z_start - ((z_start - z_end) * (s2 - s_start) / (s_end - s_start))
        slope = (curr_z - target_z_end) / L
        if slope < 0.0005: slope = 0.0005 # Minimum slope teknis

        yn, V, Fr, status = solve_manning(Q, b, m, n, slope)
        res_seg.append({'STA_Awal': s1, 'STA_Akhir': s2, 'L': L, 'Slope': slope, 'V': V, 'Fr': Fr, 'Status': status})

        # Detail titik
        for st in np.linspace(s1, s2, int(L/25)+2):
            z_d = curr_z - (slope * (st - s1))
            z_g = get_z_ground(st)
            res_det.append({'STA': st, 'Elev_Tanah': z_g, 'Elev_Desain': z_d, 'Galian': z_g - z_d})

        # Cek Drop
        drop = df_d[df_d['STA'] == s2]['TERJUNAN (m)'].sum()
        curr_z = (curr_z - (slope * L)) - drop

    return pd.DataFrame(res_seg), pd.DataFrame(res_det), Q

# =========================================================
# 5. MAIN UI
# =========================================================
st.title("🌊 JIAT Smart HEC-RAS: Professional Design")

f1 = st.file_uploader("📂 Data Tanah", type=['csv', 'xlsx'])
f2 = st.file_uploader("📂 Data Terjunan", type=['csv', 'xlsx'])

if f1 and f2:
    df_g = pd.read_csv(f1) if f1.name.endswith('csv') else pd.read_excel(f1)
    df_d = pd.read_csv(f2) if f2.name.endswith('csv') else pd.read_excel(f2)
    
    df_seg, df_det, Q_val = run_analysis(df_g, df_d, sta_awal, elev_awal, sta_akhir, elev_akhir)
    st.success("Perhitungan Selesai!")

    t1, t2, t3, t4 = st.tabs(["📊 Grafik", "📑 Data", "💾 Export Data", "🖨️ AutoCAD"])

    with t1:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_det['STA'], df_det['Elev_Tanah'], 'brown', label='Tanah')
        ax.plot(df_det['STA'], df_det['Elev_Desain'], 'blue', label='Desain')
        ax.legend(); st.pyplot(fig)

    with t2:
        st.dataframe(df_seg)

    with t3:
        st.subheader("Download Hasil Analisa")
        # Perbaikan: Membuat Excel Buffer agar tidak kosong
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_seg.to_excel(writer, sheet_name='Analisa_Segmen', index=False)
            df_det.to_excel(writer, sheet_name='Detail_STA', index=False)
            # Sheet khusus AutoCAD
            df_acad = df_det[['STA', 'Elev_Desain']].copy()
            df_acad.to_excel(writer, sheet_name='DATA_AUTOCAD', index=False)
        
        st.download_button(
            label="📥 Download Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="Hasil_Desain_JIAT.xlsx",
            mime="application/vnd.ms-excel"
        )
        st.write("File Excel berisi detail STA, Analisa Hidrolika, dan Koordinat AutoCAD.")

    with t4:
        st.code(f"Script AutoCAD (PLINE):\n" + "\n".join([f"{r.STA},{r.Elev_Desain*10}" for i, r in df_det.iterrows()]))
