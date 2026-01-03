import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS GIS", layout="wide", page_icon="🛰️")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #0f0c29, #302b63, #24243e); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .stAlert { padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE GIS (DEM FETCHING) ---
def get_elevation_profile(coords):
    """
    Mengambil data elevasi dari Open-Elevation API (Public DEM).
    Input: List of [Lat, Lon]
    Output: List of Dict {'sta': ..., 'z': ...}
    """
    # Format koordinat untuk API
    locations = [{"latitude": lat, "longitude": lon} for lat, lon in coords]
    
    try:
        # Panggil API (Gratis, Global Coverage SRTM)
        url = "https://api.open-elevation.com/api/v1/lookup"
        resp = requests.post(url, json={"locations": locations}, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()['results']
            
            # Hitung Jarak Kumulatif (Haversine)
            profile = []
            cum_dist = 0.0
            
            for i, p in enumerate(data):
                elev = p['elevation']
                
                if i > 0:
                    lat1, lon1 = coords[i-1]
                    lat2, lon2 = coords[i]
                    # Haversine Formula (Jarak antar koordinat bumi)
                    R = 6371000 # Radius bumi (meter)
                    phi1, phi2 = np.radians(lat1), np.radians(lat2)
                    dphi = np.radians(lat2 - lat1)
                    dlam = np.radians(lon2 - lon1)
                    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
                    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
                    dist = R * c
                    cum_dist += dist
                
                profile.append({"sta": cum_dist, "z": elev})
            return profile
        else:
            return None
    except Exception as e:
        st.error(f"Gagal koneksi ke Satelit DEM: {e}")
        return None

# --- 2. ENGINE HIDROLIKA (ROBUST) ---
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
    nodes = []; drops = []; dx_step = 5.0 # Step lebih besar untuk data DEM
    temp_nodes = []
    
    sorted_data = sorted(data, key=lambda x: x['STA Awal (m)'])
    
    for s in sorted_data:
        L = s['STA Akhir (m)'] - s['STA Awal (m)']
        if L <= 0.01: continue # FIX: Skip Zero Length (Masalah Kakak yang tadi)
        
        n_st = max(1, int(L/dx_step))
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

    if not nodes: return [], []

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
        n['ws'] = n['z'] + n['y_final']
        n['freeboard'] = (n['z']+n['h_ch']) - n['ws']
        A,_,_,T,_ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        n['v'] = Q/A if A>0 else 0; n['fr'] = n['v']/np.sqrt(9.81*A/T) if T>0 else 0

    return nodes, drops

# --- 3. STATE ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)"]
if 'df_pro' not in st.session_state: st.session_state['df_pro'] = pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=REQUIRED_COLS)
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24

# --- 4. UI ---
st.markdown("""<div class="header-box"><h1>🛰️ Smart HEC-RAS Satellite</h1><p>Draw on Map & Get Elevation Instantly</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Hydraulic Params")
    st.session_state['q_pro'] = st.number_input("Debit (Q)", 0.01, 1000.0, st.session_state['q_pro'])
    
    st.divider()
    use_redesign = st.checkbox("Aktifkan Redesain", False)
    ts = 0.001; db = 1.5; md = 1.5
    if use_redesign:
        ts = st.number_input("Target Slope", 0.0001, 0.05, 0.001, format="%.4f")
        db = st.number_input("Design Width", 0.1, 50.0, 1.5)
        md = st.number_input("Max Drop", 0.5, 5.0, 1.5)
    
    st.divider()
    if st.button("Reset All Data"):
        st.session_state['df_pro'] = pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=REQUIRED_COLS)
        st.rerun()

# --- 5. TABS ---
t_map, t_res, t_tab = st.tabs(["🗺️ Draw Map (GIS)", "📈 Hydraulic Profile", "📝 Data Table"])

with t_map:
    st.info("👆 Gunakan tool **Polyline** (ikon segilima) di kiri peta untuk menggambar jalur sungai/saluran.")
    
    # 1. Render Map
    m = folium.Map(location=[-6.200000, 106.816666], zoom_start=13) # Default Jakarta
    draw = Draw(
        draw_options={"polyline": True, "polygon": False, "circle": False, "marker": False, "circlemarker": False, "rectangle": False},
        edit_options={"edit": False}
    )
    draw.add_to(m)
    
    output = st_folium(m, width=1200, height=500)
    
    # 2. Process Drawing
    if output.get("all_drawings"):
        drawings = output["all_drawings"]
        if drawings:
            # Ambil gambar terakhir
            last_draw = drawings[-1]
            coords = last_draw['geometry']['coordinates'] # [[lon, lat], ...]
            # Swap to [lat, lon] for API
            path_coords = [[p[1], p[0]] for p in coords]
            
            if st.button("🚀 Ambil Data Elevasi & Hitung"):
                with st.spinner("Menghubungi Satelit DEM..."):
                    profile = get_elevation_profile(path_coords)
                    
                    if profile:
                        # Convert to DataFrame Format
                        rows = []
                        for i in range(len(profile)-1):
                            rows.append({
                                "Nama Segmen": f"S{i+1}", 
                                "STA Awal (m)": profile[i]['sta'], "STA Akhir (m)": profile[i+1]['sta'],
                                "Elev Awal (m)": profile[i]['z'], "Elev Akhir (m)": profile[i+1]['z'],
                                "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                            })
                        
                        st.session_state['df_pro'] = pd.DataFrame(rows)
                        st.success(f"Berhasil mengambil {len(rows)} titik elevasi dari Peta!")
                        st.rerun() # Refresh to show results

# EXECUTION
df = st.session_state['df_pro']
data = df.to_dict('records')
nodes_ex, _ = run_sim(data, st.session_state['q_pro'], 0.5, 0.2, False, 0, 0, 0, "existing")
nodes_new, drops_new = ([], [])
if use_redesign:
    nodes_new, drops_new = run_sim(data, st.session_state['q_pro'], 1.0, 1.0, False, ts, db, md, "redesign")

with t_res:
    if nodes_ex:
        st.subheader("Profil Hidrolis")
        fig, ax = plt.subplots(figsize=(12, 6))
        x=[n['x'] for n in nodes_ex]; z=[n['z'] for n in nodes_ex]; w=[n['ws'] for n in nodes_ex]
        
        ax.plot(x, z, 'k-', lw=1.5, label='Tanah Asli (DEM)')
        ax.plot(x, w, 'b:', label='Muka Air Eksisting')
        ax.fill_between(x, z, w, color='cyan', alpha=0.3)
        
        if use_redesign and nodes_new:
            xn=[n['x'] for n in nodes_new]; zn=[n['z'] for n in nodes_new]; wn=[n['ws'] for n in nodes_new]
            ax.plot(xn, zn, 'brown', lw=2, label='Desain Baru')
            ax.plot(xn, wn, 'g-', label='Muka Air Desain')
            # Drops
            for d in drops_new: ax.axvline(x=d, color='red', ls='--', alpha=0.5)
            
        ax.legend(); ax.grid(True, alpha=0.3); ax.set_xlabel("Jarak (m)"); ax.set_ylabel("Elevasi (m)")
        st.pyplot(fig)
    else:
        st.info("Silakan gambar jalur di Tab 'Draw Map' dulu.")

with t_tab:
    st.data_editor(df, num_rows="dynamic", width='stretch')
