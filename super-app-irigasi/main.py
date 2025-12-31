import streamlit as st

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- 2. CSS UNTUK SEMBUNYIKAN SIDEBAR GANDA ---
st.markdown("""
<style>
    /* Menyembunyikan daftar file otomatis di sidebar agar tidak ganda */
    [data-testid="stSidebarNav"] {display: none;}
    
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 60px 30px; 
        border-radius: 20px; 
        color: white; 
        text-align: center; 
        margin-bottom: 40px;
    }
    .hero-title { 
        font-size: 70px; 
        font-weight: 900; 
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 25px;
    }
    .water-logo { font-size: 80px; }
</style>
""", unsafe_allow_html=True)

# --- 3. BANNER UTAMA ---
st.markdown("""
<div class="hero-box">
    <div class="hero-title">
        <span class="water-logo">💧</span> SmartStudio
    </div>
    <p style="font-size: 20px; opacity: 0.9;">Integrated Water Resources & Infrastructure Management System</p>
</div>
""", unsafe_allow_html=True)

# --- 4. MENU NAVIGASI (Satu-satunya Navigasi) ---
st.subheader("🛠️ Modul Engineering")
col1, col2 = st.columns(2)

with col1:
    st.page_link("pages/1_Klimatologi.py", label="Klimatologi & ETo", icon="☀️", use_container_width=True)
with col2:
    st.page_link("pages/2_Pola_Tanam.py", label="Pola Tanam & NFR", icon="🌾", use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.page_link("pages/3_FJ_Mock.py", label="Debit Andalan (Mock)", icon="🌊", use_container_width=True)
with col4:
    st.page_link("pages/4_Desain_Saluran.py", label="Desain Saluran", icon="🏗️", use_container_width=True)

st.write("")
st.page_link("pages/5_Irigasi_Pipa.py", label="Irigasi Pipa & Pompa", icon="💧", use_container_width=True)

st.divider()
st.caption("SmartStudio © 2025 | Water Engineering Division")