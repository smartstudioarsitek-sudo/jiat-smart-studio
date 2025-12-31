import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 1. CONFIG ---
st.set_page_config(page_title="Analisa Klimatologi", layout="wide", page_icon="🌦️")

# --- 2. CSS PRINT & UI ---
st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
    .metric-card {
        background-color: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; border-radius: 5px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. RUMUS PENMAN-MONTEITH (Simplified) ---
def hitung_eto(temp, hum, sun, wind, lat_deg=-7.0, alt=10):
    # Konversi input ke array numpy agar perhitungan vektor
    T = np.array(temp)
    RH = np.array(hum)
    n = np.array(sun) # Jam penyinaran (n/N dalam %)
    u2 = np.array(wind) * (1000/3600) # km/jam ke m/s (jika input km/jam) atau sesuaikan
    
    # --- Konstanta Fisik ---
    # Tekanan Uap Jenuh (es)
    es = 0.6108 * np.exp((17.27 * T) / (T + 237.3))
    # Tekanan Uap Aktual (ea)
    ea = es * (RH / 100)
    # Kemiringan Kurva (delta)
    delta = (4098 * es) / ((T + 237.3)**2)
    # Konstanta Psikrometrik (gamma)
    P = 101.3 * ((293 - 0.0065 * alt) / 293)**5.26
    gamma = 0.000665 * P
    
    # --- Radiasi (Simplifikasi Angot / Ra) ---
    # Asumsi Ra rata-rata untuk Indonesia (Latitude -5 to -10)
    # Nilai Ra bulanan (MJ/m2/day)
    Ra_vals = [15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7]
    Ra = np.array(Ra_vals)
    
    # Radiasi Matahari (Rs) -> Asumsi n adalah durasi (%)
    # Rs = (as + bs * n/100) * Ra -> as=0.25, bs=0.5
    Rs = (0.25 + 0.50 * (n/100)) * Ra
    
    # Radiasi Bersih (Rn) - Simplifikasi
    # Rns = (1-albedo)*Rs -> albedo 0.23 (tanaman)
    Rns = 0.77 * Rs
    # Rnl (Radiasi Gelombang Panjang) - Simplifikasi F.A.O
    # Rnl approx 2.0 - 4.0 tergantung suhu/lembab. Kita pakai estimasi.
    Rn = Rns - 2.5 # Net Radiation approx
    
    # --- Rumus Penman-Monteith FAO 56 ---
    # ETo = (0.408*delta*Rn + gamma*(900/(T+273))*u2*(es-ea)) / (delta + gamma*(1+0.34*u2))
    
    term1 = 0.408 * delta * Rn
    term2 = gamma * (900 / (T + 273)) * u2 * (es - ea)
    term3 = delta + gamma * (1 + 0.34 * u2)
    
    ETo = (term1 + term2) / term3
    return ETo

# --- 4. STATE MANAGEMENT ---
if 'df_iklim' not in st.session_state:
    st.session_state['df_iklim'] = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'Suhu (°C)': [26.5]*12,
        'Kelembaban (%)': [85.0]*12,
        'Penyinaran (%)': [50.0]*12,
        'Angin (km/jam)': [10.0]*12
    })

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("🌍 Parameter Lokasi")
    latitude = st.number_input("Lintang (Derajat)", value=-7.5, help="Negatif untuk Lintang Selatan")
    elevasi = st.number_input("Elevasi (mdpl)", value=50.0)
    
    st.divider()
    if st.button("🔄 Reset Data Default"):
        st.session_state.pop('df_iklim')
        st.experimental_rerun()

# --- 6. MAIN CONTENT ---
st.title("🌦️ Analisa Klimatologi (ETo)")
st.markdown("Perhitungan Evapotranspirasi Potensial metode **Penman-Monteith**.")

# A. Input Data
st.subheader("1. Input Data Iklim Bulanan")
edited_df = st.data_editor(st.session_state['df_iklim'], num_rows="fixed", use_container_width=True, hide_index=True)
st.session_state['df_iklim'] = edited_df

# B. Proses Hitung
# Ambil data dari tabel editor
suhu = edited_df['Suhu (°C)'].values
hum = edited_df['Kelembaban (%)'].values
sun = edited_df['Penyinaran (%)'].values
wind = edited_df['Angin (km/jam)'].values * (1000/3600) # Convert to m/s for calculation

# Hitung
try:
    eto_result = hitung_eto(suhu, hum, sun, wind, latitude, elevasi)
    
    # Masukkan ke DataFrame Hasil
    df_hasil = edited_df[['Bulan']].copy()
    df_hasil['ETo (mm/hari)'] = np.round(eto_result, 2)
    
    # --- [PENTING] SIMPAN DATA UNTUK MODUL LAIN ---
    # Inilah baris ajaib yang membuat data "Ngelink" ke Page 5
    st.session_state['data_eto_transfer'] = df_hasil['ETo (mm/hari)'].tolist()
    
    st.subheader("2. Hasil Perhitungan ETo")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.dataframe(df_hasil.style.highlight_max(axis=0, color='#e3f2fd'), use_container_width=True)
    
    with col2:
        rata_eto = np.mean(eto_result)
        st.markdown(f"""
        <div class="metric-card">
            <h4>Rata-rata ETo</h4>
            <h2 style="margin:0;">{rata_eto:.2f} <span style="font-size:16px">mm/hari</span></h2>
            <small>✅ Data Tersimpan Otomatis</small>
        </div>
        """, unsafe_allow_html=True)
        
        # Grafik
        st.bar_chart(df_hasil.set_index('Bulan')['ETo (mm/hari)'])

    # Notifikasi sukses terselubung (agar user tahu data sudah siap)
    if 'data_eto_transfer' in st.session_state:
        st.toast(f"Data ETo berhasil dihitung & dikirim ke Modul JIAT!", icon="🚀")

except Exception as e:
    st.error(f"Terjadi kesalahan perhitungan: {e}")

# --- 7. TOMBOL CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#4CAF50;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)
