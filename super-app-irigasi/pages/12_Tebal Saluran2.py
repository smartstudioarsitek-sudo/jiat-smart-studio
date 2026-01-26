import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Estimator - SE 182/2025", layout="wide")

st.title("🌊 QS Estimator: Saluran Terintegrasi (AutoCAD Sync)")
st.caption("Standard: SE No. 182/SE/Dk/2025 | Metodologi: Geometri Presisi (Luas Penampang)")
st.divider()

# --- 2. FUNGSI PERHITUNGAN GEOMETRI PRESISI ---

def hitung_analisa_qs(h, b, m, fc, t_user_cm, dia, jarak_cm, lapis, waste_pct):
    # A. Konstanta
    gamma_air, gamma_tanah, ka, selimut = 9.81, 18.0, 0.33, 0.04
    
    # B. Rekomendasi Struktur (Logic Asli)
    Mu = 1.6 * (1/6) * gamma_air * (h**3)
    d_lentur = (Mu / (0.85 * 2000))**0.5
    sisi_miring_in = h * math.sqrt(1 + m**2)
    t_rekom_m = max(d_lentur + selimut + 0.006, sisi_miring_in / 12, 0.10)
    
    # C. VOLUME BETON (Metode AutoCAD: Selisih Dua Trapesium)
    # Ini adalah kunci sinkronisasi dengan AutoCAD
    t_m = t_user_cm / 100
    area_in = (b + m * h) * h
    # Mencari dimensi trapesium luar yang mengelilingi beton
    w_bot_out = b + 2 * t_m * (math.sqrt(1 + m**2) - m)
    w_top_out = b + 2 * m * h + 2 * t_m * math.sqrt(1 + m**2)
    h_out = h + t_m
    area_out = (w_bot_out + w_top_out) / 2 * h_out
    vol_beton_m1 = area_out - area_in
    
    # D. BERAT BESI (BBS Factor)
    berat_per_m = 0.00617 * (dia**2)
    # Keliling untuk penempatan besi (pendekatan garis tengah beton)
    t_setengah = t_m / 2
    w_mid = b + t_setengah * (math.sqrt(1 + m**2) - m)
    s_mid = (h + t_setengah) * math.sqrt(1 + m**2)
    keliling_besi = w_mid + 2 * s_mid 
    
    jml_batang = (100 / jarak_cm) + 1
    berat_netto_m2 = (2 * jml_batang) * berat_per_m * lapis
    total_besi_m1 = keliling_besi * berat_netto_m2 * (1 + waste_pct/100)
    
    # E. LUAS BEKISTING (Dinding Luar + Dinding Dalam)
    bekisting_m1 = (2 * sisi_miring_in) + (2 * (h + t_m) * math.sqrt(1 + m**2))
    
    return {
        "rekom_cm": round(t_rekom_m * 100, 1),
        "vol_beton": round(vol_beton_m1, 4),
        "berat_besi": round(total_besi_m1, 2),
        "bekisting": round(bekisting_m1, 2)
    }

# --- 3. INPUT SIDEBAR ---
with st.sidebar:
    st.header("📐 1. Geometri Saluran")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6, step=0.1)
    m_in = st.number_input("Talud (m)", value=1.0, help="0=Tegak, 1=Trapesium")
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    
    st.header("⛓️ 2. Penulangan & BBS")
    dia_in = st.number_input("Diameter Besi (mm)", value=10)
    jarak_in = st.number_input("Jarak Tulangan (cm)", value=20)
    lapis_in = st.radio("Jumlah Lapis", [1, 2], index=1)
    waste_in = st.slider("Faktor Waste/BBS (%)", 0, 15, 7)

# --- 4. DISPLAY REKOMENDASI ---
# Hitung dummy untuk mendapatkan rekomendasi tebal
dummy = hitung_analisa_qs(h_in, b_in, m_in, fc_in, 15, dia_in, jarak_in, lapis_in, waste_in)
st.warning(f"💡 **Rekomendasi Tebal Struktural:** {dummy['rekom_cm']} cm")

st.subheader("🛠️ Input Tebal Terpakai")
col_input, _ = st.columns([1, 2])
with col_input:
    t_final_cm = st.number_input("Tebal Beton Final (cm)", value=float(math.ceil(dummy['rekom_cm'])), step=1.0)

# Final Calculation
res = hitung_analisa_qs(h_in, b_in, m_in, fc_in, t_final_cm, dia_in, jarak_in, lapis_in, waste_in)

# --- 5. DASHBOARD HASIL ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Volume Beton (AutoCAD Sync)", f"{res['vol_beton']} m3/m'")
c2.metric("Berat Besi (Inc. BBS)", f"{res['berat_besi']} kg/m'")
c3.metric("Luas Bekisting (Luar+Dalam)", f"{res['bekisting']} m2/m'")

# --- 6. TABEL AHSP & REKAP ---
st.subheader("📋 Rekapitulasi Volume Pekerjaan (Per Meter Lari)")
df = pd.DataFrame({
    "Uraian Pekerjaan": [
        "Beton Struktur (Metode Luas Penampang)", 
        "Penulangan Besi Beton (Inc. Waste)", 
        "Bekisting Kayu (Dinding Luar & Dalam)",
        "Bongkaran Beton Eksisting (Jack Hammer)"
    ],
    "Volume": [res['vol_beton'], res['berat_besi'], res['bekisting'], "Sesuai Lapangan"],
    "Satuan": ["m3", "kg", "m2", "m3"],
    "Spesifikasi Detail": [
        f"Tebal {t_final_cm} cm", 
        f"D{dia_in}-{jarak_in} ({lapis_in} Lapis)", 
        "2 Sisi Dinding",
        "A.2.03.2j.1 (SE 182/2025)"
    ]
})
st.table(df)

with st.expander("🔍 Mengapa Sekarang Sama dengan AutoCAD?"):
    st.write("""
    Metode sebelumnya mengabaikan 'kelebihan' beton di sudut siku/miring. 
    Kode ini sekarang menggunakan **Metode Selisih Poligon**:
    - Luas = Luas Trapesium Luar (termasuk tebal) - Luas Trapesium Dalam (lubang).
    - Cara ini memperhitungkan sudut mati secara presisi, sama seperti AutoCAD.
    """)
