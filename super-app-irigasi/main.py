import streamlit as st
import streamlit.components.v1 as components

# --- 1. KONFIGURASI HALAMAN UTAMA ---
st.set_page_config(
    page_title="SmartStudio | Water Engineering",
    layout="wide",
    page_icon="💧",
    initial_sidebar_state="expanded"
)

# --- 2. STYLE CSS (MODERN & CLEAN) ---
st.markdown("""
<style>
    /* A. HERO SECTION */
    .hero-box {
        background: linear-gradient(120deg, #0288d1 0%, #26c6da 100%);
        padding: 30px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .hero-title { font-size: 2.5rem; font-weight: 700; margin: 0; }
    .hero-sub { font-size: 1.1rem; opacity: 0.9; margin-top: 5px; font-weight: 300; }

    /* B. CARD STYLING (Kotak Menu) */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        height: 100%;
        transition: transform 0.2s, border-color 0.2s;
    }
    div[data-testid="stVerticalBlock"]:hover {
        border-color: #0288d1;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* C. HEADER SECTIONS */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #37474f;
        margin-top: 20px;
        margin-bottom: 15px;
        border-left: 5px solid #0288d1;
        padding-left: 10px;
    }

    /* D. HIDE SIDEBAR ON PRINT (Agar Laporan Bersih) */
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        .no-print { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNGSI TOMBOL CETAK (FIXED) ---
def tombol_cetak():
    # Menggunakan window.parent.print() untuk mencetak halaman induk
    components.html(
        """
        <script>
            function cetakHalaman() {
                window.parent.print();
            }
        </script>
        <button onclick="cetakHalaman()" style="
            background-color: #4CAF50; color: white; border: none; 
            padding: 10px 20px; border-radius: 5px; cursor: pointer; 
            font-size: 14px; font-family: 'Segoe UI', sans-serif; font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            🖨️ Cetak Halaman / Save PDF
        </button>
        <div style="font-family: sans-serif; font-size: 10px; color: #666; margin-top: 5px;">
            *Jika tombol tidak respon, tekan <b>Ctrl + P</b> pada keyboard.
        </div>
        """, 
        height=80
    )

# --- 4. HERO BANNER ---
st.markdown("""
<div class="hero-box">
    <div class="hero-title">💧 SmartStudio</div>
    <div class="hero-sub">Sistem Perencanaan Irigasi & Sumber Daya Air Terpadu</div>
</div>
""", unsafe_allow_html=True)

# --- 5. GRID MENU ---

# === KELOMPOK 1: DATA & AGRONOMI ===
st.markdown('<div class="section-header">1. Data & Agronomi</div>', unsafe_allow_html=True)
st.caption("Langkah awal: Siapkan data klimatologi dan tentukan kebutuhan air tanaman.")
col1, col2 = st.columns(2)

with col1:
    st.subheader("🌦️ Modul Klimatologi")
    st.caption("Analisa Evapotranspirasi (ETo) Metode Penman-Monteith.")
    st.page_link("pages/1_Klimatologi.py", label="Buka Modul Klimatologi", icon="➡️", use_container_width=True)

with col2:
    st.subheader("🌾 Modul Pola Tanam")
    st.caption("Perhitungan Kebutuhan Air Irigasi (NFR) Padi & Palawija.")
    st.page_link("pages/2_Pola_Tanam.py", label="Buka Modul Pola Tanam", icon="➡️", use_container_width=True)

# === KELOMPOK 2: ANALISA HIDROLOGI ===
st.markdown('<div class="section-header">2. Analisa Hidrologi</div>', unsafe_allow_html=True)
st.caption("Analisa ketersediaan air sungai dan keamanan terhadap banjir.")
col3, col4 = st.columns(2)

with col3:
    st.subheader("📉 Modul FJ Mock")
    st.caption("Analisa Ketersediaan Air (Debit Andalan).")
    st.page_link("pages/3_FJ_Mock.py", label="Buka Modul FJ Mock", icon="➡️", use_container_width=True)

with col4:
    st.subheader("⛈️ Modul Analisa Banjir")
    st.caption("Analisa Debit Banjir Rencana (Metode Statistik).")
    st.page_link("pages/6_Analisa_Banjir.py", label="Buka Modul Banjir", icon="➡️", use_container_width=True)

# === KELOMPOK 3: DESAIN INFRASTRUKTUR ===
st.markdown('<div class="section-header">3. Desain Hidrolika</div>', unsafe_allow_html=True)
st.caption("Perencanaan dimensi saluran dan jaringan perpipaan.")
col5, col6 = st.columns(2)

with col5:
    st.subheader("🏞️ Modul Desain Saluran")
    st.caption("Dimensi Saluran Terbuka (Gravitasi).")
    st.page_link("pages/4_Desain_Saluran.py", label="Buka Desain Saluran", icon="➡️", use_container_width=True)

with col6:
    st.subheader("🚰 Modul Irigasi Pipa")
    st.caption("Jaringan Pipa Tekan & Pompa (JIAT).")
    st.page_link("pages/5_Irigasi_Pipa.py", label="Buka Irigasi Pipa", icon="➡️", use_container_width=True)

# --- 6. FOOTER ---
st.divider()
c_print, c_text = st.columns([1, 4])
with c_print:
    tombol_cetak()
with c_text:
    st.caption("SmartStudio v2.0 | Water Engineering Division")
    st.caption("Gunakan tombol cetak di samping untuk menyimpan halaman ini sebagai laporan PDF.")
