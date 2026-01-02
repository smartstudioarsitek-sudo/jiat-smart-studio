import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- CONFIG ---
st.set_page_config(page_title="Long Section Analyzer (Nokan)", layout="wide", page_icon="📈")

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
    .rec-box {
        background-color: #fff3e0; border: 1px solid #ffcc80; padding: 15px; border-radius: 5px; margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA ---
def solve_manning_y(Q, n, b, S, m):
    """Mencari kedalaman normal (yn)"""
    if S <= 0: return 0.001
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
    """Mencari kedalaman kritis (yc)"""
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

def generate_recommendations(V, Fr, n, material_hint=""):
    recs = []
    
    # 1. Cek Kecepatan vs Material
    if V > 10.0:
        recs.append("⚠️ **BAHAYA KAVITASI!** Kecepatan > 10 m/s. Wajib gunakan Beton Bertulang Mutu Tinggi (K-350+) & Aerator.")
    elif V > 3.0:
        if n > 0.020: # Indikasi bukan beton halus
            recs.append("⚠️ **Risiko Erosi!** Material kasar (n > 0.020) tidak tahan V > 3 m/s. Ganti ke Lining Beton.")
        else:
            recs.append("ℹ️ Gunakan Beton Mutu K-225 atau lebih.")
    elif V < 0.6:
        recs.append("⚠️ **Risiko Endapan.** Kecepatan < 0.6 m/s. Perbesar slope atau perkecil dimensi.")

    # 2. Cek Rezim Aliran
    if Fr > 1.0:
        recs.append("🌊 **Aliran Superkritis.** Wajib sediakan Kolam Olak (Stilling Basin) di ujung segmen ini.")
        if Fr > 4.5:
            recs.append("ℹ️ Froude Tinggi (>4.5). Gunakan Kolam Olak tipe USBR III.")
    else:
        recs.append("✅ Aliran Subkritis (Tenang). Tidak perlu peredam energi khusus.")

    return recs

# --- INIT STATE ---
if 'df_segments' not in st.session_state:
    data = [
        ["Segmen 1 (Hulu)", 200, 10, 1.5, 1.0, 0.017], 
        ["Segmen 2 (Tengah)", 500, 25, 1.5, 0.5, 0.017], 
        ["Segmen 3 (Hilir)", 300, 2, 2.0, 1.0, 0.025],   
    ]
    st.session_state['df_segments'] = pd.DataFrame(data, columns=["Nama Segmen", "Panjang L (m)", "Beda Tinggi dH (m)", "Lebar b (m)", "Talud m", "Kekasaran n"])

# --- UI UTAMA ---
st.markdown('<div class="header-box"><h1>📈 Long Section Analyzer</h1><p>Simulasi Profil Hidrolis Menerus (HEC-RAS Lite)</p></div>', unsafe_allow_html=True)

# SIDEBAR PARAMETER GLOBAL
with st.sidebar:
    st.header("⚙️ Parameter Global")
    Q_global = st.number_input("Debit Desain (Q) m³/s", 0.1, 50.0, 2.0, 0.1)
    Elev_Start = st.number_input("Elevasi Awal (m)", 0.0, 1000.0, 100.0, 1.0)
    
    st.divider()
    
    # --- FITUR BARU: KAMUS MANNING ---
    with st.expander("📘 Referensi Nilai Manning (n)", expanded=True):
        st.markdown("""
        <small>
        **Material & Nilai n:**
        * 🌊 **Kaca/Plastik/PVC:** 0.010
        * 🏗️ **Beton Halus:** 0.013
        * 🧱 **Beton Kasar:** 0.017
        * 🪨 **Pasangan Batu (Semen):** 0.025
        * ⛰️ **Saluran Tanah (Lurus):** 0.030
        * 🌿 **Saluran Tanah (Rumput):** 0.035
        * 🌳 **Saluran Alami (Berkelok):** 0.040+
        </small>
        """, unsafe_allow_html=True)

# TABS
tab1, tab2, tab3 = st.tabs(["📝 Input Data Segmen", "📉 Profil Memanjang", "🔍 Detail & Rekomendasi"])

# --- TAB 1: INPUT DATA ---
with tab1:
    st.subheader("1. Tabel Skema Saluran")
    st.caption("Lihat referensi nilai 'n' di sidebar kiri.")
    
    edited_df = st.data_editor(
        st.session_state['df_segments'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Panjang L (m)": st.column_config.NumberColumn(format="%.1f m"),
            "Beda Tinggi dH (m)": st.column_config.NumberColumn(format="%.2f m"),
            "Kekasaran n": st.column_config.NumberColumn(format="%.3f", help="Lihat sidebar untuk referensi")
        }
    )
    st.session_state['df_segments'] = edited_df
    
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
            
            S = dH / L if L > 0 else 0
            yn = solve_manning_y(Q_global, n, b, S, m)
            yc = solve_critical_y(Q_global, b, m)
            
            if yn < yc: 
                status = "SUPER-KRITIS (Cepat)"
            else: 
                status = "SUB-KRITIS (Tenang)"
            
            V = Q_global / ((b + m*yn)*yn) if yn > 0 else 0
            Fr = V / np.sqrt(9.81 * ( ((b+m*yn)*yn)/(b+2*m*yn) )) if yn > 0 else 0
            
            p_start = {'x': current_dist, 'z_bed': current_elev, 'z_water': current_elev + yn, 'z_crit': current_elev + yc}
            current_dist += L
            current_elev -= dH
            p_end = {'x': current_dist, 'z_bed': current_elev, 'z_water': current_elev + yn, 'z_crit': current_elev + yc}
            
            results.append({
                'data': row,
                'calc': {'S': S, 'yn': yn, 'yc': yc, 'V': V, 'Fr': Fr, 'status': status},
                'plot': [p_start, p_end]
            })
            
        st.session_state['calc_results'] = results
        st.success(f"✅ Berhasil menghitung {len(results)} segmen!")

# --- TAB 2: LONG SECTION ---
with tab2:
    st.subheader("2. Profil Hidrolis Memanjang")
    if 'calc_results' in st.session_state:
        res = st.session_state['calc_results']
        x_all, z_bed_all, z_water_all, z_crit_all = [], [], [], []
        
        for r in res:
            pts = r['plot']
            x_all.extend([pts[0]['x'], pts[1]['x']])
            z_bed_all.extend([pts[0]['z_bed'], pts[1]['z_bed']])
            z_water_all.extend([pts[0]['z_water'], pts[1]['z_water']])
            z_crit_all.extend([pts[0]['z_crit'], pts[1]['z_crit']])
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_all, z_bed_all, 'k-', linewidth=2, label='Dasar Saluran')
        ax.plot(x_all, z_water_all, 'b-', linewidth=2, label='Muka Air (NDL)')
        ax.plot(x_all, z_crit_all, 'r--', linewidth=1, label='Kritis (CDL)', alpha=0.7)
        ax.fill_between(x_all, z_bed_all, z_water_all, color='cyan', alpha=0.3)
        
        for r in res:
            pts = r['plot']
            mid_x = (pts[0]['x'] + pts[1]['x']) / 2
            mid_y = (pts[0]['z_bed'] + pts[1]['z_bed']) / 2
            ax.text(mid_x, mid_y, r['data']['Nama Segmen'], rotation=0, ha='center', va='top', fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        ax.set_xlabel("Stationing (m)")
        ax.set_ylabel("Elevasi (m)")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.5)
        st.pyplot(fig)

