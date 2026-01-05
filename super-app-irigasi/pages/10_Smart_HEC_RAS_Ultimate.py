import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate V2", layout="wide", page_icon="🏗️")

# Custom CSS untuk UI yang lebih profesional
st.markdown("""
<style>
    .reportview-container .main .block-container { padding-top: 1rem; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .run-btn>button { background-color: #28a745 !important; color: white !important; border: none; }
    .save-btn>button { background-color: #007bff !important; color: white !important; }
    .header-box { padding: 15px; background: linear-gradient(90deg, #1e3c72, #2a5298); color: white; border-radius: 10px; text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 1. SESSION STATE MANAGEMENT ---
if 'results_ex' not in st.session_state: st.session_state['results_ex'] = None
if 'results_new' not in st.session_state: st.session_state['results_new'] = None

# --- 2. FUNGSI EXPORT AUTOCAD (STANDAR BBWS) ---
def generate_bbws_scr(nodes, dataset_name="DESAIN", distorsi_v=10):
    """
    Menghasilkan script AutoCAD dengan skala distorsi 1:10 (V:H)
    Sesuai standar Gambar BBWS: Layer TANAH, AIR, STRUKTUR, TEKS.
    """
    s = f"; --- SCRIPT BBWS STANDAR ({dataset_name}) ---\n"
    s += "OSMODE 0\n"
    
    # Fungsi pembantu untuk koordinat terdistorsi
    def fmt(x, y): return f"{x:.4f},{y * distorsi_v:.4f}"

    # 1. LAYER TANAH (Eksisting)
    s += f"-LAYER M TANAH C 34 TANAH \n_PLINE\n"
    for n in nodes: s += f"{fmt(n['x'], n['z'])}\n"
    s += "\n"

    # 2. LAYER AIR (Water Surface)
    s += f"-LAYER M AIR C 150 AIR \n_PLINE\n"
    for n in nodes: s += f"{fmt(n['x'], n['ws'])}\n"
    s += "\n"

    # 3. LAYER STRUKTUR (Bank/Tanggul)
    s += f"-LAYER M STRUKTUR C 7 STRUKTUR \n_PLINE\n"
    for n in nodes: s += f"{fmt(n['x'], n['z'] + n['h_ch'])}\n"
    s += "\n"

    # 4. LAYER TEKS (Label STA)
    s += f"-LAYER M TEKS C 2 TEKS \n"
    for i, n in enumerate(nodes):
        if i % 10 == 0: # Label setiap 10 nodes agar tidak menumpuk
            s += f"-TEXT {fmt(n['x'], n['z'] - 2)} 0.5 90 STA {n['x']:.0f}\n"

    s += "ZOOM E\n"
    return s

# --- 3. UI TOOLBAR (OPEN, SAVE, RUN) ---
st.markdown('<div class="header-box"><h1>🏗️ Smart HEC-RAS: Standar BBWS</h1></div>', unsafe_allow_html=True)

col_tool1, col_tool2, col_tool3, col_tool4 = st.columns([2, 2, 2, 3])

with col_tool1:
    # FITUR OPEN PROJECT (JSON)
    uploaded_project = st.file_uploader("📂 Open Project", type=['json'])
    if uploaded_project:
        project_data = json.load(uploaded_project)
        st.session_state['df_pro'] = pd.DataFrame(project_data)
        st.success("Project Loaded!")

with col_tool2:
    # FITUR SAVE PROJECT (JSON)
    if 'df_pro' in st.session_state:
        project_json = st.session_state['df_pro'].to_json(orient='records')
        st.download_button("💾 Save Project", project_json, "Project_SDA.json", "application/json", key="save_btn")

with col_tool3:
    # TOMBOL RUN (Mencegah Lag)
    run_calc = st.button("🚀 RUN ANALYSIS", type="primary", use_container_width=True)

with col_tool4:
    st.info("💡 Skala Distorsi Vertikal Otomatis 1:10 diterapkan pada Export CAD.")

# --- 4. LOGIKA PERHITUNGAN (HANYA JALAN JIKA RUN DIKLIK) ---
if run_calc:
    with st.spinner("Menghitung Profil Hidrolika..."):
        # (Logika calculate_profiles Anda dimasukkan di sini)
        # Misal: st.session_state['results_ex'] = calculate_profiles(...)
        # Untuk demo ini, kita asumsikan fungsi calculate_profiles sudah ada seperti di kode lama Anda
        try:
            # Simulasi pemanggilan fungsi lama Anda
            # nodes_ex = calculate_profiles(nodes_raw, ...) 
            # st.session_state['results_ex'] = nodes_ex
            st.success("Analisis Selesai!")
        except Exception as e:
            st.error(f"Error saat Running: {e}")

# --- 5. VISUALISASI & EXPORT (TABEL & CAD) ---
tab_input, tab_viz, tab_export = st.tabs(["📝 Data Input", "📊 Grafik Profil", "📑 Export BBWS"])

with tab_input:
    # Editor data tetap responsif karena perhitungan dipisah ke tombol Run
    st.session_state['df_pro'] = st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with tab_export:
    st.subheader("📦 Download Script AutoCAD (Standar BBWS)")
    c1, c2 = st.columns(2)
    
    with c1:
        distorsi = st.slider("Faktor Distorsi Vertikal", 1, 20, 10, help="Standar BBWS adalah 10 (Artinya skala V=1:100 dan H=1:1000)")
        
    with c2:
        if st.session_state['results_ex']:
            scr_content = generate_bbws_scr(st.session_state['results_ex'], distorsi_v=distorsi)
            st.download_button(
                "📥 Download .SCR (Ready to Print)",
                scr_content,
                "LongSection_BBWS.scr",
                "text/plain"
            )
        else:
            st.warning("Silahkan klik 'RUN ANALYSIS' terlebih dahulu.")
