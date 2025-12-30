import streamlit as st

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- 2. CSS CUSTOM (FONT JUMBO + LOGO AIR) ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 70px 30px; 
        border-radius: 20px; 
        color: white; 
        text-align: center; 
        margin-bottom: 40px;
        box-shadow: 0 15px 30px rgba(0,0,0,0.2);
    }
    .hero-title { 
        font-size: 80px; /* JUDUL SANGAT BESAR */
        font-weight: 900; 
        margin-bottom: 5px;
    }
    .hero-subtitle { 
        font-size: 24px; /* SUBTITLE LEBIH JELAS */
        font-weight: 300; 
        opacity: 0.9;
    }
    .water-logo {
        font-size: 100px; /* LOGO AIR RAKSASA */
        margin-bottom: 10px;
        display: block;
    }
</style>
<div class="hero-box">
    <span class="water-logo">💧</span>
    <div class="hero-title">SmartStudio</div>
    <div class="hero-subtitle">Integrated Water Resources & Infrastructure Management System</div>
</div>
""", unsafe_allow_html=True)

# --- 3. MODUL NAVIGASI (DENGAN FIX FUTUREWARNING) ---
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

# Baris 3
st.write("")
st.page_link("pages/5_Irigasi_Pipa.py", label="Irigasi Pipa & Pompa", icon="💧", use_container_width=True)

st.divider()
st.caption("SmartStudio © 2025 | Water Engineering Division")