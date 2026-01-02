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
        try:
            A = (b + m*y) * y
            P = b + 2*y * np.sqrt(1 + m**2)
            R = A/P if P > 0 else 0
            f = (1/n) * A * (R**(2/3)) * (S**0.5) - Q
            
            dy = 0.001
            A_d = (b + m*(y+dy)) * (y+dy)
            P_d = b + 2*(y+dy) * np.sqrt(1 + m**2)
            R_d = A_d/P_d if P_d > 0 else 0
            f_d = (1/n) * A_d * (R_d**(2/3)) * (S**0.5) - Q
            
            df = (f_d - f) / dy
            if df == 0: break
            y_new = y - f/df
            if abs(y_new - y) < 0.0001: return abs(y_new)
            y = abs(y_new)
        except: return 0.001
    return y

def solve_critical_y(Q, b, m):
    g = 9.81
    y = 0.5
    for _ in range(30):
        try:
            A = (b + m*y) * y
            T = b + 2*m*y
            if A <= 0.001: A = 0.001
            f = (Q**2 * T) / (g * A**3) - 1
            dy = 0.001
            A_d = (b + m*(y+dy)) * (y+dy)
            T_d = b + 2*m*(y+dy)
            if A_d <= 0.001: A_d = 0.001
            f_d = (Q**2 * T_d) / (g * A_d**3) - 1
            df = (f_d - f) / dy
            if df == 0: break
            y_new = y - f/df
            if y_new > 50.0: y_new = 50.0 # Safety Cap
            if abs(y_new - y) < 0.0001: return abs(y_new)
            y = abs(y_new)
        except: return 0.001
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
if 'df_segments_sta' not in st.session_state:
    data = [
        ["Saluran 1", 0.0, 64.0, 325.54, 323.00, 0.6, 1.0, 0.017],
        ["Saluran 2", 64.0, 114.0, 322.00, 321.00, 0.6, 1.0, 0.017],
        ["Saluran 3", 114.0, 142.0, 320.00, 319.00, 0.6, 1.0, 0.017],
    ]
    cols = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
    st.session_state['df_segments_sta'] = pd.DataFrame(data, columns=cols)

if 'q_global' not in st.session_state: st.session_state['q_global'] = 0.24

