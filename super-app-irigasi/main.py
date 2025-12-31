import streamlit as st

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- 2. CSS CUSTOM (TAMPILAN BERSIH) ---
st.markdown("""
<style>
    /* Sembunyikan Sidebar Navigasi Otomatis */
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
        font-size: 60px; 
        font-weight: 900; 
        display: flex; align-items: center; justify-content: center; gap: 20px;
    }
    .hero-subtitle { font-size: 20px; opacity: 0.9; font-weight: 300; margin-top: 10px; }
    
    /* Styling Header Bagian */
    .section-header {
        font-size: 22px; font-weight: bold; color: #444; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #eee; padding-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. BANNER UTAMA ---
st.markdown("""
<div class="hero-box">
    <div class="hero-title">
        <span>💧</span> SmartStudio
    </div>
    <div class="hero-subtitle">Integrated Water Resources & Irrigation System</div>
</div>
""", unsafe_allow_html=True)

# --- 4. MENU NAVIGASI ---

# KELOMPOK 1: AGRONOMI & KLIMATOLOGI
st.markdown('<div class="section-header">☀️ Agronomi & Klimatologi</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/1_Klimatologi.py", label="Modul 1: Klimatologi & ETo", icon="☀️", use_container_width=True)
with col2:
    st.page_link("pages/2_Pola_Tanam.py", label="Modul 2: Pola Tanam & NFR", icon="🌾", use_container_width=True)

# KELOMPOK 2: HIDROLOGI SUMBER DAYA AIR
st.markdown('<div class="section-header">🌊 Analisa Hidrologi</div>', unsafe_allow_html=True)
col3, col4 = st.columns(2)
with col3:
    st.page_link("pages/3_FJ_Mock.py", label="Modul 3: Debit Andalan (Mock)", icon="🌊", use_container_width=True)
with col4:
    # MODUL BARU KITA
    st.page_link("pages/6_Analisa_Banjir.py", label="Modul 6: Debit Banjir Rencana", icon="⛈️", use_container_width=True)

# KELOMPOK 3: HIDROLIKA & BANGUNAN
st.markdown('<div class="section-header">🏗️ Desain Hidrolika</div>', unsafe_allow_html=True)
col5, col6 = st.columns(2)
with col5:
    st.page_link("pages/4_Desain_Saluran.py", label="Modul 4: Desain Saluran Terbuka", icon="🏗️", use_container_width=True)
with col6:
    st.page_link("pages/5_Irigasi_Pipa.py", label="Modul 5: Irigasi Pipa & Pompa", icon="🚰", use_container_width=True)

st.divider()
st.caption("SmartStudio © 2025 | Water Engineering Division")
