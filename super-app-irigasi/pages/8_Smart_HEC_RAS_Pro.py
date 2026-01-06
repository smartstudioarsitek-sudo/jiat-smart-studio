import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate v2", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .header-box { padding: 25px; background: linear-gradient(135deg, #1e3c72, #2a5298); color: white; border-radius: 12px; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 20px; }
    .stTabs [data-baseweb="tab--active"] { background-color: #1e3c72 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE KRITERIA KP-03 ---
MATERIAL_PROPS = {
    "Tanah (Earth)": {"n": 0.025, "v_max": 0.70},
    "Pasangan Batu (Masonry)": {"n": 0.0225, "v_max": 2.00},
    "Beton (Concrete)": {"n": 0.015, "v_max": 3.00}
}

def get_kp03_freeboard(Q):
    """Menentukan tinggi jagaan (W) berdasarkan Debit sesuai KP-03."""
    if Q < 0.5: return 0.40
    elif Q < 1.5: return 0.50
    elif Q < 5.0: return 0.60
    elif Q < 10.0: return 0.75
    else: return 1.00

# --- ENGINE HIDROLIKA CORE (HIGH ACCURACY) ---

def get_geom_props(y, b, m, Q):
    """Menghitung properti geometris basah (Trapesium)."""
    # Safety untuk kedalaman sangat kecil agar tidak error pembagian
    if y <= 0.0001: y = 0.0001
    
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    
    # Momentum function for hydraulic jump
    g = 9.81
    hydrostatic = ((y**2)/2)*b + ((y**3)/3)*m
    # Safety check untuk A agar tidak bagi nol
    M = (Q**2)/(g*A) + hydrostatic if A > 1e-6 else 0
    
    return A, P, R, T, M

def get_critical_depth(Q, b, m):
    """Menghitung kedalaman kritis (yc) dengan Iterasi Presisi Tinggi."""
    y_min, y_max = 0.001, 20.0
    g = 9.81
    
    # Meningkatkan jumlah iterasi dari 40 ke 100 untuk akurasi
    for _ in range(100):
        y = (y_min + y_max) / 2
        A = (b + m * y) * y
        T = b + 2 * m * y
        
        # Froude Number function: gA^3 - Q^2T = 0
        f_val = g * (A**3) - (Q**2) * T
        
        # Toleransi error diperkecil (1e-5)
        if abs(f_val) < 1e-5: return y
        
        if f_val < 0: y_min = y
        else: y_max = y
        
        # Cek konvergensi delta Y
        if abs(y_max - y_min) < 1e-6: return y

    return y

def solve_energy_step(y_known, Q, n, Z1, Z2, b, m, dx, mode='sub'):
    """Standard Step Method dengan akurasi tinggi (Newton/Bisection Hybrid logic)."""
    g = 9.81
    A1, _, R1, _, _ = get_geom_props(y_known, b, m, Q)
    V1 = Q/A1 if A1 > 1e-6 else 0
    H1 = Z1 + y_known + (V1**2)/(2*g)
    
    def func(y2):
        A2, _, R2, _, _ = get_geom_props(y2, b, m, Q)
        V2 = Q/A2 if A2 > 1e-6 else 0
        H2 = Z2 + y2 + (V2**2)/(2*g)
        
        # Manning Formula
        Sf1 = (n*V1)**2 / (R1**(4/3)) if R1 > 0 else 0
        Sf2 = (n*V2)**2 / (R2**(4/3)) if R2 > 0 else 0
        Sf_avg = (Sf1 + Sf2)/2
        
        # Energy Balance Error
        if mode == 'sub':
            # Subcritical: Diketahui Hilir (1), Cari Hulu (2)
            # H2 (Hulu) = H1 (Hilir) + hf
            return H2 - (H1 + (Sf_avg * dx))
        else:
            return H1 - (H2 + (Sf_avg * dx))

    # Range pencarian solusi diperluas dan safety check
    y_l, y_h = 0.001, 50.0 
    
    # Iterasi diperbanyak sampai 100x untuk konvergensi sulit
    for _ in range(100):
        ym = (y_l + y_h)/2
        err = func(ym)
        
        # Toleransi error energi sangat ketat (1e-5 meter)
        if abs(err) < 1e-5: return ym
        
        if mode == 'sub':
            if err > 0: y_h = ym # Energi tebakan terlalu tinggi, kurangi Y
            else: y_l = ym
        else:
            if err > 0: y_l = ym
            else: y_h = ym
            
        # Break jika interval sudah sangat sempit
        if abs(y_h - y_l) < 1e-6: return (y_l + y_h)/2
            
    return (y_l + y_h)/2

def check_compliance_kp03(node, v_max_limit):
    """Validasi terhadap standar teknis."""
    msgs = []
    status = "AMAN"
    
    # 1. Cek Kecepatan Minimum (Sedimentasi)
    if node['v'] < 0.6:
        msgs.append("WARNING: Kecepatan < 0.6 m/s (Potensi Endapan)")
        status = "WARNING"
    # 2. Cek Kecepatan Maksimum (Gerusan)
    if node['v'] > v_max_limit:
        msgs.append(f"BAHAYA: V > {v_max_limit} m/s (Resiko Gerusan)")
        status = "BAHAYA"
    # 3. Cek Freeboard
    required_f = get_kp03_freeboard(node['Q'])
    if node['freeboard'] < required_f:
        msgs.append(f"KRITIS: Freeboard < {required_f}m")
        status = "BAHAYA"
        
    node['compliance_status'] = status
    node['compliance_msg'] = "; ".join(msgs) if msgs else "OK: Sesuai KP-03"
    return node

def calculate_profiles(nodes, boundary_down, boundary_up, v_limit):
    """Hitung profil air lengkap."""
    # 1. Subcritical (Hilir ke Hulu)
    # Set boundary hilir
    nodes[-1]['y_sub'] = boundary_down
    
    # Loop mundur dari node terakhir ke node pertama
    for i in range(len(nodes)-2, -1, -1):
        dx = abs(nodes[i+1]['x'] - nodes[i]['x'])
        
        # Hitung Y hulu berdasarkan Y hilir yang sudah diketahui
        nodes[i]['y_sub'] = solve_energy_step(
            y_known=nodes[i+1]['y_sub'], 
            Q=nodes[i]['Q'], 
            n=nodes[i]['n'], 
            Z1=nodes[i+1]['z'], # Z Hilir (Known)
            Z2=nodes[i]['z'],   # Z Hulu (Target)
            b=nodes[i]['b'], 
            m=nodes[i]['m'], 
            dx=dx, 
            mode='sub'
        )

    # 2. Final & Compliance Calculation
    for n in nodes:
        n['yc'] = get_critical_depth(n['Q'], n['b'], n['m'])
        
        # Logic: Ambil nilai max antara Y Subkritis dan Y Kritis
        # Ini mencegah hasil perhitungan jatuh di bawah kedalaman kritis pada aliran subkritis
        n['y_final'] = max(n['y_sub'], n['yc']) 
        
        n['ws'] = n['z'] + n['y_final']
        n['bank_elev'] = n['z'] + n['h_ch']
        n['freeboard'] = n['bank_elev'] - n['ws']
        
        A, _, _, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], n['Q'])
        n['v'] = n['Q']/A if A > 0 else 0
        n['fr'] = n['v'] / np.sqrt(9.81 * (A/T)) if A/T > 1e-6 else 0
        
        check_compliance_kp03(n, v_limit)
        
    return nodes

