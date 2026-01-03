import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tempfile
import os
import zipfile
import io

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS GIS", layout="wide", page_icon="🌍")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #002B5B, #2B4865); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab-list"] button { border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 1. GIS ENGINE (DXF & SHP) ---
def calculate_stationing(points):
    """Menghitung Jarak Kumulatif (STA) dari koordinat X,Y"""
    data = []
    cum_dist = 0.0
    for i, p in enumerate(points):
        x, y, z = p
        if i > 0:
            prev = points[i-1]
            dist = np.sqrt((x - prev[0])**2 + (y - prev[1])**2)
            cum_dist += dist
        data.append({"sta": cum_dist, "z": z})
    return data

def parse_dxf(file_obj):
    try:
        import ezdxf
    except ImportError:
        return None, "Library 'ezdxf' belum terinstall. Mohon install dulu."

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(file_obj.getvalue())
            tmp_path = tmp.name
        
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        points = []
        
        # Cari Polyline (LWPOLYLINE / POLYLINE)
        for e in msp:
            if e.dxftype() == 'LWPOLYLINE':
                # LWPolyline biasanya 2D, Z diambil dari elevation
                z_default = e.dxf.elevation
                points = [(p[0], p[1], z_default) for p in e.get_points()]
                break # Ambil line pertama yg ketemu
            elif e.dxftype() == 'POLYLINE':
                # Polyline 3D (Vertex punya Z sendiri)
                points = [(v.dxf.location.x, v.dxf.location.y, v.dxf.location.z) for v in e.vertices]
                break
        
        os.remove(tmp_path)
        
        if not points: return None, "Tidak ditemukan garis (Polyline) dalam DXF."
        return calculate_stationing(points), None
        
    except Exception as e:
        return None, str(e)

def parse_shp_zip(file_obj):
    try:
        import geopandas as gpd
    except ImportError:
        return None, "Library 'geopandas' belum terinstall."

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(file_obj, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            
            # Cari file .shp
            shp_path = next((os.path.join(root, f) for root, _, files in os.walk(tmpdir) for f in files if f.endswith(".shp")), None)
            if not shp_path: return None, "Tidak ada file .shp dalam ZIP."
            
            gdf = gpd.read_file(shp_path)
            if gdf.empty: return None, "File SHP kosong."
            
            # Ambil geometri pertama (LineString)
            geom = gdf.geometry.iloc[0]
            if geom.geom_type not in ['LineString', 'LineStringZ']:
                return None, "SHP harus berupa Garis (LineString)."
                
            coords = list(geom.coords)
            # Handle 2D vs 3D tuples
            points = [(p[0], p[1], p[2] if len(p)>2 else 0) for p in coords]
            
            return calculate_stationing(points), None
            
    except Exception as e:
        return None, str(e)

# --- 2. HYDRAULIC CORE (CACHED) ---
@st.cache_data
def run_simulation(data_dicts, Q, ws_down, ws_up, force_super):
    # Simplified Standard Step Logic for Speed
    nodes = []
    # 1. Build Nodes
    for s in data_dicts:
        L = s['STA Akhir (m)'] - s['STA Awal (m)']; n_steps = max(1, int(L/2.0))
        dx = L/n_steps; z1 = s['Elev Awal (m)']; slope = (z1 - s['Elev Akhir (m)'])/L
        for i in range(n_steps+1):
            nodes.append({
                "x": s['STA Awal (m)'] + i*dx, "z": z1 - i*dx*slope,
                "b": s['Lebar b (m)'], "m": s['Talud m'], "n": s['Kekasaran n'], "seg": s['Nama Segmen'], "h_ch": s['Tinggi Saluran H (m)']
            })
    
    # 2. Calc (Simple Backward Step)
    g = 9.81
    for n in nodes: 
        # Critical Depth Approx
        n['yc'] = ((Q**2)/(g*n['b']**2))**(1/3) # Rect approx for speed
    
    nodes[-1]['y'] = ws_down
    nodes[-1]['ws'] = nodes[-1]['z'] + ws_down
    
    for i in range(len(nodes)-2, -1, -1):
        # Standard Step (Simplified Energy Balance)
        n1 = nodes[i]; n2 = nodes[i+1]
        A2 = (n2['b'] + n2['m']*n2['y'])*n2['y']; R2 = A2/(n2['b'] + 2*n2['y']*np.sqrt(1+n2['m']**2))
        V2 = Q/A2; Sf2 = (n2['n']*V2)**2 / R2**(4/3)
        
        # Iteration for y1
        y1 = n2['y'] # Initial guess
        for _ in range(5):
            A1 = (n1['b'] + n1['m']*y1)*y1; R1 = A1/(n1['b'] + 2*y1*np.sqrt(1+n1['m']**2))
            V1 = Q/A1; Sf1 = (n1['n']*V1)**2 / R1**(4/3)
            H2 = n2['z'] + n2['y'] + V2**2/(2*g)
            H1_calc = n1['z'] + y1 + V1**2/(2*g)
            h_loss = ((Sf1+Sf2)/2) * (n2['x'] - n1['x'])
            err = H2 + h_loss - H1_calc
            y1 += err * 0.5 # Relaxation
            if y1 < 0.01: y1 = 0.01
            
        n1['y'] = max(y1, n1['yc'] if not force_super else 0)
        n1['ws'] = n1['z'] + n1['y']
    
    # Finalize properties
    for n in nodes:
        A = (n['b'] + n['m']*n['y'])*n['y']
        n['v'] = Q/A if A>0 else 0
        n['fr'] = n['v']/np.sqrt(g*(A/n['b'])) if A>0 else 0 # Approx
        n['freeboard'] = (n['z'] + n['h_ch']) - n['ws']
        
    return nodes

# --- 3. STATE & UI ---
COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)"]
if 'df_pro' not in st.session_state: st.session_state['df_pro'] = pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=COLS)
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24

