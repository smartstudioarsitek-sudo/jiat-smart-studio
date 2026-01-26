import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Estimator Lengkap 2025", layout="wide")

st.title("🏗️ Estimator Saluran: Struktur, Galian & RAB (SE 182/2025)")
st.caption("Sinkronisasi AutoCAD | Galian & Timbunan | Analisa AHSP Terpadu")
st.divider()

# --- 2. FUNGSI LOGIKA (GEOMETRI, STRUKTUR & VOLUME) ---
def hitung_analisa_terpadu(h, b, m, fc, t_user_cm, dia, jarak_cm, lapis, waste_pct):
    # A. Konstanta
    gamma_air, gamma_tanah, ka, selimut = 9.81, 18.0, 0.33, 0.04
    
    # B. ANALISA STRUKTUR (Mencari Rekomendasi Tebal)
    Mu = 1.6 * (1/6) * gamma_air * (h**3)
    d_lentur = (Mu / (0.85 * 2000))**0.5
    sisi_miring_in = h * math.sqrt(1 + m**2)
    t_rekom_m = max(d_lentur + selimut + 0.006, sisi_miring_in / 12, 0.10)
    
    # C. HITUNG GEOMETRI PRESISI (AutoCAD Sync)
    t_m = t_user_cm / 100
    
    # 1. Luas Dalam (Air)
    area_in = (b + m * h) * h
    
    # 2. Luas Luar (Beton Terluar / Batas Galian)
    # Ini menghitung dimensi trapesium terluar (tanah yang harus digali)
    h_out = h + t_m
    w_bot_out = b + 2 * t_m * (math.sqrt(1 + m**2) - m)
    w_top_out = b + 2 * m * h + 2 * t_m * math.sqrt(1 + m**2)
    area_out = (w_bot_out + w_top_out) / 2 * h_out
    
    # 3. Volume Beton (Selisih Luar - Dalam)
    vol_beton = area_out - area_in
    
    # 4. Volume Galian (Minimal sebesar Luas Luar Beton)
    vol_galian = area_out 
    
    # D. BERAT BESI
    berat_per_m = 0.00617 * (dia**2)
    t_mid = t_m / 2
    w_mid = b + t_mid * (math.sqrt(1 + m**2) - m)
    s_mid = (h + t_mid) * math.sqrt(1 + m**2)
    keliling_besi = w_mid + 2 * s_mid 
    
    jml_batang = (100 / jarak_cm) + 1
    berat_netto_m2 = (2 * jml_batang) * berat_per_m * lapis
    total_besi = keliling_besi * berat_netto_m2 * (1 + waste_pct/100)
    
    # E. LUAS BEKISTING
    bekisting = (2 * sisi_miring_in) + (2 * (h + t_m) * math.sqrt(1 + m**2))
    
    return {
        "t_rekom_cm": round(t_rekom_m * 100, 1),
        "vol_beton": round(vol_beton, 4),
        "vol_galian": round(vol_galian, 4), # Volume Galian Otomatis
        "berat_besi": round(total_besi, 2),
        "bekisting": round(bekisting, 2),
        "Mu": round(Mu, 2)
    }

# --- 3. INPUT SIDEBAR ---
with st.sidebar:
    st.header("📐 1. Geometri & Mutu")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6, step=0.1)
    m_in = st.number_input("Talud (m)", value=1.0)
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    
    st.header("⛓️ 2. Spesifikasi Besi")
    dia_in = st.number_input("Diameter Besi (mm)", value=10)
    jarak_in = st.number_input("Jarak (cm)", value=20)
    lapis_in = st.radio("Jumlah Lapis", [1, 2], index=1)
    waste_in = st.slider("Waste/BBS (%)", 0, 15, 7)

# --- 4. PROSES & FINALISASI ---
res_temp = hitung_analisa_terpadu(h_in, b_in, m_in, fc_in, 15, dia_in, jarak_in, lapis_in, waste_in)

st.warning(f"💡 **Rekomendasi Tebal Struktur:** {res_temp['t_rekom_cm']} cm | **Momen:** {res_temp['Mu']} kNm")

st.subheader("🛠️ Penentuan Final & Timbunan")
c_tebal, c_timbun, c_oh = st.columns(3)
with c_tebal:
    t_final_cm = st.number_input("Tebal Terpakai (cm)", value=float(math.ceil(res_temp['t_rekom_cm'])), step=1.0)
with c_timbun:
    # Volume timbunan biasanya input manual karena tergantung kondisi lapangan (bahu jalan)
    vol_timbunan_input = st.number_input("Vol. Timbunan (m3/m')", value=0.20, help="Tanah untuk merapikan kiri/kanan saluran")
with c_oh:
    overhead_pct = st.slider("Overhead (%)", 10, 15, 10)

# Hitung Ulang dengan Tebal Final
res = hitung_analisa_terpadu(h_in, b_in, m_in, fc_in, t_final_cm, dia_in, jarak_in, lapis_in, waste_in)

