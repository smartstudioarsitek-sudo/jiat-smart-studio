import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Desain Hidrolika Saluran", layout="wide", page_icon="🏗️")

# --- CSS CUSTOM ---
st.markdown("""
<style>
    .header-box {
        padding: 20px; background-color: #546e7a; color: white;
        border-radius: 10px; text-align: center; margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px; font-weight: bold;
    }
    .metric-safe {color: green; font-weight: bold;}
    .metric-danger {color: red; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- 1. AMBIL DATA NFR DARI POLA TANAM ---
# Kita cari nilai maksimum kebutuhan air sebagai dasar desain
nfr_base = 1.25 # Default jika belum ada data
status_nfr = "⚠️ Default (Modul Pola Tanam belum dijalankan)"

if 'data_nfr_manual' in st.session_state:
    data_nfr = st.session_state['data_nfr_manual']
    if len(data_nfr) > 0:
        nfr_max = max(data_nfr) # Ambil puncak kebutuhan
        if nfr_max > 0:
            nfr_base = nfr_max
            status_nfr = "✅ Terhubung (Menggunakan NFR Maksimum Pola Tanam)"

# --- 2. INIT STATE (DATA SALURAN) ---
def init_channel_data():
    # Template Data Frame
    cols = ['Nama Saluran', 'Luas (ha)', 'Modulus (l/s/ha)', 'Efisiensi', 'Lebar b (m)', 'Tinggi h (m)', 'Talud m', 'Slope S (%)', 'Kekasaran n']
    
    if 'df_saluran_induk' not in st.session_state:
        st.session_state['df_saluran_induk'] = pd.DataFrame([
            ['Induk Kanan', 500, nfr_base, 0.90, 2.0, 1.2, 1.5, 0.04, 0.025],
            ['Induk Kiri', 400, nfr_base, 0.90, 2.0, 1.2, 1.5, 0.04, 0.025]
        ], columns=cols)
        
    if 'df_saluran_sekunder' not in st.session_state:
        st.session_state['df_saluran_sekunder'] = pd.DataFrame([
            ['Sekunder A', 150, nfr_base, 0.85, 1.0, 0.8, 1.0, 0.05, 0.025],
            ['Sekunder B', 200, nfr_base, 0.85, 1.2, 0.9, 1.0, 0.05, 0.025]
        ], columns=cols)

    if 'df_saluran_tersier' not in st.session_state:
        st.session_state['df_saluran_tersier'] = pd.DataFrame([
            ['Tersier 1', 50, nfr_base, 0.80, 0.5, 0.4, 1.0, 0.10, 0.030],
            ['Tersier 2', 40, nfr_base, 0.80, 0.5, 0.4, 1.0, 0.10, 0.030]
        ], columns=cols)

init_channel_data()

# --- 3. FUNGSI HITUNG MANNING ---
def hitung_hidrolika(df):
    # Rumus Manning: V = 1/n * R^(2/3) * S^(1/2)
    # Q = A * V
    
    # Konversi tipe data biar aman
    for c in df.columns[1:]: df[c] = pd.to_numeric(df[c])
    
    b = df['Lebar b (m)']
    h = df['Tinggi h (m)']
    m = df['Talud m']
    S = df['Slope S (%)'] / 100
    n = df['Kekasaran n']
    
    # Geometri
    A = (b + m * h) * h
    P = b + 2 * h * np.sqrt(1 + m**2)
    R = A / P
    
    # Hidrolika
    V = (1/n) * (R**(2/3)) * (S**(0.5))
    Q_cap = A * V * 1000 # m3/s -> Liter/s
    
    # Kebutuhan (Q Rencana)
    # Q_req = (Luas * Modulus) / Efisiensi
    Q_req = (df['Luas (ha)'] * df['Modulus (l/s/ha)']) / df['Efisiensi']
    
    # Hasil
    df_res = df.copy()
    df_res['A (m2)'] = np.round(A, 2)
    df_res['V (m/s)'] = np.round(V, 2)
    df_res['Q Cap (L/s)'] = np.round(Q_cap, 2)
    df_res['Q Req (L/s)'] = np.round(Q_req, 2)
    
    # Cek Status
    df_res['Status'] = np.where(df_res['Q Cap (L/s)'] >= df_res['Q Req (L/s)'], "✅ AMAN", "❌ MELUAP")
    
    return df_res

# --- 4. TAMPILAN UI ---
st.markdown("""
<div class="header-box">
    <h2>🏗️ Desain Hidrolika Saluran</h2>
    <p>Analisa Dimensi Berdasarkan Hirarki Saluran (Induk, Sekunder, Tersier)</p>
</div>
""", unsafe_allow_html=True)

st.info(f"ℹ️ **Info NFR:** {status_nfr} | **Base Modulus:** {nfr_base:.3f} l/s/ha")

# TABS
tab1, tab2, tab3 = st.tabs(["🟦 Saluran INDUK", "🟨 Saluran SEKUNDER", "🟩 Saluran TERSIER"])

def render_tab_content(key_df, label):
    st.subheader(f"1. Input Dimensi {label}")
    edited = st.data_editor(st.session_state[key_df], num_rows="dynamic", use_container_width=True, key=f"edit_{key_df}")
    st.session_state[key_df] = edited # Simpan perubahan
    
    # Hitung Realtime
    df_hasil = hitung_hidrolika(edited)
    
    st.subheader("2. Hasil Analisa Kapasitas")
    
    # Format Tampilan Tabel Hasil
    st.dataframe(
        df_hasil[['Nama Saluran', 'Q Req (L/s)', 'Q Cap (L/s)', 'V (m/s)', 'Status']]
        .style.map(lambda v: 'color: red; font-weight: bold;' if v == '❌ MELUAP' else 'color: green; font-weight: bold;', subset=['Status'])
        .format("{:.2f}", subset=['Q Req (L/s)', 'Q Cap (L/s)', 'V (m/s)']),
        use_container_width=True
    )
    
    # Warning Kecepatan
    for i, r in df_hasil.iterrows():
        if r['Status'] == "❌ MELUAP":
            st.error(f"⚠️ **{r['Nama Saluran']}**: Dimensi kurang besar! (Kurang {r['Q Req (L/s)'] - r['Q Cap (L/s)'] :.1f} L/s)")
        
        # Cek Kecepatan Izin (0.6 - 2.0 m/s)
        if r['V (m/s)'] < 0.6:
            st.warning(f"⚠️ **{r['Nama Saluran']}**: Aliran terlalu pelan ({r['V (m/s)']} m/s). Potensi endapan lumpur.")
        elif r['V (m/s)'] > 2.0:
            st.warning(f"⚠️ **{r['Nama Saluran']}**: Aliran terlalu cepat ({r['V (m/s)']} m/s). Potensi gerusan saluran.")

with tab1:
    render_tab_content('df_saluran_induk', "Saluran Induk (Efisiensi ~90%)")

with tab2:
    render_tab_content('df_saluran_sekunder', "Saluran Sekunder (Efisiensi ~85%)")

with tab3:
    render_tab_content('df_saluran_tersier', "Saluran Tersier (Efisiensi ~80%)")

# --- LAPORAN ---
st.divider()
st.markdown("### 📑 Rekapitulasi Desain")
c1, c2, c3 = st.columns(3)
c1.metric("Total Saluran Induk", len(st.session_state['df_saluran_induk']))
c2.metric("Total Saluran Sekunder", len(st.session_state['df_saluran_sekunder']))
c3.metric("Total Saluran Tersier", len(st.session_state['df_saluran_tersier']))

import streamlit.components.v1 as components
components.html("""<button onclick="window.print()" style="background:#546e7a;color:white;border:none;padding:10px 20px;border-radius:5px;">🖨️ Cetak Laporan</button>""", height=50)
