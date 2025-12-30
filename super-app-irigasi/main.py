import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="SmartStudio",
    page_icon="💧", 
    layout="wide"
)

# --- CSS KHUSUS (FONT BESAR + LOGO AIR) ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 60px 30px; 
        border-radius: 20px; 
        color: white; 
        text-align: center; 
        margin-bottom: 40px;
    }
    .hero-title { 
        font-size: 70px; /* Font Judul Dibuat Sangat Besar */
        font-weight: 900; 
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 25px;
    }
    .water-logo {
        font-size: 80px; /* Logo Air Dibuat Besar */
    }
</style>
<div class="hero-box">
    <div class="hero-title">
        <span class="water-logo">💧</span> SmartStudio
    </div>
    <p style="font-size: 20px; opacity: 0.9;">Integrated Water Resources & Infrastructure Management System</p>
</div>
""", unsafe_allow_html=True)

# --- MODUL NAVIGASI ---
st.subheader("🛠️ Modul Engineering")
col1, col2 = st.columns(2)

with col1:
    st.page_link("pages/1_Klimatologi.py", label="Klimatologi & ETo", icon="☀️", use_container_width=True)
with col2:
    st.page_link("pages/2_Pola_Tanam.py", label="Pola Tanam & NFR", icon="🌾", use_container_width=True)

# Tambahkan Baris Lainnya Sesuai Kebutuhan