# --- UI UTAMA ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 36px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 16px; opacity: 0.9;">Mode Stationing (STA) Input</p>
</div>
""", unsafe_allow_html=True)

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Parameter Global")
    st.session_state['q_global'] = st.number_input("Debit Desain (Q) m³/s", 0.001, 50.0, st.session_state['q_global'], 0.01)
    
    st.divider()
    st.subheader("👁️ Kontrol Tampilan")
    use_manual_zoom = st.checkbox("Atur Datum Manual", value=False)
    y_min_manual = st.number_input("Min Elevasi", value=300.0)
    y_max_manual = st.number_input("Max Elevasi", value=340.0)
    
    st.divider()
    st.subheader("📥 Input dari Excel")
    cols_excel = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
    df_template = pd.DataFrame([["Saluran A", 0, 50, 100, 99.5, 0.6, 1.0, 0.017]], columns=cols_excel)
    
    buffer_template = io.BytesIO()
    with pd.ExcelWriter(buffer_template, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Template Input')
    st.download_button("📄 Download Template Excel", buffer_template.getvalue(), "Template_HECRAS_STA.xlsx", "application/vnd.ms-excel")
    
    uploaded_excel = st.file_uploader("Upload File Excel (.xlsx)", type=['xlsx'])
    if uploaded_excel is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_excel)
            if all(col in df_uploaded.columns for col in cols_excel):
                if st.button("✅ Load Data Excel"):
                    st.session_state['df_segments_sta'] = df_uploaded[cols_excel]
                    st.success("Data loaded!")
                    st.rerun()
            else: st.error("Kolom Excel tidak sesuai template.")
        except Exception as e: st.error(f"Error: {e}")

    st.divider()
    st.subheader("💾 Backup Data")
    project_data = {'q': st.session_state['q_global'], 'segments': st.session_state['df_segments_sta'].to_dict(orient='records')}
    st.download_button("Simpan (.json)", json.dumps(project_data, indent=2), "backup_sta.json", "application/json")
    
    up_json = st.file_uploader("Restore (.json)", type=['json'])
    if up_json:
        try:
            loaded = json.load(up_json)
            st.session_state['q_global'] = loaded['q']
            st.session_state['df_segments_sta'] = pd.DataFrame(loaded['segments'])
            st.success("Restored!")
            st.rerun()
        except: pass

# === MAIN TABS ===
tab1, tab2, tab3 = st.tabs(["📝 Input Stationing (STA)", "📉 Profil Memanjang", "🔍 Detail & Rekomendasi"])

with tab1:
    st.subheader("1. Tabel Geometri & Stationing")
    st.caption("Masukkan STA Awal dan STA Akhir. Panjang (L) akan dihitung otomatis.")
    
    edited_df = st.data_editor(
        st.session_state['df_segments_sta'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "STA Awal (m)": st.column_config.NumberColumn(format="%.1f", required=True),
            "STA Akhir (m)": st.column_config.NumberColumn(format="%.1f", required=True),
            "Elev Awal (m)": st.column_config.NumberColumn(format="%.2f m", required=True),
            "Elev Akhir (m)": st.column_config.NumberColumn(format="%.2f m", required=True),
        }
    )
    st.session_state['df_segments_sta'] = edited_df
    
    if len(edited_df) > 0:
        results = []
        min_bed_plot = 9999
        max_water_plot = -9999
        
        for idx, row in edited_df.iterrows():
            try:
                sta_start = float(row['STA Awal (m)'])
                sta_end = float(row['STA Akhir (m)'])
                Z1, Z2 = float(row['Elev Awal (m)']), float(row['Elev Akhir (m)'])
                b, m, n = float(row['Lebar b (m)']), float(row['Talud m']), float(row['Kekasaran n'])
            except: continue 
            
            L = sta_end - sta_start
            if L <= 0: continue

            dH = Z1 - Z2
            S = dH / L 
            
            yn = solve_manning_y(st.session_state['q_global'], n, b, S, m)
            yc = solve_critical_y(st.session_state['q_global'], b, m)
            V = st.session_state['q_global'] / ((b + m*yn)*yn) if yn > 0 else 0
            Fr = V / np.sqrt(9.81 * (((b+m*yn)*yn)/(b+2*m*yn))) if yn > 0 else 0
            status = "SUPER-KRITIS" if yn < yc else "SUB-KRITIS"
            
            min_bed_plot = min(min_bed_plot, Z2)
            max_water_plot = max(max_water_plot, Z1 + yn)
            
            p_start = {'x': sta_start, 'z_bed': Z1, 'z_water': Z1 + yn, 'z_crit': Z1 + yc}
            p_end = {'x': sta_end, 'z_bed': Z2, 'z_water': Z2 + yn, 'z_crit': Z2 + yc}
            
            results.append({'data': row, 'calc': {'L': L, 'S': S, 'dH': dH, 'yn': yn, 'yc': yc, 'V': V, 'Fr': Fr, 'status': status}, 'plot': [p_start, p_end]})
            
        st.session_state['calc_results_sta'] = results
        st.session_state['plot_limits'] = (min_bed_plot, max_water_plot)
        if len(results) > 0: st.success(f"✅ Berhasil menghitung {len(results)} segmen!")

with tab2:
    st.subheader("2. Profil Memanjang (Long Section)")
    if 'calc_results_sta' in st.session_state:
        res = st.session_state['calc_results_sta']
        fig, ax = plt.subplots(figsize=(14, 7))
        
        for i, r in enumerate(res):
            pts = r['plot']
            x = [pts[0]['x'], pts[1]['x']]
            z_bed = [pts[0]['z_bed'], pts[1]['z_bed']]
            z_water = [pts[0]['z_water'], pts[1]['z_water']]
            z_crit = [pts[0]['z_crit'], pts[1]['z_crit']]
            
            ax.plot(x, z_bed, 'k-', linewidth=2.5)
            ax.plot(x, z_water, 'b-', linewidth=2)
            if z_crit[0] < z_water[0] + 5: ax.plot(x, z_crit, 'r--', linewidth=1, alpha=0.6)
            ax.fill_between(x, z_bed, z_water, color='cyan', alpha=0.3)
            
            mid_x, mid_y = (x[0] + x[1]) / 2, (z_bed[0] + z_bed[1]) / 2
            ax.text(mid_x, mid_y, str(r['data']['Nama Segmen']), ha='center', va='top', fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
            
            if i > 0:
                prev_end = res[i-1]['plot'][1]
                curr_start = r['plot'][0]
                if abs(prev_end['x'] - curr_start['x']) < 0.1: 
                    if abs(prev_end['z_bed'] - curr_start['z_bed']) > 0.05:
                        ax.plot([curr_start['x'], curr_start['x']], [prev_end['z_bed'], curr_start['z_bed']], color='gray', linestyle='--', linewidth=1.5)
                        drop_h = prev_end['z_bed'] - curr_start['z_bed']
                        if drop_h > 0: ax.text(curr_start['x'], (prev_end['z_bed'] + curr_start['z_bed'])/2, f" Drop {drop_h:.2f}m", ha='left', va='center', fontsize=7, color='brown')

        if use_manual_zoom:
            ax.set_ylim(bottom=y_min_manual, top=y_max_manual)
        else:
            min_z, max_z = st.session_state.get('plot_limits', (0, 10))
            buffer = (max_z - min_z) * 0.5 
            if buffer == 0: buffer = 1.0
            ax.set_ylim(bottom=min_z - buffer*0.2, top=max_z + buffer)

        from matplotlib.lines import Line2D
        legend_elements = [Line2D([0], [0], color='k', lw=2, label='Dasar Saluran'), Line2D([0], [0], color='b', lw=2, label='Muka Air (NDL)'), Line2D([0], [0], color='r', lw=1, linestyle='--', label='Kritis (CDL)'), Line2D([0], [0], color='gray', lw=1.5, linestyle='--', label='Bangunan Terjun')]
        ax.legend(handles=legend_elements)
        ax.set_xlabel("Stationing (m)"); ax.set_ylabel("Elevasi (m)"); ax.grid(True, linestyle=':', alpha=0.5); ax.set_title("Profil Aliran Berdasarkan STA")
        st.pyplot(fig)

with tab3:
    st.subheader("3. Detail & Rekomendasi")
    if 'calc_results_sta' in st.session_state:
        res = st.session_state['calc_results_sta']
        nama_list = [str(r['data']['Nama Segmen']) for r in res]
        pilih = st.selectbox("Pilih Segmen:", nama_list)
        selected = next(item for item in res if str(item['data']['Nama Segmen']) == pilih)
        c, d = selected['calc'], selected['data']
        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.metric("Panjang (L)", f"{c['L']:.1f} m", f"STA: {d['STA Awal (m)']} - {d['STA Akhir (m)']}")
            st.metric("Kecepatan (V)", f"{c['V']:.2f} m/s", f"Fr: {c['Fr']:.2f}")
            is_super = 'SUPER' in c['status']
            st.metric("Status Aliran", c['status'], delta="- BAHAYA" if is_super else "+ AMAN")
            st.markdown("#### 💡 Saran Teknis")
            for r in generate_recommendations(c['V'], c['Fr'], float(d['Kekasaran n'])): st.info(r)
        with col2:
            b, m, yn = float(d['Lebar b (m)']), float(d['Talud m']), c['yn']
            # --- FIX SKALA CROSS SECTION ---
            # Pakai yn untuk menentukan tinggi gambar agar proporsional
            h_draw = max(yn * 1.5, 0.5) 
            fig_cs, ax_cs = plt.subplots(figsize=(6, 3))
            
            # Gambar Tanah
            x_soil = [-m*h_draw, 0, b, b+m*h_draw]
            y_soil = [h_draw, 0, 0, h_draw]
            ax_cs.plot(x_soil, y_soil, 'k-', linewidth=2)
            
            # Gambar Air
            ax_cs.fill_between([-m*yn, 0, b, b+m*yn], [yn, 0, 0, yn], color='cyan', alpha=0.6)
            
            # Batasi Tampilan (Zoom ke area saluran)
            # Ini kuncinya: Set batas X dan Y secara eksplisit
            top_width = b + 2 * m * h_draw
            center_x = b / 2
            ax_cs.set_xlim(center_x - top_width/2 - 0.5, center_x + top_width/2 + 0.5)
            ax_cs.set_ylim(0, h_draw * 1.2)
            
            # Gambar Garis Kritis (Hanya jika masuk akal)
            if c['yc'] < h_draw * 2:
                ax_cs.hlines(c['yc'], -m*c['yc'], b+m*c['yc'], colors='red', linestyles='--', label='Kritis')
            else:
                # Jika Kritis jauh di atas (error), kasih teks aja
                ax_cs.text(b/2, h_draw, "Garis Kritis > Tinggi Saluran (Jauh)", color='red', ha='center', fontsize=8)

            ax_cs.legend(loc='upper right', fontsize='small'); ax_cs.set_aspect('equal')
            st.pyplot(fig_cs)

# === EXPORT ===
st.divider()
st.subheader("🖨️ Export Laporan")
col_ex1, col_ex2 = st.columns(2)
with col_ex1:
    if 'calc_results_sta' in st.session_state and len(st.session_state['calc_results_sta']) > 0:
        export_data = []
        for r in st.session_state['calc_results_sta']:
            row = r['data'].to_dict()
            row.update(r['calc'])
            export_data.append(row)
        df_export = pd.DataFrame(export_data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Data STA')
        st.download_button("📊 Download Excel (.xlsx)", buffer.getvalue(), "Laporan_STA.xlsx", "application/vnd.ms-excel", type="primary", use_container_width=True)
    else: st.button("📊 Download Excel", disabled=True, use_container_width=True)
with col_ex2:
    st.markdown("""<button onclick="window.print()" style="background-color: #4CAF50; border: none; color: white; padding: 10px 24px; text-align: center; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; width: 100%; height: 42px; font-weight: bold;">🖨️ Cetak PDF (Print Page)</button>""", unsafe_allow_html=True)
