import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Hybrid: Beton & Batu", layout="wide")

# --- 2. LOGIKA PERHITUNGAN (DUA MODE) ---

def hitung_beton_struktur(h, b, m, fc, t_cm, dia, jarak, lapis, waste):
    # A. ANALISA MOMEN & TEBAL (LOGIKA ASLI DIPERTAHANKAN)
    gamma_air = 9.81
    selimut = 0.04
    
    # 1. Hitung Momen (Mu) - JANGAN DIUBAH
    Mu = 1.6 * (1/6) * gamma_air * (h**3)
    
    # 2. Hitung Rekomendasi Tebal
    d_lentur = (Mu / (0.85 * 2000))**0.5 
    sisi_miring = h * math.sqrt(1 + m**2)
    t_rekom = max(d_lentur + selimut + 0.006, sisi_miring / 12, 0.10)
    
    # B. VOLUME BETON (AutoCAD Sync)
    t_m = t_cm / 100
    area_in = (b + m * h) * h
    
    # Geometri Luar
    h_out = h + t_m
    w_bot_out = b + 2 * t_m * (math.sqrt(1 + m**2) - m)
    w_top_out = b + 2 * m * h + 2 * t_m * math.sqrt(1 + m**2)
    area_out = (w_bot_out + w_top_out) / 2 * h_out
    
    vol_beton = area_out - area_in
    vol_galian = area_out
    
    # C. BESI & BEKISTING
    berat_m = 0.00617 * (dia**2)
    t_mid = t_m / 2
    keliling_besi = (b + t_mid * (math.sqrt(1+m**2)-m)) + 2*(h+t_mid)*math.sqrt(1+m**2)
    total_besi = keliling_besi * ((2 * (100/jarak + 1)) * berat_m * lapis) * (1 + waste/100)
    bekisting = (2 * sisi_miring) + (2 * (h+t_m) * math.sqrt(1+m**2))
    
    return {
        "tipe": "beton",
        "Mu": Mu, "t_rekom": round(t_rekom*100, 1),
        "v_utama": vol_beton, "v_galian": vol_galian,
        "v_extra1": total_besi, "v_extra2": bekisting
    }

def hitung_pasangan_batu(h, b, m, l_atas, l_bawah, t_lantai):
    # A. VOLUME PASANGAN BATU (GRAVITASI)
    # Dinding (Kiri + Kanan)
    # Luas penampang dinding trapesium = (Lebar Atas + Lebar Bawah) / 2 * Tinggi Tegak
    area_dinding = ((l_atas + l_bawah) / 2) * h
    vol_dinding = 2 * area_dinding
    
    # Lantai (Pondasi Bawah)
    # Asumsi lantai selebar dasar saluran
    vol_lantai = b * t_lantai
    
    vol_batu_total = vol_dinding + vol_lantai
    
    # B. PLESTERAN & SIARAN (Finishing)
    sisi_miring = h * math.sqrt(1 + m**2)
    luas_plester = (2 * sisi_miring) + b # Dinding dalam + lantai
    luas_siaran = 2 * l_atas # Bibir atas saja
    
    # C. GALIAN (Sederhana: Volume Batu + 20%)
    vol_galian = vol_batu_total * 1.2 
    
    return {
        "tipe": "batu",
        "Mu": 0, "t_rekom": 0, # Tidak pakai momen
        "v_utama": vol_batu_total, "v_galian": vol_galian,
        "v_extra1": luas_plester, "v_extra2": luas_siaran
    }

# --- 3. SIDEBAR INPUT ---
with st.sidebar:
    st.header("🏗️ Tipe Konstruksi")
    tipe_konst = st.radio("Pilih Jenis Saluran:", ["Beton Bertulang", "Pasangan Batu Kali"])
    
    st.divider()
    st.header("📋 Identitas Proyek")
    nama_saluran = st.text_input("Nama Ruas", value="Saluran Sekunder 1")
    panjang_total = st.number_input("Panjang (m')", value=100.0)
    
    st.header("📐 Dimensi Saluran")
    h_in = st.number_input("Tinggi (H)", 0.8)
    b_in = st.number_input("Lebar Dasar (B)", 0.6)
    m_in = st.number_input("Kemiringan Talud (m)", 1.0)
    
    # INPUT DINAMIS SESUAI PILIHAN
    if tipe_konst == "Beton Bertulang":
        st.subheader("⚙️ Spesifikasi Beton")
        fc_in = st.selectbox("Mutu Beton", [20, 25, 30])
        t_user = st.number_input("Tebal Dinding (cm)", 15.0)
        
        st.subheader("⛓️ Penulangan")
        dia_in = st.number_input("Diameter Besi (mm)", 10)
        jarak_in = st.number_input("Jarak (cm)", 20)
        lapis_in = st.radio("Lapis", [1, 2], index=1)
        waste_in = st.slider("Waste Besi %", 0, 15, 7)
        
    else: # Pasangan Batu
        st.subheader("🪨 Dimensi Pasangan Batu")
        st.info("Logika Gravitasi (Dinding Trapesium)")
        l_atas_in = st.number_input("Lebar Atas Dinding (m)", value=0.30, min_value=0.2)
        l_bawah_in = st.number_input("Lebar Bawah Dinding (m)", value=0.50, help="Disarankan 0.4 - 0.6 x H")
        t_lantai_in = st.number_input("Tebal Lantai Saluran (m)", value=0.20)

