import streamlit as st
import pandas as pd

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Klimatologi & ETo", layout="wide", page_icon="☀️")

# --- 2. TAMPILAN HEADER (FONT BESAR + LOGO AIR) ---
st.markdown("""
<style>
    .hero-box-small {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 30px; border-radius: 15px; color: white; text-align: center; margin-bottom: 25px;
    }
    /* Font tabel diperbesar agar jelas */
    div[data-testid="stDataFrame"] { font-size: 18px !important; }
</style>
<div class="hero-box-small">
    <h1 style="font-size: 45px; margin:0;">☀️ Modul Klimatologi & ETo</h1>
    <p style="font-size: 18px; opacity: 0.9;">Penyusunan Data Evapotranspirasi Potensial</p>
</div>
""", unsafe_allow_html=True)

# --- 3. INPUT DATA BULANAN ---
st.subheader("📝 Input Data Meteorologi")

bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
         'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

# Inisialisasi data di memori aplikasi (Session State)
if 'df_eto' not in st.session_state:
    st.session_state.df_eto = pd.DataFrame({
        'Bulan': bulan,
        'ETo (mm/hari)': [3.5, 3.8, 4.0, 4.2, 3.9, 3.7, 3.8, 4.1, 4.5, 4.8, 4.2, 3.6]
    })

# Editor Tabel
df_input = st.data_editor(
    st.session_state.df_eto,
    use_container_width=True,
    num_rows="fixed",
    key="eto_editor_v1"
)

# --- 4. TOMBOL PENGIRIM DATA (PENTING!) ---
st.divider()
if st.button("🚀 Simpan & Kirim ke Pola Tanam", use_container_width=True):
    # Data disimpan ke kunci 'data_eto_transfer' agar bisa dibaca halaman lain
    st.session_state['data_eto_transfer'] = df_input['ETo (mm/hari)'].tolist()
    st.session_state.df_eto = df_input
    st.success("✅ Data ETo berhasil dikunci dan dikirim ke Modul Pola Tanam!")

# --- 5. GRAFIK TREN ---
st.subheader("📊 Grafik Tren ETo")
st.line_chart(df_input.set_index('Bulan'))

st.caption("SmartStudio © 2025 | Water Engineering Division")
