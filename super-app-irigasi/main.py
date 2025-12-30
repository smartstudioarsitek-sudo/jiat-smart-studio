import streamlit as st  # <--- INI BARIS SAKTI YANG TADI HILANG KAK

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="JIAT Smart Studio",
    page_icon="🏗️", 
    layout="wide"
)

# --- CSS STYLING (MODERN GRADIENT) ---
st.markdown("""
<style>
    /* Reset padding atas biar rapi */
    .block-container {
        padding-top: 2rem;
    }
    
    /* 1. HERO SECTION (BANNER GRADASI) */
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 50px 30px;
        border-radius: 20px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 10px 20px rgba(13, 71, 161, 0.2);
    }
    
    .hero-title {
        font-size: 40px;
        font-weight: 800;
        margin-bottom: 10px;
    }
    
    .hero-subtitle {
        font-size: 18px;
        font-weight: 300;
        opacity: 0.9;
    }

    /* 2. STYLE UNTUK TOMBOL LINK BIAR BESAR (Opsional) */
    div[data-testid="stPageLink-NavLink"] {
        border: 1px solid #e3f2fd;
        border-radius: 10px;
        padding: 15px;
        transition: transform 0.2s;
    }
    div[data-testid="stPageLink-NavLink"]:hover {
        background-color: #f1f8fe;
        transform: scale(1.02);
        border-color: #2196f3;
    }
    
</style>
""", unsafe_allow_html=True)

# --- TAMPILAN HERO (BANNER PENGGANTI GAMBAR) ---
st.markdown("""
<div class="hero-box">
    <div class="hero-title">🏗️ Sistem Perencanaan Irigasi Terpadu</div>
    <div class="hero-subtitle">Integrated Water Resources & Infrastructure Management System</div>
</div>
""", unsafe_allow_html=True)

# --- SAMBUTAN ---
st.info("👋 **Selamat Datang, Engineer!** Silakan akses modul perhitungan teknis melalui kartu di bawah ini atau Sidebar sebelah kiri.")

# --- MENU GRID ---
st.write("") 
st.subheader("🛠️ Modul Engineering")

# Baris 1
col1, col2 = st.columns(2)

with col1:
    # Link ke halaman Klimatologi (Sesuaikan nama file di folder pages)
    # Pastikan nama file di dalam tanda kutip SAMA PERSIS dengan di folder pages
    st.page_link("pages/1_☀️_Klimatologi.py", label="Klimatologi & ETo", icon="☀️", use_container_width=True, help="Analisis Cuaca & ETo")

with col2:
    st.page_link("pages/2_🌾_Pola_Tanam.py", label="Pola Tanam & NFR", icon="🌾", use_container_width=True, help="Rencana Tanam & Kebutuhan Air")

# Baris 2
col3, col4 = st.columns(2)

with col3:
    st.page_link("pages/3_🌊_FJ_Mock.py", label="Debit Andalan (Mock)", icon="🌊", use_container_width=True, help="Analisis Ketersediaan Air Sungai")

with col4:
    st.page_link("pages/4_🏗️_Desain_Saluran.py", label="Desain Saluran", icon="🏗️", use_container_width=True, help="Dimensi Saluran & Hidrolika")

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #90a4ae; font-size: 13px; padding: 20px;'>
        Developed by <b>JIAT Smart Studio</b> | Civil Engineering Division © 2025
    </div>
    """, unsafe_allow_html=True
)