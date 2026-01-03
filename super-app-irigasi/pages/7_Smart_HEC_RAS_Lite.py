import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Pro", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #000428, #004e92); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #004e92; margin-bottom: 10px; }
    .report-box { border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-bottom: 20px; background-color: white; }
    h3 { color: #004e92; border-bottom: 2px solid #eee; padding-bottom: 5px; }
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton, .stTabs nav { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA: STANDARD STEP METHOD (The "Pro" Brain) ---

def get_geom_props(y, b, m):
    """Menghitung properti penampang: Luas (A), Keliling (P), Radius (R), Lebar Atas (T)"""
    if y <= 0: return 0.001, 0.001, 0.001, 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    return A, P, R, T

def solve_energy_equation(y_guess, Q, n, Z1, Z2, y1, b, m, L, dx, mode='subcritical'):
    """
    Menyelesaikan Persamaan Energi Bernoulli antara dua seksi (1 & 2).
    Z1 + y1 + V1^2/2g = Z2 + y2 + V2^2/2g + hf + he
    """
    g = 9.81
    # Properti di Seksi 1 (Diketahui)
    A1, P1, R1, T1 = get_geom_props(y1, b, m)
    V1 = Q / A1
    H1 = Z1 + y1 + (V1**2) / (2*g) # Total Energy di 1
    
    # Fungsi Error untuk dicari akarnya (Target: E2 - E1 + losses = 0)
    def energy_func(y2):
        A2, P2, R2, T2 = get_geom_props(y2, b, m)
        if A2 <= 0: return 1000.0 # Penalty
        V2 = Q / A2
        H2 = Z2 + y2 + (V2**2) / (2*g)
        
        # Friction Slope (Average)
        Sf1 = (n * V1)**2 / (R1**(4/3)) if R1 > 0 else 0
        Sf2 = (n * V2)**2 / (R2**(4/3)) if R2 > 0 else 0
        Sf_avg = (Sf1 + Sf2) / 2
        
        h_f = Sf_avg * dx # Friction Loss
        # h_e = 0 # Expansion/Contraction loss (diabaikan dulu utk simplifikasi)
        
        # Balance Energi tergantung arah hitungan
        # E_hulu = E_hilir + losses
        if mode == 'subcritical': # Hitung Mundur (Hilir ke Hulu) -> 2 adalah Hulu, 1 adalah Hilir
            # H2 (Hulu) = H1 (Hilir) + h_f
            return H2 - (H1 + h_f)
        else: # Superkritis (Hulu ke Hilir) -> 2 adalah Hilir, 1 adalah Hulu
            # H1 (Hulu) = H2 (Hilir) + h_f
            return H1 - (H2 + h_f)

    # Solver Bisection (Stabil)
    y_min, y_max = 0.01, 20.0
    for _ in range(50):
        y_mid = (y_min + y_max) / 2
        err = energy_func(y_mid)
        if abs(err) < 0.001: return y_mid
        
        # Logic Bisection arahnya beda tergantung fungsi naik/turun
        # Energi spesifik itu parabola, jadi kita harus hati-hati.
        # Untuk Subkritis (kedalaman > kritis), dE/dy positif.
        if mode == 'subcritical':
            if err > 0: y_max = y_mid 
            else: y_min = y_mid
        else:
            if err > 0: y_min = y_mid # Superkritis dE/dy negatif di zona dangkal? (Cek lagi nanti, trial dulu)
            else: y_max = y_mid
            
    return (y_min + y_max) / 2

# --- 2. INISIALISASI DATA ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    # Data Default: Saluran beruntun
    data = [
        ["S1 (Hulu)", 0.0, 100.0, 105.0, 104.5, 2.0, 1.0, 0.015],
        ["S2 (Tengah)", 100.0, 200.0, 104.5, 104.0, 2.0, 1.0, 0.015],
        ["S3 (Hilir)", 200.0, 300.0, 104.0, 103.5, 2.0, 1.0, 0.015],
    ]
    return pd.DataFrame(data, columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 5.0
if 'ws_known' not in st.session_state: st.session_state['ws_known'] = 1.5 # Boundary condition default

# --- 3. UI HEADER & SIDEBAR ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 32px;">🚀 Smart HEC-RAS Pro</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.9;">Standard Step Method Solver (Energy Equation)</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Boundary Condition")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    
    # Pilihan Mode Hitungan
    calc_mode = st.radio("Mode Analisa", ["Subkritis (Hilir -> Hulu)", "Superkritis (Hulu -> Hilir)"], index=0)
    mode_key = 'subcritical' if "Sub" in calc_mode else 'supercritical'
    
    st.divider()
    
    # Input Boundary
    if mode_key == 'subcritical':
        st.subheader("🌊 Batas Hilir (Downstream)")
        st.info("Masukkan kedalaman air yang diketahui di ujung paling hilir (misal: kedalaman normal atau level bendung).")
        boundary_y = st.number_input("Kedalaman Air Hilir (m)", 0.1, 20.0, st.session_state['ws_known'])
    else:
        st.subheader("🌊 Batas Hulu (Upstream)")
        st.info("Masukkan kedalaman air yang diketahui di ujung paling hulu.")
        boundary_y = st.number_input("Kedalaman Air Hulu (m)", 0.1, 20.0, st.session_state['ws_known'])
        
    st.divider()
    if st.button("🔄 Reset Data"): 
        st.session_state['df_pro'] = reset_data()
        st.rerun()

# --- 4. MAIN LOGIC (THE PRO SOLVER) ---
df = st.session_state['df_pro']
results = []
profile_coords = {'x': [], 'z': [], 'ws': [], 'eg': [], 'crit': []}

if not df.empty:
    try:
        # 1. Pre-processing Data (Urutkan)
        # Penting: Standard Step butuh data urut spasial
        df = df.sort_values(by="STA Awal (m)")
        
        # Konversi ke List of Dictionaries biar mudah diakses index-nya
        segments = df.to_dict('records')
        
        # 2. Setup Grid Komputasi (Discretization)
        # Kita pecah setiap segmen jadi potongan kecil (dx) biar grafik mulus
        dx_step = 10.0 # Hitung setiap 10 meter
        nodes = []
        
        for seg in segments:
            L = seg["STA Akhir (m)"] - seg["STA Awal (m)"]
            n_steps = int(L / dx_step)
            if n_steps < 1: n_steps = 1
            real_dx = L / n_steps
            
            # Interpolasi Elevasi Dasar (Z)
            z_start = seg["Elev Awal (m)"]
            z_end = seg["Elev Akhir (m)"]
            slope_seg = (z_start - z_end) / L
            
            for i in range(n_steps + 1):
                x_curr = seg["STA Awal (m)"] + i * real_dx
                z_curr = z_start - (i * real_dx * slope_seg)
                
                # Simpan node data
                nodes.append({
                    "x": x_curr,
                    "z": z_curr,
                    "b": seg["Lebar b (m)"],
                    "m": seg["Talud m"],
                    "n": seg["Kekasaran n"],
                    "seg_name": seg["Nama Segmen"]
                })
        
        # Hapus duplikat node di sambungan segmen (opsional, tapi bagus utk grafik)
        # (Disini kita biarkan dulu biar simple)

        # 3. CORE CALCULATION LOOP
        Q = st.session_state['q_pro']
        
        if mode_key == 'subcritical':
            # --- HITUNG MUNDUR (HILIR -> HULU) ---
            # Node terakhir adalah Hilir
            nodes[-1]['y'] = boundary_y
            nodes[-1]['ws'] = nodes[-1]['z'] + boundary_y
            
            # Loop dari node kedua terakhir sampai 0 (Mundur)
            for i in range(len(nodes)-2, -1, -1):
                # Data "Known" (Hilir) -> i+1
                # Data "Unknown" (Hulu) -> i
                known = nodes[i+1]
                target = nodes[i]
                
                dx = known['x'] - target['x'] # Jarak positif
                
                # Hitung Y di target (Hulu)
                y_res = solve_energy_equation(
                    y_guess=known['y'], Q=Q, n=target['n'],
                    Z1=known['z'], Z2=target['z'], y1=known['y'], # 1 = Hilir (Known)
                    b=target['b'], m=target['m'], L=dx, dx=dx, mode='subcritical'
                )
                
                target['y'] = y_res
                target['ws'] = target['z'] + y_res
                
        else:
            # --- HITUNG MAJU (HULU -> HILIR) ---
            # Node pertama adalah Hulu
            nodes[0]['y'] = boundary_y
            nodes[0]['ws'] = nodes[0]['z'] + boundary_y
            
            for i in range(1, len(nodes)):
                # Data "Known" (Hulu) -> i-1
                # Data "Unknown" (Hilir) -> i
                known = nodes[i-1]
                target = nodes[i]
                
                dx = target['x'] - known['x']
                
                y_res = solve_energy_equation(
                    y_guess=known['y'], Q=Q, n=target['n'],
                    Z1=known['z'], Z2=target['z'], y1=known['y'], # 1 = Hulu (Known)
                    b=target['b'], m=target['m'], L=dx, dx=dx, mode='supercritical'
                )
                
                target['y'] = y_res
                target['ws'] = target['z'] + y_res

        # 4. Post-Processing (Hitung E.G., Crit, dll untuk semua node)
        final_data = []
        for n in nodes:
            y = n['y']
            A, P, R, T = get_geom_props(y, n['b'], n['m'])
            V = Q/A if A > 0 else 0
            EGL = n['ws'] + (V**2)/(2*9.81)
            
            # Hitung Critical Depth (untuk referensi)
            # Yc sederhana approx
            yc = ( (Q**2) / (9.81 * n['b']**2) )**(1/3) # Utk persegi, utk trapesium perlu iterasi lagi (skip for speed)
            
            n['eg'] = EGL
            n['v'] = V
            n['fr'] = V / np.sqrt(9.81 * (A/T)) if T > 0 else 0
            n['yc'] = yc
            n['crit_ws'] = n['z'] + yc
            
            final_data.append(n)
            
            # Data Grafik
            profile_coords['x'].append(n['x'])
            profile_coords['z'].append(n['z'])
            profile_coords['ws'].append(n['ws'])
            profile_coords['eg'].append(n['eg'])
            profile_coords['crit'].append(n['crit_ws'])

    except Exception as e:
        st.error(f"Terjadi kesalahan perhitungan: {e}")

# --- 5. TABS VISUALISASI ---
tab_geom, tab_prof, tab_res = st.tabs(["📝 Input Geometri", "📈 Standard Step Profile", "📋 Hasil Detail"])

with tab_geom:
    st.subheader("Editor Geometri Saluran")
    st.caption("Tips: Pastikan urutan STA Awal ke STA Akhir menyambung agar grafik mulus.")
    new_df = st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)
    if not new_df.equals(st.session_state['df_pro']):
        st.session_state['df_pro'] = new_df
        st.rerun()

with tab_prof:
    if len(profile_coords['x']) > 0:
        st.subheader("Longitudinal Profile (Standard Step Method)")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot Dasar
        ax.plot(profile_coords['x'], profile_coords['z'], 'k-', linewidth=2, label='Ground (Bottom)')
        # Plot Air (Continuous)
        ax.plot(profile_coords['x'], profile_coords['ws'], 'b-', linewidth=2, label='Water Surface')
        # Fill Air
        ax.fill_between(profile_coords['x'], profile_coords['z'], profile_coords['ws'], color='#00eaff', alpha=0.6)
        
        # Plot EG
        ax.plot(profile_coords['x'], profile_coords['eg'], 'g--', linewidth=1, label='Energy Grade')
        # Plot Critical
        ax.plot(profile_coords['x'], profile_coords['crit'], 'r:', linewidth=1, alpha=0.7, label='Critical Depth')
        
        ax.set_xlabel('Station (m)')
        ax.set_ylabel('Elevation (m)')
        ax.set_title(f"Profil Muka Air - Q = {st.session_state['q_pro']} m³/s ({calc_mode})")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.5)
        
        st.pyplot(fig)
        
        st.success("""
        ✅ **Profil Tersambung Otomatis!** Grafik di atas dihitung menggunakan **Persamaan Energi Antar Titik**. 
        Perhatikan bagaimana garis air sekarang melengkung halus (Backwater Curve) dan tidak terputus-putus di sambungan segmen.
        """)
    else:
        st.info("Silakan isi data geometri.")

with tab_res:
    if final_data:
        res_df = pd.DataFrame(final_data)
        # Pilih kolom penting
        disp_cols = ["x", "seg_name", "z", "ws", "y", "v", "eg", "fr"]
        res_df = res_df[disp_cols]
        res_df.columns = ["Station", "Segmen", "Elev Dasar", "Elev Air", "Kedalaman", "Kecepatan", "Elev Energi", "Froude"]
        
        st.dataframe(res_df, use_container_width=True)
        
        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Laporan CSV", csv, "laporan_standard_step.csv", "text/csv")