st.markdown("""<div class="header-box"><h1>🌍 Smart HEC-RAS GIS</h1><p>Integrasi Peta Digital (DXF/SHP) ke Model Hidrolika</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state['q_pro'] = st.number_input("Debit (Q)", 0.01, 1000.0, st.session_state['q_pro'])
    force_super = st.checkbox("Force Supercritical", False)
    
    st.divider()
    st.subheader("📂 Import Data")
    tabs_imp = st.tabs(["📊 Excel", "📐 DXF", "🗺️ SHP"])
    
    with tabs_imp[0]:
        f = st.file_uploader("Upload Excel", type=['xlsx'])
        if f: 
            try: st.session_state['df_pro'] = pd.read_excel(f); st.rerun()
            except: pass
            
    with tabs_imp[1]:
        f = st.file_uploader("Upload DXF", type=['dxf'])
        if f and st.button("Load DXF"):
            data, err = parse_dxf(f)
            if err: st.error(err)
            else:
                # Convert Points to Segments
                rows = []
                for i in range(len(data)-1):
                    rows.append({
                        "Nama Segmen": f"S{i+1}", 
                        "STA Awal (m)": data[i]['sta'], "STA Akhir (m)": data[i+1]['sta'],
                        "Elev Awal (m)": data[i]['z'], "Elev Akhir (m)": data[i+1]['z'],
                        "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                    })
                st.session_state['df_pro'] = pd.DataFrame(rows)
                st.success(f"Sukses import {len(rows)} segmen!")
                st.rerun()

    with tabs_imp[2]:
        st.info("Upload file ZIP (berisi .shp, .shx, .dbf)")
        f = st.file_uploader("Upload ZIP", type=['zip'])
        if f and st.button("Load SHP"):
            data, err = parse_shp_zip(f)
            if err: st.error(err)
            else:
                rows = []
                for i in range(len(data)-1):
                    rows.append({
                        "Nama Segmen": f"S{i+1}", 
                        "STA Awal (m)": data[i]['sta'], "STA Akhir (m)": data[i+1]['sta'],
                        "Elev Awal (m)": data[i]['z'], "Elev Akhir (m)": data[i+1]['z'],
                        "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                    })
                st.session_state['df_pro'] = pd.DataFrame(rows)
                st.success(f"Sukses import {len(rows)} segmen!")
                st.rerun()
                
    if st.button("Reset"): 
        st.session_state['df_pro'] = pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=COLS)
        st.rerun()

# --- MAIN ---
df = st.session_state['df_pro']
nodes = run_simulation(df.to_dict('records'), st.session_state['q_pro'], 0.5, 0.2, force_super)

t1, t2, t3 = st.tabs(["📝 Input Data", "📈 Profil & Cross", "📑 Laporan"])

with t1:
    st.data_editor(df, num_rows="dynamic", width='stretch')

with t2:
    if nodes:
        st.subheader("Visualisasi")
        c1, c2 = st.columns([1,3])
        with c1:
            mode = st.radio("Tipe:", ["Long Section", "Cross Section"])
            if mode == "Cross Section":
                sel = st.selectbox("STA:", [n['x'] for n in nodes])
        
        with c2:
            fig, ax = plt.subplots(figsize=(10, 6))
            if mode == "Long Section":
                x=[n['x'] for n in nodes]; z=[n['z'] for n in nodes]; ws=[n['ws'] for n in nodes]
                ax.plot(x, z, 'k-', label='Tanah')
                ax.plot(x, ws, 'b-', label='Air')
                ax.fill_between(x, z, ws, color='cyan', alpha=0.3)
                ax.set_xlabel("Station (m)"); ax.set_ylabel("Elevasi (m)")
            else:
                n = next((i for i in nodes if i['x']==sel), None)
                if n:
                    H=n['h_ch']; B=n['b']; Z=n['m']
                    top = B + 2*Z*H
                    pts = [(-top/2, n['z']+H), (-B/2, n['z']), (B/2, n['z']), (top/2, n['z']+H)]
                    ax.add_patch(plt.Polygon(pts, fc='none', ec='black', lw=2))
                    
                    wt = B + 2*Z*n['y']
                    wpts = [(-wt/2, n['ws']), (wt/2, n['ws']), (B/2, n['z']), (-B/2, n['z'])]
                    ax.add_patch(plt.Polygon(wpts, color='cyan', alpha=0.5))
                    ax.autoscale(); ax.set_aspect('equal')
                    st.metric("Freeboard", f"{n['freeboard']:.2f} m")
            
            st.pyplot(fig)

with t3:
    if nodes:
        st.dataframe(pd.DataFrame(nodes)[['x', 'z', 'ws', 'v', 'fr', 'freeboard']].style.format("{:.3f}"), width='stretch')
