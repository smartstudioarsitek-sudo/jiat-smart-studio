import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Klimatologi (Penman)", layout="wide", page_icon="☀️")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #ff6f00 0%, #ff8f00 50%, #ffca28 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">☀️ Analisa Klimatologi</h1>
    <p style="opacity: 0.9;">Perhitungan Evapotranspirasi (ETo) Metode Penman Modifikasi</p>
</div>
""", unsafe_allow_html=True)

# --- 3. RUMUS PENMAN MODIFIKASI (ENGINE) ---
def hitung_ra_harian(lat_deg, bulan_idx):
    # Estimasi Ra (Radiasi Ekstraterestrial) sederhana berdasarkan lintang & bulan
    # bulan_idx: 0 (Jan) s/d 11 (Des)
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * (30 * (bulan_idx) + 15))
    delta = 0.409 * math.sin(2 * math.pi / 365 * (30 * (bulan_idx) + 15) - 1.39)
    ws = math.acos(-math.tan(phi) * math.tan(delta))
    
    # Rumus Ra (MJ/m2/hari) -> Konversi ke mm/hari (approx / 2.45)
    ra_val = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + 
        math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return max(0, ra_val)

def hitung_penman(row, lat, angstrom_a, angstrom_b, albedo):
    try:
        t = row['Suhu (°C)']
        rh = row['RH (%)']
        u = row['Angin (m/s)'] * 86.4 # Konversi m/s ke km/hari
        n_N = row['Penyinaran (%)'] / 100
        
        # 1. Tekanan Uap Jenuh (ea) & Aktual (ed)
        ea = 0.6108 * math.exp((17.27 * t) / (t + 237.3))
        ed = ea * (rh / 100)
        
        # 2. Kemiringan Kurva (Delta) & Konstanta Psikrometrik
        delta = (4098 * ea) / ((t + 237.3)**2)
        gamma = 0.066 # Konstanta psikrometrik approx
        
        # 3. Radiasi (Rs & Rns)
        ra = hitung_ra_harian(lat, row['Index'])
        rs = (angstrom_a + angstrom_b * n_N) * ra
        rns = (1 - albedo) * rs
        
        # 4. Radiasi Gelombang Panjang (Rnl)
        sigma_t4 = 4.903e-9 * ((t + 273.16)**4)
        rnl = sigma_t4 * (0.34 - 0.14 * math.sqrt(ed)) * (1.35 * (rs / max(0.1, (0.75 * ra))) - 0.35)
        
        # 5. Radiasi Bersih (Rn)
        rn = rns - rnl
        
        # 6. ETo Penman-Monteith / Modifikasi Approximasi
        # Menggunakan bentuk penyederhanaan umum untuk aplikasi praktis
        u2 = row['Angin (m/s)'] # Angin height 2m
        term1 = (0.408 * delta * rn)
        term2 = gamma * (900 / (t + 273)) * u2 * (ea - ed)
        div = delta + gamma * (1 + 0.34 * u2)
        
        eto = (term1 + term2) / div
        return max(0, round(eto, 2))
    except:
        return 0.0

# --- 4. DATA DEFAULT ---
def get_default_meteo():
    bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 
             'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    return pd.DataFrame({
        'Index': range(12), # Helper untuk hitungan bulan
        'Bulan': bulan,
        'Suhu (°C)': [27.5, 27.6, 27.8, 28.0, 28.1, 27.9, 27.5, 27.8, 28.2, 28.5, 28.0, 27.6],
        'RH (%)': [85, 84, 83, 82, 80, 78, 75, 72, 70, 75, 80, 84],
        'Angin (m/s)': [1.2, 1.5, 1.4, 1.3, 1.6, 1.8, 2.1, 2.3, 2.0, 1.8, 1.4, 1.3],
        'Penyinaran (%)': [45, 50, 55, 60, 65, 70, 75, 80, 75, 65, 50, 45]
    })

if 'df_klimatologi' not in st.session_state:
    st.session_state.df_klimatologi = get_default_meteo()

# --- 5. SIDEBAR PENGATURAN ---
with st.sidebar:
    st.header("🌍 Lokasi & Parameter")
    
    # TOMBOL RESET
    if st.button("🔄 Reset Data Meteo", type="secondary"):
        st.session_state.df_klimatologi = get_default_meteo()
        st.rerun()

    st.divider()
    # Parameter Penman
    lintang = st.number_input("Lintang Lokasi (Derajat)", value=-5.4, step=0.1, help="Negatif untuk Lintang Selatan (LS)")
    albedo = st.number_input("Albedo (Pantulan)", value=0.25, step=0.01)
    st.caption("Koefisien Angstrom:")
    angstrom_a = st.number_input("Konstanta a", value=0.25)
    angstrom_b = st.number_input("Konstanta b", value=0.50)

# --- 6. INPUT DAN HASIL ---
col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader("1. Input Data Meteo Bulanan")
    st.info("Masukkan data rata-rata bulanan pada tabel di bawah ini:")
    
    edited_df = st.data_editor(
        st.session_state.df_klimatologi,
        use_container_width=True,
        height=460,
        column_config={
            "Index": None, # Sembunyikan kolom index helper
            "Bulan": st.column_config.TextColumn(disabled=True)
        }
    )
    st.session_state.df_klimatologi = edited_df

# HITUNG OTOMATIS
eto_results = []
for index, row in edited_df.iterrows():
    val = hitung_penman(row, lintang, angstrom_a, angstrom_b, albedo)
    eto_results.append(val)

# Masukkan hasil ke Dataframe untuk visualisasi
df_hasil = edited_df.copy()
df_hasil['ETo (mm/hari)'] = eto_results

with col2:
    st.subheader("2. Hasil Perhitungan ETo")
    st.dataframe(
        df_hasil[['Bulan', 'ETo (mm/hari)']],
        use_container_width=True,
        height=460
    )

# --- 7. TOMBOL SIMPAN MANUAL ---
st.divider()
col_res1, col_res2 = st.columns([3, 1])

with col_res1:
    # Grafik Trend
    st.line_chart(df_hasil.set_index('Bulan')['ETo (mm/hari)'])

with col_res2:
    rata_eto = round(sum(eto_results)/12, 2)
    st.metric("Rata-rata ETo", f"{rata_eto} mm/hari")
    
    if st.button("💾 Simpan ETo ke Pola Tanam", type="primary"):
        # Simpan list ETo ke session state agar dibaca modul sebelah
        st.session_state['data_eto_transfer'] = eto_results
        st.toast(f"✅ Data ETo (Rata-rata {rata_eto}) berhasil dikirim!", icon="🚀")

# Debug info
# if 'data_eto_transfer' in st.session_state:
#     st.write(st.session_state['data_eto_transfer'])
