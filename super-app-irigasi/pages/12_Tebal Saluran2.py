import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN (DENGAN PENGAMAN) ---
try:
    st.set_page_config(page_title="Cek Tebal Saluran", layout="centered")
except:
    pass # Lewati jika config sudah di-set di main app

# --- 2. JUDUL (Agar langsung kelihatan kalau app jalan) ---
st.title("🌊 Cek Tebal Saluran Irigasi")
st.caption("Status: ✅ Aplikasi Berjalan Normal")
st.divider()

# --- 3. FUNGSI PERHITUNGAN (LOGIC FIX) ---
def hitung_ded_fix(h_saluran, b_saluran, fc):
    try:
        # Parameter Tetap
        gamma_air   = 9.81   # kN/m3
        gamma_tanah = 18.0   # kN/m3
        ka          = 0.33   # Koefisien tanah aktif
        selimut     = 0.04   # 4 cm
        
        # --- A. ANALISA BEBAN (LOAD) ---
        # Case 1: Air Penuh (Internal)
        Mu_air = 1.6 * (1/6) * gamma_air * (h_saluran**3)
        Vu_air = 1.6 * 0.5 * gamma_air * (h_saluran**2)
        
        # Case 2: Tanah Luar (Eksternal)
        Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_saluran**3)
        Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_saluran**2)
        
        # Ambil Beban Terbesar
        Mu_desain = max(Mu_air, Mu_tanah)
        Vu_desain = max(Vu_air, Vu_tanah)
        
        kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"

        # --- B. HITUNG KEBUTUHAN TEBAL ---
        
        # 1. Cek Lentur (Flexure)
        # Rn asumsi 2000 (konservatif untuk K-250)
        # d = sqrt(Mu / (0.85 * Rn * b)) -> b=1.0m
        d_lentur = (Mu_desain / (0.85 * 2000))**0.5
        
        # 2. Cek Geser (Shear) -> INI YANG KEMARIN ERROR
        # Kuat geser beton = 0.17 * sqrt(fc dalam MPa) * 1000 (ke kPa)
        # Jika fc=20 -> sqrt(20)=4.47 -> kali 1000 = 760 kPa.
        kuat_geser_kpa = 0.17 * math.sqrt(fc) * 1000 
        
        # Faktor reduksi geser = 0.75
        denom = 0.75 * kuat_geser_kpa
        
        if denom > 0:
            d_geser = Vu_desain / denom
        else:
            d_geser = 0.15 # Default safe jika error
        
        # --- C. KEPUTUSAN FINAL ---
        d_pakai = max(d_lentur, d_geser)
        
        # Tebal Struktur = d + selimut + 1/2 diameter tulangan (0.006)
        t_struktural = d_pakai + selimut + 0.006
        
        # Syarat Empiris (Kekakuan) H/12
        t_empiris = h_saluran / 12
        
        # Ambil MAX, minimal 10 cm
        t_final = max(t_struktural, t_empiris, 0.10)
        
        return {
            "H (m)": h_saluran,
            "B (m)": b_saluran,
            "Mu (kNm)": round(Mu_desain, 2),
            "Vu (kN)": round(Vu_desain, 2),
            "Kondisi": kondisi,
            "t Struktur (cm)": round(t_struktural * 100, 2),
            "t H/12 (cm)": round(t_empiris * 100, 2),
            "REKOMENDASI (cm)": round(t_final * 100, 1)
        }
        
    except Exception as e:
        return {"Error": str(e)}

# --- 4. INPUT SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Input Data")
    h_in = st.number_input("Tinggi Dinding (H)", value=1.4, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=4.2, step=0.1)
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    st.info(f"fc' {fc_in} MPa setara K-{int(fc_in/0.083)}")

# --- 5. TAMPILKAN HASIL ---
hasil = hitung_ded_fix(h_in, b_in, fc_in)

if "Error" in hasil:
    st.error(f"Terjadi Kesalahan: {hasil['Error']}")
else:
    # Tampilkan Metric Besar
    col1, col2, col3 = st.columns(3)
    col1.metric("Tinggi Saluran", f"{hasil['H (m)']} m")
    col2.metric("Kondisi Kritis", "Tekanan Air" if "Air" in hasil['Kondisi'] else "Tekanan Tanah")
    
    # Warna logic: Kalau tebal > 20 cm warnanya merah (mencurigakan), kalau ok hijau
    warna = "normal" if hasil['REKOMENDASI (cm)'] <= 20 else "inverse"
    col3.metric("REKOMENDASI TEBAL", f"{hasil['REKOMENDASI (cm)']} cm", delta="Aman DED", delta_color=warna)

    # Tabel Detail
    st.subheader("📋 Rincian Perhitungan")
    df = pd.DataFrame([hasil]).T
    df.columns = ["Nilai"]
    st.table(df)
    
    # Pesan Kesimpulan
    if hasil['REKOMENDASI (cm)'] > 20:
        st.warning(f"⚠️ Tebal {hasil['REKOMENDASI (cm)']} cm terlihat agak boros. Coba cek Mutu Beton atau Tinggi Dinding.")
    else:
        st.success(f"✅ Tebal {hasil['REKOMENDASI (cm)']} cm sudah efisien dan aman sesuai SNI.")
