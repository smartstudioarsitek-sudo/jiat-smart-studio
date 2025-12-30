import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- CSS CUSTOM UNTUK SIDEBAR & BANNER ---
st.markdown("""
<style>
    /* Mengubah tulisan 'main' di sidebar menjadi 'MENU' yang besar */
    section[data-testid="stSidebarNav"] span {
        display: none; /* Sembunyikan teks asli */
    }
    section[data-testid="stSidebarNav"]::before {
        content: "MENU"; /* Tambahkan teks MENU */
        margin-left: 20px;
        margin-top: 20px;
        font-size: 24px;
        font-weight: 800;
        color: #01579b;
        display: block;
    }

    /* Styling Banner Utama */
    .hero-box {
        background: linear-gradient(135deg, #01579b 0%, #0288d1 50%, #29b6f6 100%);
        padding: 50px; 
        border-radius: 20px; 
        color: white; 
        text-align: center; 
        margin-bottom: 30px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    .hero-title { font-size: 45px; font-weight: 800; margin-bottom: 5px; }
    .hero-subtitle { font-size: 18px; font-weight: 400; opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

# --- TAMPILAN DASHBOARD ---
st.markdown("""
<div class="hero-box">
    <div class="hero-title">💧 SmartStudio</div>
    <div class="hero-subtitle">JIAT Lampung Timur | Desa Hargomulyo</div>
</div>
""", unsafe_allow_html=True)

st.info("👋 **Selamat Datang di SmartStudio!** Silakan gunakan menu navigasi di sebelah kiri untuk memulai analisis.")

# --- TOMBOL NAVIGASI MODUL ---
st.subheader("🛠️ Modul Engineering")

col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/1_Klimatologi.py", label="Klimatologi & ETo", icon="☀️", use_container_width=True)
with col2:
    st.page_link("pages/2_Pola_Tanam.py", label="Pola Tanam & NFR", icon="🌾", use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.page_link("pages/3_FJ_Mock.py", label="Ketersediaan Air (Mock)", icon="🌊", use_container_width=True)
with col4:
    st.page_link("pages/4_Desain_Saluran.py", label="Desain Saluran Terbuka", icon="🏗️", use_container_width=True)

st.write("")
st.page_link("pages/5_Irigasi_Pipa.py", label="Jaringan Irigasi Pipa & Pompa", icon="💧", use_container_width=True)

st.divider()
st.markdown("<div style='text-align: center; color: #607d8b;'><b>SmartStudio</b> © 2025 | Water Engineering Division</div>", unsafe_allow_html=True)