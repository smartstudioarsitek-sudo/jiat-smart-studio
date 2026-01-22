import streamlit as st
import pandas as pd
import math

# --- 1. KONFIGURASI HALAMAN (WAJIB PALING ATAS) ---
# Cek apakah config sudah diset oleh main app atau belum. 
# Kalau ini file di folder 'pages/', biasanya config ikut main.
# Tapi untuk aman, kita taruh di blok try.
try:
    st.set_page_config(page_title="Hitung Tebal Saluran", layout="wide")
except:
    pass # Kalau sudah diset di main.py, abaikan saja.

st.title("🌊 Perhitungan DED Saluran Irigasi")
st.markdown("---")

# --- 2. FUNGSI RUMUS (DENGAN PENGAMAN ERROR) ---

def hitung_manning_solver(Q, b, s, n=0.015):
    """
    Mencari tinggi muka air (h) dengan iterasi.
    Diberi pengaman agar tidak endless loop atau divide by zero.
    """
    if Q <= 0 or b <= 0 or s <= 0:
        return 0.0
    
    # Tebakan awal (h = 1 meter)
    h = 1.0
    
    # Maksimal 20 kali percobaan (iterasi)
    for _ in range(20):
        try:
            A = b * h
            P = b + 2 * h
            R = A / P
            
            # Rumus Manning: Q = (1/n) * A * R^(2/3) * S^(1/2)
            Q_hitung = (1/n) * A * (R**(2.0/3.0)) * (s**0.5)
            
            # Cek selisih (Error)
            error = Q - Q_hitung
            
            # Kalau sudah sangat dekat (beda < 0.001), stop.
            if abs(error) < 0.001:
                return h
            
            # Koreksi tinggi air untuk iterasi berikutnya
            # Mencegah pembagian nol
            if Q_hitung < 0.0001: Q_hitung = 0.0001 
            
            ratio = (Q / Q_hitung) ** 0.6
            h = h * ratio
            
        except:
            # Kalau ada error matematika, kembalikan nilai terakhir
            return h
            
    return h

def hitung_struktur_beton(h_dinding, h_air_aktual, fc):
    """
    Menghitung tebal beton berdasarkan beban.
    """
    try:
        # Parameter
        gamma_air   = 9.81  # kN/m3
        gamma_tanah = 18.0  # kN/m3
        ka          = 0.33  # Koefisien tanah aktif
        selimut     = 0.04  # 4 cm
        
        # --- LOAD CASE ---
        # 1. Air Penuh (Beban dari dalam)
        # Kita asumsikan banjir sampai bibir saluran
        Mu_air = 1.6 * (1.0/6.0) * gamma_air * (h_dinding**3)
        Vu_air = 1.6 * 0.5 * gamma_air * (h_dinding**2)
        
        # 2. Tanah Luar (Beban dari luar saat kosong)
        Mu_tanah = 1.6 * (1.0/6.0) * gamma_tanah * ka * (h_dinding**3)
        Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_dinding**2)
        
        # Ambil yang terbesar
        Mu_desain = max(Mu_air, Mu_tanah)
        Vu_desain = max(Vu_air, Vu_tanah)
        kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"
        
        # --- HITUNG TEBAL PERLU ---
        
        # A. Cek Lentur (Flexure)
        # Asumsi Rn = 2000 untuk K-250 (Konservatif)
        d_lentur = (Mu_desain / (0.85 * 2000.0))**0.5 
        
        # B. Cek Geser (Shear) - PERBAIKAN UNIT
        # Kuat Geser Beton = 0.17 * sqrt(fc) -> fc dalam MPa
        # Hasil dikali 1000 agar jadi kPa (kN/m2)
        kuat_geser_kpa = 0.17 * math.sqrt(fc) * 1000
        phi_geser = 0.75
        
        # d_geser = Vu / (phi * Vc * b) -> b = 1.0 meter
        if kuat_geser_kpa > 0:
            d_geser = Vu_desain / (phi_geser * kuat_geser_kpa * 1.0)
        else:
            d_geser = 0.20 # Default kalau error
            
        # --- KEPUTUSAN FINAL ---
        d_pakai = max(d_lentur, d_geser)
        
        # Tebal = d + selimut + 1/2 diameter tulangan (0.006)
        t_calc = d_pakai + selimut + 0.006
        
        # Syarat Empiris (Kekakuan) = H / 12
        t_empiris = h_dinding / 12.0
        
        # Ambil nilai MAX, minimal 10 cm
        t_final = max(t_calc, t_empiris, 0.10)
        
        return t_final, kondisi, Mu_desain, Vu_desain

    except Exception as e:
        # Jika error, return nilai default aman
        return 0.15, f"Error Hitung: {str(e)}", 0, 0

# --- 3. INPUT USER ---

col1, col2 = st.columns(2)

with col1:
    st.info("📥 **Data Dimensi & Hidrolis**")
    Q_in = st.number_input("Debit (Q) m³/s", value=1.54, min_value=0.01)
    b_in = st.number_input("Lebar (B) m", value=4.2, min_value=0.1)
    h_in = st.number_input("Tinggi Dinding (H) m", value=1.4, min_value=0.1)
    
with col2:
    st.warning("⚙️ **Parameter Teknis**")
    s_in = st.number_input("Kemiringan (S)", value=0.0003, format="%.4f")
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30, 35])

# --- 4. EKSEKUSI PERHITUNGAN ---

# Hitung Air dulu
h_air = hitung_manning_solver(Q_in, b_in, s_in)
freeboard = h_in - h_air

# Hitung Struktur
tebal, kondisi_msg, mu, vu = hitung_struktur_beton(h_in, h_air, fc_in)

# Konversi ke cm untuk display
tebal_cm = round(tebal * 100, 1)
tebal_pasang = math.ceil(tebal_cm) # Bulatkan ke atas agar mudah

# --- 5. TAMPILKAN HASIL ---

st.divider()
st.subheader("✅ Hasil Analisa DED")

# Grid Hasil
c_res1, c_res2, c_res3, c_res4 = st.columns(4)

c_res1.metric("Tinggi Air (y)", f"{h_air:.3f} m")
c_res2.metric("Freeboard", f"{freeboard:.3f} m", 
              delta="OK" if freeboard >= 0.3 else "KURANG!", 
              delta_color="normal" if freeboard >= 0.3 else "inverse")
c_res3.metric("Momen Desain", f"{mu:.2f} kNm")
c_res4.metric("Rekomendasi Tebal", f"{tebal_pasang} cm", help=f"Hasil hitungan eksak: {tebal_cm} cm")

# Detail Text
st.caption(f"**Catatan Struktur:** Dimensi dinding dihitung berdasarkan kondisi kritis: *{kondisi_msg}*.")

if tebal_pasang > 20:
    st.error(f"⚠️ Tebal {tebal_pasang} cm terlalu besar? Cek input Tinggi Dinding atau Debit Anda.")
elif tebal_pasang < 10:
    st.info("ℹ️ Secara hitungan tebal < 10 cm cukup, tapi disarankan minimal 10 cm-12 cm untuk pelaksanaan.")
else:
    st.success(f"👍 Tebal {tebal_pasang} cm adalah dimensi yang efisien dan aman.")
