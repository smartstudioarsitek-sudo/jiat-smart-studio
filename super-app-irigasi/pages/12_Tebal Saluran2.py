import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI & JUDUL ---
st.set_page_config(page_title="Estimator SE 182/2025", layout="wide")
st.title("🌊 Estimator Saluran Terpadu (SE No. 182/2025)")
st.caption("Referensi: Lampiran IV (SDA) & Lampiran VI (CK) - Kementerian PU")

# --- 2. INPUT PARAMETER ---
with st.sidebar:
    st.header("📐 Dimensi Saluran")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6)
    m_in = st.number_input("Kemiringan (m)", value=1.0, help="1=Trapesium 45°")
    
    st.header("⛓️ Penulangan (BBS)")
    dia_in = st.number_input("Diameter Besi (mm)", value=10)
    jarak_in = st.number_input("Jarak (cm)", value=20)
    lapis_in = st.radio("Lapis Tulangan", [1, 2], index=1)
    waste_in = st.slider("Waste/BBS Factor (%)", 0, 15, 7)
    
    st.header("💰 Overhead")
    oh_in = st.slider("Overhead & Profit (%)", 10, 15, 10)

# --- 3. LOGIKA PERHITUNGAN (SESUAI GEOMETRI & SE 182) ---
# Geometri
s_miring = h_in * math.sqrt(1 + m_in**2)
keliling = b_in + (2 * s_miring)

# Perhitungan Tebal (Rumus Struktur Bapak tetap dipertahankan)
# (Asumsi tebal final dari input user/rekomendasi)
t_m = st.number_input("Tebal Beton Final (m)", value=0.15)

# Volume Pekerjaan per meter lari (m')
vol_beton = keliling * t_m
luas_bekisting = (2 * s_miring) + (2 * s_miring) # Dinding Luar + Dalam

# Berat Besi (Standard Berat Jenis 0.00617)
berat_m = 0.00617 * (dia_in**2)
jml_batang = (100 / jarak_in) + 1
berat_netto = (2 * jml_batang) * berat_m * lapis_in
total_besi_bbs = keliling * berat_netto * (1 + waste_in/100)

# --- 4. TAMPILAN OUTPUT ---
st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("Vol Beton (m3/m')", f"{vol_beton:.3f}")
col2.metric("Berat Besi (kg/m')", f"{total_besi_bbs:.2f}")
col3.metric("Luas Bekisting (m2/m')", f"{luas_bekisting:.2f}")

# --- 5. TABEL AHSP (REPLIKA PDF) ---
st.subheader("📋 Ringkasan Volume BoQ (Sesuai SE 182/2025)")
df_rab = pd.DataFrame({
    "Uraian Pekerjaan": ["Beton Struktur", "Baja Tulangan", "Bekisting Kayu"],
    "Volume": [vol_beton, total_besi_bbs, luas_bekisting],
    "Satuan": ["m3", "kg", "m2"],
    "Referensi Analisa": ["Lamp. IV SDA", "Lamp. VI CK", "Lamp. VI CK"]
})
st.table(df_rab)
