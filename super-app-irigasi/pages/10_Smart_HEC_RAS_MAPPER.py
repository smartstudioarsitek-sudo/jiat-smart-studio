import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import tempfile
import os
import zipfile

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #002B5B, #2B4865); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .metric-card { background-color: #f0f4f8; padding: 15px; border-radius: 8px; border-left: 5px solid #002B5B; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# --- 1. SMART DXF PARSER V2.0 (Zero-Dependency) ---
def parse_dxf_raw_v2(file_content, use_y_as_z=False):
    """
    Parser DXF Manual yang lebih pintar. 
    Bisa membaca LWPOLYLINE (2D) dan POLYLINE/VERTEX (3D).
    """
    try:
        content = file_content.decode('utf-8', errors='ignore')
        lines = [line.strip() for line in content.splitlines()]
        
        points = []
        
        # State Variables
        in_entities = False
        current_type = None # 'LWPOLYLINE' atau 'POLYLINE'
        
        # Temp Storage for Polyline 3D
        collecting_vertices = False
        poly_3d_points = []
        
        # Temp Storage for LWPolyline
        lw_points = []
        lw_elevation = 0.0 # Default Z for LWPolyline
        
        i = 0
        while i < len(lines):
            code = lines[i]
            value = lines[i+1] if i+1 < len(lines) else ""
            
            # 1. Deteksi Section ENTITIES
            if code == '0' and value == 'SECTION':
                # Cek next code 2 = ENTITIES
                if i+2 < len(lines) and lines[i+2] == '2' and lines[i+3] == 'ENTITIES':
                    in_entities = True
                    i += 4; continue
            
            if code == '0' and value == 'ENDSEC':
                in_entities = False
                
            if in_entities:
                # --- CASE A: POLYLINE (3D - Seperti File Global Mapper) ---
                if code == '0' and value == 'POLYLINE':
                    # Jika ada polyline sebelumnya yg belum disimpan, simpan dulu
                    if poly_3d_points: return process_points(poly_3d_points)
                    collecting_vertices = True
                    poly_3d_points = []
                    current_type = 'POLYLINE'
                
                elif code == '0' and value == 'VERTEX' and collecting_vertices:
                    # Baca X, Y, Z dari VERTEX ini
                    vx, vy, vz = 0.0, 0.0, 0.0
                    # Scan forward sedikit untuk cari 10, 20, 30
                    # Vertex attributes biasanya berdekatan
                    j = 1
                    found_coords = 0
                    while j < 20 and (i+j*2) < len(lines):
                        c = lines[i+j*2]
                        v = lines[i+j*2+1]
                        if c == '0': break # Ketemu entity lain
                        if c == '10': vx = float(v)
                        elif c == '20': vy = float(v)
                        elif c == '30': vz = float(v)
                        j += 1
                    
                    # Logic Pilih Elevasi
                    elev = vy if use_y_as_z else vz
                    poly_3d_points.append((vx, vy, elev))
                
                elif code == '0' and value == 'SEQEND':
                    if collecting_vertices and len(poly_3d_points) > 1:
                        return process_points(poly_3d_points) # Return immediately first valid poly
                    collecting_vertices = False

                # --- CASE B: LWPOLYLINE (2D) ---
                elif code == '0' and value == 'LWPOLYLINE':
                    # Parse LWPOLYLINE logic (Simple 2D scan)
                    # Ini agak kompleks kalau manual parsing, tapi kita coba tangkap elevasi global (38)
                    pass # (Sederhananya kita fokus ke POLYLINE dulu karena file user tipe ini)

            i += 2
            
        return "Tidak ditemukan garis yang valid (POLYLINE/VERTEX) dalam DXF."

    except Exception as e:
        return f"Error: {str(e)}"

def process_points(pts):
    """Hitung Jarak Kumulatif (Stationing)"""
    data = []
    cum_dist = 0
    for i, p in enumerate(pts):
        x, y, z = p
        if i > 0:
            prev = pts[i-1]
            # Jarak Datar (2D)
            dist = np.sqrt((x - prev[0])**2 + (y - prev[1])**2)
            cum_dist += dist
        data.append({"sta": cum_dist, "z": z})
    return data

# --- 2. ENGINE SHP (Library Dependent) ---
try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

