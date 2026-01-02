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
    /* Hide printing elements */
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
    <h1 style="margin:0; font-size: 32px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.8;">Steady Flow Analysis & HEC-RAS Style Plot</p>
</div>
""", unsafe_allow_html=True)

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Plan Data")
    st.session_state['q_global'] = st.number_input("Flow (Q) m³/s", 0.001, 100.0, st.session_state['q_global'], 0.01)
    
    st.divider()
    st.subheader("👁️ Plot Options")
    use_manual_zoom = st.checkbox("Manual Scaling", value=False)
    
    if use_manual_zoom:
        c1, c2 = st.columns(2)
        with c1: y_min = st.number_input("Min Elev", 0.0, 1000.0, 318.0)
        with c2: y_max = st.number_input("Max Elev", 0.0, 1000.0, 330.0)
    
    st.divider()
    st.subheader("📥 Excel Import")
    cols_excel = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
    
    # Template
    df_temp = pd.DataFrame([["Reach-1", 0, 50, 100, 99.5, 1.0, 1.0, 0.017]], columns=cols_excel)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("📄 Template Excel", buf.getvalue(), "HECRAS_Template.xlsx")
    
    up_file = st.file_uploader("Upload .xlsx", type=['xlsx'])
    if up_file:
        try:
            df_up = pd.read_excel(up_file)
            if all(c in df_up.columns for c in cols_excel):
                if st.button("Load Excel Data"):
                    st.session_state['df_segments_sta'] = df_up[cols_excel]
                    st.rerun()
            else: st.error("Kolom tidak sesuai template.")
        except: st.error("File error.")

# === MAIN CONTENT ===
tab_input, tab_plot, tab_table = st.tabs(["📝 Geometry Data", "📈 Profile Plot (HEC-RAS Style)", "📋 Output Table"])

# --- TAB 1: INPUT ---
with tab_input:
    st.subheader("Geometric Data Editor")
    edited_df = st.data_editor(st.session_state['df_segments_sta'], num_rows="dynamic", use_container_width=True)
    st.session_state['df_segments_sta'] = edited_df
    
    # --- CALCULATION CORE ---
    if len(edited_df) > 0:
        results = []
        # Arrays untuk Continuous Plotting
        plot_x, plot_bed, plot_ws, plot_egl, plot_crit = [], [], [], [], []
        
        # Sort by STA Awal
        calc_df = edited_df.sort_values(by="STA Awal (m)")
        
        for idx, row in calc_df.iterrows():
            try:
                sta1, sta2 = row['STA Awal (m)'], row['STA Akhir (m)']
                z1, z2 = row['Elev Awal (m)'], row['Elev Akhir (m)']
                b, m, n = row['Lebar b (m)'], row['Talud m'], row['Kekasaran n']
            except: continue
            
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
            
            # Energy Grade
            Vel_Head = (V**2) / (2*9.81)
            EGL = (z2 + yn) + Vel_Head
            EG_Slope = (n * V)**2 / (R**(4/3)) if R>0 else 0
            
            # Store Table Data
            results.append({
                "Reach": "Main Channel",
                "River Sta": sta2,
                "Profile": "PF 1",
                "Q Total": Q,
                "Min Ch El": z2,
                "W.S. Elev": z2 + yn,
                "Crit W.S.": z2 + yc,
                "E.G. Elev": EGL,
                "E.G. Slope": S,
                "Vel Chnl": V,
                "Flow Area": A,
                "Top Width": TopW,
                "Froude # Chl": Fr
            })
            
            # Store Plot Data (Start Point & End Point) to create CONTINUOUS LINE
            # Point 1 (Start)
            plot_x.append(sta1)
            plot_bed.append(z1)
            plot_ws.append(z1 + yn)
            plot_egl.append(z1 + yn + Vel_Head)
            plot_crit.append(z1 + yc)
            
            # Point 2 (End)
            plot_x.append(sta2)
            plot_bed.append(z2)
            plot_ws.append(z2 + yn)
            plot_egl.append(z2 + yn + Vel_Head)
            plot_crit.append(z2 + yc)
            
        st.session_state['hec_results'] = results
        st.session_state['plot_arrays'] = {
            'x': plot_x, 'bed': plot_bed, 'ws': plot_ws, 'egl': plot_egl, 'crit': plot_crit
        }

# --- TAB 2: HEC-RAS STYLE PLOT ---
with tab_plot:
    if 'plot_arrays' in st.session_state and len(st.session_state['plot_arrays']['x']) > 0:
        d = st.session_state['plot_arrays']
        
        # Setup Figure
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.set_facecolor('white') # HEC-RAS white background
        
        # 1. GROUND (Black Line with Vertices)
        ax.plot(d['x'], d['bed'], color='black', linewidth=1.5, marker='.', markersize=4, label='Ground')
        
        # 2. WATER SURFACE (Blue Line + Cyan Fill)
        ax.plot(d['x'], d['ws'], color='blue', linewidth=1.0, label='W.S.')
        ax.fill_between(d['x'], d['bed'], d['ws'], color='#00FFFF', alpha=1.0) # HEC-RAS Cyan
        
        # 3. CRITICAL DEPTH (Red Dashed)
        # Filter extreme values for plotting
        clean_crit = [c if c < w + 10 else np.nan for c, w in zip(d['crit'], d['ws'])]
        ax.plot(d['x'], clean_crit, color='red', linestyle='--', linewidth=1.0, label='Crit')
        
        # 4. ENERGY GRADE (Green Dashed)
        ax.plot(d['x'], d['egl'], color='green', linestyle='--', linewidth=1.0, label='E.G.')
        
        # Formatting Grid & Labels
        ax.set_xlabel("Main Channel Distance (m)", fontweight='bold', fontsize=10)
        ax.set_ylabel("Elevation (m)", fontweight='bold', fontsize=10)
        ax.set_title("Profile Plot", fontweight='bold', fontsize=12)
        
        # Grid titik-titik (HEC-RAS style)
        ax.grid(True, which='major', linestyle=':', linewidth=0.5, color='gray')
        ax.minorticks_on()
        ax.grid(True, which='minor', linestyle=':', linewidth=0.3, color='lightgray')

        # === LEGEND BOX (SEPERTI YANG DILINGKARI) ===
        # Membuat Custom Legend di Pojok Kanan Atas
        legend_elements = [
            Line2D([0], [0], color='green', linestyle='--', lw=1.5, label='E.G.'),
            Line2D([0], [0], color='blue', lw=1.5, label='W.S.'),
            Line2D([0], [0], color='red', linestyle='--', lw=1.5, label='Crit'),
            Line2D([0], [0], color='black', marker='.', lw=1.5, label='Ground'),
        ]
        
        # Legend Box: White background, Black border
        ax.legend(handles=legend_elements, loc='upper right', frameon=True, 
                  facecolor='white', edgecolor='black', framealpha=1.0, fontsize=9,
                  title="Legend", title_fontsize=9)
        
        # Manual Zoom
        if use_manual_zoom:
            ax.set_ylim(y_min, y_max)
        else:
            # Auto zoom yang pintar (fokus ke air)
            y_data_vals = [y for y in d['bed'] + d['ws'] if not np.isnan(y)]
            if y_data_vals:
                min_y, max_y = min(y_data_vals), max(y_data_vals)
                margin = (max_y - min_y) * 0.2
                ax.set_ylim(min_y - margin, max_y + margin)
        
        st.pyplot(fig)
        st.caption("ℹ️ Grafik ini menggunakan standar visualisasi HEC-RAS.")

# --- TAB 3: HEC-RAS STYLE TABLE ---
with tab_table:
    if 'hec_results' in st.session_state:
        res = st.session_state['hec_results']
        df_hec = pd.DataFrame(res)
        
        # Kolom sesuai screenshot User
        cols_order = ["Reach", "River Sta", "Profile", "Q Total", "Min Ch El", "W.S. Elev", "Crit W.S.", "E.G. Elev", "E.G. Slope", "Vel Chnl", "Flow Area", "Top Width", "Froude # Chl"]
        
        # Pastikan kolom ada
        final_df = pd.DataFrame()
        for c in cols_order:
            if c in df_hec.columns: final_df[c] = df_hec[c]
            else: final_df[c] = "-"
            
        # Format Angka
        for c in final_df.columns:
            if c not in ["Reach", "Profile"]:
                try: final_df[c] = final_df[c].astype(float).map('{:,.2f}'.format)
                except: pass

        st.subheader("HEC-RAS Profile Output Table")
        st.dataframe(final_df, use_container_width=True, hide_index=True)
        
        # Export
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False, sheet_name='HEC-RAS Output')
        st.download_button("💾 Download Excel Table", buf.getvalue(), "HEC_RAS_Table.xlsx", "application/vnd.ms-excel", type="primary")