# --- AUTOCAD EXPORT SCRIPT (IMPROVED) ---

def generate_cad_script(nodes, mode="LONG", scale_v=10.0, ds_name="DESAIN"):
    """Script AutoCAD dengan skala vertikal dan layer terpisah."""
    s = f"; SCR AutoCAD Generated for {ds_name}\nOSMODE 0\n"
    
    if mode == "LONG":
        # Layer Dasar Saluran
        s += f"-LAYER M {ds_name}_BED C 30  \n_PLINE\n"
        for n in nodes: s += f"{n['x']:.3f},{n['z']*scale_v:.3f}\n"
        s += "\n"
        # Layer Muka Air
        s += f"-LAYER M {ds_name}_WS C 150  \n_PLINE\n"
        for n in nodes: s += f"{n['x']:.3f},{n['ws']*scale_v:.3f}\n"
        s += "\n"
        # Layer Top Bank
        s += f"-LAYER M {ds_name}_TOP C 10  \n_PLINE\n"
        for n in nodes: s += f"{n['x']:.3f},{n['bank_elev']*scale_v:.3f}\n"
        s += "\n"
    else:
        # Cross Section logic
        col = 0; spacing = 25.0
        for n in nodes[::10]: # Print per 10m atau station tertentu
            bx = col * spacing; by = 0
            b, m, h, y = n['b'], n['m'], n['h_ch'], n['y_final']
            tw = (b + 2*m*h)/2
            s += f"-LAYER M {ds_name}_CS C 7  \n_PLINE\n"
            s += f"{bx-tw:.3f},{h:.3f}\n{bx-b/2:.3f},0\n{bx+b/2:.3f},0\n{bx+tw:.3f},{h:.3f}\n\n"
            col += 1
            
    s += "ZOOM E\n"
    return s

