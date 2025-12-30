import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Sistem Irigasi Terpadu",
    page_icon="💧", 
    layout="wide"
)

# --- CSS TEMA TEKNIK SIPIL ---
st.markdown("""
<style>
    .stAppHeader {background-color: #f8f9fa;}
    
    .box-menu {
        padding: 25px;
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #dee2e6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    
    .box-menu:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        border-color: #0d6efd;
    }

    .big-icon {
        font-size: 60px;
        margin-bottom: 15px;
    }
    
    h3 {color: #0d6efd; font-weight: 700;}
    p {color: #6c757d; font-size: 14px;}
</style>
""", unsafe_allow_html=True)

# --- HERO SECTION ---
st.title("🏗️ Sistem Perencanaan Irigasi Terpadu")
st.markdown("### *Integrated Water Infrastructure Management System*")
st.markdown("---")

# --- BANNER IMAGE (LINK WIKIMEDIA - LEBIH STABIL) ---
# Menggunakan Link Wikimedia Commons (Hoover Dam) yang servernya jarang down
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Hoover_Dam_from_air.jpg/1280px-Hoover_Dam_from_air.jpg", 
         use_container_width=True, 
         caption="Infrastruktur Bendungan & Pengendalian Sumber Daya Air")

st.write("") 

# --- SAMBUTAN ---
st.info("👋 **Selamat Datang, Engineer!** Dashboard ini mengintegrasikan analisis hidrologi hulu, kebutuhan air irigasi, hingga desain teknis saluran hilir.")

# --- MENU GRID ---
st.subheader("🛠️ Modul Engineering")
st.caption("Pilih tools analisis di Sidebar sebelah kiri ( < ) untuk memulai.")

# Baris 1
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">☀️</div>
        <h3>Klimatologi & ETo</h3>
        <p>Analisis data hidroklimatologi dan perhitungan Evapotranspirasi (Penman-Monteith).</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🌾</div>
        <h3>Pola Tanam & NFR</h3>
        <p>Simulasi neraca air lahan, koefisien tanaman (Kc), dan kebutuhan bersih air irigasi (NFR).</p>
    </div>
    """, unsafe_allow_html=True)

# Baris 2
col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🌊</div>
        <h3>Debit Andalan (Mock)</h3>
        <p>Analisis ketersediaan air sungai (Inflow) menggunakan Metode F.J. Mock untuk desain Intake.</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🏗️</div>
        <h3>Desain Saluran</h3>
        <p>Perhitungan dimensi hidrolis saluran (Trapesium/Persegi) dengan kontrol kestabilan aliran.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
# Footer
st.markdown(
    """
    <div style='text-align: center; color: #adb5bd; padding: 20px;'>
        <b>JIAT Smart Studio</b> | Civil & Water Resources Engineering © 2025
    </div>
    """, unsafe_allow_html=True
)