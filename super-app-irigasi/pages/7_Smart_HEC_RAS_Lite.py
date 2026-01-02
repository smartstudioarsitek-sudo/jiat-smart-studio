import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as patches
import io
import json # Pastikan library json diimport

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Lite", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #1e3c72, #2a5298); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 10px; }
    .report-box { border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-bottom: 20px; background-color: white; }
    h3 { color: #1e3c72; border-bottom: 2px solid #eee; padding-bottom: 5px; }
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton, .stTabs nav { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA ---
def solve_manning_y(Q, n, b, S, m):
    if S <= 0: return 0.001
    y = 0.5
    for _ in range(50):
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
    for _ in range(50):
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
            if y_new > 50.0: y_new = 50.0 
            if abs(y_new - y) < 0.0001: return abs(y_new)
            y = abs(y_new)
        except: return 0.001
    return y

# --- 1. INISIALISASI & AUTO-FIX DATA ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    data = [
        ["Saluran 1", 0.0, 64.0, 325.54, 323.00, 0.6, 1.0, 0.017],
        ["Saluran 2", 64.0, 114.0, 322.00, 321.00, 0.6, 1.0, 0.017],
        ["Saluran 3", 114.0, 142.0, 320.00, 319.00, 0.6, 1.0, 0.017],
    ]
    return pd.DataFrame(data, columns=REQUIRED_COLS)

if 'df_segments_sta' not in st.session_state:
    st.session_state['df_segments_sta'] = reset_data()
else:
    current_cols = list(st.session_state['df_segments_sta'].columns)
    if not all(col in current_cols for col in REQUIRED_COLS):
        st.toast("⚠️ Reset format tabel...", icon="🔄")
        st.session_state['df_segments_sta'] = reset_data()

if 'q_global' not in st.session_state: st.session_state['q_global'] = 0.24

# --- 2. HEADER & SIDEBAR ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 32px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.8;">Steady Flow Analysis & HEC-RAS Style Plot</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Plan Data")
    st.session_state['q_global'] = st.number_input("Flow (Q) m³/s", 0.001, 100.0, st.session_state['q_global'], 0.01)
    
    st.divider()
    
    # --- RESTORE TOMBOL SAVE JSON ---
    st.subheader("💾 Manajemen File")
    project_data = {
        'q': st.session_state['q_global'],
        'segments': st.session_state['df_segments_sta'].to_dict(orient='records')
    }
    json_str = json.dumps(project_data, indent=2)
    st.download_button("💾 Simpan Project (.json)", json_str, file_name="project_hecras.json", mime="application/json")
    
    uploaded_json = st.file_uploader("Buka Project (.json)", type=['json'])
    if uploaded_json is not None:
        try:
            loaded = json.load(uploaded_json)
            st.session_state['q_global'] = loaded['q']
            st.session_state['df_segments_sta'] = pd.DataFrame(loaded['segments'])
            st.success("✅ Project Dimuat!")
            st.rerun()
        except: st.error("Format file salah.")
    
    st.divider()
    
    aspect_ratio_fix = st.slider("📐 Skala Vertikal (Long Section)", 0.1, 10.0, 1.0, 0.1)
    
    use_manual_zoom = st.checkbox("Manual Scaling", value=False)
    if use_manual_zoom:
        c1, c2 = st.columns(2)
        with c1: y_min = st.number_input("Min Elev", 0.0, 1000.0, 318.0)
        with c2: y_max = st.number_input("Max Elev", 0.0, 1000.0, 330.0)
    
    st.divider()
    st.subheader("📥 Excel Import")
    
    df_temp = pd.DataFrame([["Reach-1", 0, 50, 100, 99.5, 1.0, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("📄 Template Excel", buf.getvalue(), "HECRAS_Template.xlsx")
    
    up_file = st.file_uploader("Upload .xlsx", type=['xlsx'])
    if up_file:
        try:
            df_up = pd.read_excel(up_file, engine='openpyxl')
            if all(c in df_up.columns for c in REQUIRED_COLS):
                if st.button("Load Excel Data"):
                    st.session_state['df_segments_sta'] = df_up[REQUIRED_COLS]
                    st.rerun()
            else: st.error("Kolom tidak sesuai template.")
        except Exception as e: st.error(f"Error: {e}")
        
    if st.button("🔄 Reset Data Default", use_container_width=True):
        st.session_state['df_segments_sta'] = reset_data()
        st.rerun()

# --- 3. MAIN LOGIC ---
edited_df = st.session_state['df_segments_sta']
results = []
plot_x, plot_bed, plot_ws, plot_egl, plot_crit = [], [], [], [], []

if len(edited_df) > 0:
    try:
        numeric_cols = ["STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
        calc_df = edited_df.copy()
        for col in numeric_cols:
            calc_df[col] = pd.to_numeric(calc_df[col], errors='coerce')
        
        calc_df = calc_df.sort_values(by="STA Awal (m)")
        
        for idx, row in calc_df.iterrows():
            if row[numeric_cols].isnull().any(): continue
            
            nama = str(row['Nama Segmen'])
            sta1, sta2 = row['STA Awal (m)'], row['STA Akhir (m)']
            z1, z2 = row['Elev Awal (m)'], row['Elev Akhir (m)']
            b, m, n = row['Lebar b (m)'], row['Talud m'], row['Kekasaran n']
            
            L = sta2 - sta1
            if L <= 0: continue
            
            S = (z1 - z2) / L
            Q = st.session_state['q_global']
            
            # Hydraulics
            yn = solve_manning_y(Q, n, b, S, m)
            yc = solve_critical_y(Q, b, m)
            
            A = (b + m*yn) * yn
            P = b + 2*yn * np.sqrt(1 + m**2)
            R = A/P if P > 0 else 0
            TopW = b + 2*m*yn
            V = Q/A if A > 0 else 0
            Fr = V / np.sqrt(9.81 * (A/TopW)) if TopW > 0 else 0
            
            Vel_Head = (V**2) / (2*9.81)
            EGL = (z2 + yn) + Vel_Head
            EG_Slope = (n * V)**2 / (R**(4/3)) if R>0 else 0
            
            # LOGIC KETERANGAN / KESIMPULAN
            if Fr > 1.1: status = "SUPERKRITIS"
            elif Fr < 0.9: status = "SUBKRITIS"
            else: status = "KRITIS"
            
            note = f"{status}"
            if V > 3.0: note += " (Erosi!)"
            if V < 0.6: note += " (Endapan)"
            
            results.append({
                "Reach": nama,
                "Sta Start": sta1,
                "Sta Finish": sta2,
                "Q Total": Q,
                "Min Ch El": z2,
                "W.S. Elev": z2 + yn,
                "Crit W.S.": z2 + yc,
                "E.G. Elev": EGL,
                "E.G. Slope": S,
                "Vel Chnl": V,
                "Flow Area": A,
                "Bottom Width": b,
                "Talud": m, 
                "Top Width": TopW,
                "Froude # Chl": Fr,
                "Keterangan": note  # <-- KOLOM BARU
            })
            
            plot_x.extend([sta1, sta2])
            plot_bed.extend([z1, z2])
            plot_ws.extend([z1 + yn, z2 + yn])
            plot_egl.extend([z1 + yn + Vel_Head, z2 + yn + Vel_Head])
            plot_crit.extend([z1 + yc, z2 + yc])
            
    except Exception as e: st.error(f"Error: {e}")

# --- 4. TABS ---
tab_input, tab_plot, tab_cross, tab_table, tab_report = st.tabs(["📝 Geometry", "📈 Profile Plot", "🖼️ Cross Section", "📋 Output Table", "📄 Laporan Teknis"])

with tab_input:
    st.subheader("Geometric Data Editor")
    new_edited = st.data_editor(st.session_state['df_segments_sta'], num_rows="dynamic", use_container_width=True)
    if not new_edited.equals(st.session_state['df_segments_sta']):
        st.session_state['df_segments_sta'] = new_edited
        st.rerun()

with tab_plot:
    if len(plot_x) > 0:
        fig_height = 6 * aspect_ratio_fix 
        if fig_height > 20: fig_height = 20
        if fig_height < 4: fig_height = 4
        
        fig, ax = plt.subplots(figsize=(14, fig_height))
        ax.set_facecolor('white') 
        
        ax.plot(plot_x, plot_bed, color='black', linewidth=1.5, marker='.', markersize=4, label='Ground')
        ax.plot(plot_x, plot_ws, color='blue', linewidth=1.0, label='W.S.')
        ax.fill_between(plot_x, plot_bed, plot_ws, color='#00FFFF', alpha=1.0)
        
        clean_crit = [c if c < w + 10 else np.nan for c, w in zip(plot_crit, plot_ws)]
        ax.plot(plot_x, clean_crit, color='red', linestyle='--', linewidth=1.0, label='Crit')
        ax.plot(plot_x, plot_egl, color='green', linestyle='--', linewidth=1.0, label='E.G.')
        
        ax.set_xlabel("Main Channel Distance (m)", fontweight='bold')
        ax.set_ylabel("Elevation (m)", fontweight='bold')
        ax.set_title("Profile Plot", fontweight='bold')
        ax.grid(True, which='major', linestyle=':', linewidth=0.5, color='gray')
        ax.minorticks_on()
        ax.grid(True, which='minor', linestyle=':', linewidth=0.2, color='lightgray')

        q_label = f"{st.session_state['q_global']} m³/s"
        legend_elements = [
            Line2D([0], [0], color='green', linestyle='--', lw=1.5, label=f'E.G. (PF 1)'),
            Line2D([0], [0], color='blue', lw=1.5, label=f'W.S. (PF 1)'),
            Line2D([0], [0], color='red', linestyle='--', lw=1.5, label=f'Crit (PF 1)'),
            Line2D([0], [0], color='black', marker='.', lw=1.5, label='Ground'),
        ]
        leg = ax.legend(handles=legend_elements, loc='upper right', frameon=True, 
                        facecolor='white', edgecolor='black', title=f"Profile: PF 1\nQ = {q_label}")
        leg.get_title().set_fontsize('9') 
        
        if use_manual_zoom: 
            ax.set_ylim(y_min, y_max)
        else:
            y_vals = [y for y in plot_bed + plot_ws if not np.isnan(y)]
            if y_vals:
                min_y, max_y = min(y_vals), max(y_vals)
                margin = (max_y - min_y) * 0.2 if max_y != min_y else 1.0
                ax.set_ylim(min_y - margin, max_y + margin)
        
        st.pyplot(fig)
    else: st.info("No data to plot.")

with tab_cross:
    st.subheader("Cross Section Plotter")
    if len(results) > 0:
        seg_names = [r['Reach'] for r in results]
        selected_seg = st.selectbox("Pilih Segmen / Cross Section:", seg_names)
        
        data = next(item for item in results if item["Reach"] == selected_seg)
        b, m = data['Bottom Width'], data['Talud']
        z_min, ws_elev = data['Min Ch El'], data['W.S. Elev']
        eg_elev, crit_elev = data['E.G. Elev'], data['Crit W.S.']
        
        max_h_draw = max(ws_elev, eg_elev) - z_min + 0.5
        if max_h_draw < 0.5: max_h_draw = 0.5
        
        x_ground = [-(b/2 + m*max_h_draw), -b/2, b/2, b/2 + m*max_h_draw]
        y_ground = [z_min + max_h_draw, z_min, z_min, z_min + max_h_draw]
        
        fig_xs, ax_xs = plt.subplots(figsize=(10, 6))
        ax_xs.set_facecolor('white')
        
        ax_xs.plot(x_ground, y_ground, color='black', linewidth=2, marker='s', markersize=4, label='Ground')
        ax_xs.plot([x_ground[0], x_ground[-1]], [y_ground[0], y_ground[-1]], 'ro', markersize=6, label='Bank Sta')

        depth = ws_elev - z_min
        if depth > 0:
            top_w_water = b + 2 * m * depth
            x_water = [-top_w_water/2, top_w_water/2]
            y_water = [ws_elev, ws_elev]
            poly_x = [-top_w_water/2, -b/2, b/2, top_w_water/2]
            poly_y = [ws_elev, z_min, z_min, ws_elev]
            ax_xs.fill(poly_x, poly_y, color='#00FFFF', alpha=1.0, label='Water')
            ax_xs.plot(x_water, y_water, color='blue', linewidth=1.5, label='W.S.')
            ax_xs.text(0, ws_elev, '▼', color='blue', fontsize=12, ha='center', va='bottom')

        xmin_plot, xmax_plot = min(x_ground), max(x_ground)
        ax_xs.hlines(eg_elev, xmin_plot, xmax_plot, colors='green', linestyles='--', label='E.G.')
        if crit_elev < z_min + max_h_draw + 2:
            ax_xs.hlines(crit_elev, xmin_plot, xmax_plot, colors='red', linestyles='--', label='Crit')

        ax_xs.annotate('', xy=(-b/2, z_min - 0.2), xytext=(b/2, z_min - 0.2), arrowprops=dict(arrowstyle='<->', color='black', lw=1.0))
        ax_xs.text(0, z_min - 0.35, f"b = {b:.2f} m", ha='center', va='top', fontsize=10, fontweight='bold')
        
        # Title Fix using Sta
        ax_xs.set_title(f"Cross Section: {data['Reach']} (Sta {data['Sta Start']} - {data['Sta Finish']})", fontweight='bold')
        
        info_text = (f"Reach: {data['Reach']}\nQ = {data['Q Total']} m³/s\nV = {data['Vel Chnl']} m/s\nFr = {data['Froude # Chl']}")
        ax_xs.text(0.02, 0.98, info_text, transform=ax_xs.transAxes, fontsize=9, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='gray'))

        ax_xs.set_xlabel("Offset (m)"); ax_xs.set_ylabel("Elevation (m)")
        ax_xs.grid(True, which='major', linestyle=':', linewidth=0.5, color='gray')
        ax_xs.set_aspect('equal')
        ax_xs.legend(loc='upper right')
        st.pyplot(fig_xs)
    else: st.info("Belum ada data.")

with tab_table:
    if len(results) > 0:
        df_hec = pd.DataFrame(results)
        
        col_mapping = {
            "Reach": "Segment Name",
            "Sta Start": "Sta Start (m)",
            "Sta Finish": "Sta Finish (m)",
            "Q Total": "Q Total (m³/s)",
            "Min Ch El": "Min Ch El (m)",
            "W.S. Elev": "W.S. Elev (m)",
            "Crit W.S.": "Crit W.S. (m)",
            "E.G. Elev": "E.G. Elev (m)",
            "E.G. Slope": "E.G. Slope (m/m)",
            "Vel Chnl": "Vel Chnl (m/s)",
            "Flow Area": "Flow Area (m²)",
            "Bottom Width": "Bottom Width (m)",
            "Top Width": "Top Width (m)",
            "Froude # Chl": "Froude # Chl",
            "Keterangan": "Keterangan / Kesimpulan" # <-- HEADER BARU
        }
        
        cols_order_internal = ["Reach", "Sta Start", "Sta Finish", "Q Total", "Min Ch El", "W.S. Elev", "Crit W.S.", "E.G. Elev", "E.G. Slope", "Vel Chnl", "Flow Area", "Bottom Width", "Top Width", "Froude # Chl", "Keterangan"]
        
        final_df = pd.DataFrame()
        for c in cols_order_internal:
            if c in df_hec.columns: final_df[c] = df_hec[c]
            else: final_df[c] = "-"
            
        for c in final_df.columns:
            if c not in ["Reach", "Keterangan"]:
                try: final_df[c] = final_df[c].astype(float).map('{:,.2f}'.format)
                except: pass
        
        final_df_display = final_df.rename(columns=col_mapping)

        st.subheader("HEC-RAS Profile Output Table")
        st.dataframe(final_df_display, use_container_width=True, hide_index=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            final_df_display.to_excel(writer, index=False, sheet_name='HEC-RAS Output')
        st.download_button("💾 Export Table to Excel", buf.getvalue(), "HEC_RAS_Table.xlsx", "application/vnd.ms-excel", type="primary")
    else: st.info("No data available.")

# --- FITUR BARU: TAB LAPORAN TEKNIS ---
with tab_report:
    st.markdown("""
        <div style="text-align: center;">
            <h2>LAPORAN PERHITUNGAN HIDROLIS SALURAN</h2>
            <p>Simulasi Steady Flow Analysis menggunakan Metode Standard Step (Manning)</p>
        </div>
        <hr>
    """, unsafe_allow_html=True)
    
    if len(results) > 0:
        # 1. INPUT DATA
        st.markdown("### 1. Data Perencanaan")
        st.write(f"**Debit Desain (Q):** {st.session_state['q_global']} m³/s")
        st.write("**Data Geometri Saluran:**")
        st.dataframe(st.session_state['df_segments_sta'], hide_index=True)
        
        # 2. METODOLOGI
        st.markdown("### 2. Metodologi Analisa")
        st.markdown("""
        Analisa dilakukan menggunakan pendekatan aliran tunak (Steady Flow) 1-Dimensi dengan persamaan Manning.
        Kapasitas saluran dievaluasi berdasarkan elevasi muka air normal (Normal Depth) dan dikontrol terhadap kedalaman kritis (Critical Depth) untuk menentukan rezim aliran.
        """)
        
        # 3. HASIL ANALISA
        st.markdown("### 3. Hasil Analisa Hidrolis")
        st.dataframe(final_df_display, use_container_width=True, hide_index=True)
        
        # 4. REKOMENDASI TEKNIS (OTOMATIS)
        st.markdown("### 4. Evaluasi & Rekomendasi Teknis")
        
        # Logic Rekomendasi
        count_super = sum(1 for r in results if r['Froude # Chl'] > 1.1)
        count_high_vel = sum(1 for r in results if r['Vel Chnl'] > 3.0)
        
        recs = []
        if count_super > 0:
            recs.append(f"⚠️ Terdeteksi **{count_super} segmen dengan Aliran Superkritis (Fr > 1)**. Berpotensi gerusan tinggi. Disarankan memasang **Bangunan Peredam Energi (Kolam Olak)** di hilir segmen tersebut atau mengubah kemiringan dasar saluran menjadi lebih landai.")
        
        if count_high_vel > 0:
            recs.append(f"⚠️ Terdeteksi **{count_high_vel} segmen dengan Kecepatan Tinggi (> 3 m/s)**. Saluran pasangan batu kali berisiko tergerus. Disarankan menggunakan **Lining Beton (Concrete Lining)** dengan mutu minimal K-225.")
        
        if not recs:
            recs.append("✅ Secara umum kondisi aliran **Aman (Stabil)**. Kecepatan dan Froude Number berada dalam batas izin.")
            
        for i, r in enumerate(recs):
            st.info(f"{i+1}. {r}")
            
    else:
        st.warning("Data belum tersedia. Silakan isi data di Tab Geometry Data.")
    
    st.markdown("<br><br><p style='text-align:center; font-size:12px; color:gray;'>Dicetak secara otomatis oleh Smart HEC-RAS Lite</p>", unsafe_allow_html=True)
    st.markdown("""<button onclick="window.print()" style="width:100%; background:#28a745; color:white; border:none; padding:12px; border-radius:5px; font-weight:bold; cursor:pointer;">🖨️ Cetak Laporan PDF</button>""", unsafe_allow_html=True)
