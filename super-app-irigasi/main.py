import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="JIAT Smart Studio",
    page_icon="💧",
    layout="wide"
)

# --- CSS UNTUK TAMPILAN CANTIK ---
st.markdown("""
<style>
    /* Mengubah warna background header */
    .stAppHeader {background-color: #f0f2f6;}
    
    /* Membuat kotak kartu menu lebih rapi */
    .box-menu {
        padding: 20px;
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
    }
    .big-icon {
        font-size: 50px;
        margin-bottom: 10px;
    }
    h3 {color: #0d47a1;}
</style>
""", unsafe_allow_html=True)

# --- HERO SECTION (JUDUL BESAR) ---
st.title("💧 Sistem Perencanaan Irigasi Terpadu")
st.markdown("### *Integrated Water Resources Management System*")
st.markdown("---")

# --- BANNER IMAGE (Ganti Link Gambar yang Aman) ---
# Kita pakai gambar dari Unsplash yang reliable
st.image("https://images.unsplash.com/photo-1599939571322-792a326991f2?q=80&w=2500&auto=format&fit=crop", 
         use_column_width=True, 
         caption="Sistem Irigasi Modern & Manajemen Sumber Daya Air")

st.write("") # Spasi
st.write("") 

# --- SAMBUTAN ---
st.info("👋 **Selamat Datang, Engineer!** Aplikasi ini dirancang untuk mempermudah perhitungan teknis irigasi dari hulu ke hilir dalam satu platform terintegrasi.")

# --- MENU GRID (KARTU-KARTU) ---
st.subheader("📚 Modul Aplikasi")
st.caption("Silakan pilih modul di Sidebar sebelah kiri ( < ) untuk memulai.")

# Baris 1
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">☀️</div>
        <h3>Klimatologi & ETo</h3>
        <p>Analisis data iklim harian/bulanan dan perhitungan Evapotranspirasi (ETo) metode Penman-Monteith.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🌾</div>
        <h3>Pola Tanam & NFR</h3>
        <p>Perencanaan jadwal tanam, koefisien tanaman (Kc), dan perhitungan kebutuhan air di sawah (NFR/DR).</p>
    </div>
    """, unsafe_allow_html=True)

# Baris 2
col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🌊</div>
        <h3>Analisis Sungai (Mock)</h3>
        <p>Analisis ketersediaan air sungai (Debit Andalan) menggunakan Metode F.J. Mock untuk intake bendung.</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🏗️</div>
        <h3>Desain Saluran</h3>
        <p>Perhitungan dimensi saluran irigasi (Trapesium/Persegi) secara massal (Batch) dengan cek banjir otomatis.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("Developed by **JIAT Smart Studio** © 2025 | Engineering Division")