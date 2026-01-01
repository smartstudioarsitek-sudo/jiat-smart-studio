import streamlit as st
import pandas as pd
import numpy as np
import json

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Analisa Klimatologi (15 Harian)", layout="wide", page_icon="🌦️")

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
    .success-box {
        padding: 10px; background-color: #d1e7dd; color: #0f5132; 
        border: 1px solid #badbcc; border-radius: 5px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. RUMUS PENMAN MODIFIKASI (SUPPORT 24 PERIODE) ---
def hitung_penman_modifikasi(temp, hum, sun, wind, c_factor=1.1):
    # Konversi input ke numpy array float
    def to_float(arr): return np.array([float(x) for x in arr])

    try:
        T = to_float(temp)
        RH = to_float(hum)
        n = to_float(sun)
        u_km_jam = to_float(wind)
        u_km_day = u_km_jam * 24 

        # 1. Tekanan Uap
        ea = 6.11 * np.exp((17.27 * T) / (T + 237.3))
        ed = ea * (RH / 100)
        
        # 2. Faktor Pembobot (W)
        W = 0.4025 + 0.013 * T - 0.0001 * (T**2)
        
        # 3. Fungsi Angin f(u) KP-01
        fu = 0.27 * (1 + u_km_day / 100)
        
        # 4. Radiasi (Ra) - Expand 12 bulan jadi 24 periode
        # Nilai Ra Bulanan (Indonesia Lintang Rendah)
        ra_bulanan = [15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7]
        
        # Cek apakah inputnya 12 atau 24?
        if len(T) == 24:
            # Jika input 24, Ra juga harus 24 (Duplikasi nilai bulanan ke periode 1 & 2)
            Ra = []
            for val in ra_bulanan: Ra.extend([val, val])
            Ra = np.array(Ra)
        else:
            Ra = np.array(ra_bulanan)

        # Hitung Radiasi
        Rs = (0.25 + 0.54 * (n/100)) * Ra
        Rns = (1 - 0.20) * Rs
        
        # Rnl
        func_t = 11.0 + 0.22 * T 
        func_ed = 0.34 - 0.044 * np.sqrt(ed)
        func_n = 0.1 + 0.9 * (n/100)
        Rnl = func_t * func_ed * func_n
        
        Rn = Rns - Rnl
        
        # 5. ETo
        ETo_star = W * Rn + (1 - W) * fu * (ea - ed)
        ETo = c_factor * ETo_star
        return ETo
        
    except Exception as e:
        return np.zeros(len(temp))

# --- 3. STATE MANAGEMENT (DATA 24 PERIODE) ---
def init_state():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])

    if 'df_iklim_24' not in st.session_state:
        # Default Data Dummy (24 Baris)
        st.session_state['df_iklim_24'] = pd.DataFrame({
            'Periode': periods,
            'Suhu (°C)': [27.0]*24,
            'Kelembaban (%)': [80.0]*24,
            'Penyinaran (%)': [50.0]*24,
            'Angin (km/jam)': [10.0]*24
        })

init_state()