# --- UI APP ---

st.markdown('<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate v2</h1><p>Desain Saluran Irigasi Standar KP-03 & Ekspor AutoCAD</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📋 Parameter User")
    material = st.selectbox("Material Saluran", list(MATERIAL_PROPS.keys()))
    m_data = MATERIAL_PROPS[material]
    
    st.info(f"Karakteristik {material}:\n- Manning n: {m_data['n']}\n- V Max: {m_data['v_max']} m/s")
    
    st.divider()
    st.header("📐 Setting Gambar (AutoCAD)")
    v_scale = st.number_input("Skala Vertikal (Exaggeration)", 1.0, 100.0, 10.0)
    
    st.divider()
    # Boundary Conditions
    q_global = st.number_input("Debit Rencana (Q) m³/s", 0.01, 50.0, 0.50)
    h_hilir = st.number_input("Kedalaman Air Hilir (m)", 0.0, 5.0, 0.45)
    
    st.divider()
    # --- FITUR BARU: TOMBOL RUN ---
    st.markdown("### 🚀 Kontrol Simulasi")
    run_btn = st.button("JALANKAN SIMULASI", type="primary", use_container_width=True)

# --- DATA PROCESSING ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        ["Segmen 1", 0, 100, 105.0, 104.5, 0.8, 1.0, 1.2],
        ["Segmen 2", 100, 250, 104.5, 103.0, 0.8, 1.0, 1.2]
    ], columns=["Nama", "STA Awal", "STA Akhir", "Z Awal", "Z Akhir", "Lebar b", "Talud m", "Tinggi H"])

# Inisialisasi Session State untuk Hasil
if 'result_df' not in st.session_state:
    st.session_state.result_df = None
if 'result_nodes' not in st.session_state:
    st.session_state.result_nodes = None

tab1, tab2, tab3 = st.tabs(["📝 Input & Edit", "📊 Hasil Analisis Hidrolika", "💾 Ekspor Output"])

with tab1:
    st.subheader("Edit Geometri Saluran")
    st.info("💡 Tekan tombol 'JALANKAN SIMULASI' di menu kiri (Sidebar) setelah mengubah data.")
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
    # Update df in session state immediately on edit
    st.session_state.df = edited_df

