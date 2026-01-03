import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Pro", layout="wide", page_icon="🌊")

# CSS Agar Pesan Error/Sukses Lebih Jelas
st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #000428, #004e92); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 5px; margin-bottom: 10px; }
    .error-box { padding: 10px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 5px; margin-bottom: 10px; }
    @media print { .stSidebar, header, footer { display: none !important; } }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA ---
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
    
    # CHOKING / DROP DETECTION
    yc_target = ((Q**2) / (g * b**2))**(1/3)
    Ec_target = Z2 + yc_target + (Q/(b*yc_target))**2 / (2*g)
    
    # Jika Energi Hilir tidak cukup untuk naik ke Hulu (Drop Structure)
    if mode == 'subcritical' and H1 < Ec_target:
        return yc_target

    def energy_func(y2):
        A2, P2, R2, T2 = get_geom_props(y2, b, m)
        if A2 <= 0: return 1000.0
        V2 = Q / A2
        H2 = Z2 + y2 + (V2**2) / (2*g)
        
        Sf1 = (n * V1)**2 / (R1**(4/3)) if R1 > 0 else 0
        Sf2 = (n * V2)**2 / (R2**(4/3)) if R2 > 0 else 0
        Sf_avg = (Sf1 + Sf2) / 2
        h_f = Sf_avg * dx
        
        if mode == 'subcritical': return H2 - (H1 + h_f)
        else: return H1 - (H2 + h_f)

    y_min, y_max = 0.01, 50.0
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

# --- 2. INISIALISASI ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_known' not in st.session_state: st.session_state['ws_known'] = 0.4
if 'last_uploaded_file' not in st.session_state: st.session_state['last_uploaded_file'] = None

