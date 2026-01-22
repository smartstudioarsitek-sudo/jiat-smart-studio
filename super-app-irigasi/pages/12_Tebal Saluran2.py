import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN ---
try:
    st.set_page_config(page_title="Cek Tebal Saluran", layout="centered")
except:
    pass 

# --- 2. JUDUL ---
st.title("🌊 Cek Tebal & Perimeter Saluran")
st.caption("Status: ✅ Aplikasi Berjalan Normal")
st.divider()

# --- 3. FUNGSI PERHITUNGAN (UPDATE PERIMETER) ---
def hitung_ded_fix(h_saluran, b_saluran, m_talud, fc):
    try:
        # Parameter Tetap
        gamma_air   = 9.81
        gamma_tanah = 18.0
        ka          = 0.33
        selimut     = 0.04
        
        # --- A. GEOMETRI & PERIMETER ---
        # 1. Panjang Sisi Miring (Slant Length) per satu sisi
        sisi_miring = h_saluran * math.sqrt(1 + m_talud**2)
        
        # 2. Keliling Tampang Basah (Lining Perimeter)
        # Total panjang beton = Lebar Dasar + (2 x Sisi Miring)
        # Ini dipakai untuk menghitung Volume Beton di RAB
        keliling_tampang = b_saluran + (2 * sisi_miring)
        
        # --- B. ANALISA BEBAN ---
        Mu_air = 1.6 * (1/6) * gamma_air * (h_saluran**3)
        Vu_air = 1.6 * 0.5 * gamma_air * (h_saluran**2)
        
        Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_saluran**3)
        Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_saluran**2)
        
        Mu_desain = max(Mu_air, Mu_tanah)
        Vu_desain = max(Vu_air, Vu_tanah)
        kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"

        # --- C. HITUNG KEBUTUHAN TEBAL ---
        # Cek Lentur
        d_lentur = (Mu_desain / (0.85 * 2000))**0.5
        
        # Cek Geser
        kuat_geser_kpa = 0.17 * math.sqrt(fc) * 1000 
        denom = 0.75 * kuat_geser_kpa
        
        if denom > 0:
            d_geser = Vu_desain / denom
        else:
            d_geser = 0.15 
        
        # --- D. KEPUTUSAN FINAL ---
        d_pakai = max(d_lentur, d_geser)
        t_struktural = d_pakai + selimut + 0.006
        
        # Syarat Empiris (Kekakuan)
        t_empiris = sisi_miring / 12
        
        # Ambil MAX, minimal 10 cm
        t_final = max(t_struktural, t_empiris, 0.10)
        
        return {
            "H (m)": h_saluran,
            "B (m)": b_saluran,
            "m (Talud)": m_talud,
            "Sisi Miring (m)": round(sisi_miring, 2),
            "Keliling (m)": round(keliling_tampang, 2), # <-- PARAMETER BARU
            "Mu (kNm)": round(Mu_desain, 2),
            "Vu (kN)": round(Vu_desain, 2),
            "Kondisi": kondisi,
            "t Struktur (cm)": round(t_struktural * 100, 2),
            "t Empiris (cm)": round(t_empiris * 100, 2),
            "REKOMENDASI (cm)": round(t_final * 100, 1)
        }
        
    except Exception as e:
        return {"Error": str(e)}

# --- 4. INPUT SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Input Data")
    h_in = st.number_input("Tinggi Dinding (H)", value=1.4, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=4.2, step=0.1)
    m_in = st.number_input("Kemiringan Talud (m)", value=0.0, step=0.1)
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    
    st.divider()
    st.info("💡 **Tips:** 'Keliling' berguna untuk menghitung kebutuhan bekisting dan volume beton.")

# --- 5. TAMPILKAN HASIL ---
hasil = hitung_ded_fix(h_in, b_in, m_in, fc_in)

if "Error" in hasil:
    st.error(f"Terjadi Kesalahan: {hasil['Error']}")
else:
    # Baris 1: Dimensi & Geometri
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tinggi (H)", f"{hasil['H (m)']} m")
    c2.metric("Talud (m)", f"{hasil['m (Talud)']}")
    c3.metric("Sisi Miring", f"{hasil['Sisi Miring (m)']} m")
    c4.metric("Keliling", f"{hasil['Keliling (m)']} m", help="Panjang total permukaan beton (Lantai + 2 Dinding)")

    # Baris 2: Hasil Struktur
    st.divider()
    c_res1, c_res2, c_res3 = st.columns([1, 1, 2])
    
    c_res1.metric("Momen Desain", f"{hasil['Mu (kNm)']} kNm")
    
    # Warna logic
    warna = "normal" if hasil['REKOMENDASI (cm)'] <= 25 else "inverse"
    c_res3.metric("REKOMENDASI TEBAL", f"{hasil['REKOMENDASI (cm)']} cm", delta="DED Approved", delta_color=warna)

    # Tabel Detail
    st.subheader("📋 Rincian Perhitungan")
    df = pd.DataFrame([hasil]).T
    df.columns = ["Nilai"]
    st.table(df)
    
    if hasil['REKOMENDASI (cm)'] > 20:
        st.warning(f"⚠️ Tebal {hasil['REKOMENDASI (cm)']} cm cukup tebal. Coba cek Mutu Beton.")
    else:
        st.success(f"✅ Tebal {hasil['REKOMENDASI (cm)']} cm aman.")
