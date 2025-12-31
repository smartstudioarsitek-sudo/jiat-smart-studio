import streamlit as st
import pandas as pd

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Klimatologi & ETo", layout="wide", page_icon="☀️")

# --- 2. HEADER SMARTSTUDIO ---
st.markdown("""
<style>
    .hero-box-small {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 25px; border-radius: 15px; color: white; text-align: center; margin-bottom: 20px;
    }
</style>
<div class="hero-box-small">
    <h1 style="font-size: 40px; margin:0;">☀️ Klimatologi & Evapotranspirasi (ETo)</h1>
    <p style="font-size: 16px; opacity: 0.9;">Pusat Data Meteorologi Terpadu</p>
</div>
""", unsafe_allow_html=True)

# --- 3. INPUT DATA METEOROLOGI ---
st.subheader("📝 Tabel Input Data Bulanan")

bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
         'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

# Template data awal
if 'df_eto' not in st.session_state:
    st.session_state.df_eto = pd.DataFrame({
        'Bulan': bulan,
        'Suhu (°C)': [27.5]*12,
        'Kelembaban (%)': [80]*12,
        'Kec. Angin (m/s)': [2.1]*12,
        'Penyinaran (%)': [65]*12,
        'ETo (mm/hari)': [3.5, 3.8, 4.0, 4.2, 3.9, 3.7, 3.8, 4.1, 4.5, 4.8, 4.2, 3.6]
    })

# Editor tabel dengan font yang jelas
df_input = st.data_editor(
    st.session_state.df_eto,
    use_container_width=True,
    num_rows="fixed",
    key="eto_editor_v1"
)

# --- 4. TOMBOL SIMPAN KE MEMORI (SESSION STATE) ---
st.divider()
col1, col2 = st.columns([1, 4])

with col1:
    if st.button("💾 Simpan Data ETo", use_container_width=True):
        # Menyimpan kolom ETo ke session_state agar bisa dibaca di Pola Tanam
        st.session_state['data_eto_transfer'] = df_input['ETo (mm/hari)'].tolist()
        st.session_state.df_eto = df_input
        st.success("Data berhasil dikunci!")

with col2:
    if 'data_eto_transfer' in st.session_state:
        st.info("💡 Data ETo sekarang tersedia untuk digunakan di Modul Pola Tanam & NFR.")

# --- 5. VISUALISASI SEDERHANA ---
st.subheader("📊 Grafik Tren ETo Bulanan")
st.line_chart(df_input.set_index('Bulan')['ETo (mm/hari)'])