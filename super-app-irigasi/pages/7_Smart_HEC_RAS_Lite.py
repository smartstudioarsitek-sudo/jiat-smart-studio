import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import io

# --- CONFIG ---
# Judul di Browser Tab diganti jadi Smart HEC-RAS Lite
st.set_page_config(page_title="Smart HEC-RAS Lite", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    /* Header Box dengan Warna Biru HEC-RAS */
    .header-box {
        padding: 25px; 
        background: linear-gradient(90deg, #0d47a1, #1976d2); 
        color: white;
        border-radius: 12px; 
        text-align: center; 
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card {
        background-color: #e3f2fd; border-left: 5px solid #2196f3; padding: 10px; border-radius: 5px;
    }
    .super-critical { color: red; font-weight: bold; }
    .sub-critical { color: green; font-weight: bold; }
    
    /* Hide Streamlit elements when printing */
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA (Manning & Critical Flow) ---
def solve_manning_y(Q, n, b, S, m):
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

def generate_recommendations(V, Fr, n):
    recs = []
    if V > 10.0: recs.append("⚠️ **BAHAYA KAVITASI!** V > 10 m/s. Wajib Beton Mutu Tinggi (K-350+) & Aerator.")
    elif V > 3.0:
        if n > 0.020: recs.append("⚠️ **Risiko Erosi!** Material kasar tidak tahan V > 3 m/s. Ganti Lining Beton.")
        else: recs.append("ℹ️ Gunakan Beton Mutu K-225 atau lebih.")
    elif V < 0.6: recs.append("⚠️ **Risiko Endapan.** V < 0.6 m/s. Perbesar slope.")
    
    if Fr > 1.0:
        recs.append("🌊 **Superkritis.** Wajib Kolam Olak di hilir.")
        if Fr > 4.5: recs.append("ℹ️ Froude Tinggi (>4.5). Gunakan Kolam Olak USBR III.")
    else: recs.append("✅ Subkritis. Aman.")
    return recs

# --- INIT STATE ---
if 'df_segments' not in st.session_state:
    data = [
        ["Segmen 1 (Hulu)", 200, 10, 1.5, 1.0, 0.017], 
        ["Segmen 2 (Tengah)", 500, 25, 1.5, 0.5, 0.017], 
        ["Segmen 3 (Hilir)", 300, 2, 2.0, 1.0, 0.025],   
    ]
    st.session_state['df_segments'] = pd.DataFrame(data, columns=["Nama Segmen", "Panjang L (m)", "Beda Tinggi dH (m)", "Lebar b (m)", "Talud m", "Kekasaran n"])
if 'q_global' not in st.session_state: st.session_state['q_global'] = 2.0
if 'elev_start' not in st.session_state: st.session_state['elev_start'] = 100.0

# --- UI UTAMA ---
# JUDUL BARU SESUAI REQUEST
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 36px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 16px; opacity: 0.9;">Simulasi Profil Hidrolis Menerus & Analisa Saluran Ekstrim</p>
</div>
""", unsafe_allow_html=True)

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Parameter Global")
    st.session_state['q_global'] = st.number_input("Debit Desain (Q) m³/s", 0.1, 50.0, st.session_state['q_global'], 0.1)
    st.session_state['elev_start'] = st.number_input("Elevasi Awal (m)", 0.0, 1000.0, st.session_state['elev_start'], 1.0)
    
    st.divider()
    
    # SAVE / OPEN
    st.subheader("💾 Manajemen File")
    project_data = {
        'q': st.session_state['q_global'],
        'elev': st.session_state['elev_start'],
        'segments': st.session_state['df_segments'].to_dict(orient='records')
    }
    json_str = json.dumps(project_data, indent=2)
    st.download_button("💾 Simpan Data (.json)", json_str, file_name="smart_hec_ras_data.json", mime="application/json")
    
    uploaded_json = st.file_uploader("Buka File Data", type=['json'])
    if uploaded_json is not None:
        try:
            loaded = json.load(uploaded_json)
            st.session_state['q_global'] = loaded['q']
            st.session_state['elev_start'] = loaded['elev']
            st.session_state['df_segments'] = pd.DataFrame(loaded['segments'])
            st.success("✅ Data Berhasil Dimuat!")
            st.rerun()
        except: st.error("Format file salah.")

    with st.expander("📘 Referensi Nilai n"):
        st.markdown("* Beton: 0.013-0.017\n* Batu: 0.025\n* Tanah: 0.030")

# === MAIN TABS ===
tab1, tab2, tab3 = st.tabs(["📝 Input Data", "📉 Profil Memanjang", "🔍 Detail & Rekomendasi"])

with tab1:
    st.subheader("1. Tabel Skema Saluran")
    edited_df = st.data_editor(st.session_state['df_segments'], num_rows="dynamic", use_container_width=True)
    st.session_state['df_segments'] = edited_df
    
    if len(edited_df) > 0:
        results = []
        current_dist = 0
        current_elev = st.session_state['elev_start']
        
        for idx, row in edited_df.iterrows():
            try:
                L, dH = float(row['Panjang L (m)']), float(row['Beda Tinggi dH (m)'])
                b, m, n = float(row['Lebar b (m)']), float(row['Talud m']), float(row['Kekasaran n'])
            except: continue 
            
            S = dH / L if L > 0 else 0
            yn = solve_manning_y(st.session_state['q_global'], n, b, S, m)
            yc = solve_critical_y(st.session_state['q_global'], b, m)
            status = "SUPER-KRITIS" if yn < yc else "SUB-KRITIS"
            V = st.session_state['q_global'] / ((b + m*yn)*yn) if yn > 0 else 0
            Fr = V / np.sqrt(9.81 * (((b+m*yn)*yn)/(b+2*m*yn))) if yn > 0 else 0
            
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
        if len(results) > 0: st.success(f"✅ Berhasil menghitung {len(results)} segmen!")

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
            ax.text(mid_x, mid_y, str(r['data']['Nama Segmen']), ha='center', va='top', fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        ax.set_xlabel("Jarak (m)"); ax.set_ylabel("Elevasi (m)"); ax.legend(); ax.grid(True, linestyle=':', alpha=0.5)
        st.pyplot(fig)

with tab3:
    st.subheader("3. Detail & Rekomendasi")
    if 'calc_results' in st.session_state:
        res = st.session_state['calc_results']
        nama_list = [str(r['data']['Nama Segmen']) for r in res]
        pilih = st.selectbox("Pilih Segmen:", nama_list)
        selected = next(item for item in res if str(item['data']['Nama Segmen']) == pilih)
        c, d = selected['calc'], selected['data']
        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.metric("Kecepatan (V)", f"{c['V']:.2f} m/s", f"Fr: {c['Fr']:.2f}")
            is_super = 'SUPER' in c['status']
            st.metric("Status Aliran", c['status'], delta="- BAHAYA" if is_super else "+ AMAN")
            st.markdown("#### 💡 Saran Teknis")
            for r in generate_recommendations(c['V'], c['Fr'], float(d['Kekasaran n'])): st.info(r)
        with col2:
            b, m, yn = float(d['Lebar b (m)']), float(d['Talud m']), c['yn']
            h_draw = max(yn * 1.5, 1.0)
            fig_cs, ax_cs = plt.subplots(figsize=(6, 3))
            x_soil = [-m*h_draw, 0, b, b+m*h_draw]
            y_soil = [h_draw, 0, 0, h_draw]
            ax_cs.plot(x_soil, y_soil, 'k-', linewidth=2)
            ax_cs.fill_between([-m*yn, 0, b, b+m*yn], [yn, 0, 0, yn], color='cyan', alpha=0.6)
            ax_cs.hlines(c['yc'], -m*c['yc'], b+m*c['yc'], colors='red', linestyles='--', label='Kritis')
            ax_cs.legend(); ax_cs.set_aspect('equal')
            st.pyplot(fig_cs)

# === EXPORT ===
st.divider()
st.subheader("🖨️ Export Laporan")
col_ex1, col_ex2 = st.columns(2)

with col_ex1:
    if 'calc_results' in st.session_state and len(st.session_state['calc_results']) > 0:
        export_data = []
        for r in st.session_state['calc_results']:
            row = r['data'].to_dict()
            row.update(r['calc'])
            export_data.append(row)
        df_export = pd.DataFrame(export_data)
        buffer = io.BytesIO()
        
        # FIX: Gunakan engine openpyxl agar tidak error ModuleNotFoundError
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Smart HEC-RAS Lite')
            
        st.download_button("📊 Download Excel (.xlsx)", buffer.getvalue(), "Laporan_Smart_HEC_RAS.xlsx", "application/vnd.ms-excel", type="primary", use_container_width=True)
    else:
        st.button("📊 Download Excel", disabled=True, use_container_width=True)

with col_ex2:
    st.markdown("""<button onclick="window.print()" style="background-color: #4CAF50; border: none; color: white; padding: 10px 24px; text-align: center; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; width: 100%; height: 42px; font-weight: bold;">🖨️ Cetak PDF (Print Page)</button>""", unsafe_allow_html=True)
