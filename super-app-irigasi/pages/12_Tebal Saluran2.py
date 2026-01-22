import streamlit as st
import pandas as pd
import math

# --- 1. CONFIGURASI HALAMAN (DENGAN PENGAMAN) ---
try:
    st.set_page_config(page_title="Cek Tebal Saluran", layout="centered")
except:
    pass # Lewati jika config sudah di-set di main app

# --- 2. JUDUL ---
st.title("🌊 Cek Tebal Saluran Irigasi")
st.caption("Status: ✅ Aplikasi Berjalan Normal")
st.divider()

# --- 3. FUNGSI PERHITUNGAN (UPDATE PARAMETER M) ---
def hitung_ded_fix(h_saluran, b_saluran, m_talud, fc):
    try:
        # Parameter Tetap
        gamma_air   = 9.81   # kN/m3
        gamma_tanah = 18.0   # kN/m3
        ka          = 0.33   # Koefisien tanah aktif
        selimut     = 0.04   # 4 cm
        
        # --- A. GEOMETRI BARU ---
        # Hitung Panjang Sisi Miring (Slant Length)
        # Rumus Pythagoras: L = H * sqrt(1 + m^2)
        panjang_sisi_miring = h_saluran * math.sqrt(1 + m_talud**2)
        
        # --- B. ANALISA BEBAN (LOAD) ---
        # Catatan: Untuk keamanan (konservatif), beban Momen & Geser 
        # tetap dihitung berdasarkan Tinggi Vertikal (H) karena tekanan air/tanah
        # adalah fungsi dari kedalaman (depth), bukan kemiringan.
        
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

        # --- C. HITUNG KEBUTUHAN TEBAL ---
        
        # 1. Cek Lentur (Flexure)
        # Rn asumsi 2000 (konservatif K-250)
        d_lentur = (Mu_desain / (0.85 * 2000))**0.5
        
        # 2. Cek Geser (Shear)
        # Kuat geser beton = 0.17 * sqrt(fc dalam MPa) * 1000 (ke kPa)
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
        # UPDATE: Gunakan Panjang Sisi Miring / 12 (Bukan H vertikal)
        # Dinding miring lebih panjang, jadi butuh lebih tebal agar kaku.
        t_empiris = panjang_sisi_miring / 12
        
        # Ambil MAX, minimal 10 cm
        t_final = max(t_struktural, t_empiris, 0.10)
        
        return {
            "H (m)": h_saluran,
            "B (m)": b_saluran,
            "m (Talud)": m_talud,
            "Sisi Miring (m)": round(panjang_sisi_miring, 2),
            "Mu (kNm)": round(Mu_desain, 2),
            "Vu (kN)": round(Vu_desain, 2),
            "Kondisi": kondisi,
            "t Struktur (cm)": round(t_struktural * 100, 2),
            "t Empiris (L/12)": round(t_empiris * 100, 2), # Label diperjelas
            "REKOMENDASI (cm)": round(t_final * 100, 1)
        }
        
    except Exception as e:
        return {"Error": str(e)}

# --- 4. INPUT SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Input Data")
    h_in = st.number_input("Tinggi Dinding (H)", value=1.4, step=0.1)
    b_in = st.number_input("Lebar Dasar (B)", value=4.2, step=0.1)
    
    # INPUT BARU: KEMIRINGAN TALUD (m)
    m_in = st.number_input("Kemiringan Talud (m)", value=0.0, step=0.1, help="0=Tegak, 1=Miring 1:1")
    
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    st.info(f"fc' {fc_in} MPa setara K-{int(fc_in/0.083)}")

# --- 5. TAMPILKAN HASIL ---
hasil = hitung_ded_fix(h_in, b_in, m_in, fc_in)

if "Error" in hasil:
    st.error(f"Terjadi Kesalahan: {hasil['Error']}")
else:
    # Tampilkan Metric
    col1, col2, col3, col4 = st.columns(4) # Tambah 1 kolom
    col1.metric("Tinggi (H)", f"{hasil['H (m)']} m")
    col2.metric("Talud (m)", f"{hasil['m (Talud)']}")
    
    # Logic warna
    warna = "normal" if hasil['REKOMENDASI (cm)'] <= 25 else "inverse"
    col3.metric("Sisi Miring", f"{hasil['Sisi Miring (m)']} m", help="Panjang dinding beton sebenarnya")
    col4.metric("REKOMENDASI", f"{hasil['REKOMENDASI (cm)']} cm", delta="DED OK", delta_color=warna)

    # Tabel Detail
    st.subheader("📋 Rincian Perhitungan")
    df = pd.DataFrame([hasil]).T
    df.columns = ["Nilai"]
    st.table(df)
    
    # Pesan Kesimpulan
    if m_in > 0:
        st.info(f"ℹ️ Karena talud miring (m={m_in}), syarat kekakuan dihitung dari panjang sisi miring ({hasil['Sisi Miring (m)']} m), bukan tinggi tegak.")
    
    if hasil['REKOMENDASI (cm)'] > 20:
        st.warning(f"⚠️ Tebal {hasil['REKOMENDASI (cm)']} cm cukup tebal. Coba cek Mutu Beton.")
    else:
        st.success(f"✅ Tebal {hasil['REKOMENDASI (cm)']} cm aman.")