# --- TAB 3: DETAIL & REKOMENDASI ---
with tab3:
    st.subheader("3. Detail Per Segmen")
    if 'calc_results' in st.session_state:
        res = st.session_state['calc_results']
        nama_list = [r['data']['Nama Segmen'] for r in res]
        pilih = st.selectbox("Pilih Segmen:", nama_list)
        
        selected = next(item for item in res if item['data']['Nama Segmen'] == pilih)
        d = selected['data']
        c = selected['calc']
        
        col_det1, col_det2 = st.columns([1, 1.5])
        
        with col_det1:
            st.markdown("#### Parameter")
            st.write(f"**Q:** {Q_global} m³/s | **n:** {d['Kekasaran n']}")
            st.write(f"**Slope:** {c['S']*100:.2f}%")
            st.write(f"**V:** {c['V']:.2f} m/s | **Fr:** {c['Fr']:.2f}")
            
            # --- FITUR BARU: REKOMENDASI OTOMATIS ---
            st.markdown("#### 💡 Rekomendasi Desain")
            recs = generate_recommendations(c['V'], c['Fr'], float(d['Kekasaran n']))
            
            if len(recs) > 0:
                for r in recs:
                    st.markdown(f"""<div style="margin-bottom:5px; padding:8px; background:#fff8e1; border-left:4px solid #ffb300; border-radius:4px; font-size:14px;">{r}</div>""", unsafe_allow_html=True)
            else:
                st.success("✅ Desain Optimal. Tidak ada isu kritis.")

        with col_det2:
            st.markdown("#### Cross Section")
            b, m, yn = float(d['Lebar b (m)']), float(d['Talud m']), c['yn']
            h_draw = max(yn * 1.5, 1.0)
            fig_cs, ax_cs = plt.subplots(figsize=(6, 3))
            
            x_soil = [-m*h_draw, 0, b, b+m*h_draw]
            y_soil = [h_draw, 0, 0, h_draw]
            ax_cs.plot(x_soil, y_soil, 'k-', linewidth=2)
            ax_cs.fill_between([-m*yn, 0, b, b+m*yn], [yn, 0, 0, yn], color='cyan', alpha=0.6, label='Air')
            ax_cs.hlines(c['yc'], -m*c['yc'], b+m*c['yc'], colors='red', linestyles='--', label='Kritis')
            ax_cs.set_aspect('equal')
            ax_cs.legend(fontsize='small')
            st.pyplot(fig_cs)
