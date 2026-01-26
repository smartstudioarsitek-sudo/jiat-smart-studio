import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Estimator - Saluran Terpadu", layout="wide")

st.title("🏗️ Saluran SDA: Rekomendasi Struktur & Input Terpakai")
st.caption("Standard: Permen PUPR 2025 | Lokasi: Bengkulu")
st.divider()

# --- 2. FUNGSI ANALISA STRUKTUR (Mencari Rekomendasi) ---
def analisa_rekomendasi(h_saluran, b_saluran, m_talud, fc):
    gamma_air, gamma_tanah, ka, selimut = 9.81, 18.0, 0.33, 0.04
    sisi_miring = h_saluran * math.sqrt(1 + m_talud**2)
    
    # Hitung Momen & Geser
    Mu = 1.6 * (1/6) * gamma_air * (h_saluran**3)
    Vu = 1.6 * 0.5 * gamma_air * (h_saluran**2)
    
    d_lentur = (Mu / (0.85 * 2000))**0.5
    t_struktural = d_lentur + selimut + 0.006
    t_empiris = sisi_miring / 12
    t_min = max(t_struktural, t_empiris, 0.10)
    
    return round(t_min * 100, 1), sisi_miring, (b_saluran + 2 * sisi_miring)

# --- 3. INPUT SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Input Parameter")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6, step=0.1)
    m_in = st.number_input("Talud (m)", value=1.0)
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    
# --- 4. PROSES PERHITUNGAN ---
t_rekom, s_miring, keliling = analisa_rekomendasi(h_in, b_in, m_in, fc_in)

# Tampilkan Rekomendasi Dulu
st.warning(f"💡 **Rekomendasi Tebal Struktural:** {t_rekom} cm")

# --- 5. INPUT TEBAL TERPAKAI (USER DECISION) ---
st.subheader("🛠️ Penentuan Tebal & Volume")
col_input, col_empty = st.columns([1, 2])
with col_input:
    # Default value otomatis mengikuti rekomendasi
    t_terpakai_cm = st.number_input("Masukkan Tebal Terpakai (cm)", value=float(math.ceil(t_rekom)), step=1.0)

# --- 6. HITUNG QUANTITY BERDASARKAN TEBAL TERPAKAI ---
t_m = t_terpakai_cm / 100
vol_beton = keliling * t_m
berat_besi = keliling * 14.81 # Rasio D10-200 2 lapis
bekisting = (2 * s_miring) + (2 * s_miring) # Luas Luar + Dalam Dinding

# --- 7. DISPLAY HASIL AKHIR ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Volume Beton", f"{vol_beton:.3f} m3/m'")
c2.metric("Berat Besi (D10-200)", f"{berat_besi:.2f} kg/m'")
c3.metric("Luas Bekisting", f"{bekisting:.2f} m2/m'")

# Tabel Rincian
st.subheader("📋 Daftar Kebutuhan per Meter Lari (m')")
data_rab = {
    "Item Pekerjaan": ["Beton Mutu f'c 20 MPa", "Penulangan (Besi Beton)", "Bekisting Kayu"],
    "Volume": [f"{vol_beton:.3f}", f"{berat_besi:.2f}", f"{bekisting:.2f}"],
    "Satuan": ["m3", "kg", "m2"],
    "Keterangan": [f"Tebal {t_terpakai_cm} cm", "2 Lapis D10-200", "Luar & Dalam Dinding"]
}
st.table(pd.DataFrame(data_rab))

st.info("ℹ️ **Info QS:** Angka di atas adalah per 1 meter panjang saluran. Kalikan dengan total panjang saluran untuk mendapatkan total volume di RAB.")
