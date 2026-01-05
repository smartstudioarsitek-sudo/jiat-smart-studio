import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate", layout="wide", page_icon="🏗️")

# --- 2. SETUP & STATE (PASTIKAN INI ADA DI ATAS SIDEBAR) ---

# Definisikan kolom wajib termasuk kolom baru "Slope Desain S"
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", 
                 "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)", "Slope Desain S"]

def reset_data():
    # Default data dengan kolom Slope
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5, 0.001]], columns=REQUIRED_COLS)

# --- BAGIAN PENTING (INI YANG HILANG/KELEWAT) ---
if 'df_pro' not in st.session_state: 
    st.session_state['df_pro'] = reset_data()

if 'q_pro' not in st.session_state: 
    st.session_state['q_pro'] = 0.24  # <--- Ini obat errornya

if 'ws_down' not in st.session_state: 
    st.session_state['ws_down'] = 0.5

if 'ws_up' not in st.session_state: 
    st.session_state['ws_up'] = 0.2 
# ------------------------------------------------

# --- UI SIDEBAR (BARU BOLEH DI BAWAH SINI) ---
# ...

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #134E5E, #71B280); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .stDataFrame { border: 1px solid #ddd; border-radius: 5px; }
    @media print { .stSidebar, header, footer { display: none !important; } }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA & AUTOCAD ---

def get_critical_depth(Q, b, m):
    y_min, y_max = 0.01, 20.0
    for _ in range(30):
        y = (y_min + y_max) / 2
        A = (b + m * y) * y; T = b + 2 * m * y
        if A <= 0: A = 0.001
        f_val = 9.81 * (A**3) - (Q**2) * T
        if abs(f_val) < 0.01: return y
        if f_val < 0: y_min = y
        else: y_max = y
    return (y_min + y_max) / 2

def get_geom_props(y, b, m, Q):
    if y <= 0.001: y = 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    hydrostatic_term = ((y**2)/2) * b + ((y**3)/3) * m
    g = 9.81
    if A > 0.0001: M = (Q**2)/(g*A) + hydrostatic_term 
    else: M = 0
    return A, P, R, T, M

def solve_energy_step(y_known, Q, n, Z1, Z2, b, m, dx, mode):
    g = 9.81
    A1, P1, R1, T1, M1 = get_geom_props(y_known, b, m, Q)
    V1 = Q/A1
    H1 = Z1 + y_known + (V1**2)/(2*g)
    
    def func(y2):
        A2, P2, R2, T2, M2 = get_geom_props(y2, b, m, Q)
        V2 = Q/A2
        H2 = Z2 + y2 + (V2**2)/(2*g)
        Sf1 = (n*V1)**2 / (R1**(4/3))
        Sf2 = (n*V2)**2 / (R2**(4/3))
        Sf_avg = (Sf1 + Sf2)/2
        loss = Sf_avg * dx
        if mode == 'sub': return H2 - (H1 + loss)
        else: return H1 - (H2 + loss)

    y_min, y_max = 0.01, 50.0
    for _ in range(50):
        y_mid = (y_min + y_max)/2
        err = func(y_mid)
        if abs(err) < 0.001: return y_mid
        if mode == 'sub': 
            if err > 0: y_max = y_mid 
            else: y_min = y_mid
        else:
            if err > 0: y_min = y_mid
            else: y_max = y_mid
    return (y_min + y_max)/2

