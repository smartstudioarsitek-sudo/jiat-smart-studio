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

No,Uraian Komponen,Kode,Satuan,Koefisien,Harga Satuan (Rp),Jumlah Harga (Rp)
A,TENAGA KERJA,,,,,
1,Pekerja,L.01,OH,"0,0070",...,...
2,Tukang Besi,L.02,OH,"0,0070",...,...
3,Kepala Tukang,L.03,OH,"0,0007",...,...
4,Mandor,L.04,OH,"0,0004",...,...
,Jumlah Harga Tenaga Kerja,,,,,(Total A)
B,BAHAN,,,,,
1,Besi Beton (Polos/Ulir),-,kg,"1,0500",...,...
2,Kawat Beton (Bindraat),-,kg,"0,0150",...,...
,Jumlah Harga Bahan,,,,,(Total B)
C,PERALATAN,,,,,
1,"Alat Bantu (Gunting, Kunci)",-,Set,"0,0100",...,...
,Jumlah Harga Peralatan,,,,,(Total C)
D,Jumlah Harga (A + B + C),,,,,(D)
E,Overhead & Profit (10% - 15%),,,,,(10% x D)
F,HARGA SATUAN PEKERJAAN (HSP),,,,,(D + E)


# ... (Kode Geometri Sebelumnya Tetap Sama) ...

# --- MODUL 3: ANALISA BIAYA (RAB) ---
st.header("💰 3. Estimasi Biaya (RAB Lengkap)")

# A. Input Harga Satuan Dasar (HSD) - Bengkulu
with st.expander("📝 Input Harga Satuan Dasar (Upah & Bahan)", expanded=True):
    col_hsd1, col_hsd2 = st.columns(2)
    with col_hsd1:
        st.caption("Upah Tenaga Kerja")
        upah_pekerja = st.number_input("Upah Pekerja (Rp/OH)", value=110000)
        upah_tukang = st.number_input("Upah Tukang (Rp/OH)", value=135000)
        upah_mandor = st.number_input("Upah Mandor (Rp/OH)", value=150000)
    with col_hsd2:
        st.caption("Harga Bahan Material")
        harga_besi = st.number_input("Besi Beton (Rp/kg)", value=14500)
        harga_kawat = st.number_input("Kawat Beton (Rp/kg)", value=24000)
        harga_kayu = st.number_input("Kayu Kelas III (Rp/m3)", value=2800000)
        harga_paku = st.number_input("Paku (Rp/kg)", value=22000)
        harga_minyak = st.number_input("Minyak Bekisting (Rp/Ltr)", value=18000)

# B. Hitung HSP (Harga Satuan Pekerjaan)
# 1. HSP Penulangan (A.4.1.1.17)
hsp_besi = ((0.007*upah_pekerja + 0.007*upah_tukang + 0.0007*upah_tukang*1.1 + 0.0004*upah_mandor) + \
           (1.05*harga_besi + 0.015*harga_kawat)) * 1.10 # O&P 10%

# 2. HSP Bekisting Dinding (A.4.1.1.21) - Asumsi Pakai Papan
biaya_upah_bek = (0.66*upah_pekerja + 0.33*upah_tukang + 0.033*upah_tukang*1.1 + 0.033*upah_mandor)
biaya_mat_bek = (0.045*harga_kayu + 0.30*harga_paku + 0.10*harga_minyak + 0.015*2500000) # +Balok Kaso
hsp_bekisting = (biaya_upah_bek + biaya_mat_bek) * 1.10

# 3. HSP Beton (Asumsi K-250 Manual / A.4.1.1.8) - Simplified
# Semen 384kg, Pasir 0.49m3, Kerikil 0.77m3 (Standar SNI)
# Kita buat input manual saja untuk HSP Beton agar simple
hsp_beton = st.number_input("HSP Beton f'c 20 MPa (Rp/m3) - Dari Analisa Lain", value=1529264)

# C. Hitung Total Biaya per Meter Lari
biaya_m_beton = res['vol_beton'] * hsp_beton
biaya_m_besi = res['berat_besi'] * hsp_besi # Ingat berat_besi disini harus netto jika koef bahan 1.05
biaya_m_bekisting = res['bekisting'] * hsp_bekisting
total_per_m = biaya_m_beton + biaya_m_besi + biaya_m_bekisting

# D. Output Biaya
st.divider()
st.subheader(f"💵 Total Biaya: Rp {total_per_m:,.0f} / meter lari")

df_biaya = pd.DataFrame({
    "Uraian": ["Beton Struktur", "Penulangan", "Bekisting Dinding"],
    "Vol / m'": [res['vol_beton'], res['berat_besi'], res['bekisting']],
    "HSP (Rp)": [f"{hsp_beton:,.0f}", f"{hsp_besi:,.0f}", f"{hsp_bekisting:,.0f}"],
    "Total (Rp)": [biaya_m_beton, biaya_m_besi, biaya_m_bekisting]
})
st.dataframe(df_biaya.style.format({"Total (Rp)": "{:,.0f}"}))

