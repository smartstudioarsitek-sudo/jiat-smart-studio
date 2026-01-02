import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- CONFIG ---
st.set_page_config(page_title="Long Section Analyzer (extrim)", layout="wide", page_icon="📈")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #1565c0, #1976d2); color: white;
        border-radius: 10px; text-align: center; margin-bottom: 20px;
    }
    .metric-card {
        background-color: #e3f2fd; border-left: 5px solid #2196f3; padding: 10px; border-radius: 5px;
    }
    .super-critical { color: red; font-weight: bold; }
    .sub-critical { color: green; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA ---
def solve_manning_y(Q, n, b, S, m):
    """Mencari kedalaman normal (yn)"""
    if S <= 0: return 0 # Slope nol/negatif tidak punya yn di Manning
    y = 0.5
    for _ in range(20):
        A = (b + m*y) * y
        P = b + 2*y * np.sqrt(1 + m**2)
        R = A/P
        f = (1/n) * A * (R**(2/3)) * (S**0.5) - Q
        
        dy = 0.001
        A_d = (b + m*(y+dy)) * (y+dy)
        P_d = b + 2*(y+dy) * np.sqrt(1 + m**2)
        R_d = A_d/P_d
        f_d = (1/n) * A_d * (R_d**(2/3)) * (S**0.5) - Q
        
        df = (f_d - f) / dy
        if df == 0: break
        y_new = y - f/df
        if abs(y_new - y) < 0.0001: return abs(y_new)
        y = abs(y_new)
    return y

def solve_critical_y(Q, b, m):
    """Mencari kedalaman kritis (yc) -> Froude = 1"""
    # Rumus: Q^2 * T / (g * A^3) = 1
    g = 9.81
    y = 0.5
    for _ in range(20):
        A = (b + m*y) * y
        T = b + 2*m*y
        if A <= 0: A = 0.01
        
        f = (Q**2 * T) / (g * A**3) - 1
        
        dy = 0.001
        A_d = (b + m*(y+dy)) * (y+dy)
        T_d = b + 2*m*(y+dy)
        f_d = (Q**2 * T_d) / (g * A_d**3) - 1
        
        df = (f_d - f) / dy
        if df == 0: break
        y_new = y - f/df
        if abs(y_new - y) < 0.0001: return abs(y_new)
        y = abs(y_new)
    return y

# --- INIT STATE ---
if 'df_segments' not in st.session_state:
    # Data Awal: Contoh Kasus Nokan (Saluran -> Terjun -> Saluran)
    data = [
        ["Segmen 1 (Hulu)", 200, 10, 1.5, 1.0, 0.017], # L=200m, BedaTinggi=10m (Curam)
        ["Segmen 2 (Tengah)", 500, 25, 1.5, 0.5, 0.017], # L=500m, BedaTinggi=25m (Sangat Curam)
        ["Segmen 3 (Hilir)", 300, 2, 2.0, 1.0, 0.025],   # L=300m, BedaTinggi=2m (Landai)
    ]
    st.session_state['df_segments'] = pd.DataFrame(data, columns=["Nama Segmen", "Panjang L (m)", "Beda Tinggi dH (m)", "Lebar b (m)", "Talud m", "Kekasaran n"])

# --- UI UTAMA ---
st.markdown('<div class="header-box"><h1>📈 Long Section Analyzer</h1><p>Simulasi Profil Hidrolis Menerus (HEC-RAS Lite)</p></div>', unsafe_allow_html=True)

# SIDEBAR PARAMETER GLOBAL
with st.sidebar:
    st.header("⚙️ Parameter Global")
    Q_global = st.number_input("Debit Desain (Q) m³/s", 0.1, 50.0, 2.0, 0.1)
    Elev_Start = st.number_input("Elevasi Awal (m)", 0.0, 1000.0, 100.0, 1.0, help="Elevasi dasar saluran di titik paling hulu (0+000)")
    
    st.divider()
    st.info("💡 **Tips:** Input data segmen secara urut dari Hulu ke Hilir pada Tab 1.")

# TABS
tab1, tab2, tab3 = st.tabs(["📝 Input Data Segmen", "📉 Profil Memanjang (Long Section)", "🔍 Detail Cross Section"])

# --- TAB 1: INPUT DATA ---
with tab1:
    st.subheader("1. Tabel Skema Saluran")
    st.caption("Edit tabel di bawah ini. Klik '+' untuk tambah segmen baru.")
    
    edited_df = st.data_editor(
        st.session_state['df_segments'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Panjang L (m)": st.column_config.NumberColumn(format="%.1f m"),
            "Beda Tinggi dH (m)": st.column_config.NumberColumn(format="%.2f m", help="Selisih elevasi awal dan akhir segmen"),
            "Kekasaran n": st.column_config.NumberColumn(format="%.3f")
        }
    )
    st.session_state['df_segments'] = edited_df
    
    # PROSES HITUNG
    if len(edited_df) > 0:
        results = []
        current_dist = 0
        current_elev = Elev_Start
        
        for idx, row in edited_df.iterrows():
            L = float(row['Panjang L (m)'])
            dH = float(row['Beda Tinggi dH (m)'])
            b = float(row['Lebar b (m)'])
            m = float(row['Talud m'])
            n = float(row['Kekasaran n'])
            
            # Hitung Slope
            S = dH / L if L > 0 else 0
            
            # Hitung Hidrolika
            yn = solve_manning_y(Q_global, n, b, S, m)
            yc = solve_critical_y(Q_global, b, m)
            
            # Flow Regime
            if yn < yc: 
                status = "SUPER-KRITIS (Cepat)"
                color_st = "red"
            else: 
                status = "SUB-KRITIS (Tenang)"
                color_st = "green"
            
            V = Q_global / ((b + m*yn)*yn) if yn > 0 else 0
            Fr = V / np.sqrt(9.81 * ( ((b+m*yn)*yn)/(b+2*m*yn) )) if yn > 0 else 0
            
            # Simpan Data untuk Plotting (Titik Awal & Akhir Segmen)
            # Titik Awal Segmen
            p_start = {
                'x': current_dist,
                'z_bed': current_elev,
                'z_water': current_elev + yn,
                'z_crit': current_elev + yc
            }
            
            # Update Posisi ke Akhir Segmen
            current_dist += L
            current_elev -= dH
            
            # Titik Akhir Segmen
            p_end = {
                'x': current_dist,
                'z_bed': current_elev,
                'z_water': current_elev + yn,
                'z_crit': current_elev + yc
            }
            
            results.append({
                'data': row,
                'calc': {'S': S, 'yn': yn, 'yc': yc, 'V': V, 'Fr': Fr, 'status': status},
                'plot': [p_start, p_end]
            })
            
        st.session_state['calc_results'] = results
        st.success(f"✅ Berhasil menghitung {len(results)} segmen saluran!")

# --- TAB 2: LONG SECTION ---
with tab2:
    st.subheader("2. Profil Hidrolis Memanjang")
    if 'calc_results' in st.session_state:
        res = st.session_state['calc_results']
        
        # Siapkan Array untuk Plot
        x_all, z_bed_all, z_water_all, z_crit_all = [], [], [], []
        
        for r in res:
            pts = r['plot']
            # Start Point
            x_all.append(pts[0]['x'])
            z_bed_all.append(pts[0]['z_bed'])
            z_water_all.append(pts[0]['z_water'])
            z_crit_all.append(pts[0]['z_crit'])
            # End Point
            x_all.append(pts[1]['x'])
            z_bed_all.append(pts[1]['z_bed'])
            z_water_all.append(pts[1]['z_water'])
            z_crit_all.append(pts[1]['z_crit'])
            
            # Tambahkan gap NaN agar garis tidak nyambung tegak lurus jika ada terjunan tegak (opsional, disini kita assume continuous grade)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot Garis
        ax.plot(x_all, z_bed_all, 'k-', linewidth=2, label='Dasar Saluran (Bed)')
        ax.plot(x_all, z_water_all, 'b-', linewidth=2, label='Muka Air Normal (NDL)')
        ax.plot(x_all, z_crit_all, 'r--', linewidth=1, label='Kedalaman Kritis (CDL)', alpha=0.7)
        
        # Fill Air
        ax.fill_between(x_all, z_bed_all, z_water_all, color='cyan', alpha=0.3)
        
        # Anotasi Segmen
        for r in res:
            pts = r['plot']
            mid_x = (pts[0]['x'] + pts[1]['x']) / 2
            mid_y = (pts[0]['z_bed'] + pts[1]['z_bed']) / 2
            ax.text(mid_x, mid_y, r['data']['Nama Segmen'], rotation=0, ha='center', va='top', fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        ax.set_xlabel("Jarak / Stationing (m)")
        ax.set_ylabel("Elevasi (m)")
        ax.set_title("Long Section: Bed vs Water Surface vs Critical Depth")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.5)
        
        st.pyplot(fig)
        
        st.info("ℹ️ **Garis Biru (NDL):** Tinggi muka air rencana. **Garis Merah Putus (CDL):** Batas kritis. Jika Biru di bawah Merah, aliran Superkritis (Cepat).")

# --- TAB 3: DETAIL & CROSS SECTION ---
with tab3:
    st.subheader("3. Detail Per Segmen")
    if 'calc_results' in st.session_state:
        res = st.session_state['calc_results']
        
        # Pilihi Segmen
        nama_list = [r['data']['Nama Segmen'] for r in res]
        pilih = st.selectbox("Pilih Segmen untuk Detail:", nama_list)
        
        # Ambil Data Terpilih
        selected = next(item for item in res if item['data']['Nama Segmen'] == pilih)
        d = selected['data']
        c = selected['calc']
        
        col_det1, col_det2 = st.columns([1, 1.5])
        
        with col_det1:
            st.markdown("#### Parameter Hidrolis")
            st.write(f"**Debit (Q):** {Q_global} m³/s")
            st.write(f"**Slope (S):** {c['S']*100:.3f} %")
            st.write(f"**Kedalaman Normal (yn):** {c['yn']:.3f} m")
            st.write(f"**Kedalaman Kritis (yc):** {c['yc']:.3f} m")
            st.write(f"**Kecepatan (V):** {c['V']:.2f} m/s")
            st.write(f"**Froude (Fr):** {c['Fr']:.2f}")
            
            if c['Fr'] > 1:
                st.markdown(f"Status: <span class='super-critical'>{c['status']}</span>", unsafe_allow_html=True)
                st.warning("⚠️ Perlu peredam energi di hilir segmen ini!")
            else:
                st.markdown(f"Status: <span class='sub-critical'>{c['status']}</span>", unsafe_allow_html=True)

        with col_det2:
            st.markdown("#### Cross Section")
            # Gambar Penampang
            b, m, yn = float(d['Lebar b (m)']), float(d['Talud m']), c['yn']
            h_draw = max(yn * 1.5, 1.0) # Tinggi galian visual
            
            fig_cs, ax_cs = plt.subplots(figsize=(6, 3))
            
            # Tanah
            x_soil = [-m*h_draw, 0, b, b+m*h_draw]
            y_soil = [h_draw, 0, 0, h_draw]
            ax_cs.plot(x_soil, y_soil, 'k-', linewidth=2)
            
            # Air
            x_water = [-m*yn, b+m*yn]
            y_water = [yn, yn]
            ax_cs.fill_between([-m*yn, 0, b, b+m*yn], [yn, 0, 0, yn], color='cyan', alpha=0.6, label='Air (yn)')
            
            # Kritis Line (Visualisasi batas kritis di penampang)
            yc = c['yc']
            ax_cs.hlines(yc, -m*yc, b+m*yc, colors='red', linestyles='--', label='Batas Kritis (yc)')

            ax_cs.set_title(f"Penampang: {pilih}")
            ax_cs.legend(loc='upper right', fontsize='small')
            ax_cs.set_aspect('equal')
            st.pyplot(fig_cs)