def calculate_profiles(nodes, Q, boundary_down, boundary_up, force_super=False):
    for n in nodes:
        n['yc'] = get_critical_depth(Q, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # Subcritical
    nodes[-1]['y_sub'] = boundary_down
    for i in range(len(nodes)-2, -1, -1):
        dx = nodes[i+1]['x'] - nodes[i]['x']
        known, target = nodes[i+1], nodes[i]
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sub'], Q, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sub')
            if y_calc < yc: y_calc = yc + 0.01 
        except: y_calc = yc + 0.01
        target['y_sub'] = y_calc

    # Supercritical
    nodes[0]['y_sup'] = boundary_up
    for i in range(1, len(nodes)):
        dx = nodes[i]['x'] - nodes[i-1]['x']
        known, target = nodes[i-1], nodes[i]
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sup'], Q, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sup')
            if y_calc > yc: y_calc = yc - 0.01 
        except: y_calc = yc - 0.01
        target['y_sup'] = y_calc

    # Selection Logic
    for n in nodes:
        if force_super:
            if n['y_sup'] > 0.011 and n['y_sup'] < 49.0: 
                n['y_final'] = n['y_sup']
                n['regime'] = "Supercritical"
            else: 
                n['y_final'] = n['yc']
                n['regime'] = "Critical"
        else:
            if n['y_sub'] <= 0.011 or n['y_sub'] > 49.0: M_sub = -1.0
            else: _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q)
            if n['y_sup'] <= 0.011 or n['y_sup'] > 49.0: M_sup = -1.0
            else: _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q)
            
            if M_sub == -1 and M_sup == -1: 
                n['y_final'] = n['yc']
                n['regime'] = "Critical"
            elif M_sub >= M_sup: 
                n['y_final'] = n['y_sub']
                n['regime'] = "Subcritical"
            else: 
                n['y_final'] = n['y_sup']
                n['regime'] = "Supercritical"
            
        n['ws'] = n['z'] + n['y_final']
        n['crit_ws'] = n['z'] + n['yc']
        H_ch = n.get('h_ch', 1.5)
        n['bank_elev'] = n['z'] + H_ch
        n['freeboard'] = n['bank_elev'] - n['ws']
        n['h_design'] = n['y_final'] + 0.4
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        V = Q/A if A > 0 else 0
        n['v'] = V 
        n['eg'] = n['ws'] + (V**2)/(2*9.81)
        D_hyd = A/T if T > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0

    return nodes

def generate_long_section_scr(nodes, dataset_name="Eksisting"):
    s = "; --- SMART HEC-RAS LONG SECTION SCRIPT ---\n"
    s += "OSMODE 0\n" 
    
    # Layer Dasar
    s += f"-LAYER M {dataset_name}_DASAR C 30 {dataset_name}_DASAR \n"
    s += "_PLINE\n"
    for n in nodes: s += f"{n['x']:.4f},{n['z']:.4f}\n"
    s += "\n"
    
    # Layer Air
    s += f"-LAYER M {dataset_name}_AIR C 150 {dataset_name}_AIR \n"
    s += "_PLINE\n"
    for n in nodes: s += f"{n['x']:.4f},{n['ws']:.4f}\n"
    s += "\n"
    
    # Layer Bank
    s += f"-LAYER M {dataset_name}_BANK C 10 {dataset_name}_BANK \n"
    s += "_PLINE\n"
    for n in nodes:
        bank = n['z'] + n['h_ch']
        s += f"{n['x']:.4f},{bank:.4f}\n"
    s += "\n"
    
    s += "ZOOM E\n"
    return s

def generate_cross_section_scr(nodes, dataset_name="Desain", spacing_x=20, spacing_y=20):
    s = "; --- SMART HEC-RAS CROSS SECTION SCRIPT ---\n"
    s += "OSMODE 0\n"
    
    row_count = 0
    col_count = 0
    max_cols = 5 
    
    for i, n in enumerate(nodes):
        base_x = col_count * spacing_x
        base_y = row_count * spacing_y * -1 
        
        b = n['b']; m = n['m']; z = n['z']; h = n['h_ch']
        ws = n['ws']; y = n['y_final']
        
        top_w_half = (b + 2*m*h) / 2
        x1, y1 = -top_w_half, h
        x2, y2 = -b/2, 0
        x3, y3 = b/2, 0
        x4, y4 = top_w_half, h
        
        # Saluran
        s += f"-LAYER M {dataset_name}_CS_SALURAN C 7 {dataset_name}_CS_SALURAN \n"
        s += "_PLINE\n"
        s += f"{base_x + x1:.4f},{base_y + y1:.4f}\n"
        s += f"{base_x + x2:.4f},{base_y + y2:.4f}\n"
        s += f"{base_x + x3:.4f},{base_y + y3:.4f}\n"
        s += f"{base_x + x4:.4f},{base_y + y4:.4f}\n"
        s += "\n"
        
        # Air
        if y > 0.01:
            top_w_water = (b + 2*m*y) / 2
            wx1, wy1 = -top_w_water, y
            wx2, wy2 = top_w_water, y
            
            s += f"-LAYER M {dataset_name}_CS_AIR C 150 {dataset_name}_CS_AIR \n"
            s += "_PLINE\n"
            s += f"{base_x + wx1:.4f},{base_y + wy1:.4f}\n"
            s += f"{base_x + wx2:.4f},{base_y + wy2:.4f}\n"
            s += "\n"
        
        # Teks
        s += f"-LAYER M {dataset_name}_TEXT C 2 {dataset_name}_TEXT \n"
        s += f"-TEXT {base_x:.4f},{base_y - 2:.4f} 0.5 0 STA {n['x']:.2f}\n"
        
        col_count += 1
        if col_count >= max_cols:
            col_count = 0
            row_count += 1
            
    s += "ZOOM E\n"
    return s

