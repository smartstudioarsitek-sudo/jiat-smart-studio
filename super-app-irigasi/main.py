import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- CSS BANNER GRADASI ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 40px; 
        border-radius: 15px; 
        color: white; 
        text-align: center; 
        margin-bottom: 25px;
    }
</style>
<div class="hero-box">
    <h1>🏗️ SmartStudio</h1>
    <p>Integrated Water Resources & Infrastructure Management System</p>
</div>
""", unsafe_allow_html=True)


st.markdown("""
<div style='text-align: left; margin-bottom: 30px;'>
    <h2 style='margin-bottom: 0;'>💧 SmartStudio</h2>
    <p style='color: #666;'> Tahun: 2025</p>
</div>
""", unsafe_allow_html=True)

# --- MENU GRID ---
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
st.caption("Smart Studio © 2025 | Engineering Division")