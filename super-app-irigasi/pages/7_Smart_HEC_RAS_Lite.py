import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import io

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Lite", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #1e3c72, #2a5298); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 5px solid #007bff; }
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
    
    # --- FITUR BARU: SKALA PROPORTIONAL ---
    st.subheader("👁️ Plot Options (Tampilan)")
    # Slider untuk mengatur "Kemanisan" grafik (Vertical Exaggeration)
    aspect_ratio_fix = st.slider("📐 Skala Vertikal (Exaggeration)", 0.1, 10.0, 1.0, 0.1, help="Geser ke kanan agar grafik terlihat lebih tinggi/curam (tidak gepeng).")
    
    use_manual_zoom = st.checkbox("Atur Batas Manual (Zoom)", value=False)
    if use_manual_zoom:
        c1, c2 = st.columns(2)
        with c1: y_min = st.number_input("Min Elev", 0.0, 1000.0, 318.0)
        with c2: y_max = st.number_input("Max Elev", 0.0, 1000.0, 330.0)
        x_max_limit = st.number_input("Max Stationing", 0.0, 5000.0, 200.0)
    
    st.divider()
    st.subheader("📥 Excel Import")
    
    df_temp = pd.DataFrame([["Reach-1", 0, 50, 100, 99.5, 1.0, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("📄 Template Excel", buf.getvalue(), "HECRAS_Template.xlsx")
    
    up_file = st.file_uploader("Upload .xlsx", type=['xlsx'])
    if up_file:
        try:
            df_up = pd.read_excel(up_file)
            if all(c in df_up.columns for c in REQUIRED_COLS):
                if st.button("Load Excel Data"):
                    st.session_state['df_segments_sta'] = df_up[REQUIRED_COLS]
                    st.rerun()
            else: st.error("Kolom tidak sesuai template.")
        except: st.error("File error.")
        
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
                "Top Width": TopW,
                "Froude # Chl": Fr
            })
            
            plot_x.extend([sta1, sta2])
            plot_bed.extend([z1, z2])
            plot_ws.extend([z1 + yn, z2 + yn])
            plot_egl.extend([z1 + yn + Vel_Head, z2 + yn + Vel_Head])
            plot_crit.extend([z1 + yc, z2 + yc])
            
    except Exception as e: st.error(f"Error: {e}")

# --- 4. TABS ---
tab_input, tab_plot, tab_table = st.tabs(["📝 Geometry Data", "📈 Profile Plot (HEC-RAS Style)", "📋 Output Table"])

with tab_input:
    st.subheader("Geometric Data Editor")
    new_edited = st.data_editor(st.session_state['df_segments_sta'], num_rows="dynamic", use_container_width=True)
    if not new_edited.equals(st.session_state['df_segments_sta']):
        st.session_state['df_segments_sta'] = new_edited
        st.rerun()

with tab_plot:
    if len(plot_x) > 0:
        # Atur Figsize berdasarkan Aspect Ratio Slider
        # Default lebar 14, tinggi disesuaikan slider (exaggeration)
        fig_height = 6 * aspect_ratio_fix 
        if fig_height > 20: fig_height = 20 # Batasi biar gak kegedean
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

        # --- LEGEND DENGAN ANGKA (PERMINTAAN USER) ---
        q_label = f"{st.session_state['q_global']} m³/s"
        
        legend_elements = [
            Line2D([0], [0], color='green', linestyle='--', lw=1.5, label=f'E.G. (PF 1)'),
            Line2D([0], [0], color='blue', lw=1.5, label=f'W.S. (PF 1)'),
            Line2D([0], [0], color='red', linestyle='--', lw=1.5, label=f'Crit (PF 1)'),
            Line2D([0], [0], color='black', marker='.', lw=1.5, label='Ground'),
        ]
        # Menambahkan Judul Legend agar mirip HEC-RAS
        leg = ax.legend(handles=legend_elements, loc='upper right', frameon=True, 
                        facecolor='white', edgecolor='black', title=f"Profile: PF 1\nQ = {q_label}")
        leg.get_title().set_fontsize('9') 
        
        if use_manual_zoom: 
            ax.set_ylim(y_min, y_max)
            ax.set_xlim(0, x_max_limit)
        else:
            y_vals = [y for y in plot_bed + plot_ws if not np.isnan(y)]
            if y_vals:
                min_y, max_y = min(y_vals), max(y_vals)
                margin = (max_y - min_y) * 0.2 if max_y != min_y else 1.0
                ax.set_ylim(min_y - margin, max_y + margin)
        
        st.pyplot(fig)
        st.caption(f"💡 Tips: Gunakan slider **'Skala Vertikal'** di sidebar kiri untuk mengatur proporsi grafik agar terlihat manis.")
    else: st.info("No data to plot.")

with tab_table:
    if len(results) > 0:
        df_hec = pd.DataFrame(results)
        cols_order = ["Reach", "Sta Start", "Sta Finish", "Q Total", "Min Ch El", "W.S. Elev", "Crit W.S.", "E.G. Elev", "E.G. Slope", "Vel Chnl", "Flow Area", "Bottom Width", "Top Width", "Froude # Chl"]
        
        final_df = pd.DataFrame()
        for c in cols_order:
            if c in df_hec.columns: final_df[c] = df_hec[c]
            else: final_df[c] = "-"
            
        for c in final_df.columns:
            if c not in ["Reach"]:
                try: final_df[c] = final_df[c].astype(float).map('{:,.2f}'.format)
                except: pass

        st.subheader("HEC-RAS Profile Output Table")
        st.dataframe(final_df, use_container_width=True, hide_index=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False, sheet_name='HEC-RAS Output')
        st.download_button("💾 Export Table to Excel", buf.getvalue(), "HEC_RAS_Table.xlsx", "application/vnd.ms-excel", type="primary")
    else: st.info("No data available.")
