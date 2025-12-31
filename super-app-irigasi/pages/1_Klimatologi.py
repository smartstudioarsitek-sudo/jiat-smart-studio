import streamlit as st
import pandas as pd
import numpy as np

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Analisa Klimatologi", layout="wide", page_icon="🌦️")

st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
    .metric-card {
        background-color: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; border-radius: 5px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. RUMUS PENMAN-MONTEITH (Simplified) ---
def hitung_eto(temp, hum, sun, wind, lat_deg=-7.0, alt=10):
    # Konversi ke array numpy (Safe Float)
    def to_float(arr):
        return np.array([float(x) for x in arr])

    T = to_float(temp)
    RH = to_float(hum)
    n = to_float(sun)
    u2 = to_float(wind) * (1000/3600) # km/jam ke m/s
    
    # --- Konstanta Fisik ---
    es = 0.6108 * np.exp((17.27 * T) / (T + 237.3))
    ea = es * (RH / 100)
    delta = (4098 * es) / ((T + 237.3)**2)
    P = 101.3 * ((293 - 0.0065 * alt) / 293)**5.26
    gamma = 0.000665 * P
    
    # Radiasi (Simplifikasi)
    Ra = np.array([15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7])
    Rs = (0.25 + 0.50 * (n/100)) * Ra
    Rns = 0.77 * Rs
    Rn = Rns - 2.5 
    
    term1 = 0.408 * delta * Rn
    term2 = gamma * (900 / (T + 273)) * u2 * (es - ea)
    term3 = delta + gamma * (1 + 0.34 * u2)
    
    ETo = (term1 + term2) / term3
    return ETo

# --- 3. STATE MANAGEMENT ---
if 'df_iklim' not in st.session_state:
    st.session_state['df_iklim'] = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'Suhu (°C)': [26.5]*12,
        'Kelembaban (%)': [85.0]*12,
        'Penyinaran (%)': [50.0]*12,
        'Angin (km/jam)': [10.0]*12
    })

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🌍 Parameter Lokasi")
    latitude = st.number_input("Lintang (Derajat)", value=-7.5)
    elevasi = st.number_input("Elevasi (mdpl)", value=50.0)
    st.divider()
    if st.button("🔄 Reset Data"):
        st.session_state.pop('df_iklim')
        st.rerun()

# --- 5. MAIN CONTENT ---
st.title("🌦️ Analisa Klimatologi (ETo)")
st.caption("Metode Penman-Monteith (Modifikasi FAO-56)")

# A. Input Data
st.subheader("1. Input Data Iklim")
edited_df = st.data_editor(st.session_state['df_iklim'], num_rows="fixed", use_container_width=True, hide_index=True)
st.session_state['df_iklim'] = edited_df

# B. Proses Hitung
# Ambil data dan pastikan formatnya benar
try:
    suhu = edited_df['Suhu (°C)'].tolist()
    hum = edited_df['Kelembaban (%)'].tolist()
    sun = edited_df['Penyinaran (%)'].tolist()
    wind = edited_df['Angin (km/jam)'].tolist()

    eto_result = hitung_eto(suhu, hum, sun, wind, latitude, elevasi)
    
    # Siapkan DataFrame Hasil
    df_hasil = edited_df[['Bulan']].copy()
    df_hasil['ETo (mm/hari)'] = np.round(eto_result, 2)
    
    # --- [PENTING] AUTO-SEND KE PAGE LAIN ---
    st.session_state['data_eto_transfer'] = df_hasil['ETo (mm/hari)'].tolist()
    
    st.subheader("2. Hasil Perhitungan")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # [SOLUSI ANTI-ERROR]: Filter kolom angka saja untuk diformat
        # Ini mencegah error "ValueError" saat mencoba memformat teks 'Bulan'
        numeric_cols = df_hasil.select_dtypes(include=[np.number]).columns
        
        st.dataframe(
            df_hasil.style
            .background_gradient(cmap="Blues", subset=['ETo (mm/hari)'])
            .format("{:.2f}", subset=numeric_cols), # <--- KUNCI PERBAIKANNYA DI SINI
            use_container_width=True
        )
    
    with col2:
        rata_eto = np.mean(eto_result)
        st.markdown(f"""
        <div class="metric-card">
            <h4>Rata-rata ETo</h4>
            <h2 style="margin:0;">{rata_eto:.2f} <span style="font-size:16px">mm/hari</span></h2>
            <small>✅ Data Terkirim ke JIAT</small>
        </div>
        """, unsafe_allow_html=True)
        st.bar_chart(df_hasil.set_index('Bulan')['ETo (mm/hari)'])

except Exception as e:
    st.error(f"⚠️ Terjadi kesalahan input: {e}")

# --- 6. TOMBOL CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#4CAF50;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)
