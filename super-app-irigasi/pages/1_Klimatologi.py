import streamlit as st
import pandas as pd
import numpy as np
import json

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Analisa Klimatologi (15 Harian)", layout="wide", page_icon="🌦️")

st.markdown("""
<style>
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

# --- 2. RUMUS ---
def hitung_penman_modifikasi(temp, hum, sun, wind, c_factor=1.1):
    def to_float(arr): return np.array([float(x) for x in arr])
    try:
        T = to_float(temp)
        RH = to_float(hum)
        n = to_float(sun)
        u_km_jam = to_float(wind)
        u_km_day = u_km_jam * 24 
        ea = 6.11 * np.exp((17.27 * T) / (T + 237.3))
        ed = ea * (RH / 100)
        W = 0.4025 + 0.013 * T - 0.0001 * (T**2)
        fu = 0.27 * (1 + u_km_day / 100)
        ra_bulanan = [15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7]
        if len(T) == 24:
            Ra = []
            for val in ra_bulanan: Ra.extend([val, val])
            Ra = np.array(Ra)
        else: Ra = np.array(ra_bulanan)
        Rs = (0.25 + 0.54 * (n/100)) * Ra
        Rns = (1 - 0.20) * Rs
        func_t = 11.0 + 0.22 * T 
        func_ed = 0.34 - 0.044 * np.sqrt(ed)
        func_n = 0.1 + 0.9 * (n/100)
        Rnl = func_t * func_ed * func_n
        Rn = Rns - Rnl
        ETo_star = W * Rn + (1 - W) * fu * (ea - ed)
        ETo = c_factor * ETo_star
        return ETo
    except: return np.zeros(len(temp))

# --- 3. STATE ---
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
            'Angin (m/s)': [1.5]*24
        })
init_state()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📂 File & Tools")
    
    # Template
    df_template = pd.DataFrame({'Suhu': [27.5, 28.0], 'RH': [80, 82], 'Sinar': [50, 60], 'Angin': [10, 12]})
    st.download_button("📥 Template CSV", df_template.to_csv(index=False).encode('utf-8'), "template_iklim.csv", "text/csv")
    
    st.divider()
    
    # Upload & Proses (SMART CSV READER)
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    convert_wind = False
    convert_sun = False
    max_sun_hour = 12.0
    
    if uploaded_file is not None:
        with st.expander("⚙️ Opsi Konversi Satuan", expanded=True):
            st.info("Matikan centang jika data sudah dalam satuan m/s dan %")
            convert_wind = st.checkbox("Angin m/s ➡️ km/jam", value=False) 
            convert_sun = st.checkbox("Sinar Jam ➡️ Persen (%)", value=False) 
            if convert_sun: max_sun_hour = st.number_input("Max Jam/Hari", 8.0, 14.0, 12.0)

        if st.button("🔄 Proses & Masukkan ke Tabel", type="primary"):
            try:
                # 1. SMART READ (Coba Koma, Coba Titik Koma)
                df_csv = None
                file_opts = [
                    {'sep': ',', 'dec': '.'}, 
                    {'sep': ';', 'dec': '.'}, # Ini yang cocok buat file Kakak
                    {'sep': ';', 'dec': ','}
                ]
                
                for opt in file_opts:
                    try:
                        uploaded_file.seek(0)
                        temp_df = pd.read_csv(uploaded_file, sep=opt['sep'], decimal=opt['dec'])
                        # Cek apakah kolomnya cukup?
                        if temp_df.select_dtypes(include=[np.number]).shape[1] >= 4:
                            df_csv = temp_df
                            break
                    except: pass
                
                # 2. PROSES DATA
                if df_csv is not None:
                    df_numeric = df_csv.select_dtypes(include=[np.number])
                    vals = df_numeric.iloc[:, :4].values
                    r_suhu, r_rh, r_sun, r_wind = vals[:,0], vals[:,1], vals[:,2], vals[:,3]
                    
                    # Logika Konversi
                    # Note: Jika data Kakak m/s, tapi rumus butuh km/jam, kita kali 3.6 di sini
                    if convert_wind: r_wind_km = r_wind * 3.6
                    else: r_wind_km = r_wind * 3.6 # Asumsi input m/s, dikonversi ke km/jam utk Rumus Penman
                    
                    if convert_sun:
                        if np.mean(r_sun) > 24: r_sun = (r_sun / 30 / max_sun_hour) * 100
                        else: r_sun = (r_sun / max_sun_hour) * 100
                        r_sun = np.where(r_sun > 100, 100, r_sun)

                    n_suhu, n_rh, n_sun, n_wind = [], [], [], []
                    if len(df_csv) == 12:
                        for i in range(12):
                            n_suhu.extend([r_suhu[i]]*2); n_rh.extend([r_rh[i]]*2); n_sun.extend([r_sun[i]]*2); n_wind.extend([r_wind[i]]*2) # Simpan m/s di tabel visual
                    elif len(df_csv) >= 24:
                        n_suhu, n_rh, n_sun, n_wind = r_suhu[:24], r_rh[:24], r_sun[:24], r_wind[:24]
                    
                    st.session_state['df_iklim_24']['Suhu (°C)'] = n_suhu
                    st.session_state['df_iklim_24']['Kelembaban (%)'] = n_rh
                    st.session_state['df_iklim_24']['Penyinaran (%)'] = n_sun
                    st.session_state['df_iklim_24']['Angin (m/s)'] = n_wind
                    st.success("✅ Data Berhasil Masuk!")
                    st.rerun()
                else: st.error("❌ Format CSV Salah (Minimal 4 kolom angka)")
            except Exception as e: st.error(f"Error: {e}")

    st.divider()
    st.header("Parameter")
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, 0.9, 0.1) # Default 0.9 biar ETo ga ketinggian

# --- 5. MAIN CONTENT ---
st.title("🌦️ Klimatologi (Sistem 15 Harian)")
st.caption("Metode Penman Modifikasi (KP-01) - 24 Periode")

st.subheader("1. Input Data Iklim")
# Hapus use_container_width agar log bersih
edited_df = st.data_editor(st.session_state['df_iklim_24'], height=400, hide_index=True) 
st.session_state['df_iklim_24'] = edited_df

# Proses Hitung
try:
    suhu = edited_df['Suhu (°C)'].tolist()
    hum = edited_df['Kelembaban (%)'].tolist()
    sun = edited_df['Penyinaran (%)'].tolist()
    wind_ms = edited_df['Angin (m/s)'].tolist()
    
    # Konversi m/s ke km/jam untuk rumus
    wind_km = [x * 3.6 for x in wind_ms]
    
    eto_result = hitung_penman_modifikasi(suhu, hum, sun, wind_km, c_factor=c_factor)
    
    df_hasil = edited_df[['Periode']].copy()
    df_hasil['ETo (mm/hari)'] = np.round(eto_result, 2)
    st.session_state['data_eto_transfer'] = df_hasil['ETo (mm/hari)'].tolist()
    
    st.subheader("2. Hasil Perhitungan")
    col1, col2 = st.columns([2, 1])
    with col1:
        num_cols = df_hasil.select_dtypes(include=[np.number]).columns
        # Hapus use_container_width di sini juga
        st.dataframe(df_hasil.style.background_gradient(cmap="Oranges", subset=['ETo (mm/hari)']).format("{:.2f}", subset=num_cols), height=400)
        
        st.divider()
        if st.button("🚀 KIRIM DATA ETo", type="primary"):
            st.session_state['data_eto_manual'] = df_hasil['ETo (mm/hari)'].tolist()
            st.markdown('<div class="success-box">✅ Terkirim! Buka Page Pola Tanam & Irigasi.</div>', unsafe_allow_html=True)
    with col2:
        rata_eto = np.mean(eto_result)
        st.markdown(f"""<div class="metric-card"><h4>Rata-rata ETo</h4><h2 style="margin:0;">{rata_eto:.2f} mm/hari</h2></div>""", unsafe_allow_html=True)
        st.bar_chart(df_hasil.set_index('Periode')['ETo (mm/hari)'])
except Exception as e: st.error(f"⚠️ Error: {e}")
