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

# --- 2. RUMUS PENMAN MODIFIKASI (Standar KP-01) ---
def hitung_penman_modifikasi(temp, hum, sun, wind, lat_deg=-7.0, angot_vals=None, c_factor=1.1):
    # Fungsi bantu konversi ke float array
    def to_float(arr):
        return np.array([float(x) for x in arr])

    try:
        T = to_float(temp)      # Suhu (C)
        RH = to_float(hum)      # Kelembaban (%)
        n = to_float(sun)       # Penyinaran (%)
        u_km_jam = to_float(wind) 
        
        # Konversi Angin: km/jam -> km/hari (KP-01 butuh km/hari)
        u_km_day = u_km_jam * 24 

        # 1. Tekanan Uap Jenuh (ea) dalam mbar
        # Rumus pendekatan: ea = 6.11 * exp(17.27T / (T+237.3))
        ea = 6.11 * np.exp((17.27 * T) / (T + 237.3))
        
        # 2. Tekanan Uap Aktual (ed) dalam mbar
        ed = ea * (RH / 100)
        
        # 3. Faktor Pembobot (W) - Weighting Factor
        # W dikalkulasi berdasarkan suhu (T)
        # Tabel KP-01 bisa didekati dengan rumus:
        W = 0.4025 + 0.013 * T - 0.0001 * (T**2) # Aproksimasi polinomial utk range 20-35 C
        
        # 4. Fungsi Angin f(u)
        # Rumus KP-01: f(u) = 0.27 * (1 + U/100)
        fu = 0.27 * (1 + u_km_day / 100)
        
        # 5. Radiasi (Rn)
        # a. Radiasi Ekstra Terestrial (Ra) - Nilai Angot
        if angot_vals is None:
            # Default Ra Indonesia (Lintang -5 s/d -10)
            Ra = np.array([15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7])
        else:
            Ra = np.array(angot_vals)
            
        # b. Radiasi Gelombang Pendek (Rs)
        # Rumus: Rs = (0.25 + 0.54 * n/N) * Ra  --> Koefisien a=0.25, b=0.54 (Umum di Indonesia)
        Rs = (0.25 + 0.54 * (n/100)) * Ra
        
        # c. Radiasi Bersih Gelombang Pendek (Rns) -> Albedo 0.20 (Tanaman/Air)
        albedo = 0.20
        Rns = (1 - albedo) * Rs
        
        # d. Radiasi Gelombang Panjang (Rnl)
        # Rumus Brunt: Rnl = f(T) * f(ed) * f(n/N)
        # f(T) = sigma * (T+273)^4
        sigma = 2.043e-10 # Konstanta Stefan-Boltzmann dlm mm/hari (approximated value context)
        # Agar sesuai satuan KP-01 tabel, kita pakai pendekatan langsung FT dari tabel:
        # FT approx = 15 s/d 16. Kita pakai rumus manual saja:
        ft_val = sigma * ((T + 273.16)**4) # Ini dlm MJ, perlu konversi. 
        # Untuk simplifikasi coding tanpa tabel look-up yang rumit, kita pakai rumus umum Penman:
        # Rnl = sigma*T^4 * (0.34 - 0.044*sqrt(ed)) * (0.1 + 0.9*n/N)
        # sigma*T^4 approx 15-16 mm/day equivalent evap.
        
        # Kita pakai Rumus Penman Modifikasi yang disederhanakan (versi Prosida):
        # ETo* = W * Rn + (1-W) * f(u) * (ea - ed)
        # Dimana Rn = Rns - Rnl
        
        # Hitung Rnl (Net Longwave) mm/day
        # Konstanta sigma T4 (mm/day)
        sigma_t4 = 1.98 * 10**-9 * ((T + 273.16)**4) * 0.408 # Konversi ke mm/day kira2
        # Koreksi: Kita pakai rumus approach praktis KP-01:
        # Rnl = f(T) * f(ed) * f(n/N)
        func_t = 11.0 + 0.22 * T # Tabel T vs f(T) KP-01 linear approach
        func_ed = 0.34 - 0.044 * np.sqrt(ed)
        func_n = 0.1 + 0.9 * (n/100)
        Rnl = func_t * func_ed * func_n
        
        Rn = Rns - Rnl
        
        # 6. ETo Tanpa Koreksi (ETo*)
        ETo_star = W * Rn + (1 - W) * fu * (ea - ed)
        
        # 7. ETo Final (Dengan Faktor Koreksi c)
        # c biasanya 0.9 - 1.1 tergantung angin siang/malam. KP-01 sering pakai 1.1 untuk aman.
        ETo = c_factor * ETo_star
        
        return ETo
        
    except Exception as e:
        return np.zeros(12)