# --- 4. SIDEBAR (TOOLS) ---
with st.sidebar:
    st.header("📂 File & Tools")
    
    # A. GENERATOR DATA BULANAN (FITUR PENTING!)
    with st.expander("⚡ Generator Data (Input Cepat)"):
        st.caption("Input data bulanan saja, nanti otomatis dipecah jadi 15 harian.")
        
        # Form kecil untuk input bulanan
        df_temp_month = pd.DataFrame({
            'Bulan': ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'],
            'Suhu': [27.0]*12, 'RH': [80.0]*12, 'Sinar': [50.0]*12, 'Angin': [10.0]*12
        })
        edited_month = st.data_editor(df_temp_month, height=300, hide_index=True)
        
        if st.button("Generate ke Tabel Utama ➡️"):
            # Proses Expand 12 -> 24
            new_suhu, new_rh, new_sun, new_wind = [], [], [], []
            for idx, row in edited_month.iterrows():
                # Periode 1
                new_suhu.append(row['Suhu']); new_rh.append(row['RH'])
                new_sun.append(row['Sinar']); new_wind.append(row['Angin'])
                # Periode 2 (Sama)
                new_suhu.append(row['Suhu']); new_rh.append(row['RH'])
                new_sun.append(row['Sinar']); new_wind.append(row['Angin'])
            
            # Update Session State
            st.session_state['df_iklim_24']['Suhu (°C)'] = new_suhu
            st.session_state['df_iklim_24']['Kelembaban (%)'] = new_rh
            st.session_state['df_iklim_24']['Penyinaran (%)'] = new_sun
            st.session_state['df_iklim_24']['Angin (km/jam)'] = new_wind
            st.rerun()

    st.divider()
    
    # B. FILE MANAGER
    uploaded_file = st.file_uploader("Buka File JSON", type=["json"])
    if uploaded_file is not None:
        try:
            data_load = json.load(uploaded_file)
            st.session_state['df_iklim_24'] = pd.DataFrame(data_load['df_iklim_data'])
            st.session_state['temp_c_factor'] = data_load.get('c_factor', 1.1)
            st.success("Data Terbuka!")
            st.rerun()
        except: st.error("File Salah.")

    st.header("Parameter")
    def_c = st.session_state.get('temp_c_factor', 1.1)
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, def_c, 0.1)
    
    # Save Button
    data_save = {
        'df_iklim_data': st.session_state['df_iklim_24'].to_dict(orient='records'),
        'c_factor': c_factor
    }
    st.download_button("💾 Simpan Data", json.dumps(data_save, indent=2), "klimatologi_15hari.json", "application/json")

# --- 5. MAIN CONTENT ---
st.title("🌦️ Klimatologi (Sistem 15 Harian)")
st.caption("Metode Penman Modifikasi (KP-01) - 24 Periode")

# A. Input Data
st.subheader("1. Input Data Iklim (24 Periode)")
edited_df = st.data_editor(
    st.session_state['df_iklim_24'], 
    height=400, 
    use_container_width=True, 
    hide_index=True
)
st.session_state['df_iklim_24'] = edited_df

# B. Proses Hitung
try:
    # Ambil kolom
    suhu = edited_df['Suhu (°C)'].tolist()
    hum = edited_df['Kelembaban (%)'].tolist()
    sun = edited_df['Penyinaran (%)'].tolist()
    wind = edited_df['Angin (km/jam)'].tolist()

    # Hitung ETo (Function otomatis detect 24 data)
    eto_result = hitung_penman_modifikasi(suhu, hum, sun, wind, c_factor=c_factor)
    
    # Hasil
    df_hasil = edited_df[['Periode']].copy()
    df_hasil['ETo (mm/hari)'] = np.round(eto_result, 2)
    
    # --- AUTO LINK ---
    st.session_state['data_eto_transfer'] = df_hasil['ETo (mm/hari)'].tolist()
    
    st.subheader("2. Hasil Perhitungan")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Filter kolom angka untuk format
        numeric_cols = df_hasil.select_dtypes(include=[np.number]).columns
        st.dataframe(
            df_hasil.style.background_gradient(cmap="Oranges", subset=['ETo (mm/hari)'])
            .format("{:.2f}", subset=numeric_cols), 
            use_container_width=True,
            height=400
        )
        
        # --- TOMBOL KIRIM MANUAL ---
        st.divider()
        st.info("👇 Klik tombol ini untuk mengirim data ke Irigasi Pipa")
        if st.button("🚀 KIRIM DATA ETo (24 Periode)", type="primary", use_container_width=True):
            st.session_state['data_eto_manual'] = df_hasil['ETo (mm/hari)'].tolist()
            st.markdown(f"""
            <div class="success-box">
                <b>✅ Terkirim!</b><br>
                Silakan buka Page <b>Irigasi Pipa</b> dan klik tombol <b>'Ambil Data ETo'</b>.
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        rata_eto = np.mean(eto_result)
        st.markdown(f"""
        <div class="metric-card">
            <h4>Rata-rata ETo</h4>
            <h2 style="margin:0;">{rata_eto:.2f} <span style="font-size:16px">mm/hari</span></h2>
            <small>✅ 24 Periode (Sinkron)</small>
        </div>
        """, unsafe_allow_html=True)
        st.bar_chart(df_hasil.set_index('Periode')['ETo (mm/hari)'])

except Exception as e:
    st.error(f"⚠️ Terjadi kesalahan: {e}")

# --- 6. CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#ff9800;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)