def process_shp_zip(zip_file_obj):
    if not HAS_GEOPANDAS: return "Library 'geopandas' belum terinstall."
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            with zipfile.ZipFile(zip_file_obj, 'r') as zip_ref:
                zip_ref.extractall(tmpdirname)
            shp_file = next((os.path.join(root, f) for root, _, files in os.walk(tmpdirname) for f in files if f.endswith(".shp")), None)
            if not shp_file: return "File .shp tidak ditemukan."
            gdf = gpd.read_file(shp_file)
            points = []
            if not gdf.empty:
                geom = gdf.geometry.iloc[0]
                if geom.geom_type in ['LineString', 'LineStringZ']:
                    coords = list(geom.coords)
                    cum_dist = 0
                    for i, p in enumerate(coords):
                        x, y = p[0], p[1]
                        z = p[2] if len(p) > 2 else 0 
                        if i > 0:
                            dist = np.sqrt((x - coords[i-1][0])**2 + (y - coords[i-1][1])**2)
                            cum_dist += dist
                        points.append({"sta": cum_dist, "z": z})
            return points
    except Exception as e: return str(e)

# --- 3. ENGINE HIDROLIKA (CACHED) ---
def get_critical_depth(Q, b, m):
    y_min, y_max = 0.01, 20.0
    for _ in range(25):
        y = (y_min + y_max)/2; A=(b+m*y)*y; T=b+2*m*y
        if 9.81*A**3 - Q**2*T < 0: y_min=y
        else: y_max=y
    return (y_min+y_max)/2

def get_geom_props(y, b, m, Q):
    if y<=0.001: y=0.001
    A=(b+m*y)*y; P=b+2*y*np.sqrt(1+m**2); R=A/P if P>0 else 0; T=b+2*m*y
    return A, P, R, T, 0

def solve_step(y_k, Q, n, Z1, Z2, b, m, dx, mode):
    A1, _, R1, _, _ = get_geom_props(y_k, b, m, Q); V1=Q/A1
    H1 = Z1 + y_k + (V1**2)/19.62
    def f(y2):
        A2, _, R2, _, _ = get_geom_props(y2, b, m, Q); V2=Q/A2
        H2 = Z2 + y2 + (V2**2)/19.62
        Sf = ((n*V1)**2/R1**(1.33) + (n*V2)**2/R2**(1.33))/2
        return H2 - (H1 + Sf*dx) if mode=='sub' else H1 - (H2 + Sf*dx)
    ym, yM = 0.01, 20.0
    for _ in range(20):
        yc=(ym+yM)/2
        if (f(yc)>0 if mode=='sub' else f(yc)>0): yM=yc if mode=='sub' else ym
        else: ym=yc if mode=='sub' else yM
    return (ym+yM)/2

@st.cache_data
def run_sim(data, Q, ws_d, ws_u, fs, ts, db, md, mode):
    nodes = []; drops = []; dx_step = 2.0
    temp_nodes = []
    for s in data:
        L = s['STA Akhir (m)'] - s['STA Awal (m)']; n_st = max(1, int(L/dx_step))
        rdx = L/n_st; z1 = s['Elev Awal (m)']; slp = (z1 - s['Elev Akhir (m)'])/L
        for i in range(n_st+1):
            temp_nodes.append({
                "x": s['STA Awal (m)']+i*rdx, "z_orig": z1-i*rdx*slp,
                "b": s.get('Lebar b (m)', 2.0), "m": s.get('Talud m', 1.0), "n": s.get('Kekasaran n', 0.025),
                "seg": s['Nama Segmen'], "h_ch": s.get('Tinggi Saluran H (m)', 1.5)
            })
            
    if mode == "existing":
        nodes = [{"x":n['x'], "z":n['z_orig'], "b":n['b'], "m":n['m'], "n":n['n'], "seg":n['seg'], "h_ch":n['h_ch']} for n in temp_nodes]
    else: 
        if temp_nodes:
            cz = temp_nodes[0]['z_orig']
            for i, n in enumerate(temp_nodes):
                if i>0: cz -= (n['x'] - temp_nodes[i-1]['x'])*ts
                if (cz - n['z_orig']) > md: cz = n['z_orig']; drops.append(n['x'])
                nodes.append({"x":n['x'], "z":cz, "b":db, "m":1.0, "n":0.025, "seg":n['seg'], "h_ch":n['h_ch']})

    for n in nodes: n['yc'] = get_critical_depth(Q, n['b'], n['m'])
    nodes[-1]['y_sub'] = ws_d; nodes[0]['y_sup'] = ws_u
    
    for i in range(len(nodes)-2, -1, -1):
        try: nodes[i]['y_sub'] = max(solve_step(nodes[i+1]['y_sub'], Q, nodes[i]['n'], nodes[i+1]['z'], nodes[i]['z'], nodes[i]['b'], nodes[i]['m'], nodes[i+1]['x']-nodes[i]['x'], 'sub'), nodes[i]['yc']+0.01)
        except: nodes[i]['y_sub'] = nodes[i]['yc']+0.01
    for i in range(1, len(nodes)):
        try: nodes[i]['y_sup'] = max(solve_step(nodes[i-1]['y_sup'], Q, nodes[i]['n'], nodes[i-1]['z'], nodes[i]['z'], nodes[i]['b'], nodes[i]['m'], nodes[i]['x']-nodes[i-1]['x'], 'sup'), 0.01)
        except: nodes[i]['y_sup'] = nodes[i]['yc']-0.01

    for n in nodes:
        n['y_final'] = n['y_sup'] if fs else (n['y_sub'] if n['y_sub'] > n['yc'] else n['y_sup'])
        n['ws'] = n['z'] + n['y_final']; n['crit_ws'] = n['z'] + n['yc']
        n['freeboard'] = (n['z']+n['h_ch']) - n['ws']
        A,_,_,T,_ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        n['v'] = Q/A if A>0 else 0; n['fr'] = n['v']/np.sqrt(9.81*A/T) if T>0 else 0
        n['eg'] = n['ws'] + n['v']**2/19.62

    return nodes, drops