# --- 3. STATE MANAGEMENT ---
if 'df_iklim' not in st.session_state:
    st.session_state['df_iklim'] = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'Suhu (°C)': [27.1, 27.2, 27.5, 28.0, 27.8, 27.2, 26.8, 27.0, 27.5, 28.1, 27.8, 27.3],
        'Kelembaban (%)': [82.0, 83.0, 81.0, 80.0, 78.0, 76.0, 72.0, 70.0, 72.0, 75.0, 79.0, 81.0],
        'Penyinaran (%)': [45.0, 48.0, 52.0, 60.0, 75.0, 80.0, 85.0, 88.0, 80.0, 70.0, 55.0, 48.0],
        'Angin (km/jam)': [12.0, 11.0, 10.0, 9.0, 10.0, 11.0, 13.0, 14.0, 13.0, 11.0, 10.0, 11.0]
    })

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🌍 Parameter KP-01")
    
    # Faktor Koreksi c
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, 1.1, 0.1, help="Standar KP-01 biasanya 1.1 (Angin siang > malam)")
    
    st.divider()
    if st.button("🔄 Reset Data"):
        if 'df_iklim' in st.session_state:
            del st.session_state['df_iklim']
        st.rerun()

# --- 5. MAIN CONTENT ---
st.title("🌦️ Klimatologi (Penman Modifikasi)")
st.caption("Metode Standar KP-01 (Kriteria Perencanaan Irigasi)")

# A. Input Data
st.subheader("1. Input Data Iklim")
st.info("💡 Tips: Copy data Excel (Suhu, RH, Angin, Sinar), klik pojok kiri atas tabel input, lalu Ctrl+V.")

edited_df = st.data_editor(st.session_state['df_iklim'], num_rows="fixed", use_container_width=True, hide_index=True)
st.session_state['df_iklim'] = edited_df

# B. Proses Hitung
try:
    # Ambil data
    suhu = edited_df['Suhu (°C)'].tolist()
    hum = edited_df['Kelembaban (%)'].tolist()
    sun = edited_df['Penyinaran (%)'].tolist()
    wind = edited_df['Angin (km/jam)'].tolist()

    # Hitung dengan Penman Modifikasi
    eto_result = hitung_penman_modifikasi(suhu, hum, sun, wind, c_factor=c_factor)
    
    # DataFrame Hasil
    df_hasil = edited_df[['Bulan']].copy()
    df_hasil['ETo (mm/hari)'] = np.round(eto_result, 2)
    
    # --- [PENTING] TRANSFER DATA ---
    st.session_state['data_eto_transfer'] = df_hasil['ETo (mm/hari)'].tolist()
    
    st.subheader("2. Hasil Perhitungan (Standar KP-01)")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Logic Anti-Error (Sama seperti sebelumnya)
        numeric_cols = df_hasil.select_dtypes(include=[np.number]).columns
        
        st.dataframe(
            df_hasil.style
            .background_gradient(cmap="Oranges", subset=['ETo (mm/hari)']) # Ganti warna jadi Oranges biar beda
            .format("{:.2f}", subset=numeric_cols), 
            use_container_width=True
        )
    
    with col2:
        rata_eto = np.mean(eto_result)
        st.markdown(f"""
        <div class="metric-card">
            <h4>Rata-rata ETo</h4>
            <h2 style="margin:0;">{rata_eto:.2f} <span style="font-size:16px">mm/hari</span></h2>
            <small>✅ Metode KP-01 (Modified)</small>
        </div>
        """, unsafe_allow_html=True)
        st.bar_chart(df_hasil.set_index('Bulan')['ETo (mm/hari)'])

except Exception as e:
    st.error(f"⚠️ Terjadi kesalahan input: {e}")

# --- 6. CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#ff9800;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)