# --- CALCULATION LOGIC (ONLY RUNS ON BUTTON CLICK) ---
if run_btn:
    all_nodes = []
    # 1. Generate Node dari DataFrame
    for _, row in st.session_state.df.iterrows():
        L = row['STA Akhir'] - row['STA Awal']
        # Perbaikan: Mencegah error jika panjang segmen < 5 meter
        steps = int(L/5) if L >= 5 else 1 
        dx = L/steps
        z_slope = (row['Z Awal'] - row['Z Akhir'])/L
        
        for i in range(steps + 1):
            curr_x = row['STA Awal'] + (i * dx)
            all_nodes.append({
                "x": curr_x,
                "z": row['Z Awal'] - (i * dx * z_slope),
                "b": row['Lebar b'], "m": row['Talud m'], "h_ch": row['Tinggi H'],
                "n": m_data['n'], "Q": q_global
            })

    # Urutkan berdasarkan STA
    all_nodes = sorted(all_nodes, key=lambda k: k['x'])

    # 2. Run Heavy Calculation
    if len(all_nodes) > 1:
        with st.spinner('Sedang menghitung profil muka air...'):
            try:
                res_nodes = calculate_profiles(all_nodes, h_hilir, 0, m_data['v_max'])
                res_df = pd.DataFrame(res_nodes)
                
                # Simpan Hasil ke Session State agar tidak hilang saat klik tab lain
                st.session_state.result_nodes = res_nodes
                st.session_state.result_df = res_df
                st.success("✅ Perhitungan Selesai!")
            except Exception as e:
                st.error(f"Terjadi kesalahan perhitungan: {e}")
    else:
        st.warning("Silakan masukkan data geometri yang valid (Panjang > 0).")

# --- DISPLAY RESULTS (FROM SESSION STATE) ---
with tab2:
    if st.session_state.result_df is not None:
        res_df = st.session_state.result_df
        
        col_l, col_r = st.columns([2, 1])
        
        with col_l:
            st.subheader("Profil Memanjang (Long Section)")
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(res_df['x'], res_df['z'], 'brown', lw=3, label='Dasar Saluran')
            ax.plot(res_df['x'], res_df['ws'], 'blue', lw=2, label='Muka Air')
            ax.plot(res_df['x'], res_df['bank_elev'], 'black', ls='--', label='Tanggul')
            ax.fill_between(res_df['x'], res_df['z'], res_df['ws'], color='skyblue', alpha=0.3)
            ax.set_ylabel("Elevasi (m)")
            ax.legend()
            st.pyplot(fig)
            
        with col_r:
            st.subheader("Status KP-03")
            status_counts = res_df['compliance_status'].value_counts()
            st.write(status_counts)
            if "BAHAYA" in status_counts:
                st.error("⚠️ Ada bagian saluran yang tidak aman!")
            else:
                st.success("✅ Seluruh segmen aman.")

        st.dataframe(res_df[['x', 'z', 'ws', 'v', 'fr', 'freeboard', 'compliance_status', 'compliance_msg']].style.highlight_max(axis=0), use_container_width=True)
    else:
        st.info("👋 Silakan klik tombol **'JALANKAN SIMULASI'** di menu kiri untuk melihat hasil.")

with tab3:
    if st.session_state.result_nodes is not None and st.session_state.result_df is not None:
        st.subheader("📥 Download Hasil Pekerjaan")
        c1, c2, c3 = st.columns(3)
        
        res_nodes = st.session_state.result_nodes
        res_df = st.session_state.result_df
        
        with c1:
            scr_long = generate_cad_script(res_nodes, "LONG", v_scale)
            st.download_button("📐 AutoCAD Long Section (.scr)", scr_long, "LongSection_Design.scr")
            st.caption("Gunakan perintah 'SCRIPT' di AutoCAD")
            
        with c2:
            scr_cross = generate_cad_script(res_nodes, "CROSS")
            st.download_button("📐 AutoCAD Cross Section (.scr)", scr_cross, "CrossSection_Design.scr")
            
        with c3:
            toweb_df = res_df[['x', 'z', 'ws', 'v', 'fr', 'freeboard', 'compliance_status']]
            st.download_button("📋 Laporan Excel (.csv)", toweb_df.to_csv(index=False), "Laporan_Teknis_Irigasi.csv")
    else:
         st.info("👋 Hasil belum tersedia. Klik **'JALANKAN SIMULASI'** terlebih dahulu.")

st.divider()
st.markdown("💡 **Tips:** Untuk akurasi 100%, pastikan input **STA Hilir** dan **Elevasi Hilir** sesuai dengan data ukur lapangan.")
