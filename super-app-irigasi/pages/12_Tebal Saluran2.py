import streamlit as st
import pandas as pd
import math

# --- CONFIGURASI ---
st.set_page_config(page_title="QS Estimator - Saluran Terpadu", layout="wide")

st.title("🏗️ Kalkulator Saluran: Struktur + BBS Factor")
st.divider()

# --- INPUT SIDEBAR ---
with st.sidebar:
    st.header("⚙️ 1. Parameter Geometri")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6, step=0.1)
    m_in = st.number_input("Talud (m)", value=1.0)
    
    st.header("⛓️ 2. Spesifikasi Besi")
    dia_in = st.number_input("Diameter Besi (mm)", value=10)
    jarak_in = st.number_input("Jarak Antar Besi (cm)", value=20)
    lapis_in = st.radio("Jumlah Lapis", [1, 2], index=1)
    
    st.header("⚖️ 3. Faktor Waste (BBS)")
    # Input faktor waste (Standard PUPR 5%, Keamanan 10%)
    waste_in = st.slider("Faktor Waste/BBS (%)", 0, 15, 7)

# --- LOGIKA PERHITUNGAN ---
# 1. Geometri
sisi_miring = h_in * math.sqrt(1 + m_in**2)
keliling = b_in + (2 * sisi_miring)

# 2. Berat Besi Teoritis
berat_per_m = 0.00617 * (dia_in**2)
jml_batang = (100 / jarak_in) + 1
panjang_besi_m2 = 2 * jml_batang # 2 arah (X dan Y)
berat_netto_m2 = panjang_besi_m2 * berat_per_m * lapis_in

# 3. Aplikasi Faktor BBS/Waste
faktor_bbs = 1 + (waste_in / 100)
berat_bruto_m2 = berat_netto_m2 * faktor_bbs # Berat yang masuk ke RAB

# 4. Akumulasi per Meter Lari (m')
total_besi_m_lari = keliling * berat_bruto_m2

# --- DISPLAY ---
st.subheader("🛠️ Hasil Perhitungan Volume Besi")
c1, c2, c3 = st.columns(3)

c1.metric("Berat Netto (Tanpa Waste)", f"{keliling * berat_netto_m2:.2f} kg/m'")
c2.metric("Faktor BBS", f"{waste_in} %")
c3.metric("TOTAL BERAT RAB", f"{total_besi_m_lari:.2f} kg/m'", delta=f"Waste: {(total_besi_m_lari - (keliling * berat_netto_m2)):.2f} kg")

st.divider()

# Tabel AHSP
st.subheader("📋 Data Rekapitulasi untuk RAB")
data_rab = {
    "Item": ["Penulangan Besi Beton"],
    "Volume/m'": [f"{total_besi_m_lari:.2f}"],
    "Satuan": ["kg"],
    "Keterangan": [f"D{dia_in}-{jarak_in} | {lapis_in} Lapis | Inc. BBS {waste_in}%"]
}
st.table(pd.DataFrame(data_rab))

with st.expander("🔍 Mengapa harus ada Faktor BBS?"):
    st.write(f"""
    Dalam 1 meter lari saluran, berat teoritis adalah **{(keliling * berat_netto_m2):.2f} kg**. 
    Namun di lapangan, Anda butuh **{total_besi_m_lari:.2f} kg** karena:
    - **Overlap:** Setiap sambungan besi butuh tumpang tindih ±40-50 cm.
    - **Hook:** Tekukan besi di ujung dinding atau pertemuan lantai.
    - **Sisa Potongan:** Besi lonjoran 12m tidak selalu habis terbagi rata.
    """)