# --- UI ---
st.markdown("""<div class="header-box"><h1>🚀 Smart HEC-RAS Pro</h1><p>Standard Step Method (Auto-Load & Drop Detection)</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Boundary Condition")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    mode = st.radio("Mode", ["Subkritis (Hilir->Hulu)", "Superkritis (Hulu->Hilir)"], index=0)
    mode_key = 'subcritical' if "Sub" in mode else 'supercritical'
    
    st.divider()
    
    if mode_key == 'subcritical':
        st.subheader("🌊 Batas Hilir")
        boundary_y = st.number_input("Kedalaman Hilir (m)", 0.01, 50.0, st.session_state['ws_known'])
    else:
        st.subheader("🌊 Batas Hulu")
        boundary_y = st.number_input("Kedalaman Hulu (m)", 0.01, 50.0, st.session_state['ws_known'])
    
    st.divider()
    
    # --- IMPORT EXCEL (AUTO-LOAD VERSION) ---
    st.subheader("📥 Excel Import")
    
    # Template
    df_temp = pd.DataFrame([["S1", 0, 50, 100, 99.5, 0.6, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("📄 Template Excel", buf.getvalue(), "Template_Pro.xlsx")
    
    # Uploader dengan KEY unik biar bisa di-reset
    up_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'], key="excel_uploader")
    
    if up_file is not None:
        # Cek apakah ini file baru atau file lama yang masih nyangkut
        if up_file != st.session_state['last_uploaded_file']:
            try:
                df_up = pd.read_excel(up_file)
                
                # Smart Matcher (Lebih Toleran)
                def clean(t): return str(t).lower().replace(" ", "").replace("(m)", "").replace(".", "")
                df_up.columns = [clean(c) for c in df_up.columns]
                
                mapping = {
                    "Nama Segmen": ["nama", "reach", "segmen"], 
                    "STA Awal (m)": ["staawal", "start", "hulu", "sta1"],
                    "STA Akhir (m)": ["staakhir", "end", "hilir", "sta2"], 
                    "Elev Awal (m)": ["elevawal", "z1", "startelv", "elev1"],
                    "Elev Akhir (m)": ["elevakhir", "z2", "endelv", "elev2"], 
                    "Lebar b (m)": ["lebar", "width", "b"],
                    "Talud m": ["talud", "slope", "m", "z"], 
                    "Kekasaran n": ["kekasaran", "manning", "n"]
                }
                
                new_data = pd.DataFrame()
                found_cols = []
                for sys_col, keywords in mapping.items():
                    for kw in keywords:
                        match = next((c for c in df_up.columns if kw in c), None)
                        if match:
                            new_data[sys_col] = df_up[match]
                            found_cols.append(sys_col)
                            break
                
                # Jika minimal 5 kolom ketemu, kita anggap sukses
                if len(found_cols) >= 5:
                    # Isi kolom yang hilang dengan default
                    for col in REQUIRED_COLS:
                        if col not in new_data.columns:
                            new_data[col] = 0.0 if "Nama" not in col else "S-X"
                    
                    st.session_state['df_pro'] = new_data
                    st.session_state['last_uploaded_file'] = up_file # Tandai file ini sudah diload
                    st.toast("✅ Data Excel Berhasil Masuk!", icon="📂")
                    st.rerun() # Refresh otomatis
                else:
                    st.error("Gagal baca kolom. Pastikan pakai Template.")
                    
            except Exception as e:
                st.error(f"Error baca file: {e}")

    # Tombol Reset Manual
    if st.button("🔄 Reset Data (Hapus Semua)"): 
        st.session_state['df_pro'] = reset_data()
        st.session_state['last_uploaded_file'] = None
        st.rerun()

# --- 3. MAIN LOGIC & REPORT ---
df = st.session_state['df_pro']

# --- DETEKTIF DATA: Tampilkan Data Terakhir S22 ---
if not df.empty:
    last_row = df.iloc[-1]
    elev_akhir_s22 = last_row.get("Elev Akhir (m)", 0)
    elev_awal_s22 = last_row.get("Elev Awal (m)", 0)
    
    # Cek apakah Nanjak?
    is_nanjak = elev_akhir_s22 > elev_awal_s22
    
    st.info(f"""
    🕵️ **Detektif Data:**
    Sistem membaca Segmen Terakhir (**{last_row.get('Nama Segmen', 'Unknown')}**) sebagai berikut:
    - Elevasi Awal: **{elev_awal_s22} m**
    - Elevasi Akhir: **{elev_akhir_s22} m**
    - Status: **{'⛔ NANJAK (Bahaya!)' if is_nanjak else '✅ MENURUN (Aman)'}**
    
    *(Jika status masih NANJAK, berarti file Excel Kakak belum terupdate atau salah edit)*
    """)

# ... (Logic hitungan sama seperti sebelumnya) ...
profile = {'x': [], 'z': [], 'ws': [], 'eg': [], 'crit': []}
final_data = []

if not df.empty:
    try:
        df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        dx_step = 5.0
        nodes = []
        for seg in segments:
            L = seg["STA Akhir (m)"] - seg["STA Awal (m)"]
            if L <= 0: continue
            n_steps = int(L / dx_step); 
            if n_steps < 1: n_steps = 1
            real_dx = L / n_steps
            z_s, z_e = seg["Elev Awal (m)"], seg["Elev Akhir (m)"]
            slope = (z_s - z_e) / L
            for i in range(n_steps + 1):
                nodes.append({
                    "x": seg["STA Awal (m)"] + i * real_dx,
                    "z": z_s - (i * real_dx * slope),
                    "b": seg["Lebar b (m)"], "m": seg["Talud m"], "n": seg["Kekasaran n"], "seg": seg["Nama Segmen"]
                })
        
        Q = st.session_state['q_pro']
        
        if mode_key == 'subcritical':
            nodes[-1]['y'] = boundary_y
            nodes[-1]['ws'] = nodes[-1]['z'] + boundary_y
            for i in range(len(nodes)-2, -1, -1):
                dx = nodes[i+1]['x'] - nodes[i]['x']
                y_res = solve_energy_equation(nodes[i+1]['y'], Q, nodes[i]['n'], nodes[i+1]['z'], nodes[i]['z'], nodes[i+1]['y'], nodes[i]['b'], nodes[i]['m'], dx, dx, 'subcritical')
                nodes[i]['y'] = y_res
                nodes[i]['ws'] = nodes[i]['z'] + y_res
        else:
            nodes[0]['y'] = boundary_y
            nodes[0]['ws'] = nodes[0]['z'] + boundary_y
            for i in range(1, len(nodes)):
                dx = nodes[i]['x'] - nodes[i-1]['x']
                y_res = solve_energy_equation(nodes[i-1]['y'], Q, nodes[i]['n'], nodes[i-1]['z'], nodes[i]['z'], nodes[i-1]['y'], nodes[i]['b'], nodes[i]['m'], dx, dx, 'supercritical')
                nodes[i]['y'] = y_res
                nodes[i]['ws'] = nodes[i]['z'] + y_res

        for n in nodes:
            y, b, m = n['y'], n['b'], n['m']
            A, P, R, T = get_geom_props(y, b, m)
            V = Q/A if A>0 else 0
            n['eg'] = n['ws'] + (V**2)/(19.62)
            n['crit_ws'] = n['z'] + ((Q**2)/(9.81 * b**2))**(1/3)
            final_data.append(n)
            profile['x'].append(n['x']); profile['z'].append(n['z'])
            profile['ws'].append(n['ws']); profile['eg'].append(n['eg']); profile['crit'].append(n['crit_ws'])

    except Exception as e: st.error(f"Error: {e}")

# --- TABS ---
t1, t2, t3 = st.tabs(["📝 Input", "📈 Grafik Profil", "📋 Laporan"])

with t1:
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with t2:
    if len(profile['x']) > 0:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(profile['x'], profile['z'], 'k-', lw=2, label='Dasar')
        ax.plot(profile['x'], profile['ws'], 'b-', lw=2, label='Muka Air')
        ax.fill_between(profile['x'], profile['z'], profile['ws'], color='#00eaff', alpha=0.6)
        ax.plot(profile['x'], profile['crit'], 'r:', label='Kritis')
        ax.plot(profile['x'], profile['eg'], 'g--', label='Energi')
        ax.legend(); ax.grid(True, ls=':')
        st.pyplot(fig)
    else: st.info("Upload Excel dulu.")

with t3:
    if final_data:
        res = pd.DataFrame(final_data)[["x", "seg", "z", "ws", "y", "eg", "crit_ws"]]
        res.columns = ["Sta", "Segmen", "Elev Dasar", "W.S.", "Depth", "E.G.", "Crit W.S."]
        st.dataframe(res, use_container_width=True)
