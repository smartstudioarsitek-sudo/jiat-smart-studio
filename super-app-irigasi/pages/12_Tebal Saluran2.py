import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Estimator Terpadu", layout="wide")

st.title("🏗️ Kalkulator Saluran: Struktur, Besi (BBS) & Bekisting")
st.caption("Standard: Permen PUPR 2025 | Wilayah: Bengkulu/Lampung")
st.divider()

# --- 2. FUNGSI ANALISA STRUKTUR (Mencari Rekomendasi Tebal) ---
def analisa_struktur(h_saluran, b_saluran, m_talud, fc):
    gamma_air, gamma_tanah, ka, selimut = 9.81, 18.0, 0.33, 0.04
    sisi_miring = h_saluran * math.sqrt(1 + m_talud**2)
    
    # Hitung Momen Desain sederhana
    Mu = 1.6 * (1/6) * gamma_air * (h_saluran**3)
    d_lentur = (Mu / (0.85 * 2000))**0.5
    
    t_min = max(d_lentur + selimut + 0.006, sisi_miring / 12, 0.10)
    
    return round(t_min * 100, 1), sisi_miring, (b_saluran + 2 * sisi_miring)

# --- 3. INPUT SIDEBAR ---
with st.sidebar:
    st.header("⚙️ 1. Parameter Geometri")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6, step=0.1)
    m_in = st.number_input("Talud (m)", value=1.0, help="0=Tegak, 1=Trapesium")
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    
    st.header("⛓️ 2. Spesifikasi Besi")
    dia_in = st.number_input("Diameter Besi (mm)", value=10)
    jarak_in = st.number_input("Jarak Antar Besi (cm)", value=20)
    lapis_in = st.radio("Jumlah Lapis", [1, 2], index=1)
    waste_in = st.slider("Faktor BBS/Waste Besi (%)", 0, 15, 7)

# --- 4. PROSES ANALISA AWAL ---
t_rekom, s_miring, keliling_beton = analisa_struktur(h_in, b_in, m_in, fc_in)

# Tampilkan Rekomendasi
st.warning(f"💡 **Rekomendasi Tebal Struktural:** {t_rekom} cm")

# --- 5. INPUT TEBAL TERPAKAI ---
st.subheader("🛠️ Penentuan Final & Output Pekerjaan")
col_t, col_empty = st.columns([1, 2])
with col_t:
    t_terpakai_cm = st.number_input("Tebal Beton Terpakai (cm)", value=float(math.ceil(t_rekom)), step=1.0)

# --- 6. LOGIKA PERHITUNGAN VOLUME (QS LOGIC) ---
# A. Volume Beton
t_m = t_terpakai_cm / 100
vol_beton = keliling_beton * t_m

# B. Berat Besi dengan BBS Factor
berat_per_m = 0.00617 * (dia_in**2)
jml_batang_per_m = (100 / jarak_in) + 1
berat_netto_m2 = (2 * jml_batang_per_m) * berat_per_m * lapis_in
berat_bruto_m2 = berat_netto_m2 * (1 + (waste_in/100))
total_berat_besi = keliling_beton * berat_bruto_m2

# C. Luas Bekisting (Dinding Luar + Dalam)
# Lantai tidak dihitung karena dicor di atas pasir
total_bekisting = (2 * s_miring) + (2 * s_miring)

# --- 7. DISPLAY HASIL AKHIR ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Volume Beton", f"{vol_beton:.3f} m3/m'")
c2.metric("Berat Besi (Inc. BBS)", f"{total_berat_besi:.2f} kg/m'")
c3.metric("Luas Bekisting", f"{total_bekisting:.2f} m2/m'")

# Tabel Rekapitulasi untuk RAB
st.subheader("📋 Rekapitulasi Volume per Meter Lari (m')")
data_rab = {
    "Item Pekerjaan": ["Beton Struktur f'c 20 MPa", "Penulangan Besi Beton", "Bekisting Kayu Kelas III"],
    "Volume": [f"{vol_beton:.3f}", f"{total_berat_besi:.2f}", f"{total_bekisting:.2f}"],
    "Satuan": ["m3", "kg", "m2"],
    "Spesifikasi Detail": [
        f"Tebal {t_terpakai_cm} cm", 
        f"D{dia_in}-{jarak_in} ({lapis_in} Lapis, BBS {waste_in}%)", 
        "Dinding Luar & Dalam"
    ]
}
st.table(pd.DataFrame(data_rab))

st.info("📌 **Pesan QS:** Volume di atas baru untuk 1 meter. Kalikan dengan panjang saluran di excel RAB Anda!")