st.info("💡 **Tips:** Kalikan 'Total Biaya' di atas dengan Panjang Saluran (m) untuk mendapatkan Nilai Kontrak Proyek.")

# ... (Pastikan kode Geometri dan Besi/Bekisting di atasnya sudah ada) ...

# --- MODUL 3: ANALISA BIAYA (RAB LENGKAP - A.4.1.1.8) ---
st.header("💰 3. Estimasi Biaya (RAB Lengkap)")

# A. INPUT HARGA SATUAN DASAR (HSD)
with st.expander("📝 Input Harga Upah & Bahan (Update HSD)", expanded=True):
    col_hsd1, col_hsd2 = st.columns(2)
    
    with col_hsd1:
        st.subheader("👷 Upah Kerja")
        upah_pekerja = st.number_input("Pekerja (Rp/OH)", value=110000)
        upah_tukang = st.number_input("Tukang Batu/Kayu (Rp/OH)", value=135000)
        upah_mandor = st.number_input("Mandor (Rp/OH)", value=150000)
        
    with col_hsd2:
        st.subheader("🧱 Bahan Material")
        harga_semen = st.number_input("Semen (Rp/kg)", value=1600, help="Contoh: Rp 80.000/sak 50kg = Rp 1.600/kg")
        harga_pasir = st.number_input("Pasir Beton (Rp/m3)", value=250000)
        harga_split = st.number_input("Kerikil/Split (Rp/m3)", value=350000)
        harga_besi = st.number_input("Besi Beton (Rp/kg)", value=14500)
        harga_kayu = st.number_input("Kayu Kelas III (Rp/m3)", value=2800000)
        harga_paku = st.number_input("Paku (Rp/kg)", value=22000)

# B. PERHITUNGAN ANALISA HARGA SATUAN (HSP)

# 1. HSP Beton K-225 (A.4.1.1.8)
# Tenaga
upah_beton = (1.650*upah_pekerja) + (0.275*upah_tukang) + \
             (0.028*upah_tukang*1.1) + (0.083*upah_mandor)
# Bahan
mat_beton = (371.0*harga_semen) + (0.4986*harga_pasir) + (0.7756*harga_split) + (215*0) # Air dianggap 0/gratis
hsp_beton = (upah_beton + mat_beton) * 1.10 # Overhead 10%

# 2. HSP Penulangan (A.4.1.1.17)
upah_besi = (0.007*upah_pekerja) + (0.007*upah_tukang) + \
            (0.0007*upah_tukang*1.1) + (0.0004*upah_mandor)
mat_besi = (1.05*harga_besi) + (0.015*24000) # Kawat asumsi 24rb
hsp_besi = (upah_besi + mat_besi) * 1.10

# 3. HSP Bekisting (A.4.1.1.21)
upah_bek = (0.66*upah_pekerja) + (0.33*upah_tukang) + \
           (0.033*upah_tukang*1.1) + (0.033*upah_mandor)
mat_bek = (0.045*harga_kayu) + (0.30*harga_paku) + (0.10*15000) # Minyak 15rb
hsp_bekisting = (upah_bek + mat_bek) * 1.10

# C. REKAPITULASI BIAYA
# Mengambil volume dari fungsi hitung_analisa_qs sebelumnya
vol_b = res['vol_beton']
vol_s = res['berat_besi']
vol_k = res['bekisting']

biaya_beton = vol_b * hsp_beton
biaya_besi = vol_s * hsp_besi
biaya_bek = vol_k * hsp_bekisting
total_per_meter = biaya_beton + biaya_besi + biaya_bek

# D. TAMPILAN OUTPUT
st.divider()
st.subheader(f"💵 Total Biaya Konstruksi: Rp {total_per_meter:,.0f} / m'")

# Tabel Detail
rekap_data = {
    "Uraian Pekerjaan": ["1. Beton K-225 (A.4.1.1.8)", "2. Penulangan (A.4.1.1.17)", "3. Bekisting (A.4.1.1.21)"],
    "Volume / m'": [f"{vol_b:.3f} m3", f"{vol_s:.2f} kg", f"{vol_k:.2f} m2"],
    "Harga Satuan (HSP)": [f"Rp {hsp_beton:,.0f}", f"Rp {hsp_besi:,.0f}", f"Rp {hsp_bekisting:,.0f}"],
    "Jumlah Harga (Rp)": [biaya_beton, biaya_besi, biaya_bek]
}
df_rekap = pd.DataFrame(rekap_data)
st.dataframe(df_rekap.style.format({"Jumlah Harga (Rp)": "{:,.0f}"}))

# Input Panjang Saluran
st.divider()
panjang_proyek = st.number_input("Masukkan Panjang Saluran Total (meter)", value=100)
st.success(f"### 🏷️ TOTAL RAB PROYEK: Rp {(total_per_meter * panjang_proyek):,.0f}")