# --- 2. SETUP & STATE ---

# Kolom Data Eksisting + 4 Kolom Baru untuk Parameter Desain
REQUIRED_COLS = [
    "Nama Segmen", "STA Awal (m)", "STA Akhir (m)", 
    "Elev Awal (m)", "Elev Akhir (m)", 
    "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)",
    # --- KOLOM DESAIN BARU (Per Segmen) ---
    "Desain S", "Desain B (m)", "Desain m", "Max Drop (m)"
]

def reset_data():
    # S1 punya default: S=0.001, B=0.6, m=1.0, Drop=1.5
    return pd.DataFrame([
        ["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5, 0.001, 0.6, 1.0, 1.5]
    ], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: 
    st.session_state['df_pro'] = reset_data()

# Variable default global (untuk inisialisasi saja)
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2

# --- UI SIDEBAR ---
st.markdown("""<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate</h1><p>Excel • GeoJSON/GIS • AutoCAD Export</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter Hidrolis")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    force_super = st.checkbox("🔥 Force Supercritical", value=False)
    
    st.divider()
    st.subheader("📂 Upload Data")
    
    # TAB UPLOAD
    tab_ex, tab_gis, tab_csv = st.tabs(["📄 Excel", "🌍 GeoJSON", "🔢 CSV"])

  # ... (setelah df terbentuk dari upload excel/gis) ...

# 1. Hapus kolom "Slope Desain S" lama jika ada (sesuai request)
if "Slope Desain S" in df.columns:
    df = df.drop(columns=["Slope Desain S"])

# 2. Tambahkan 4 Kolom Desain Baru dengan nilai default aman
defaults = {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5}

for col, val in defaults.items():
    if col not in df.columns:
        df[col] = val

# ... (lanjutkan simpan ke session_state) ...
  
    with tab_ex:
        # TOMBOL DOWNLOAD TEMPLATE
        buffer_template = io.BytesIO()
        with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
            reset_data().to_excel(writer, index=False)
        st.download_button("📥 Download Template Excel", buffer_template.getvalue(), "Template_Saluran.xlsx")

        up_excel = st.file_uploader("Upload .xlsx", type=['xlsx'], key="xls_up")
        
        if up_excel:
            try:
                df = pd.read_excel(up_excel)
                # Normalisasi Nama Kolom (Agar huruf besar/kecil tidak masalah)
                df.columns = [c.strip() for c in df.columns] 

                # ... (setelah df terbentuk dari upload) ...

                # SAFETY: Cek apakah kolom "Slope Desain S" ada, jika tidak, buat dengan default
                if "Slope Desain S" not in df.columns:
                    df["Slope Desain S"] = 0.001 # Default value

                # ... (lanjutkan code seperti biasa) ...
                
                # Cek kolom kunci
                if "Elev Awal (m)" in df.columns:
                    st.session_state['df_pro'] = df
                    
                    # --- FIX PENTING: RESET EDITOR CACHE ---
                    # Ini yang bikin tabel tadi gak berubah meski data sudah masuk
                    if 'editor_input' in st.session_state:
                        del st.session_state['editor_input']
                        
                    st.success("Data Excel berhasil dimuat! Tabel akan diperbarui...")
                    st.rerun()
                else:
                    st.error(f"Format Salah. Kolom ditemukan: {list(df.columns)}")
            except Exception as e: st.error(f"Error: {e}")

    with tab_gis:
        st.info("Support GeoJSON/JSON. Untuk SHP, convert dulu ke GeoJSON.")
        up_geo = st.file_uploader("Upload .geojson", type=['geojson', 'json'], key="geo_up")
        
        def_b = st.number_input("Default Lebar (b)", 0.1, 50.0, 2.0, key="def_b")
        def_m = st.number_input("Default Talud (m)", 0.0, 10.0, 1.0, key="def_m")
        def_n = st.number_input("Default Manning (n)", 0.001, 0.1, 0.025, format="%.3f", key="def_n")
        
        if up_geo and st.button("🚀 Load GIS"):
            try:
                data = json.load(up_geo)
                features = data.get('features', [])
                new_rows = []
                coords = []
                for f in features:
                    geo = f.get('geometry', {})
                    if geo.get('type') == 'LineString':
                        coords = geo.get('coordinates', [])
                        break
                
                if coords:
                    current_dist = 0.0
                    for i in range(len(coords) - 1):
                        p1 = coords[i]; p2 = coords[i+1]
                        dist = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                        z1 = p1[2] if len(p1) > 2 else 0
                        z2 = p2[2] if len(p2) > 2 else 0
                        
                        new_rows.append({
                            "Nama Segmen": f"S{i+1}", 
                            "STA Awal (m)": current_dist, 
                            "STA Akhir (m)": current_dist + dist,
                            "Elev Awal (m)": z1, "Elev Akhir (m)": z2,
                            "Lebar b (m)": def_b, "Talud m": def_m, 
                            "Kekasaran n": def_n, "Tinggi Saluran H (m)": 1.5
                        })
                        current_dist += dist
                    
                    if new_rows:
                        st.session_state['df_pro'] = pd.DataFrame(new_rows)
                        if 'editor_input' in st.session_state: del st.session_state['editor_input']
                        st.success(f"Berhasil load {len(new_rows)} segmen!")
                        st.rerun()
                else:
                    st.error("Tidak ditemukan LineString dalam GeoJSON.")
            except Exception as e: st.error(f"Error parse GeoJSON: {e}")

    with tab_csv:
        up_gis = st.file_uploader("Upload CSV Global Mapper", type=['csv', 'txt'], key="csv_up")
        if up_gis and st.button("🚀 Load CSV"):
            try:
                df_gis = pd.read_csv(up_gis)
                df_gis.columns = [c.lower() for c in df_gis.columns]
                col_dist = next((c for c in df_gis.columns if any(x in c for x in ['dist', 'len', 'x', 'sta'])), None)
                col_elev = next((c for c in df_gis.columns if any(x in c for x in ['elev', 'z', 'height'])), None)
                
                if col_dist and col_elev:
                    new_rows = []
                    for i in range(len(df_gis) - 1):
                        d1 = df_gis.iloc[i][col_dist]; d2 = df_gis.iloc[i+1][col_dist]
                        z1 = df_gis.iloc[i][col_elev]; z2 = df_gis.iloc[i+1][col_elev]
                        if abs(d2 - d1) < 0.01: continue
                        new_rows.append({
                            "Nama Segmen": f"S{i+1}", "STA Awal (m)": d1, "STA Akhir (m)": d2,
                            "Elev Awal (m)": z1, "Elev Akhir (m)": z2,
                            "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                        })
                    st.session_state['df_pro'] = pd.DataFrame(new_rows)
                    if 'editor_input' in st.session_state: del st.session_state['editor_input']
                    st.success(f"Import {len(new_rows)} segmen sukses!")
                    st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    st.divider()
    st.subheader("🛠️ Auto-Redesign")
    
    use_redesign = st.checkbox("Aktifkan Redesain", value=True) 
    
    target_slope = 0.001; design_b = 1.5; design_m = 1.0; max_drop = 1.5; start_offset = 0.0
    
    if use_redesign:
        target_slope = st.number_input("Target S", 0.0001, 0.05, 0.001, format="%.4f")
        design_b = st.number_input("Lebar Desain B (m)", 0.1, 50.0, 0.60)
        design_m = st.number_input("Talud Desain m", 0.0, 10.0, 1.0, step=0.1)
        max_drop = st.number_input("Max Drop (m)", 0.5, 5.0, 1.5)
        start_offset = st.number_input("Offset Elevasi STA 0 (+/- m)", -50.0, 50.0, -1.0, step=0.1)
    
    st.divider()
    if st.button("Reset Data"): 
        st.session_state['df_pro'] = reset_data()
        if 'editor_input' in st.session_state: del st.session_state['editor_input']
        st.rerun()

# --- MAIN LOGIC ---
df = st.session_state['df_pro']
profile_ex = {'x': [], 'z': [], 'ws': [], 'crit': [], 'bank': []} 
profile_new = {'x': [], 'z': [], 'ws': [], 'drops': []} 

final_data_ex = []; final_data_new = []; all_nodes_ex = []; all_nodes_new = []

if not df.empty:
    try:
        if "STA Awal (m)" in df.columns: df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        dx_step = 2.0 
        
        # 1. EKSISTING
        nodes_ex = []
        for idx, seg in enumerate(segments):
            sta1 = seg.get("STA Awal (m)", 0); sta2 = seg.get("STA Akhir (m)", 0)
            z1 = seg.get("Elev Awal (m)", 0); z2 = seg.get("Elev Akhir (m)", 0)
            L = sta2 - sta1
            if L <= 0: continue
            n_steps = int(L / dx_step); 
            if n_steps < 1: n_steps = 1
            real_dx = L / n_steps
            slope = (z1 - z2) / L
            h_ch = seg.get("Tinggi Saluran H (m)", 1.5)
            
            for i in range(n_steps + 1):
                nodes_ex.append({
                    "x": sta1 + i * real_dx, "z": z1 - (i * real_dx * slope),
                    "b": seg.get("Lebar b (m)", 1.0), "m": seg.get("Talud m", 1.0), 
                    "n": seg.get("Kekasaran n", 0.025), "seg": seg.get("Nama Segmen", f"S{idx}"),
                    "h_ch": h_ch
                })
        
        if len(nodes_ex) > 0:
            nodes_ex = calculate_profiles(nodes_ex, st.session_state['q_pro'], st.session_state['ws_down'], st.session_state['ws_up'], force_super)
            all_nodes_ex = nodes_ex
            for n in nodes_ex:
                profile_ex['x'].append(n['x']); profile_ex['z'].append(n['z'])
                profile_ex['ws'].append(n['ws']); profile_ex['crit'].append(n['crit_ws'])
                profile_ex['bank'].append(n['bank_elev'])
                final_data_ex.append(n)

        # 2. REDESAIN
        if use_redesign and len(nodes_ex) > 0:
            nodes_new = []
            start_z_original = nodes_ex[0]['z']
            
            # --- MODIFIKASI DIMULAI DISINI ---
            # 1. Buat Dictionary Map biar gampang cari slope berdasarkan nama segmen
            #    Format: {'S1': 0.002, 'S2': 0.005, ...}
            seg_map_slope = df.set_index('Nama Segmen')['Slope Desain S'].to_dict()
            
            current_z = start_z_original + start_offset 
            
            for i, n in enumerate(nodes_ex):
                # Ambil nama segmen dari node saat ini
                seg_name = n['seg']
                
                # Ambil slope spesifik segmen tersebut (fallback ke target_slope global jika error)
                local_slope = seg_map_slope.get(seg_name, target_slope) 

                if i > 0:
                    dx = n['x'] - nodes_ex[i-1]['x']
                    # Hitung penurunan elevasi berdasarkan slope LOKAL segmen ini
                    current_z -= dx * local_slope
                
                # Logic Drop Structure (Terjun)
                if (current_z - n['z']) > max_drop:
                      current_z = n['z']; profile_new['drops'].append(n['x'])

                nodes_new.append({
                    "x": n['x'], "z": current_z, "b": design_b, "m": design_m, 
                    "n": 0.025, "seg": n['seg'], "h_ch": n['h_ch']
                })
            # --- MODIFIKASI SELESAI ---
            
            res_new = calculate_profiles(nodes_new, st.session_state['q_pro'], 1.0, 1.0, False)
            all_nodes_new = res_new 
            for n in res_new:
                profile_new['x'].append(n['x']); profile_new['z'].append(n['z']); profile_new['ws'].append(n['ws'])
                n['z_original'] = next((ex['z'] for ex in nodes_ex if abs(ex['x'] - n['x']) < 0.01), 0)
                final_data_new.append(n)

    except Exception as e: st.error(f"Error: {e}")

# --- TABS UI ---
if use_redesign:
    tab_titles = ["📝 Input Data", "🛠️ Hasil Redesain", "📈 Profil Eksisting", "📑 Rekap AutoCAD", "📋 Laporan"]
else:
    tab_titles = ["📝 Input Data", "📈 Profil Eksisting", "📑 Rekap AutoCAD", "📋 Laporan"]

active_tabs = st.tabs(tab_titles)

# TAB 1: INPUT
with active_tabs[0]:
    st.info("💡 Edit data Eksisting di sini. Data ini bisa dari hasil upload Excel/GIS di sebelah kiri (sidebar).")
    # KEY DITAMBAHKAN AGAR BISA DI-RESET
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", width='stretch', key="editor_input")

idx = 1 

# TAB 2: REDESAIN
if use_redesign:
    with active_tabs[idx]:
        rt_graph, rt_table, rt_cs = st.tabs(["📉 Grafik", "📋 Tabel", "❌ CS Redesain"])
        with rt_graph:
            if len(profile_new['x']) > 0:
                fig, ax = plt.subplots(figsize=(14, 6))
                ax.plot(profile_ex['x'], profile_ex['z'], 'k--', lw=1, alpha=0.5, label='Tanah Asli')
                ax.plot(profile_new['x'], profile_new['z'], 'brown', lw=2, label='Desain')
                ax.plot(profile_new['x'], profile_new['ws'], 'g-', lw=2, label='Air')
                ax.fill_between(profile_new['x'], profile_new['z'], profile_new['ws'], color='#ccffcc', alpha=0.6)
                for d in profile_new['drops']: ax.axvline(x=d, color='red', ls='--')
                ax.legend(); st.pyplot(fig)
        with rt_table:
            if final_data_new:
                 st.dataframe(pd.DataFrame(final_data_new)[['x','z','ws','y_final','v']])
        with rt_cs:
            if len(all_nodes_new) > 0:
                sta_list_new = [n['x'] for n in all_nodes_new]
                sel = st.select_slider("Station", options=sta_list_new)
                node = next((n for n in all_nodes_new if n['x'] == sel), None)
                if node:
                    fig_cs, ax_cs = plt.subplots(figsize=(6,4))
                    b, m, z, y, ws = node['b'], node['m'], node['z'], node['y_final'], node['ws']
                    H = node['h_ch']; T = b + 2*m*y; TopW = b + 2*m*H
                    x_g = [-TopW/2, -b/2, b/2, TopW/2]; y_g = [z+H, z, z, z+H]
                    ax_cs.plot(x_g, y_g, 'r-', lw=3)
                    if y > 0.001: ax_cs.fill([-T/2, T/2, b/2, -b/2], [ws, ws, z, z], color='#00eaff', alpha=0.6)
                    ax_cs.grid(True); st.pyplot(fig_cs)
    idx += 1

# TAB 3: PROFIL EKSISTING
with active_tabs[idx]:
    if len(profile_ex['x']) > 0:
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(profile_ex['x'], profile_ex['z'], 'k-', lw=2, label='Tanah')
        ax.plot(profile_ex['x'], profile_ex['ws'], 'b-', lw=2, label='Air')
        ax.fill_between(profile_ex['x'], profile_ex['z'], profile_ex['ws'], color='#00eaff', alpha=0.4)
        ax.legend(); st.pyplot(fig)
idx += 1

# TAB 4: REKAP AUTOCAD (.scr)
with active_tabs[idx]:
    st.subheader("📑 Export Script AutoCAD (.scr)")
    st.markdown("""
    **Cara Penggunaan:**
    1. Download file `.scr` di bawah.
    2. Buka AutoCAD, ketik command `SCRIPT` lalu enter.
    3. Pilih file yang sudah didownload. Gambar akan otomatis terbentuk!
    """)
    
    col_scr1, col_scr2 = st.columns(2)
    
    with col_scr1:
        st.info("📉 **Script Long Section (Memanjang)**")
        data_choice = st.radio("Pilih Data:", ["Eksisting", "Redesain"], horizontal=True)
        nodes_to_export = all_nodes_new if (data_choice == "Redesain" and use_redesign) else all_nodes_ex
        
        if nodes_to_export:
            scr_long = generate_long_section_scr(nodes_to_export, dataset_name=data_choice.upper())
            st.download_button(
                label=f"📥 Download Long Section ({data_choice})",
                data=scr_long,
                file_name=f"LS_{data_choice}.scr",
                mime="text/plain"
            )
        else:
            st.warning("Data tidak tersedia.")

    with col_scr2:
        st.info("❌ **Script Cross Section (Melintang)**")
        grid_x = st.number_input("Jarak Antar Gambar Horizontal (m)", 10, 100, 30)
        grid_y = st.number_input("Jarak Antar Gambar Vertikal (m)", 10, 100, 20)
        
        if nodes_to_export:
            scr_cs = generate_cross_section_scr(nodes_to_export, dataset_name=data_choice.upper(), spacing_x=grid_x, spacing_y=grid_y)
            st.download_button(
                label=f"📥 Download Cross Section ({data_choice})",
                data=scr_cs,
                file_name=f"CS_{data_choice}.scr",
                mime="text/plain"
            )
idx += 1

# TAB 5: LAPORAN STYLING
with active_tabs[idx]:
    st.subheader("📋 Laporan Analisis Hidrolika")
    
    df_rep = pd.DataFrame(final_data_new if (use_redesign and final_data_new) else final_data_ex)
    
    if not df_rep.empty:
        cols_wanted = ['x', 'z', 'ws', 'y_final', 'v', 'fr', 'freeboard', 'regime']
        if 'z_original' in df_rep.columns: cols_wanted.insert(1, 'z_original')
        
        existing_cols = [c for c in cols_wanted if c in df_rep.columns]
        df_show = df_rep[existing_cols].copy()
        
        rename_map = {
            'x': 'Station (m)', 'z': 'Elev Dasar (m)', 'z_original': 'Tanah Asli (m)',
            'ws': 'Muka Air (m)', 'y_final': 'Kedalaman (m)', 'v': 'Kecepatan (m/s)',
            'fr': 'Froude Num', 'freeboard': 'Freeboard (m)', 'regime': 'Status'
        }
        df_show.rename(columns=rename_map, inplace=True)
        
        def highlight_danger(val):
            return 'background-color: #ffcccc' if val < 0.3 else ''
        
        def highlight_froude(val):
            return 'color: purple; font-weight: bold' if val > 1 else ''

        styler = df_show.style.format("{:.2f}", subset=[c for c in df_show.columns if c != 'Status'])\
            .set_properties(**{'text-align': 'center'})\
            .set_table_styles([{'selector': 'th','props': [('background-color', '#4CAF50'), ('color', 'white')]}])
        
        if 'Freeboard (m)' in df_show.columns:
            styler = styler.applymap(highlight_danger, subset=['Freeboard (m)'])
        if 'Froude Num' in df_show.columns:
            styler = styler.applymap(highlight_froude, subset=['Froude Num'])
            
        st.dataframe(styler, height=500, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_show.to_excel(writer, index=False, sheet_name='Laporan')
        
        st.download_button("📥 Download Excel Laporan", buffer.getvalue(), "Laporan_Hidrolika.xlsx", "application/vnd.ms-excel")
    else:
        st.warning("Belum ada data untuk ditampilkan.")
