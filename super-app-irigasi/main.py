import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Sistem Irigasi Terpadu",
    page_icon="🌾", # Ganti icon jadi padi
    layout="wide"
)

# --- CSS UNTUK TEMA SAWAH/AIR YANG SEGAR ---
st.markdown("""
<style>
    /* Background Header agak kebiruan dikit */
    .stAppHeader {background-color: #f4f8fb;}
    
    /* Styling Kotak Menu Kartu */
    .box-menu {
        padding: 25px;
        background-color: #ffffff;
        border-radius: 15px;
        border: 1px solid #e3f2fd; /* Border biru muda */
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
        transition: transform 0.3s, box-shadow 0.3s; /* Animasi halus */
    }
    
    /* Efek saat mouse diarahkan ke kotak (Hover) */
    .box-menu:hover {
        transform: translateY(-5px); /* Naik sedikit */
        box-shadow: 0 10px 20px rgba(13, 71, 161, 0.15); /* Bayangan biru */
        border-color: #2196f3; /* Border jadi biru terang */
    }

    .big-icon {
        font-size: 60px;
        margin-bottom: 15px;
        color: #0277bd; /* Warna ikon biru air */
    }
    
    h3 {
        color: #1565c0; /* Warna judul biru tua */
        font-weight: 700;
    }
    
    p {
        color: #546e7a; /* Warna teks abu kebiruan */
    }
</style>
""", unsafe_allow_html=True)

# --- HERO SECTION (JUDUL) ---
st.title("🌾 Sistem Perencanaan Irigasi Terpadu")
st.markdown("### *Integrated Water Resources Management System*")
st.markdown("---")

# --- BANNER IMAGE (TEMA SAWAH/IRIGASI) ---
# Gambar Terasering Sawah yang Segar (Unsplash)
st.image("https://images.unsplash.com/photo-1530507629858-e4977d30e9e0?q=80&w=2500&auto=format&fit=crop", 
         use_column_width=True, 
         caption="Manajemen Air untuk Ketahanan Pangan Berkelanjutan")

st.write("") 
st.write("") 

# --- SAMBUTAN ---
st.info("💧 **Selamat Datang, Engineer!** Platform ini mengintegrasikan analisis hidrologi, kebutuhan air tanaman, dan desain infrastruktur irigasi dalam satu dasbor terpusat.")

# --- MENU GRID (KARTU-KARTU) ---
st.subheader("🗺️ Navigasi Modul")
st.caption("Pilih modul analisis di Sidebar sebelah kiri ( < ) untuk memulai perhitungan.")

# Baris 1
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">☀️</div>
        <h3>Klimatologi & ETo</h3>
        <p>Analisis data cuaca dan perhitungan Evapotranspirasi standar FAO Penman-Monteith.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🌾</div>
        <h3>Pola Tanam & NFR</h3>
        <p>Simulasi jadwal tanam padi/palawija dan hitungan kebutuhan air bersih di sawah (NFR).</p>
    </div>
    """, unsafe_allow_html=True)

# Baris 2
col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🌊</div>
        <h3>Analisis Sungai (Mock)</h3>
        <p>Estimasi ketersediaan debit andalan sungai (Q80%) untuk sumber air irigasi.</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="box-menu">
        <div class="big-icon">🏗️</div>
        <h3>Desain Saluran</h3>
        <p>Kalkulator dimensi saluran terbuka (Batch System) dengan kontrol hidrolis otomatis.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
# Footer dengan sentuhan profesional
st.markdown(
    """
    <div style='text-align: center; color: #78909c; padding: 20px;'>
        Developed with 💙 by <b>JIAT Smart Studio</b> | Water Engineering Division © 2025
    </div>
    """, unsafe_allow_html=True
)