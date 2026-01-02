import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- CONFIG & METODOLOGI ---
st.set_page_config(page_title="Desain Saluran", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background-color: #546e7a; color: white;
        border-radius: 10px; text-align: center; margin-bottom: 20px;
    }
    .metric-safe {color: green; font-weight: bold;}
    .metric-danger {color: red; font-weight: bold;}
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# KOTAK METODOLOGI
st.markdown("""
<div style="background-color: #eceff1; padding: 15px; border-radius: 5px; border-left: 5px solid #607d8b; margin-bottom: 20px;">
    <strong>ℹ️ METODOLOGI: Hidrolika Saluran Terbuka (Open Channel)</strong><br>
    <ul>
        <li><strong>Kapasitas Debit:</strong> Rumus Manning (V = 1/n × R⅔ × S½)</li>
        <li><strong>Geometri:</strong> Penampang Trapesium (A = (b + mh)h)</li>
        <li><strong>Kontrol:</strong> Kecepatan Izin (0.6 - 2.0 m/s) & Froude Number (Aliran Subkritis/Superkritis).</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# --- 1. DATA NFR LINK ---
nfr_base = 1.25 
status_nfr = "⚠️ Default (Modul Pola Tanam belum dijalankan)"
if 'data_nfr_manual' in st.session_state:
    data_nfr = st.session_state['data_nfr_manual']
    if len(data_nfr) > 0:
        nfr_max = max(data_nfr)
        if nfr_max > 0:
            nfr_base = nfr_max
            status_nfr = "✅ Terhubung (NFR Max Pola Tanam)"

# --- 2. INIT STATE ---
def init_channel_data():
    cols = ['Nama Saluran', 'Luas (ha)', 'Modulus (l/s/ha)', 'Efisiensi', 'Lebar b (m)', 'Tinggi h (m)', 'Talud m', 'Slope S (%)', 'Kekasaran n']
    if 'df_saluran_induk' not in st.session_state:
        st.session_state['df_saluran_induk'] = pd.DataFrame([['Induk Kanan', 500, nfr_base, 0.90, 2.0, 1.2, 1.5, 0.04, 0.025]], columns=cols)
    if 'df_saluran_sekunder' not in st.session_state:
        st.session_state['df_saluran_sekunder'] = pd.DataFrame([['Sekunder A', 150, nfr_base, 0.85, 1.0, 0.8, 1.0, 0.05, 0.025]], columns=cols)
    if 'df_saluran_tersier' not in st.session_state:
        st.session_state['df_saluran_tersier'] = pd.DataFrame([['Tersier 1', 50, nfr_base, 0.80, 0.5, 0.4, 1.0, 0.10, 0.030]], columns=cols)
init_channel_data()

# --- 3. FUNGSI HITUNG & GAMBAR ---
def hitung_hidrolika(df):
    for c in df.columns[1:]: df[c] = pd.to_numeric(df[c])
    
    b, h, m = df['Lebar b (m)'], df['Tinggi h (m)'], df['Talud m']
    S = df['Slope S (%)'] / 100
    n = df['Kekasaran n']
    
    A = (b + m * h) * h
    P = b + 2 * h * np.sqrt(1 + m**2)
    R = A / P
    V = (1/n) * (R**(2/3)) * (S**(0.5))
    Q_cap = A * V * 1000 
    Q_req = (df['Luas (ha)'] * df['Modulus (l/s/ha)']) / df['Efisiensi']
    
    # Froude Number (Fr = V / sqrt(g * D)) -> D = A / T -> T = b + 2mh
    T_top = b + 2 * m * h
    D_hyd = A / T_top
    Fr = V / np.sqrt(9.81 * D_hyd)

    df_res = df.copy()
    df_res['V (m/s)'] = np.round(V, 2)
    df_res['Q Cap (L/s)'] = np.round(Q_cap, 2)
    df_res['Q Req (L/s)'] = np.round(Q_req, 2)
    df_res['Fr'] = np.round(Fr, 2)
    df_res['Status'] = np.where(df_res['Q Cap (L/s)'] >= df_res['Q Req (L/s)'], "✅ AMAN", "❌ MELUAP")
    return df_res

def gambar_penampang(b, h, m, h_air=None):
    # Setup Koordinat Trapesium
    # (0,h) ____b____ (b,h)
    #      /         \
    #     /           \
    # (-mh,0)_________(b+mh,0) -> Tapi kita balik agar dasar di y=0
    
    # Koordinat Dasar (Bottom)
    # Kiri Bawah (0, 0) -> Kanan Bawah (b, 0)
    # Kiri Atas (-mh, h) -> Kanan Atas (b+mh, h)
    
    fig, ax = plt.subplots(figsize=(6, 3))
    
    # Tanah/Saluran
    x_coords = [-m*h, 0, b, b + m*h]
    y_coords = [h, 0, 0, h]
    
    ax.plot(x_coords, y_coords, color='brown', linewidth=2, label='Saluran')
    
    # Air (Asumsi Penuh h)
    if h_air is None: h_air = h * 0.9 # Default visualisasi 90% penuh
    
    width_top_water = b + 2 * m * h_air
    x_water = [-(m*h_air), b + (m*h_air)]
    y_water = [h_air, h_air]
    
    # Fill Water
    ax.fill_between([-(m*h_air), 0, b, b+(m*h_air)], [h_air, 0, 0, h_air], color='cyan', alpha=0.6, label='Air')
    
    # Anotasi Dimensi
    ax.text(b/2, -h*0.1, f"b = {b} m", ha='center', va='top', fontsize=10)
    ax.text(b + m*h + h*0.1, h/2, f"h = {h} m", ha='left', va='center', fontsize=10)
    ax.text(-m*h/2, h/2, f"m = {m}", ha='right', va='center', fontsize=9, rotation=45)

    ax.set_aspect('equal')
    ax.axis('off') # Hilangkan sumbu biar bersih
    ax.set_title("Visualisasi Penampang", fontsize=10)
    return fig

# --- 4. TAMPILAN UTAMA ---
st.markdown('<div class="header-box"><h2>🏗️ Desain Hidrolika Saluran</h2></div>', unsafe_allow_html=True)
st.info(f"ℹ️ **Info NFR:** {status_nfr} | **Base Modulus:** {nfr_base:.3f} l/s/ha")

# SIDEBAR UPLOAD SKEMA
with st.sidebar:
    st.header("🗺️ Peta Skema")
    skema_file = st.file_uploader("Upload Gambar Skema (JPG/PNG)", type=['jpg','png','jpeg'])
    if skema_file:
        st.image(skema_file, caption="Skema Jaringan Irigasi", use_container_width=True)
    else:
        st.info("Upload gambar skema jaringan di sini untuk referensi.")

# TABS UTAMA
tab1, tab2, tab3 = st.tabs(["🟦 Saluran INDUK", "🟨 Saluran SEKUNDER", "🟩 Saluran TERSIER"])

def render_tab(key_df, label):
    c_input, c_visual = st.columns([1.5, 1])
    
    with c_input:
        st.subheader(f"1. Dimensi {label}")
        edited = st.data_editor(st.session_state[key_df], num_rows="dynamic", use_container_width=True, key=f"edit_{key_df}")
        st.session_state[key_df] = edited
        
        # Hitung
        df_hasil = hitung_hidrolika(edited)
        
        st.subheader("2. Hasil Analisa")
        st.dataframe(
            df_hasil[['Nama Saluran', 'Q Req (L/s)', 'Q Cap (L/s)', 'V (m/s)', 'Fr', 'Status']]
            .style.map(lambda v: 'color: red; font-weight: bold;' if v == '❌ MELUAP' else 'color: green; font-weight: bold;', subset=['Status'])
            .format("{:.2f}", subset=['Q Req (L/s)', 'Q Cap (L/s)', 'V (m/s)', 'Fr']),
            use_container_width=True
        )

    with c_visual:
        st.subheader("3. Visualisasi")
        if len(edited) > 0:
            # Ambil baris pertama atau yang dipilih (Logic sederhana: baris pertama dulu)
            pilih_saluran = st.selectbox("Pilih Saluran utk Visualisasi:", edited['Nama Saluran'].unique(), key=f"sel_{key_df}")
            row = edited[edited['Nama Saluran'] == pilih_saluran].iloc[0]
            
            try:
                fig = gambar_penampang(float(row['Lebar b (m)']), float(row['Tinggi h (m)']), float(row['Talud m']))
                st.pyplot(fig)
                
                # Info Cepat
                row_res = df_hasil[df_hasil['Nama Saluran'] == pilih_saluran].iloc[0]
                st.info(f"**{pilih_saluran}**\n\nKecepatan: {row_res['V (m/s)']} m/s\n\nFroude: {row_res['Fr']} ({'Superkritis' if row_res['Fr']>1 else 'Subkritis'})")
            except:
                st.warning("Lengkapi data dimensi untuk melihat gambar.")

    # Warning Global
    for i, r in df_hasil.iterrows():
        if r['Status'] == "❌ MELUAP":
            st.error(f"⚠️ **{r['Nama Saluran']}**: Dimensi kurang besar! (Kurang {r['Q Req (L/s)'] - r['Q Cap (L/s)'] :.1f} L/s)")
        if r['V (m/s)'] < 0.6:
            st.warning(f"⚠️ **{r['Nama Saluran']}**: Aliran terlalu pelan ({r['V (m/s)']} m/s). Endapan!")
        elif r['V (m/s)'] > 2.0:
            st.warning(f"⚠️ **{r['Nama Saluran']}**: Aliran terlalu cepat ({r['V (m/s)']} m/s). Gerusan!")

with tab1: render_tab('df_saluran_induk', "Saluran Induk")
with tab2: render_tab('df_saluran_sekunder', "Saluran Sekunder")
with tab3: render_tab('df_saluran_tersier', "Saluran Tersier")

st.divider()
import streamlit.components.v1 as components
components.html("""<button onclick="window.print()" style="background:#546e7a;color:white;border:none;padding:10px 20px;border-radius:5px;">🖨️ Cetak Laporan</button>""", height=50)
