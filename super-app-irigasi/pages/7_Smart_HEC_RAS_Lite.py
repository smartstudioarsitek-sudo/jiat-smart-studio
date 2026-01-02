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
        padding: 20px; background: linear-gradient(90deg, #1e3c72, #2a5298); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stDataFrame { font-size: 12px; font-family: 'Arial', sans-serif; }
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA (ROBUST) ---
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
            if y_new > 50.0: y_new = 50.0 # Safety Cap
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
    <p style="margin-top:5px; font-size: 14px; opacity: 0.8;">Steady Flow Analysis & Profile Plot</p>
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
# Tab Layout
tab_input, tab_plot, tab_table = st.tabs(["📝 Geometry Data", "📈 Profile Plot (HEC-RAS Style)", "📋 Output Table"])

# --- TAB 1: INPUT ---
with tab_input:
    st.subheader("Geometric Data Editor")
    edited_df = st.data_editor(st.session_state['df_segments_sta'], num_rows="dynamic", use_container_width=True)
    st.session_state['df_segments_sta'] = edited_df
    
    # --- CALCULATION CORE ---
    if len(edited_df) > 0:
        results = []
        plot_data = []
        
        # Sort by STA Awal just in case
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
            
            # 1. Hydraulic Depth
            yn = solve_manning_y(Q, n, b, S, m)
            yc = solve_critical_y(Q, b, m)
            
            # 2. Hydraulic Properties
            A = (b + m*yn) * yn
            P = b + 2*yn * np.sqrt(1 + m**2)
            R = A/P if P > 0 else 0
            TopW = b + 2*m*yn
            V = Q/A if A > 0 else 0
            Fr = V / np.sqrt(9.81 * (A/TopW)) if TopW > 0 else 0
            
            # 3. Energy Grade
            Vel_Head = (V**2) / (2*9.81)
            EGL = (z2 + yn) + Vel_Head # Calculated at downstream end
            EG_Slope = (n * V)**2 / (R**(4/3)) if R>0 else 0 # Friction Slope
            
            # Store Result for Table (Downstream Node)
            results.append({
                "Reach": "Main Channel",
                "River Sta": sta2, # Reporting at End Station
                "Profile": "PF 1",
                "Q Total": Q,
                "Min Ch El": z2,
                "W.S. Elev": z2 + yn,
                "Crit W.S.": z2 + yc,
                "E.G. Elev": EGL,
                "E.G. Slope": S, # Using Bed Slope as approx for Normal Depth assumption
                "Vel Chnl": V,
                "Flow Area": A,
                "Top Width": TopW,
                "Froude # Chl": Fr
            })
            
            # Store Data for Plotting (Start & End points)
            # Upstream Point
            ws1 = z1 + yn
            egl1 = z1 + yn + Vel_Head
            crit1 = z1 + yc
            
            # Downstream Point
            ws2 = z2 + yn
            egl2 = z2 + yn + Vel_Head
            crit2 = z2 + yc
            
            plot_data.append({
                'x': [sta1, sta2],
                'bed': [z1, z2],
                'ws': [ws1, ws2],
                'egl': [egl1, egl2],
                'crit': [crit1, crit2],
                'name': row['Nama Segmen']
            })
            
        st.session_state['hec_results'] = results
        st.session_state['plot_data'] = plot_data

# --- TAB 2: HEC-RAS STYLE PLOT ---
with tab_plot:
    if 'plot_data' in st.session_state:
        pdata = st.session_state['plot_data']
        
        # Setup Figure
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_facecolor('white') # HEC-RAS default background
        
        # Iterasi Gambar
        for i, p in enumerate(pdata):
            x = p['x']
            bed = p['bed']
            ws = p['ws']
            egl = p['egl']
            crit = p['crit']
            
            # 1. BED (Black Line)
            ax.plot(x, bed, color='black', linewidth=2, label='Ground' if i==0 else "")
            
            # 2. WATER (Cyan Fill & Blue Line)
            ax.plot(x, ws, color='blue', linewidth=1, label='WS' if i==0 else "")
            ax.fill_between(x, bed, ws, color='#00FFFF', alpha=1.0) # HEC-RAS Cyan
            
            # 3. CRIT (Red Dashed)
            # Filter error values for display
            if crit[0] < ws[0] + 10:
                ax.plot(x, crit, color='red', linestyle='--', linewidth=1, label='Crit' if i==0 else "")
            
            # 4. EGL (Green Dashed)
            ax.plot(x, egl, color='green', linestyle='--', linewidth=1, label='EG' if i==0 else "")
            
            # Label Segmen
            mid_x = np.mean(x)
            mid_y = np.mean(bed)
            ax.text(mid_x, mid_y, p['name'], fontsize=7, ha='center', va='top', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

            # Drop Lines (Vertical Connection)
            if i > 0:
                prev = pdata[i-1]
                if abs(prev['x'][1] - x[0]) < 0.1: # Connected
                    if abs(prev['bed'][1] - bed[0]) > 0.05:
                         ax.plot([x[0], x[0]], [prev['bed'][1], bed[0]], color='gray', linestyle=':')

        # Formatting
        ax.set_xlabel("Main Channel Distance (m)", fontweight='bold')
        ax.set_ylabel("Elevation (m)", fontweight='bold')
        ax.set_title("Profile Plot", fontweight='bold')
        ax.grid(True, which='both', linestyle=':', linewidth=0.5, color='gray')
        
        # Manual Zoom Logic
        if use_manual_zoom:
            ax.set_ylim(y_min, y_max)
        
        # Legend (Custom)
        from matplotlib.lines import Line2D
        custom_lines = [
            Line2D([0], [0], color='green', linestyle='--', lw=1),
            Line2D([0], [0], color='blue', lw=1),
            Line2D([0], [0], color='red', linestyle='--', lw=1),
            Line2D([0], [0], color='black', lw=2),
        ]
        ax.legend(custom_lines, ['EG', 'WS', 'Crit', 'Ground'], loc='upper right', frameon=True, edgecolor='black')
        
        st.pyplot(fig)

# --- TAB 3: HEC-RAS STYLE TABLE ---
with tab_table:
    if 'hec_results' in st.session_state:
        res = st.session_state['hec_results']
        
        # Create DataFrame
        df_hec = pd.DataFrame(res)
        
        # Format Columns (Rounding)
        cols_fmt = ["Q Total", "Min Ch El", "W.S. Elev", "Crit W.S.", "E.G. Elev", "E.G. Slope", "Vel Chnl", "Flow Area", "Top Width", "Froude # Chl"]
        for c in cols_fmt:
            if c in df_hec.columns:
                df_hec[c] = df_hec[c].map('{:,.2f}'.format)
        
        # Display Table HEC-RAS Style
        st.subheader("HEC-RAS Output Table")
        st.dataframe(
            df_hec, 
            column_config={
                "River Sta": st.column_config.NumberColumn(format="%.1f"),
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Export Buttons
        c_ex1, c_ex2 = st.columns(2)
        with c_ex1:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_hec.to_excel(writer, index=False, sheet_name='Profile Output Table')
            st.download_button("💾 Export Table to Excel", buf.getvalue(), "HEC_RAS_Table.xlsx", "application/vnd.ms-excel", type="primary", use_container_width=True)
            
        with c_ex2:
            st.markdown("""<button onclick="window.print()" style="width:100%; background:#4CAF50; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold;">🖨️ Print Report</button>""", unsafe_allow_html=True)
