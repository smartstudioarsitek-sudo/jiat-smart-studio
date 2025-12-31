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
    .stExpander { border: 1px solid #ddd; border-radius: 5px; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">☀️ Analisa Klimatologi</h1>
    <p style="opacity: 0.9;">Perhitungan ETo Metode Penman Modifikasi (Standar KP-01)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. ENGINE PERHITUNGAN (PENMAN) ---
def hitung_ra_harian(lat_deg, bulan_idx):
    # Konversi Lintang ke Radian
    phi = math.radians(lat_deg)
    # Deklinasi Matahari (Delta)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * (30 * bulan_idx + 15))
    delta = 0.409 * math.sin(2 * math.pi / 365 * (30 * bulan_idx + 15) - 1.39)
    # Sudut Saat Matahari Terbenam (ws)
    ws_val = -math.tan(phi) * math.tan(delta)
    # Safety check domain acos (-1 s/d 1)
    ws_val = max(-1.0, min(1.0, ws_val))
    ws = math.acos(ws_val)
    
    # Ra (Radiasi Ekstraterestrial) dalam mm/hari
    ra_val = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + 
        math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return max(0, ra_val)

def hitung_penman(row, lat, a, b, albedo):
    try:
        t = row['Suhu (°C)']
        rh = row['RH (%)']
        u_ms = row['Angin (m/s)']
        n_N = row['Penyinaran (%)'] / 100
        
        if pd.isna(t) or pd.isna(rh): return 0.0

        # 1. Tekanan Uap (ea & ed) - kPa
        ea = 0.6108 * math.exp((17.27 * t) / (t + 237.3))
        ed = ea * (rh / 100)
        
        # 2. Kemiringan Kurva (Delta)
        delta = (4098 * ea) / ((t + 237.3)**2)
        gamma = 0.066 # Konstanta psikrometrik (kPa/°C)
        
        # 3. Radiasi Matahari (Rs)
        ra = hitung_ra_harian(lat, row['Index'])
        rs = (a + b * n_N) * ra
        
        # 4. Radiasi Bersih (Rn)
        rns = (1 - albedo) * rs
        sigma_t4 = 4.903e-9 * ((t + 273.16)**4)
        # Rumus Rnl Penman-Monteith FAO/KP-01
        rnl = sigma_t4 * (0.34 - 0.14 * math.sqrt(ed)) * (1.35 * (rs / max(0.1, (0.75 * ra))) - 0.35)
        rn = rns - rnl
        
        # 5. ETo (mm/hari)
        u2 = u_ms # Asumsi data angin diukur pada ketinggian 2m
        term1 = 0.408 * delta * rn
        term2 = gamma * (900 / (t + 273)) * u2 * (ea - ed)
        div = delta + gamma * (1 + 0.34 * u2)
        
        eto = (term1 + term2) / div
        return max(0, round(eto, 2))
    except:
        return 0.0

# --- 4. DATA DEFAULT ---
def get_default_meteo():
    return pd.DataFrame({
        'Index': range(12),
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'],
        'Suhu (°C)': [27.5]*12,
        'RH (%)': [85.0]*12,
        'Angin (m/s)': [1.5]*12,
        'Penyinaran (%)': [60.0]*12
    })

if 'df_klimatologi' not in st.session_state:
    st.session_state.df_klimatologi = get_default_meteo()

# --- 5. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("🌍 Lokasi Proyek")
    
    # Lintang Wajib Ada (Karena mempengaruhi Ra)
    lintang = st.number_input(
        "📍 Lintang Lokasi (Latitude)", 
        value=-5.40, step=0.1, format="%.2f",
        help="Posisi lintang daerah studi. Gunakan nilai NEGATIF (-) untuk Lintang Selatan (Indonesia bag. selatan khatulistiwa) dan POSITIF (+) untuk Utara."
    )
    st.info(f"Lokasi: {abs(lintang)}° {'LS' if lintang < 0 else 'LU'}")

    st.divider()
    
    # Parameter Lanjut Disembunyikan (Clean UI)
    with st.expander("⚙️ Parameter Kalibrasi (Advanced)"):
        st.write("Ubah hanya jika ada data spesifik:")
        albedo = st.number_input("Albedo (Pantulan)", value=0.25, step=0.01, 
                               help="Koefisien pantulan tajuk. Tanaman hijau/rumput = 0.23 - 0.25. Air = 0.05.")
        st.caption("Koefisien Angstrom (Radiasi):")
        a = st.number_input("Konstanta a", value=0.25, help="Radiasi gelombang pendek yang menembus atmosfer.")
        b = st.number_input("Konstanta b", value=0.50, help="Radiasi gelombang panjang.")

    # Tombol Reset
    if st.button("🔄 Reset Tabel", type="secondary"):
        st.session_state.df_klimatologi = get_default_meteo()
        st.rerun()

# --- 6. MAIN CONTENT ---
col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader("1. Input Data Meteo")
    
    # INFO COPY PASTE
    st.info("💡 **Tips Excel:** Anda bisa Copy data (Suhu, RH, Angin, Penyinaran) dari Excel, lalu klik sel pertama tabel di bawah, dan tekan **Ctrl+V**.")
    
    edited_df = st.data_editor(
        st.session_state.df_klimatologi,
        use_container_width=True,
        height=460,
        column_config={
            "Index": None, # Hide index internal
            "Bulan": st.column_config.TextColumn(disabled=True),
            "Suhu (°C)": st.column_config.NumberColumn(required=True),
            "RH (%)": st.column_config.NumberColumn(required=True, min_value=0, max_value=100),
            "Angin (m/s)": st.column_config.NumberColumn(required=True, min_value=0),
            "Penyinaran (%)": st.column_config.NumberColumn(required=True, min_value=0, max_value=100)
        }
    )
    # Update Session State
    st.session_state.df_klimatologi = edited_df

# HITUNG LIVE
eto_list = []
for idx, row in edited_df.iterrows():
    val = hitung_penman(row, lintang, a, b, albedo)
    eto_list.append(val)

# Dataframe Hasil
df_hasil = edited_df.copy()
df_hasil['ETo (mm/hari)'] = eto_list

with col2:
    st.subheader("2. Hasil ETo (Penman)")
    
    # Tampilkan Tabel Hasil (Read Only)
    st.dataframe(
        df_hasil[['Bulan', 'ETo (mm/hari)']].style.background_gradient(cmap="Blues"),
        use_container_width=True,
        height=460
    )

# --- 7. FOOTER & SEND ---
st.divider()
col_grafik, col_tombol = st.columns([3, 1])

with col_grafik:
    st.line_chart(df_hasil.set_index('Bulan')[['ETo (mm/hari)']], color="#ffaa00")

with col_tombol:
    avg_eto = round(sum(eto_list)/12, 2)
    st.metric("Rata-rata ETo", f"{avg_eto} mm/hari")
    
    if st.button("🚀 Kirim Data ke Pola Tanam", type="primary"):
        st.session_state['data_eto_transfer'] = eto_list
        st.toast(f"✅ Data ETo tersimpan! Siap digunakan di modul berikutnya.", icon="💾")