# --- 5. MODUL HARGA (AHSP LENGKAP) ---
st.divider()
st.header("💰 Analisa Harga Satuan (AHSP SE 182/2025)")

with st.expander("📝 Input Harga Upah, Bahan & Alat", expanded=True):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.caption("Upah (Rp/Hari)")
        u_pekerja = st.number_input("Pekerja", value=110000)
        u_tukang = st.number_input("Tukang", value=135000)
        u_mandor = st.number_input("Mandor", value=150000)
    with col_b:
        st.caption("Bahan (Rp)")
        p_besi = st.number_input("Besi (kg)", value=14500)
        p_semen = st.number_input("Semen (kg)", value=1600)
        p_pasir = st.number_input("Pasir (m3)", value=250000)
        p_split = st.number_input("Split (m3)", value=350000)
        p_kayu = st.number_input("Papan (m3)", value=2800000)
    with col_c:
        st.caption("Alat (Rp)")
        sewa_stamper = st.number_input("Sewa Stamper (Hari)", value=150000, help="Untuk pemadatan timbunan")

# --- PERHITUNGAN HSP ---
oh_factor = 1 + (overhead_pct / 100)

# 1. Galian Tanah Biasa Manual (A.2.1.1.1)
# Koef: 0.75 Pekerja + 0.025 Mandor
hsp_galian = ((0.75 * u_pekerja) + (0.025 * u_mandor)) * oh_factor

# 2. Timbunan Kembali Dipadatkan (A.2.2.1.9)
# Koef: 0.50 Pekerja + 0.05 Mandor + 0.05 Sewa Stamper
hsp_timbunan = ((0.50 * u_pekerja) + (0.05 * u_mandor) + (0.05 * sewa_stamper)) * oh_factor

# 3. Beton K-225 (A.4.1.1.8)
hsp_beton = ((1.65*u_pekerja + 0.275*u_tukang + 0.083*u_mandor) + (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * oh_factor

# 4. Penulangan (A.4.1.1.17)
hsp_besi = ((0.007*u_pekerja + 0.007*u_tukang + 0.0004*u_mandor) + (1.05*p_besi + 0.015*24000)) * oh_factor

# 5. Bekisting (A.4.1.1.21)
hsp_bekisting = ((0.66*u_pekerja + 0.33*u_tukang + 0.033*u_mandor) + (0.045*p_kayu + 0.3*22000 + 0.1*18000)) * oh_factor

# --- 6. DISPLAY OUTPUT ---
st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("Vol. Beton (Structure)", f"{res['vol_beton']} m3/m'")
col2.metric("Vol. Galian (Excavation)", f"{res['vol_galian']} m3/m'", help="Area Trapesium Luar Beton")
col3.metric("Harga Galian /m3", f"Rp {hsp_galian:,.0f}")

st.subheader("📋 Rekapitulasi RAB per Meter Lari")

data_rab = {
    "No": ["1", "2", "3", "4", "5"],
    "Uraian Pekerjaan": [
        "Galian Tanah Biasa (Manual)",
        "Beton Mutu f'c 19.3 MPa (K-225)",
        "Baja Tulangan (Polos/Ulir)",
        "Bekisting Dinding Saluran",
        "Timbunan Kembali Dipadatkan"
    ],
    "Analisa": ["A.2.1.1.1", "A.4.1.1.8", "A.4.1.1.17", "A.4.1.1.21", "A.2.2.1.9"],
    "Volume": [res['vol_galian'], res['vol_beton'], res['berat_besi'], res['bekisting'], vol_timbunan_input],
    "Satuan": ["m3", "m3", "kg", "m2", "m3"],
    "Harga Satuan (Rp)": [hsp_galian, hsp_beton, hsp_besi, hsp_bekisting, hsp_timbunan],
    "Total Harga (Rp)": [
        res['vol_galian']*hsp_galian,
        res['vol_beton']*hsp_beton,
        res['berat_besi']*hsp_besi,
        res['bekisting']*hsp_bekisting,
        vol_timbunan_input*hsp_timbunan
    ]
}

df_rab = pd.DataFrame(data_rab)
# Format tampilan Rupiah di Tabel
st.dataframe(df_rab.style.format({
    "Harga Satuan (Rp)": "{:,.0f}",
    "Total Harga (Rp)": "{:,.0f}",
    "Volume": "{:.3f}"
}), hide_index=True, use_container_width=True)

# Total Grand
grand_total = df_rab["Total Harga (Rp)"].sum()
st.success(f"### 💰 Total Biaya Konstruksi per Meter Lari: Rp {grand_total:,.0f}")

with st.expander("ℹ️ Penjelasan Volume Galian Otomatis"):
    st.write("""
    **Volume Galian** dihitung otomatis berdasarkan **Luas Penampang Trapesium Luar** (Luas Beton + Luas Lubang). 
    Ini adalah volume minimal tanah yang harus dibuang agar saluran beton dengan tebal tersebut bisa masuk.
    
    *Rumus: Area Galian = Area Beton + Area Air (Lubang)*
    """)
