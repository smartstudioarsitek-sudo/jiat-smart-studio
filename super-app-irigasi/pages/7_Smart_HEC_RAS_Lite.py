import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import io

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Lite", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 25px; background: linear-gradient(90deg, #0d47a1, #1976d2); 
        color: white; border-radius: 12px; text-align: center; margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card {
        background-color: #e3f2fd; border-left: 5px solid #2196f3; padding: 10px; border-radius: 5px;
    }
    /* Hide Streamlit elements when printing */
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA ---
def solve_manning_y(Q, n, b, S, m):
    if S <= 0: return 0.001
    y = 0.5
    for _ in range(30):
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
    for _ in range(30):
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
    elif V < 0.6: recs.append("⚠️ **Risiko Endapan.** V < 0.6 m/s. Cek elevasi akhir.")
    if Fr > 1.0: recs.append("🌊 **Superkritis.** Wajib Kolam Olak di hilir segmen ini.")
    else: recs.append("✅ Subkritis. Aman.")
    return recs

# --- INIT STATE ---
if 'df_segments_v2' not in st.session_state:
    data = [
        ["Segmen 1 (Hulu)", 200, 100.0, 90.0, 1.5, 1.0, 0.017],
        ["Segmen 2 (Drop)", 50, 88.0, 85.0, 1.5, 0.5, 0.017],
        ["Segmen 3 (Hilir)", 300, 85.0, 84.0, 2.0, 1.0, 0.025],
    ]
    st.session_state['df_segments_v2'] = pd.DataFrame(data, columns=["Nama Segmen", "Panjang L (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"])
if 'q_global' not in st.session_state: st.session_state['q_global'] = 0.24

