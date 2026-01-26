import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS & Structural Estimator 2025", layout="wide")

st.title("🏗️ Kalkulator Saluran: Struktur & RAB (SE 182/2025)")
st.caption("Sinkronisasi AutoCAD | Analisa Struktur | RAB Terintegrasi")
st.divider()

# --- 2. FUNGSI LOGIKA (GABUNGAN STRUKTUR & GEOMETRI) ---
def hitung_analisa_terpadu(h, b, m, fc, t_user_cm, dia, jarak_cm, lapis, waste_pct):
    # A. Konstanta (Logika Asli Bapak)
    gamma_air, gamma_tanah, ka, selimut = 9.81, 18.0, 0.33, 0.04
    
    # B. ANALISA STRUKTUR (Mencari Rekomendasi Tebal)
    Mu = 1.6 * (1/6) * gamma_air * (h**3)
    d_lentur = (Mu / (0.85 * 2000))**0.5
    sisi_miring_in = h * math.sqrt(1 + m**2)
    # Rumus Tebal Rekomendasi (Original Logic)
    t_rekom_m = max(d_lentur + selimut + 0.006, sisi_miring_in / 12, 0.10)
    
    # C. VOLUME BETON (Metode AutoCAD Sync: Selisih Trapesium)
    t_m = t_user_cm / 100
    area_in = (b + m * h) * h
    h_out = h + t_m
    w_bot_out = b + 2 * t_m * (math.sqrt(1 + m**2) - m)
    w_top_out = b + 2 * m * h + 2 * t_m * math.sqrt(1 + m**2)
    area_out = (w_bot_out + w_top_out) / 2 * h_out
    vol_beton = area_out - area_in
    
    # D. BERAT BESI (BBS Factor)
    berat_per_m = 0.00617 * (dia**2)
    t_mid = t_m / 2
    w_mid = b + t_mid * (math.sqrt(1 + m**2) - m)
    s_mid = (h + t_mid) * math.sqrt(1 + m**2)
    keliling_besi = w_mid + 2 * s_mid 
    
    jml_batang = (100 / jarak_cm) + 1
    berat_netto_m2 = (2 * jml_batang) * berat_per_m * lapis
    total_besi = keliling_besi * berat_netto_m2 * (1 + waste_pct/100)
    
    # E. LUAS BEKISTING (Dinding Luar + Dalam)
    bekisting = (2 * sisi_miring_in) + (2 * (h + t_m) * math.sqrt(1 + m**2))
    
    return {
        "t_rekom_cm": round(t_rekom_m * 100, 1),
        "vol_beton": round(vol_beton, 4),
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

# --- 4. PROSES ANALISA ---
# Mengambil rekomendasi awal berdasarkan input
res_temp = hitung_analisa_terpadu(h_in, b_in, m_in, fc_in, 15, dia_in, jarak_in, lapis_in, waste_in)

st.warning(f"💡 **Rekomendasi Tebal Struktural (Momen {res_temp['Mu']} kNm):** {res_temp['t_rekom_cm']} cm")

st.subheader("🛠️ Penentuan Final")
col_t, _ = st.columns([1, 2])
with col_t:
    t_final_cm = st.number_input("Tebal Beton Terpakai (cm)", value=float(math.ceil(res_temp['t_rekom_cm'])), step=1.0)

# Kalkulasi Final dengan Tebal Terpakai
res = hitung_analisa_terpadu(h_in, b_in, m_in, fc_in, t_final_cm, dia_in, jarak_in, lapis_in, waste_in)

# --- 5. MODUL HARGA (AHSP SE 182/2025) ---
st.divider()
st.header("💰 Estimasi Biaya & AHSP")
with st.expander("📝 Update Harga Satuan Dasar (HSD)"):
    c_upah, c_mat = st.columns(2)
    with c_upah:
        u_pekerja = st.number_input("Pekerja (Rp/OH)", value=110000)
        u_tukang = st.number_input("Tukang (Rp/OH)", value=135000)
        u_mandor = st.number_input("Mandor (Rp/OH)", value=150000)
    with c_mat:
        p_besi = st.number_input("Harga Besi (Rp/kg)", value=14500)
        p_semen = st.number_input("Semen (Rp/kg)", value=1600)
        p_pasir = st.number_input("Pasir (Rp/m3)", value=250000)
        p_split = st.number_input("Split (Rp/m3)", value=350000)
        p_kayu = st.number_input("Kayu Kls III (Rp/m3)", value=2800000)

# Perhitungan Harga Satuan Pekerjaan (HSP) + Overhead 10%
# 1. Beton (A.4.1.1.8)
hsp_beton = ((1.65*u_pekerja + 0.275*u_tukang + 0.083*u_mandor) + (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * 1.10
# 2. Besi (A.4.1.1.17)
hsp_besi = ((0.007*u_pekerja + 0.007*u_tukang + 0.0004*u_mandor) + (1.05*p_besi + 0.015*24000)) * 1.10
# 3. Bekisting (A.4.1.1.21)
hsp_bekisting = ((0.66*u_pekerja + 0.33*u_tukang + 0.033*u_mandor) + (0.045*p_kayu + 0.3*22000 + 0.1*18000)) * 1.10

# --- 6. DISPLAY HASIL AKHIR ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Volume Beton (AutoCAD)", f"{res['vol_beton']} m3/m'")
c2.metric("Berat Besi (BBS)", f"{res['berat_besi']} kg/m'")
c3.metric("Luas Bekisting", f"{res['bekisting']} m2/m'")

# Tabel RAB per meter lari
st.subheader("📋 Rekapitulasi Biaya per Meter Lari (m')")
df_rab = pd.DataFrame({
    "Uraian Pekerjaan": ["Beton K-225 (A.4.1.1.8)", "Penulangan (A.4.1.1.17)", "Bekisting Kayu (A.4.1.1.21)"],
    "Volume": [res['vol_beton'], res['berat_besi'], res['bekisting']],
    "Satuan": ["m3", "kg", "m2"],
    "Harga Satuan (Rp)": [f"{hsp_beton:,.0f}", f"{hsp_besi:,.0f}", f"{hsp_bekisting:,.0f}"],
    "Total (Rp)": [res['vol_beton']*hsp_beton, res['berat_besi']*hsp_besi, res['bekisting']*hsp_bekisting]
})
st.table(df_rab.style.format({"Total (Rp)": "{:,.0f}"}))

st.success(f"### Total RAB Proyek (100m): Rp {( (res['vol_beton']*hsp_beton + res['berat_besi']*hsp_besi + res['bekisting']*hsp_bekisting) * 100):,.0f}")
