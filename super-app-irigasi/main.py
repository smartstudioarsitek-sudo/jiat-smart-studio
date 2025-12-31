import streamlit as st
import streamlit.components.v1 as components

# --- 1. KONFIGURASI HALAMAN UTAMA ---
st.set_page_config(
    page_title="SmartStudio - Water Engineering",
    layout="wide",
    page_icon="💧",
    initial_sidebar_state="expanded"
)

# --- 2. GLOBAL CSS (UNTUK MEMPERCANTIK & PRINT) ---
st.markdown("""
<style>
    /* A. STYLE UMUM */
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #0f172a; }
    
    /* B. HERO SECTION (BANNER ATAS) */
    .hero-container {
        background: linear-gradient(135deg, #0288d1 0%, #26c6da 100%);
        padding: 40px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .hero-title { font-size: 3rem; font-weight: 800; margin: 0; }
    .hero-subtitle { font-size: 1.2rem; opacity: 0.9; margin-top: 10px; }

    /* C. STYLE KARTU MENU (CARD) */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
    }
    
    /* D. CSS KHUSUS PRINT (Agar Sidebar Hilang saat Print) */
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0 !important; }
        .no-print { display: none !important; }
        /* Paksa background warna tercetak */
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- 3. JAVASCRIPT PRINT TRIGGER ---
# Fungsi untuk tombol print yang bisa dipanggil di mana saja
def tombol_cetak():
    # Membuat tombol HTML custom yang memicu window.print()
    components.html(
        """
        <style>
        .btn-print {
            background-color: #4CAF50; border: none; color: white; 
            padding: 10px 24px; text-align: center; text-decoration: none;
            display: inline-block; font-size: 16px; margin: 4px 2px; 
            cursor: pointer; border-radius: 8px; font-family: sans-serif;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2); transition: 0.3s;
        }
        .btn-print:hover { background-color: #45a049; }
        </style>
        <button class="btn-print" onclick="window.print()">🖨️ Cetak / Simpan PDF</button>
        """,
        height=60
    )

# --- 4. HEADER HERO SECTION ---
st.markdown("""
<div class="hero-container">
    <div class="hero-title">💧 SmartStudio</div>
    <div class="hero-subtitle">Integrated Water Resources & Irrigation System Planning</div>
</div>
""", unsafe_allow_html=True)

# --- 5. DASHBOARD GRID MENU ---

# --- BARIS 1: DATA DASAR ---
st.write("### ☀️ 1. Data & Agronomi")
st.write("Langkah awal: Siapkan data klimatologi dan tentukan kebutuhan air tanaman.")
col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("#### 🌦️ Modul 1: Klimatologi")
        st.caption("Analisa Evapotranspirasi (ETo) Metode Penman-Monteith.")
        # Gunakan st.page_link agar transisi INSTAN (tanpa reload berat)
        # Pastikan nama file di folder pages sesuai (misal: pages/1_Klimatologi.py)
        st.page_link("pages/1_Klimatologi.py", label="Buka Modul Klimatologi", icon="🌦️")

with col2:
    with st.container(border=True):
        st.markdown("#### 🌾 Modul 2: Pola Tanam")
        st.caption("Perhitungan Kebutuhan Air Irigasi (NFR) Padi & Palawija.")
        st.page_link("pages/2_Pola_Tanam.py", label="Buka Modul Pola Tanam", icon="🌾")

# --- BARIS 2: ANALISA HIDROLOGI ---
st.divider()
st.write("### 🌊 2. Analisa Hidrologi")
st.write("Analisa ketersediaan air sungai dan keamanan terhadap banjir.")
col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown("#### 📉 Modul 3: Ketersediaan Air")
        st.caption("Analisa Debit Andalan Sungai Metode FJ. Mock.")
        st.page_link("pages/3_FJ_Mock.py", label="Buka Modul FJ Mock", icon="📉")

with col4:
    with st.container(border=True):
        st.markdown("#### ⛈️ Modul 6: Analisa Banjir")
        st.caption("Analisa Debit Banjir Rencana (Rasional, Haspers, Weduwen).")
        st.page_link("pages/6_Analisa_Banjir.py", label="Buka Modul Banjir", icon="⛈️")

# --- BARIS 3: DESAIN INFRASTRUKTUR ---
st.divider()
st.write("### 🏗️ 3. Desain Hidrolika")
st.write("Perencanaan dimensi saluran dan jaringan perpipaan.")
col5, col6 = st.columns(2)

with col5:
    with st.container(border=True):
        st.markdown("#### 🏞️ Modul 4: Saluran Terbuka")
        st.caption("Desain Dimensi Saluran Irigasi (Trarapesium/Persegi).")
        st.page_link("pages/4_Desain_Saluran.py", label="Buka Desain Saluran", icon="🏞️")

with col6:
    with st.container(border=True):
        st.markdown("#### 🚰 Modul 5: Pipa & Pompa (JIAT)")
        st.caption("Desain Jaringan Pipa Tekan, Head Loss & Pompa.")
        st.page_link("pages/5_Irigasi_Pipa.py", label="Buka Irigasi Pipa", icon="🚰")

# --- 6. FOOTER & PRINT BUTTON ---
st.divider()
c_print, c_copy = st.columns([1, 4])
with c_print:
    st.write("**Menu Cepat:**")
    tombol_cetak()
with c_copy:
    st.caption("© 2025 SmartStudio | Water Engineering Division")
    st.caption("Tips: Gunakan tombol cetak di atas untuk menyimpan laporan ini sebagai PDF.")
