import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="JIAT Smart Studio",
    page_icon="🏗️", 
    layout="wide"
)

# --- CSS BANNER GRADASI ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 40px; border-radius: 15px; color: white; text-align: center; margin-bottom: 25px;
    }
</style>
<div class="hero-box">
    <h1>🏗️ Sistem Perencanaan Irigasi Terpadu</h1>
    <p>Integrated Water Resources & Infrastructure Management System</p>
</div>
""", unsafe_allow_html=True)

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

# Baris 3 - Modul Pipa (JIAT)
st.write("")
st.page_link("pages/5_Irigasi_Pipa.py", label="Irigasi Pipa & Pompa (JIAT)", icon="💧", use_container_width=True)

st.divider()
st.caption("JIAT Smart Studio © 2025 | Engineering Division")