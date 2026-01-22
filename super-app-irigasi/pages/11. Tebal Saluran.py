import streamlit as st
import pandas as pd
import math

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Kalkulator Tebal Saluran Irigasi",
    page_icon="🌊",
    layout="centered"
)

# --- FUNGSI PERHITUNGAN (LOGIC) ---
def hitung_detail_ded_irigasi(h_saluran, b_saluran, fc, fy):
    # 1. PARAMETER DESAIN
    gamma_air   = 9.81   # kN/m3
    gamma_tanah = 18.0   # kN/m3
    ka          = 0.33   # Koefisien tanah aktif
    selimut     = 0.04   # 4 cm
    
    # Konversi
    fc_kpa = fc * 1000

    # 2. ANALISA BEBAN
    # Case A: Air Penuh
    Mu_air = 1.6 * (1/6) * gamma_air * (h_saluran**3)
    Vu_air = 1.6 * 0.5 * gamma_air * (h_saluran**2)
    
    # Case B: Tanah Luar
    Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_saluran**3)
    Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_saluran**2)
    
    # Governing Load
    Mu_desain = max(Mu_air, Mu_tanah)
    Vu_desain = max(Vu_air, Vu_tanah)
    kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"

    # 3. KEBUTUHAN STRUKTURAL
    # Cek Lentur (Rn asumsi 1800)
    d_lentur = (Mu_desain / (0.85 * 1800))**0.5
    
    # Cek Geser
    denom_geser = 0.75 * 0.17 * math.sqrt(fc_kpa)
    d_geser = Vu_desain / denom_geser
    
    # 4. TEBAL AKHIR
    d_pakai = max(d_lentur, d_geser)
    t_struktural = d_pakai + selimut + 0.006  # + setengah dia. tulangan
    
    # Syarat Empiris (Kekakuan) H/12
    t_min_empiris = h_saluran / 12
    
    # Final Decision
    t_final = max(t_struktural, t_min_empiris)
    
    # Pembulatan ke atas (kelipatan 0.5 cm atau 1 cm agar rapi)
    # Kita buat logic: minimal 10 cm, lalu bulatkan 2 desimal
    t_final = max(t_final, 0.10)
    
    return {
        "H (m)": h_saluran,
        "B (m)": b_saluran,
        "Mu (kNm)": round(Mu_desain, 2),
        "Vu (kN)": round(Vu_desain, 2),
        "Kondisi Kritis": kondisi,
        "Tebal Perlu (cm)": round(t_struktural * 100, 2),
        "Syarat H/12 (cm)": round(t_min_empiris * 100, 2),
        "REKOMENDASI (cm)": round(t_final * 100, 1) # 1 desimal
    }

# --- UI STREAMLIT ---
st.title("🌊 Cek Tebal Dinding Saluran")
st.markdown("Alat bantu **DED Irigasi** untuk estimasi tebal beton bertulang.")
st.divider()

# Input di Sidebar
with st.sidebar:
    st.header("Parameter Input")
    h_input = st.number_input("Tinggi Saluran H (m)", min_value=0.1, max_value=5.0, value=1.4, step=0.1)
    b_input = st.number_input("Lebar Dasar B (m)", min_value=0.1, max_value=10.0, value=4.2, step=0.1)
    st.divider()
    fc_input = st.selectbox("Mutu Beton (fc')", [20, 25, 30], index=0, help="20 MPa setara K-250")
    fy_input = st.number_input("Mutu Baja (fy)", value=240, disabled=True, help="Default U-24 polos")

# Hitung
hasil = hitung_detail_ded_irigasi(h_input, b_input, fc_input, fy_input)

# Tampilkan Hasil Utama (Metric)
col1, col2, col3 = st.columns(3)
col1.metric("Tinggi Saluran", f"{hasil['H (m)']} m")
col2.metric("Kondisi Kritis", "Tekanan Air" if "Air" in hasil['Kondisi Kritis'] else "Tekanan Tanah")
col3.metric("Rekomendasi Tebal", f"{hasil['REKOMENDASI (cm)']} cm", delta="Aman untuk DED")

# Tampilkan Detail Perhitungan
st.subheader("📋 Detail Analisa Struktur")
df_res = pd.DataFrame([hasil])

# Format tabel agar lebih enak dibaca (Transpose)
df_display = df_res.T
df_display.columns = ["Nilai"]
st.table(df_display)

# Penjelasan Teknis
with st.expander("Lihat Catatan Teknis"):
    st.markdown("""
    **Metodologi Perhitungan:**
    1. **Beban:** Menggunakan faktor beban 1.6 (SNI) untuk tekanan hidrostatis dan tekanan tanah aktif.
    2. **Struktur:** Mengecek kebutuhan tebal akibat Momen Lentur dan Gaya Geser (*Shear*).
    3. **Empiris:** Memastikan tebal dinding minimal **H/12** agar dinding kaku (*stiff*).
    4. **Output:** Nilai rekomendasi adalah nilai terbesar dari analisis di atas, dibulatkan untuk kemudahan pelaksanaan.
    """)