# --- 4. ENGINE HITUNG ---
st.title(f"🛠️ Estimator: {tipe_konst}")

if tipe_konst == "Beton Bertulang":
    # Panggil Fungsi Beton (MOMEN TETAP ADA)
    # Hitung dummy untuk rekomendasi dulu
    dummy = hitung_beton_struktur(h_in, b_in, m_in, fc_in, 15, dia_in, jarak_in, lapis_in, waste_in)
    st.info(f"💡 **Analisa Momen (Mu): {dummy['Mu']:.2f} kNm** | Rekomendasi Tebal: **{dummy['t_rekom']} cm**")
    
    # Hitung Final
    res = hitung_beton_struktur(h_in, b_in, m_in, fc_in, t_user, dia_in, jarak_in, lapis_in, waste_in)
    
    # Label untuk Tabel
    lbl_utama = "Beton K-225 (A.4.1.1.8)"
    lbl_extra1 = "Besi Tulangan (A.4.1.1.17)"
    lbl_extra2 = "Bekisting (A.4.1.1.21)"
    sat_utama, sat_ex1, sat_ex2 = "m3", "kg", "m2"

else: # Pasangan Batu
    res = hitung_pasangan_batu(h_in, b_in, m_in, l_atas_in, l_bawah_in, t_lantai_in)
    st.success("✅ Menggunakan Analisa Volume Gravitasi (Tanpa Tulangan)")
    
    # Label untuk Tabel
    lbl_utama = "Pasangan Batu 1:4 (A.3.2.1.2)"
    lbl_extra1 = "Plesteran 1:3 + Acian (A.4.4.2.4)"
    lbl_extra2 = "Siaran 1:2 (A.4.4.2.27)"
    sat_utama, sat_ex1, sat_ex2 = "m3", "m2", "m2"

# --- 5. INPUT HARGA (HSD) ---
st.divider()
with st.expander("💰 Input Harga Satuan Dasar (Upah & Bahan)", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        u_pekerja = st.number_input("Upah Pekerja", 110000)
        u_tukang = st.number_input("Upah Tukang", 135000)
        u_mandor = st.number_input("Upah Mandor", 150000)
        overhead = st.slider("Overhead %", 10, 15, 10)
    with c2: # Bahan Beton
        p_semen = st.number_input("Semen (kg)", 1600)
        p_pasir = st.number_input("Pasir (m3)", 250000)
        p_split = st.number_input("Split (m3)", 350000)
        p_besi = st.number_input("Besi (kg)", 14500)
    with c3: # Bahan Batu & Bekisting
        p_batu = st.number_input("Batu Belah (m3)", 280000)
        p_kayu = st.number_input("Papan Bekisting (m3)", 2800000)

# HITUNG HSP (OTOMATIS SESUAI PILIHAN)
oh = 1 + (overhead/100)
hsp_galian = ((0.75*u_pekerja)+(0.025*u_mandor)) * oh

if tipe_konst == "Beton Bertulang":
    hsp_utama = ((1.65*u_pekerja + 0.275*u_tukang + 0.083*u_mandor) + (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * oh
    hsp_ex1 = ((0.007*u_pekerja + 0.007*u_tukang + 0.0004*u_mandor) + (1.05*p_besi + 0.015*24000)) * oh
    hsp_ex2 = ((0.66*u_pekerja + 0.33*u_tukang + 0.033*u_mandor) + (0.045*p_kayu + 0.3*22000)) * oh
else: # Pasangan Batu (HSP BEDA)
    # A.3.2.1.2 Pasangan Batu (1.2 m3 Batu, 163 kg Semen, 0.52 m3 Pasir)
    hsp_utama = ((1.5*u_pekerja + 0.75*u_tukang + 0.075*u_mandor) + (1.2*p_batu + 163*p_semen + 0.52*p_pasir)) * oh
    # Plesteran (Estimasi 6 kg Semen, 0.02 Pasir per m2)
    hsp_ex1 = ((0.3*u_pekerja + 0.15*u_tukang) + (6*p_semen + 0.024*p_pasir)) * oh
    # Siaran
    hsp_ex2 = ((0.15*u_pekerja + 0.075*u_tukang) + (3*p_semen + 0.01*p_pasir)) * oh

# --- 6. OUTPUT RAB ---
st.subheader("📊 Rekapitulasi Biaya (RAB)")
df = pd.DataFrame({
    "Uraian Pekerjaan": ["Galian Tanah", lbl_utama, lbl_extra1, lbl_extra2],
    "Volume": [res['v_galian']*panjang_total, res['v_utama']*panjang_total, res['v_extra1']*panjang_total, res['v_extra2']*panjang_total],
    "Satuan": ["m3", sat_utama, sat_ex1, sat_ex2],
    "Harga Satuan": [hsp_galian, hsp_utama, hsp_ex1, hsp_ex2]
})
df["Total Harga (Rp)"] = df["Volume"] * df["Harga Satuan"]

st.dataframe(df.style.format({"Volume": "{:.2f}", "Harga Satuan": "{:,.0f}", "Total Harga (Rp)": "{:,.0f}"}), use_container_width=True)
st.success(f"### 💰 Total Anggaran: Rp {df['Total Harga (Rp)'].sum():,.0f}")

# --- 7. EXPORT ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RAB')
    return output.getvalue()

st.download_button("📥 Download Excel", to_excel(df), f"RAB_{nama_saluran}.xlsx")
