import streamlit as st
import pandas as pd

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Klimatologi & ETo", layout="wide", page_icon="☀️")

# --- 2. HEADER SMARTSTUDIO ---
st.markdown("""
<style>
    .hero-box-small {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 30px; border-radius: 15px; color: white; text-align: center; margin-bottom: 25px;
    }
    div[data-testid="stDataFrame"] { font-size: 16px !important; }
</style>
<div class="hero-box-small">
    <h1 style="font-size: 45px; margin:0;">☀️ Klimatologi & ETo</h1>
    <p style="font-size: 18px; opacity: 0.9;">Input Data Meteorologi & Evapotranspirasi</p>
</div>
""", unsafe_allow_html=True)

# --- 3. INPUT DATA METEOROLOGI LENGKAP ---
st.subheader("📝 Input Parameter Meteorologi")
st.info("Ketik data Suhu, Kelembaban, Angin, dan Penyinaran pada tabel di bawah ini:")

bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
         'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

# Inisialisasi Data Lengkap (Saya ganti nama key agar tabel langsung berubah)
if 'df_meteo_lengkap' not in st.session_state:
    st.session_state.df_meteo_lengkap = pd.DataFrame({
        'Bulan': bulan,
        'Suhu Rata-rata (°C)': [27.5] * 12,
        'Kelembaban (%)': [82.0] * 12,
        'Kecepatan Angin (m/s)': [1.8] * 12,
        'Penyinaran Matahari (%)': [65.0] * 12,
        'ETo (mm/hari)': [3.5, 3.8, 4.0, 4.2, 3.9, 3.7, 3.8, 4.1, 4.5, 4.8, 4.2, 3.6]
    })

# Menampilkan Tabel Editor
df_input = st.data_editor(
    st.session_state.df_meteo_lengkap,
    use_container_width=True,
    num_rows="fixed",
    height=460, # Agar tabel terlihat penuh tanpa scroll berlebih
    key="editor_meteo_v2" # Key baru untuk memaksa refresh tampilan
)

# --- 4. TOMBOL SIMPAN ---
st.divider()
col_btn1, col_btn2 = st.columns([1, 3])

with col_btn1:
    if st.button("🚀 Simpan & Kirim Data", use_container_width=True):
        # Simpan ETo ke memori untuk Modul Pola Tanam
        st.session_state['data_eto_transfer'] = df_input['ETo (mm/hari)'].tolist()
        # Simpan tabel lengkap juga (opsional)
        st.session_state.df_meteo_lengkap = df_input
        st.success("✅ Data Tersimpan!")

with col_btn2:
    if 'data_eto_transfer' in st.session_state:
        st.info(f"💡 Data ETo Bulan Januari: {st.session_state['data_eto_transfer'][0]} mm/hari (Siap digunakan di Pola Tanam)")

# --- 5. GRAFIK CHECKSUM ---
st.subheader("📊 Grafik Kontrol")
tab1, tab2 = st.tabs(["ETo & Suhu", "Kelembaban & Penyinaran"])

with tab1:
    st.line_chart(df_input.set_index('Bulan')[['ETo (mm/hari)', 'Suhu Rata-rata (°C)']])
with tab2:
    st.line_chart(df_input.set_index('Bulan')[['Kelembaban (%)', 'Penyinaran Matahari (%)']])

st.caption("SmartStudio © 2025 | Water Engineering Division")
