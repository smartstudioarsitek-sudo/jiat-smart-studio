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

    /* 2. KARTU MENU */
    .box-menu {
        padding: 25px;
        background-color: #ffffff;
        border-radius: 15px;
        border: 1px solid #e3f2fd;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 100%;
    }
    
    .box-menu:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(33, 150, 243, 0.2);
        border-color: #2196f3;
    }

    .big-icon {
        font-size: 50px;
        margin-bottom: 15px;
    }
    
    /* HILANGKAN GARIS BAWAH LINK */
    a { text-decoration: none; color: inherit; }
    a:hover { text-decoration: none; color: inherit; }
    
    h3 { color: #1565c0; font-weight: 700; font-size: 20px;}
    p { color: #546e7a; font-size: 14px; line-height: 1.5;}
    
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