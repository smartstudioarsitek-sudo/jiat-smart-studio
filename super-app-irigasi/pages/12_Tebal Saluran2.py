import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
try:
    st.set_page_config(page_title="QS Estimator - Saluran SDA", layout="centered")
except:
    pass 

# --- 2. JUDUL ---
st.title("🏗️ QS Calculator: Tebal, Besi & Bekisting")
st.caption("Standard: Permen PUPR No. 182 Tahun 2025 | Wilayah: Bengkulu/Lampung")
st.divider()

# --- 3. FUNGSI PERHITUNGAN (DIPERBARUI) ---
def hitung_rab_detail(h_saluran, b_saluran, m_talud, fc):
    try:
        # Parameter Teknis
        gamma_air   = 9.81
        gamma_tanah = 18.0
        ka          = 0.33
        selimut     = 0.04
        
        # --- A. GEOMETRI & PERIMETER ---
        sisi_miring = h_saluran * math.sqrt(1 + m_talud**2)
        # Keliling basah (dalam)
        keliling_dalam = b_saluran + (2 * sisi_miring)
        
        # --- B. ANALISA STRUKTUR (Mencari Tebal) ---
        Mu_air = 1.6 * (1/6) * gamma_air * (h_saluran**3)
        Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_saluran**3)
        Mu_desain = max(Mu_air, Mu_tanah)
        
        d_lentur = (Mu_desain / (0.85 * 2000))**0.5
        t_struktural = d_lentur + selimut + 0.006
        t_empiris = sisi_miring / 12
        t_final_m = max(t_struktural, t_empiris, 0.10) # m
        
        # --- C. OUTPUT QS (PER METER LARI / m') ---
        # 1. Volume Beton (m3/m')
        vol_beton = keliling_dalam * t_final_m
        
        # 2. Berat Besi (kg/m') 
        # Asumsi: Besi 10-20 (2 lapis) = 14.81 kg/m2 lining
        rasio_besi_m2 = 14.81 
        berat_besi = keliling_dalam * rasio_besi_m2
        
        # 3. Luas Bekisting (m2/m')
        # Asumsi: Bekisting Luar & Dalam pada dinding (Sesuai Standar SDA)
        # Lantai tidak pakai bekisting (di atas pasir)
        luas_bekisting = (2 * sisi_miring) + (2 * sisi_miring)
        
        return {
            "Tebal Rekomendasi (cm)": round(t_final_m * 100, 1),
            "Volume Beton (m3/m')": round(vol_beton, 3),
            "Berat Besi (kg/m')": round(berat_besi, 2),
            "Luas Bekisting (m2/m')": round(luas_bekisting, 2),
            "Keliling Basah (m)": round(keliling_dalam, 2),
            "Sisi Miring (m)": round(sisi_miring, 2)
        }
        
    except Exception as e:
        return {"Error": str(e)}

# --- 4. INPUT SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Parameter Desain")
    h_in = st.number_input("Tinggi Dinding (H)", value=0.8, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=0.6, step=0.1)
    m_in = st.number_input("Kemiringan Talud (m)", value=1.0, step=0.1, help="0=Tegak, 1=Trapesium 45°")
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    st.divider()
    st.warning("⚠️ Berat besi dihitung berdasarkan pola 2 lapis Besi 10 jarak 20cm.")

# --- 5. TAMPILKAN HASIL ---
hasil = hitung_rab_detail(h_in, b_in, m_in, fc_in)

if "Error" in hasil:
    st.error(f"Terjadi Kesalahan: {hasil['Error']}")
else:
    # Baris Utama: Hasil Output RAB
    col1, col2, col3 = st.columns(3)
    col1.metric("Volume Beton", f"{hasil['Volume Beton (m3/m\')']} m3/m'")
    col2.metric("Berat Besi", f"{hasil['Berat Besi (kg/m\')']} kg/m'")
    col3.metric("Luas Bekisting", f"{hasil['Luas Bekisting (m2/m\')']} m2/m'")

    st.divider()
    
    # Detail Struktur
    st.subheader("📋 Rincian Analisa Per Meter Lari")
    df = pd.DataFrame([hasil]).T
    df.columns = ["Nilai Satuan"]
    st.table(df)

    # Reminder PPN & Overhead
    st.info("""
    **Catatan QS:** 1. Harga total di RAB harus dikalikan lagi dengan **Panjang Saluran (L)**.
    2. Jangan lupa menambahkan **Overhead & Profit 15%** dan **PPN 11%** pada rekapitulasi akhir.
    3. Volume Bekisting diasumsikan untuk sisi luar dan dalam dinding saluran.
    """)