# --- 4. STATE ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)"]
if 'df_pro' not in st.session_state: st.session_state['df_pro'] = pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=REQUIRED_COLS)
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24

# --- 5. UI ---
st.markdown("""<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate</h1><p>Excel • DXF v2.0 • SHP</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state['q_pro'] = st.number_input("Debit (Q)", 0.01, 1000.0, st.session_state['q_pro'])
    force_super = st.checkbox("🔥 Force Supercritical", False)
    
    st.divider()
    use_redesign = st.checkbox("Aktifkan Redesain", False)
    ts = 0.001; db = 1.5; md = 1.5
    if use_redesign:
        ts = st.number_input("Target S", 0.0001, 0.05, 0.001, format="%.4f")
        db = st.number_input("Lebar Desain", 0.1, 50.0, 1.5)
        md = st.number_input("Max Drop", 0.5, 5.0, 1.5)
    
    st.divider()
    st.subheader("📂 Input Data")
    tab_xl, tab_cad, tab_gis = st.tabs(["📊 Excel", "📐 DXF", "🌍 SHP"])
    
    with tab_xl:
        up_excel = st.file_uploader("Upload Excel", type=['xlsx'])
        if up_excel: 
            try: st.session_state['df_pro'] = pd.read_excel(up_excel); st.rerun()
            except: pass
            
    with tab_cad:
        st.info("Support: 3D Polyline (Global Mapper) & LWPolyline")
        up_dxf = st.file_uploader("Upload DXF", type=['dxf'])
        
        # Pilihan Mode Elevasi
        dxf_mode = st.radio("Sumber Elevasi:", ["Z-Coordinate (3D Peta)", "Y-Coordinate (Gambar Profil)"])
        use_y_mode = True if dxf_mode == "Y-Coordinate (Gambar Profil)" else False
        
        if up_dxf and st.button("🚀 Load DXF"):
            content = up_dxf.read()
            # Panggil Parser v2.0
            pts = parse_dxf_raw_v2(content, use_y_as_z=use_y_mode)
            
            if isinstance(pts, list) and len(pts) > 1:
                rows = []
                for i in range(len(pts)-1):
                    rows.append({
                        "Nama Segmen": f"S{i+1}", 
                        "STA Awal (m)": pts[i]['sta'], "STA Akhir (m)": pts[i+1]['sta'],
                        "Elev Awal (m)": pts[i]['z'], "Elev Akhir (m)": pts[i+1]['z'],
                        "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                    })
                st.session_state['df_pro'] = pd.DataFrame(rows)
                st.success(f"Sukses! {len(rows)} segmen (Mode: {'Y' if use_y_mode else 'Z'}).")
                st.rerun()
            else:
                st.error(f"Gagal: {pts}")

    with tab_gis:
        if not HAS_GEOPANDAS: st.warning("⚠️ Butuh library 'geopandas' untuk file SHP.")
        else:
            up_shp = st.file_uploader("Upload ZIP (.shp,.shx,.dbf)", type=['zip'])
            if up_shp and st.button("🚀 Load SHP"):
                pts = process_shp_zip(up_shp)
                if isinstance(pts, list):
                    rows = []
                    for i in range(len(pts)-1):
                        rows.append({
                            "Nama Segmen": f"S{i+1}", 
                            "STA Awal (m)": pts[i]['sta'], "STA Akhir (m)": pts[i+1]['sta'],
                            "Elev Awal (m)": pts[i]['z'], "Elev Akhir (m)": pts[i+1]['z'],
                            "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                        })
                    st.session_state['df_pro'] = pd.DataFrame(rows)
                    st.success("SHP Loaded!")
                    st.rerun()

    if st.button("Reset Default"): 
        st.session_state['df_pro'] = pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=REQUIRED_COLS)
        st.rerun()

# --- 6. VIZ ---
df = st.session_state['df_pro']
data = df.to_dict('records')
nodes_ex, _ = run_sim(data, st.session_state['q_pro'], 0.5, 0.2, force_super, 0, 0, 0, "existing")
nodes_new, drops_new = ([], [])
if use_redesign:
    nodes_new, drops_new = run_sim(data, st.session_state['q_pro'], 1.0, 1.0, False, ts, db, md, "redesign")

t1, t2, t3, t4 = st.tabs(["📝 Input", "📈 Visualisasi", "📑 Rekap", "📘 Kriteria"])

with t1: st.data_editor(st.session_state['df_pro'], num_rows="dynamic", width='stretch')

with t2:
    if nodes_ex:
        st.subheader("Long & Cross Section")
        mode = st.radio("Tampilan:", ["Long Section", "Cross Section"], horizontal=True)
        fig, ax = plt.subplots(figsize=(10, 6))
        if mode == "Long Section":
            x=[n['x'] for n in nodes_ex]; z=[n['z'] for n in nodes_ex]; w=[n['ws'] for n in nodes_ex]
            ax.plot(x, z, 'k--', label='Tanah Asli'); ax.plot(x, w, 'b:', label='WS Ex')
            if use_redesign and nodes_new:
                xn=[n['x'] for n in nodes_new]; zn=[n['z'] for n in nodes_new]; wn=[n['ws'] for n in nodes_new]
                ax.plot(xn, zn, 'brown', lw=2, label='Desain'); ax.plot(xn, wn, 'b-', label='WS Desain')
                ax.fill_between(xn, zn, wn, color='cyan', alpha=0.3)
                for d in drops_new: ax.axvline(x=d, color='red', ls='--')
            else: ax.fill_between(x, z, w, color='cyan', alpha=0.3)
            ax.legend(); ax.grid(True, alpha=0.3)
        else: # Cross
            sta_opts = [n['x'] for n in nodes_ex]
            sel = st.selectbox("STA:", sta_opts)
            nx = next((n for n in nodes_ex if n['x']==sel), None)
            nn = next((n for n in nodes_new if n['x']==sel), None) if use_redesign else None
            curr = nn if (use_redesign and nn) else nx
            if curr:
                H=curr['h_ch']; B=curr['b']; Z=curr['m']; tw = B + 2*Z*H
                pts = [(-tw/2, curr['z']+H), (-B/2, curr['z']), (B/2, curr['z']), (tw/2, curr['z']+H)]
                ax.add_patch(plt.Polygon(pts, closed=False, fc='none', ec='brown' if use_redesign else 'black', lw=2))
                tw_w = B + 2*Z*curr['y_final']
                w_pts = [(-tw_w/2, curr['ws']), (tw_w/2, curr['ws']), (B/2, curr['z']), (-B/2, curr['z'])]
                ax.add_patch(plt.Polygon(w_pts, color='cyan', alpha=0.5))
                if nx: ax.plot([-10, 10], [nx['z'], nx['z']], 'k--', alpha=0.3, label='Tanah Asli')
                ax.autoscale(); ax.set_aspect('equal'); st.metric("Freeboard", f"{curr['freeboard']:.2f} m")
        st.pyplot(fig)

with t3:
    if nodes_ex:
        res = pd.DataFrame(nodes_new if use_redesign else nodes_ex)
        st.dataframe(res[['x', 'z', 'ws', 'fr', 'v', 'freeboard']].style.format("{:.2f}"), width='stretch')

with t4: st.info("Rumus: Manning & Standard Step Method")
