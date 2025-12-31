import streamlit as st

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- 2. CSS UNTUK TAMPILAN PROFESIONAL ---
st.markdown("""
<style>
    /* MENYEMBUNYIKAN SIDEBAR OTOMATIS AGAR TIDAK GANDA */
    [data-testid="stSidebarNav"] {display: none;}
    
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 60px 30px; 
        border-radius: 20px; 
        color: white; 
        text-align: center; 
        margin-bottom: 40px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    .hero-title { 
        font-size: 70px; 
        font-weight: 900; 
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 25px;
        margin-bottom: 10px;
    }
    .water-logo { font-size: 80px; }
    .hero-subtitle { font-size: 22px; opacity: 0.9; font-weight: 300; }
</style>
""", unsafe_allow_html=True)

# --- 3. BANNER UTAMA ---
st.markdown("""
<div class="hero-box">
    <div class="hero-title">
        <span class="water-logo">🏗️</span> SmartStudio
    </div>
    <div class="hero-subtitle">Integrated Water Resources & Infrastructure Management System</div>
</div>
""", unsafe_allow_html=True)

# --- 4. MENU NAVIGASI DASHBOARD ---
st.subheader("🛠️ Modul Engineering")

# Baris 1
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/1_Klimatologi.py", label="Klimatologi & ETo", icon="☀️", use_container_width=True)
with col2:
    st.page_link("pages/2_Pola_Tanam.py", label="Pola Tanam & NFR", icon="🌾", use_container_width=True)

# Baris 2
col3, col4 = st.columns(2)
with col3:
    st.page_link("pages/3_FJ_Mock.py", label="Debit Andalan (Mock)", icon="🌊", use_container_width=True)
with col4:
    st.page_link("pages/4_Desain_Saluran.py", label="Desain Saluran", icon="🏗️", use_container_width=True)

# Baris 3 (Modul Tambahan)
st.write("")
st.page_link("pages/5_Irigasi_Pipa.py", label="Irigasi Pipa & Pompa", icon="💧", use_container_width=True)

st.divider()
st.caption("SmartStudio © 2025 | Water Engineering Division")