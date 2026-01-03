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
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton, .stTabs nav { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA: STANDARD STEP METHOD ---
def get_geom_props(y, b, m):
    if y <= 0: return 0.001, 0.001, 0.001, 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    return A, P, R, T

def solve_energy_equation(y_guess, Q, n, Z1, Z2, y1, b, m, L, dx, mode='subcritical'):
    g = 9.81
    A1, P1, R1, T1 = get_geom_props(y1, b, m)
    V1 = Q / A1
    H1 = Z1 + y1 + (V1**2) / (2*g)
    
    def energy_func(y2):
        A2, P2, R2, T2 = get_geom_props(y2, b, m)
        if A2 <= 0: return 1000.0
        V2 = Q / A2
        H2 = Z2 + y2 + (V2**2) / (2*g)
        
        Sf1 = (n * V1)**2 / (R1**(4/3)) if R1 > 0 else 0
        Sf2 = (n * V2)**2 / (R2**(4/3)) if R2 > 0 else 0
        Sf_avg = (Sf1 + Sf2) / 2
        
        h_f = Sf_avg * dx
        
        if mode == 'subcritical':
            return H2 - (H1 + h_f)
        else:
            return H1 - (H2 + h_f)

    y_min, y_max = 0.01, 20.0
    for _ in range(50):
        y_mid = (y_min + y_max) / 2
        err = energy_func(y_mid)
        if abs(err) < 0.001: return y_mid
        
        if mode == 'subcritical':
            if err > 0: y_max = y_mid 
            else: y_min = y_mid
        else:
            if err > 0: y_min = y_mid
            else: y_max = y_mid
            
    return (y_min + y_max) / 2

# --- 2. INISIALISASI DATA ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    data = [
        ["S1 (Hulu)", 0.0, 100.0, 105.0, 104.5, 2.0, 1.0, 0.015],
        ["S2 (Tengah)", 100.0, 200.0, 104.5, 104.0, 2.0, 1.0, 0.015],
        ["S3 (Hilir)", 200.0, 300.0, 104.0, 103.5, 2.0, 1.0, 0.015],
    ]
    return pd.DataFrame(data, columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 5.0
if 'ws_known' not in st.session_state: st.session_state['ws_known'] = 1.5

# --- 3. SIDEBAR LENGKAP ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 32px;">🚀 Smart HEC-RAS Pro</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.9;">Standard Step Method Solver (Energy Equation)</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Boundary Condition")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    
    calc_mode = st.radio("Mode Analisa", ["Subkritis (Hilir -> Hulu)", "Superkritis (Hulu -> Hilir)"], index=0)
    mode_key = 'subcritical' if "Sub" in calc_mode else 'supercritical'
    
    st.divider()
    
    if mode_key == 'subcritical':
        st.subheader("🌊 Batas Hilir (Downstream)")
        st.info("Masukkan kedalaman air yang diketahui di ujung paling hilir.")
        boundary_y = st.number_input("Kedalaman Air Hilir (m)", 0.1, 20.0, st.session_state['ws_known'])
    else:
        st.subheader("🌊 Batas Hulu (Upstream)")
        boundary_y = st.number_input("Kedalaman Air Hulu (m)", 0.1, 20.0, st.session_state['ws_known'])
        
    st.divider()

    # --- FITUR IMPORT EXCEL (DIPULIHKAN) ---
    st.subheader("📥 Excel Import")
    
    df_temp = pd.DataFrame([["Saluran 1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("📄 Template Excel", buf.getvalue(), "Template_Pro.xlsx")
    
    up_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    if up_file:
        try:
            df_up = pd.read_excel(up_file)
            
            # Smart Column Matcher
            def clean(t): return str(t).lower().replace(" ", "").replace("(m)", "").replace(".", "")
            df_up.columns = [clean(c) for c in df_up.columns]
            
            mapping = {
                "Nama Segmen": ["nama", "reach", "segmen"],
                "STA Awal (m)": ["staawal", "start", "hulu"],
                "STA Akhir (m)": ["staakhir", "end", "hilir"],
                "Elev Awal (m)": ["elevawal", "z1", "startelv"],
                "Elev Akhir (m)": ["elevakhir", "z2", "endelv"],
                "Lebar b (m)": ["lebar", "width", "b"],
                "Talud m": ["talud", "slope", "m", "z"],
                "Kekasaran n": ["kekasaran", "manning", "n"]
            }
            
            new_data = pd.DataFrame()
            found_count = 0
            for sys_col, keywords in mapping.items():
                for kw in keywords:
                    match = next((c for c in df_up.columns if kw in c), None)
                    if match:
                        new_data[sys_col] = df_up[match]
                        found_count += 1
                        break
            
            if found_count >= 6:
                if st.button("✅ Load Data Excel"):
                    st.session_state['df_pro'] = new_data
                    st.success("Data berhasil di-load!")
                    st.rerun()
            else: st.error("Format Excel tidak dikenali. Gunakan template.")
        except Exception as e: st.error(f"Error: {e}")

    # --- FITUR SAVE/LOAD PROJECT ---
    st.subheader("💾 Manajemen Project")
    project_data = {'q': st.session_state['q_pro'], 'segments': st.session_state['df_pro'].to_dict(orient='records')}
    st.download_button("Simpan Project (.json)", json.dumps(project_data, indent=2), "pro_project.json", "application/json")
    
    up_json = st.file_uploader("Buka Project (.json)", type=['json'])
    if up_json:
        try:
            loaded = json.load(up_json)
            st.session_state['q_pro'] = float(loaded['q'])
            st.session_state['df_pro'] = pd.DataFrame(loaded['segments'])
            st.rerun()
        except: st.error("File JSON rusak.")

    if st.button("🔄 Reset Data"): 
        st.session_state['df_pro'] = reset_data()
        st.rerun()

# --- 4. MAIN LOGIC ---
df = st.session_state['df_pro']
profile_coords = {'x': [], 'z': [], 'ws': [], 'eg': [], 'crit': []}
final_data = []

if not df.empty:
    try:
        df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        
        dx_step = 5.0 # Resolusi lebih halus
        nodes = []
        
        for seg in segments:
            L = seg["STA Akhir (m)"] - seg["STA Awal (m)"]
            if L <= 0: continue
            
            n_steps = int(L / dx_step)
            if n_steps < 1: n_steps = 1
            real_dx = L / n_steps
            
            z_start = seg["Elev Awal (m)"]
            z_end = seg["Elev Akhir (m)"]
            slope_seg = (z_start - z_end) / L
            
            for i in range(n_steps + 1):
                x_curr = seg["STA Awal (m)"] + i * real_dx
                z_curr = z_start - (i * real_dx * slope_seg)
                nodes.append({
                    "x": x_curr, "z": z_curr,
                    "b": seg["Lebar b (m)"], "m": seg["Talud m"], "n": seg["Kekasaran n"],
                    "seg_name": seg["Nama Segmen"]
                })
        
        Q = st.session_state['q_pro']
        
        if mode_key == 'subcritical':
            # Hilir ke Hulu
            nodes[-1]['y'] = boundary_y
            nodes[-1]['ws'] = nodes[-1]['z'] + boundary_y
            
            for i in range(len(nodes)-2, -1, -1):
                dx = nodes[i+1]['x'] - nodes[i]['x']
                y_res = solve_energy_equation(
                    y_guess=nodes[i+1]['y'], Q=Q, n=nodes[i]['n'],
                    Z1=nodes[i+1]['z'], Z2=nodes[i]['z'], y1=nodes[i+1]['y'],
                    b=nodes[i]['b'], m=nodes[i]['m'], L=dx, dx=dx, mode='subcritical'
                )
                nodes[i]['y'] = y_res
                nodes[i]['ws'] = nodes[i]['z'] + y_res
        else:
            # Hulu ke Hilir
            nodes[0]['y'] = boundary_y
            nodes[0]['ws'] = nodes[0]['z'] + boundary_y
            
            for i in range(1, len(nodes)):
                dx = nodes[i]['x'] - nodes[i-1]['x']
                y_res = solve_energy_equation(
                    y_guess=nodes[i-1]['y'], Q=Q, n=nodes[i]['n'],
                    Z1=nodes[i-1]['z'], Z2=nodes[i]['z'], y1=nodes[i-1]['y'],
                    b=nodes[i]['b'], m=nodes[i]['m'], L=dx, dx=dx, mode='supercritical'
                )
                nodes[i]['y'] = y_res
                nodes[i]['ws'] = nodes[i]['z'] + y_res

        for n in nodes:
            y = n['y']
            A, P, R, T = get_geom_props(y, n['b'], n['m'])
            V = Q/A if A > 0 else 0
            EGL = n['ws'] + (V**2)/(2*9.81)
            yc = ( (Q**2) / (9.81 * n['b']**2) )**(1/3) 
            
            n['eg'] = EGL; n['v'] = V; n['fr'] = V / np.sqrt(9.81 * (A/T)) if T > 0 else 0
            n['yc'] = yc; n['crit_ws'] = n['z'] + yc
            
            final_data.append(n)
            profile_coords['x'].append(n['x']); profile_coords['z'].append(n['z'])
            profile_coords['ws'].append(n['ws']); profile_coords['eg'].append(n['eg'])
            profile_coords['crit'].append(n['crit_ws'])

    except Exception as e: st.error(f"Error Calculation: {e}")

# --- 5. TABS VISUALISASI ---
tab_geom, tab_prof, tab_res = st.tabs(["📝 Input Geometri", "📈 Standard Step Profile", "📋 Laporan Hasil"])

with tab_geom:
    st.subheader("Editor Geometri Saluran")
    st.caption("Tips: Pastikan urutan STA menyambung dari Hulu ke Hilir.")
    new_df = st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)
    if not new_df.equals(st.session_state['df_pro']):
        st.session_state['df_pro'] = new_df
        st.rerun()

with tab_prof:
    if len(profile_coords['x']) > 0:
        st.subheader(f"Profil Muka Air ({calc_mode})")
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(profile_coords['x'], profile_coords['z'], 'k-', linewidth=2, label='Dasar Saluran')
        ax.plot(profile_coords['x'], profile_coords['ws'], 'b-', linewidth=2, label='Muka Air')
        ax.fill_between(profile_coords['x'], profile_coords['z'], profile_coords['ws'], color='#00eaff', alpha=0.6)
        
        ax.plot(profile_coords['x'], profile_coords['eg'], 'g--', linewidth=1, label='Garis Energi')
        ax.plot(profile_coords['x'], profile_coords['crit'], 'r:', linewidth=1, alpha=0.8, label='Kedalaman Kritis')
        
        ax.set_xlabel('Station (m)'); ax.set_ylabel('Elevation (m)')
        ax.legend(); ax.grid(True, linestyle=':', alpha=0.5)
        st.pyplot(fig)
        
        st.success("✅ Profil dihitung menggunakan Standard Step Method (Iterasi Energi).")
    else: st.info("Silakan isi data geometri.")

with tab_res:
    if final_data:
        res_df = pd.DataFrame(final_data)
        disp_cols = ["x", "seg_name", "z", "ws", "y", "v", "eg", "fr"]
        res_df = res_df[disp_cols]
        res_df.columns = ["Station", "Segmen", "Elev Dasar", "Elev Air", "Kedalaman", "Kecepatan", "Elev Energi", "Froude"]
        
        # Format
        for c in res_df.columns:
            if res_df[c].dtype == 'float64': res_df[c] = res_df[c].map('{:,.2f}'.format)
            
        st.dataframe(res_df, use_container_width=True)
        
        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Laporan CSV", csv, "laporan_pro_standard_step.csv", "text/csv")
