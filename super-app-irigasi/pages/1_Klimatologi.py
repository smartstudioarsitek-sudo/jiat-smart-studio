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

# --- 2. RUMUS PENMAN MODIFIKASI ---
def hitung_penman_modifikasi(temp, hum, sun, wind, c_factor=1.1):
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
        
        # 4. Radiasi
        ra_bulanan = [15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7]
        if len(T) == 24:
            Ra = []
            for val in ra_bulanan: Ra.extend([val, val])
            Ra = np.array(Ra)
        else:
            Ra = np.array(ra_bulanan)

        # Hitung
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

# --- 3. STATE MANAGEMENT ---
def init_state():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])

    if 'df_iklim_24' not in st.session_state:
        st.session_state['df_iklim_24'] = pd.DataFrame({
            'Periode': periods,
            'Suhu (°C)': [27.0]*24,
            'Kelembaban (%)': [80.0]*24,
            'Penyinaran (%)': [50.0]*24,
            'Angin (km/jam)': [10.0]*24
        })

init_state()

# --- 4. SIDEBAR (MANUAL TRIGGER IMPORT) ---
with st.sidebar:
    st.header("📂 File & Tools")
    
    # Template
    df_template = pd.DataFrame({
        'Suhu': [27.5, 28.0], 'RH': [80, 82], 'Sinar': [50, 60], 'Angin': [10, 12]
    })
    csv_template = df_template.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Template CSV", data=csv_template, file_name="template_iklim.csv", mime="text/csv")

    st.divider()

    # --- UPLOAD SECTION ---
    uploaded_file = st.file_uploader("Upload Data (JSON / CSV)", type=["json", "csv"])
    
    # VARIABLE KONFIGURASI
    convert_wind = False
    convert_sun = False
    max_sun_hour = 12.0
    
    # JIKA CSV DI-UPLOAD
    if uploaded_file is not None and uploaded_file.name.endswith('.csv'):
        # 1. Tampilkan Opsi Konversi
        with st.expander("⚙️ Opsi Konversi Satuan", expanded=True):
            st.info("Centang jika data CSV berbeda satuan:")
            convert_wind = st.checkbox("Angin (m/s) ➡️ km/jam", value=True) 
            convert_sun = st.checkbox("Sinar (Jam) ➡️ Persen (%)", value=True) 
            if convert_sun:
                max_sun_hour = st.number_input("Max Penyinaran (Jam/Hari)", 8.0, 14.0, 12.0)

        # 2. TOMBOL EKSEKUSI (INI YANG KAKAK MINTA)
        if st.button("🔄 Proses & Masukkan ke Tabel", type="primary"):
            try:
                # A. BACA FILE (Coba Koma dulu, lalu Titik Koma)
                try:
                    df_csv = pd.read_csv(uploaded_file)
                    if df_csv.shape[1] < 2:
                        uploaded_file.seek(0)
                        df_csv = pd.read_csv(uploaded_file, sep=';')
                except:
                    uploaded_file.seek(0)
                    df_csv = pd.read_csv(uploaded_file, sep=';')
                
                # B. FILTER KOLOM ANGKA
                df_numeric = df_csv.select_dtypes(include=[np.number])
                
                if df_numeric.shape[1] >= 4:
                    vals = df_numeric.iloc[:, :4].values
                    
                    raw_suhu = vals[:, 0]
                    raw_rh = vals[:, 1]
                    raw_sun = vals[:, 2]
                    raw_wind = vals[:, 3]
                    
                    # C. KONVERSI
                    if convert_wind: raw_wind = raw_wind * 3.6
                    if convert_sun:
                        if np.mean(raw_sun) > 24: # Asumsi jam bulanan
                            raw_sun = (raw_sun / 30 / max_sun_hour) * 100
                        else: # Asumsi jam harian
                            raw_sun = (raw_sun / max_sun_hour) * 100
                        raw_sun = np.where(raw_sun > 100, 100, raw_sun)

                    # D. EXPAND (12 -> 24)
                    new_suhu, new_rh, new_sun, new_wind = [], [], [], []
                    
                    if len(df_csv) == 12:
                        for i in range(12):
                            new_suhu.extend([raw_suhu[i], raw_suhu[i]])
                            new_rh.extend([raw_rh[i], raw_rh[i]])
                            new_sun.extend([raw_sun[i], raw_sun[i]])
                            new_wind.extend([raw_wind[i], raw_wind[i]])
                        st.toast("✅ Data Bulanan berhasil di-expand!")
                            
                    elif len(df_csv) >= 24:
                        new_suhu = raw_suhu[:24]
                        new_rh = raw_rh[:24]
                        new_sun = raw_sun[:24]
                        new_wind = raw_wind[:24]
                        st.toast("✅ Data 24 Periode berhasil dimuat!")
                    
                    # E. UPDATE STATE & RERUN (KUNCI AGAR TABEL BERUBAH)
                    st.session_state['df_iklim_24']['Suhu (°C)'] = new_suhu
                    st.session_state['df_iklim_24']['Kelembaban (%)'] = new_rh
                    st.session_state['df_iklim_24']['Penyinaran (%)'] = new_sun
                    st.session_state['df_iklim_24']['Angin (km/jam)'] = new_wind
                    
                    st.rerun() # <--- INI YANG BIKIN INSTANT UPDATE
                    
                else:
                    st.error("❌ Format CSV Salah! Tidak ditemukan 4 kolom angka.")

            except Exception as e:
                st.error(f"Error: {e}")

    # JIKA JSON (PROJECT SAVE)
    elif uploaded_file is not None and uploaded_file.name.endswith('.json'):
        if st.button("📂 Load Data JSON"):
            data_load = json.load(uploaded_file)
            if 'df_iklim_data' in data_load:
                st.session_state['df_iklim_24'] = pd.DataFrame(data_load['df_iklim_data'])
                st.session_state['temp_c_factor'] = data_load.get('c_factor', 1.1)
                st.success("✅ Data Project Dimuat!")
                st.rerun()

    st.divider()
    st.header("Parameter")
    def_c = st.session_state.get('temp_c_factor', 1.1)
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, def_c, 0.1)
    
    # Save Button
    data_save = {
        'df_iklim_data': st.session_state['df_iklim_24'].to_dict(orient='records'),
        'c_factor': c_factor
    }
    st.download_
