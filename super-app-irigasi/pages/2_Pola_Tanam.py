import streamlit as st
import pandas as pd

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Pola Tanam & NFR", layout="wide", page_icon="🌾")

# --- 2. TAMPILAN HEADER (TEMA BIRU SMARTSTUDIO) ---
st.markdown("""
<style>
    .hero-box-small {
        background: linear-gradient(120deg, #1b5e20 0%, #2e7d32 50%, #4caf50 100%);
        padding: 30px; border-radius: 15px; color: white; text-align: center; margin-bottom: 25px;
    }
    div[data-testid="stDataFrame"] { font-size: 16px !important; }
</style>
<div class="hero-box-small">
    <h1 style="font-size: 45px; margin:0;">🌾 Modul Pola Tanam & NFR</h1>
    <p style="font-size: 18px; opacity: 0.9;">Perhitungan Kebutuhan Air Irigasi di Sawah (NFR)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. PENGAMBILAN DATA OTOMATIS (SESSION STATE) ---
st.subheader("⚙️ Sinkronisasi Data")

# Mengecek apakah ada data kiriman dari Modul 1
if 'data_eto_transfer' in st.session_state:
    eto_otomatis = st.session_state['data_eto_transfer']
    st.success("✅ Data ETo berhasil ditarik otomatis dari Modul Klimatologi.")
else:
    eto_otomatis = [0.0] * 12
    st.warning("⚠️ Data ETo belum tersedia. Silakan isi dan 'Simpan' di Modul Klimatologi agar otomatis terisi di sini.")

# --- 4. TABEL PERHITUNGAN NFR ---
bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
         'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

# Template data Pola Tanam
df_pola = pd.DataFrame({
    'Bulan': bulan,
    'ETo (mm/hari)': eto_otomatis,
    'Koef Tanaman (Kc)': [1.1] * 12,
    'Perkolasi (P)': [2.0] * 12,
    'Hujan Efektif (Re)': [0.0] * 12
})

st.write("Silakan sesuaikan nilai Kc, Perkolasi, dan Hujan Efektif di bawah ini:")
df_nfr_input = st.data_editor(df_pola, use_container_width=True, key="nfr_editor")

# --- 5. LOGIKA HITUNG NFR ---
# Rumus Sederhana: NFR = (ETo * Kc + P - Re) / 8.64 (untuk merubah ke lt/dt/ha)
nfr_list = []
for i, row in df_nfr_input.iterrows():
    nfr_val = (row['ETo (mm/hari)'] * row['Koef Tanaman (Kc)'] + row['Perkolasi (P)'] - row['Hujan Efektif (Re)'])
    # Pastikan tidak negatif
    nfr_list.append(max(0, round(nfr_val, 3)))

df_nfr_input['NFR (lt/dt/ha)'] = nfr_list

# --- 6. TOMBOL SIMPAN HASIL KE DESAIN SALURAN ---
st.divider()
nfr_max = max(nfr_list)

col1, col2 = st.columns([2, 1])
with col1:
    st.dataframe(df_nfr_input[['Bulan', 'NFR (lt/dt/ha)']], use_container_width=True)

with col2:
    st.metric("NFR Maksimum", f"{nfr_max} lt/dt/ha")
    if st.button("🚀 Kirim NFR ke Desain Saluran", use_container_width=True):
        st.session_state['nfr_global'] = nfr_max
        st.success(f"Nilai {nfr_max} dikunci sebagai Modulus!")

st.caption("SmartStudio © 2025 | Water Engineering Division")