# --- UI UTAMA ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 36px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 16px; opacity: 0.9;">Mode Elevasi Absolut (Cascade Modeling)</p>
</div>
""", unsafe_allow_html=True)

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Parameter Global")
    st.session_state['q_global'] = st.number_input("Debit Desain (Q) m³/s", 0.1, 50.0, st.session_state['q_global'], 0.01)
    
    st.divider()
    
    # --- FITUR BARU: IMPORT DARI EXCEL ---
    st.subheader("📥 Input dari Excel")
    
    # 1. DOWNLOAD TEMPLATE
    # Buat dummy dataframe untuk template
    df_template = pd.DataFrame([
        ["STA 0+00", 50, 100, 99.5, 0.6, 1.0, 0.017],
        ["STA 0+50", 50, 99.5, 99.0, 0.6, 1.0, 0.017]
    ], columns=["Nama Segmen", "Panjang L (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"])
    
    buffer_template = io.BytesIO()
    with pd.ExcelWriter(buffer_template, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Template Input')
    
    st.download_button(
        label="📄 Download Template Excel",
        data=buffer_template.getvalue(),
        file_name="Template_HECRAS_Lite.xlsx",
        mime="application/vnd.ms-excel",
        help="Download format Excel ini, isi datanya, lalu upload di bawah."
    )
    
    # 2. UPLOAD EXCEL
    uploaded_excel = st.file_uploader("Upload File Excel (.xlsx)", type=['xlsx'])
    if uploaded_excel is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_excel)
            # Validasi Kolom
            required_cols = ["Nama Segmen", "Panjang L (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
            if all(col in df_uploaded.columns for col in required_cols):
                if st.button("✅ Load Data Excel"):
                    st.session_state['df_segments_v2'] = df_uploaded[required_cols] # Ambil kolom yg sesuai aja
                    st.success("Data berhasil masuk tabel!")
                    st.rerun()
            else:
                st.error(f"Format kolom salah! Gunakan tombol Download Template di atas.")
        except Exception as e:
            st.error(f"Error membaca file: {e}")

    st.divider()
    
    # MANAJEMEN FILE JSON (LAMA)
    st.subheader("💾 Backup Data (.json)")
    project_data = {
        'q': st.session_state['q_global'],
        'segments': st.session_state['df_segments_v2'].to_dict(orient='records')
    }
    json_str = json.dumps(project_data, indent=2)
    st.download_button("Simpan Backup (.json)", json_str, file_name="hecras_backup.json", mime="application/json")
    
    uploaded_json = st.file_uploader("Restore Backup (.json)", type=['json'])
    if uploaded_json:
        try:
            loaded = json.load(uploaded_json)
            st.session_state['q_global'] = loaded['q']
            st.session_state['df_segments_v2'] = pd.DataFrame(loaded['segments'])
            st.success("Backup dimuat!")
            st.rerun()
        except: pass

# === MAIN TABS ===
tab1, tab2, tab3 = st.tabs(["📝 Input Elevasi", "📉 Profil Memanjang (Cascade)", "🔍 Detail & Rekomendasi"])

with tab1:
    st.subheader("1. Tabel Geometri & Elevasi")
    st.caption("Tips: Gunakan menu 'Input dari Excel' di sidebar kiri untuk data banyak.")
    
    edited_df = st.data_editor(
        st.session_state['df_segments_v2'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Panjang L (m)": st.column_config.NumberColumn(format="%.1f m"),
            "Elev Awal (m)": st.column_config.NumberColumn(format="%.2f m", required=True),
            "Elev Akhir (m)": st.column_config.NumberColumn(format="%.2f m", required=True),
        }
    )
    st.session_state['df_segments_v2'] = edited_df
    
    if len(edited_df) > 0:
        results = []
        cumulative_dist = 0
        
        for idx, row in edited_df.iterrows():
            try:
                L, Z1, Z2 = float(row['Panjang L (m)']), float(row['Elev Awal (m)']), float(row['Elev Akhir (m)'])
                b, m, n = float(row['Lebar b (m)']), float(row['Talud m']), float(row['Kekasaran n'])
            except: continue 
            
            dH = Z1 - Z2
            S = dH / L if L > 0 else 0
            
            yn = solve_manning_y(st.session_state['q_global'], n, b, S, m)
            yc = solve_critical_y(st.session_state['q_global'], b, m)
            V = st.session_state['q_global'] / ((b + m*yn)*yn) if yn > 0 else 0
            Fr = V / np.sqrt(9.81 * (((b+m*yn)*yn)/(b+2*m*yn))) if yn > 0 else 0
            status = "SUPER-KRITIS" if yn < yc else "SUB-KRITIS"
            
            p_start = {'x': cumulative_dist, 'z_bed': Z1, 'z_water': Z1 + yn, 'z_crit': Z1 + yc}
            cumulative_dist += L
            p_end = {'x': cumulative_dist, 'z_bed': Z2, 'z_water': Z2 + yn, 'z_crit': Z2 + yc}
            
            results.append({
                'data': row,
                'calc': {'S': S, 'dH': dH, 'yn': yn, 'yc': yc, 'V': V, 'Fr': Fr, 'status': status},
                'plot': [p_start, p_end]
            })
            
        st.session_state['calc_results_v2'] = results
        if len(results) > 0: st.success(f"✅ Berhasil menghitung {len(results)} segmen secara Absolut!")

with tab2:
    st.subheader("2. Profil Memanjang (Long Section)")
    if 'calc_results_v2' in st.session_state:
        res = st.session_state['calc_results_v2']
        fig, ax = plt.subplots(figsize=(14, 7))
        
        for i, r in enumerate(res):
            pts = r['plot']
            x = [pts[0]['x'], pts[1]['x']]
            z_bed = [pts[0]['z_bed'], pts[1]['z_bed']]
            z_water = [pts[0]['z_water'], pts[1]['z_water']]
            z_crit = [pts[0]['z_crit'], pts[1]['z_crit']]
            
            ax.plot(x, z_bed, 'k-', linewidth=2.5)
            ax.plot(x, z_water, 'b-', linewidth=2)
            ax.plot(x, z_crit, 'r--', linewidth=1, alpha=0.6)
            ax.fill_between(x, z_bed, z_water, color='cyan', alpha=0.3)
            
            mid_x, mid_y = (x[0] + x[1]) / 2, (z_bed[0] + z_bed[1]) / 2
            ax.text(mid_x, mid_y, str(r['data']['Nama Segmen']), ha='center', va='top', fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
            
            if i > 0:
                prev_end = res[i-1]['plot'][1]
                curr_start = r['plot'][0]
                if abs(prev_end['z_bed'] - curr_start['z_bed']) > 0.05:
                    ax.plot([curr_start['x'], curr_start['x']], [prev_end['z_bed'], curr_start['z_bed']], color='gray', linestyle='--', linewidth=1.5)
                    drop_h = prev_end['z_bed'] - curr_start['z_bed']
                    if drop_h > 0: ax.text(curr_start['x'], (prev_end['z_bed'] + curr_start['z_bed'])/2, f" Drop {drop_h:.2f}m", ha='left', va='center', fontsize=7, color='brown')

        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='k', lw=2, label='Dasar Saluran'),
            Line2D([0], [0], color='b', lw=2, label='Muka Air (NDL)'),
            Line2D([0], [0], color='r', lw=1, linestyle='--', label='Kritis (CDL)'),
            Line2D([0], [0], color='gray', lw=1.5, linestyle='--', label='Bangunan Terjun'),
        ]
        ax.legend(handles=legend_elements)
        ax.set_xlabel("Jarak (m)"); ax.set_ylabel("Elevasi (m)"); ax.grid(True, linestyle=':', alpha=0.5); ax.set_title("Profil Aliran Cascade")
        st.pyplot(fig)

with tab3:
    st.subheader("3. Detail & Rekomendasi")
    if 'calc_results_v2' in st.session_state:
        res = st.session_state['calc_results_v2']
        nama_list = [str(r['data']['Nama Segmen']) for r in res]
        pilih = st.selectbox("Pilih Segmen:", nama_list)
        selected = next(item for item in res if str(item['data']['Nama Segmen']) == pilih)
        c, d = selected['calc'], selected['data']
        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.metric("Slope (S)", f"{c['S']*100:.3f} %", f"dH: {c['dH']:.2f} m")
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
    if 'calc_results_v2' in st.session_state and len(st.session_state['calc_results_v2']) > 0:
        export_data = []
        for r in st.session_state['calc_results_v2']:
            row = r['data'].to_dict()
            row.update(r['calc'])
            export_data.append(row)
        df_export = pd.DataFrame(export_data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='HEC-RAS Lite Data')
        st.download_button("📊 Download Excel (.xlsx)", buffer.getvalue(), "Laporan_Elevasi.xlsx", "application/vnd.ms-excel", type="primary", use_container_width=True)
    else:
        st.button("📊 Download Excel", disabled=True, use_container_width=True)

with col_ex2:
    st.markdown("""<button onclick="window.print()" style="background-color: #4CAF50; border: none; color: white; padding: 10px 24px; text-align: center; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; width: 100%; height: 42px; font-weight: bold;">🖨️ Cetak PDF (Print Page)</button>""", unsafe_allow_html=True)
