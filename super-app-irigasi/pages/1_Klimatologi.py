import streamlit as st
import pandas as pd
import numpy as np
import math
import altair as alt
import json

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ETo Smart Calc", layout="wide", page_icon="☀️")

# --- CSS UI ---
st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] {display: none !important;}
        .no-print {display: none !important;}
    }
    .box-hasil {padding: 15px; background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 5px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. RUMUS FAO-56 PENMAN-MONTEITH (ENGINE)
# ==========================================
def calc_eto_fao56(row, lat_deg, elev_m):
    # Konversi Lintang ke Radian
    lat_rad = math.radians(lat_deg)
    
    # Ambil Data Baris
    T_max = row['T Max (°C)']
    T_min = row['T Min (°C)']
    RH_mean = row['RH Mean (%)']
    u2 = row['Angin u2 (m/s)']
    n_sun = row['Sinar (jam)']
    
    # 1. Mean Temperature
    T_mean = (T_max + T_min) / 2
    
    # 2. Slope Vapor Pressure Curve (Delta)
    delta = 4098 * (0.6108 * math.exp(17.27 * T_mean / (T_mean + 237.3))) / ((T_mean + 237.3)**2)
    
    # 3. Psychrometric Constant (Gamma)
    P = 101.3 * ((293 - 0.0065 * elev_m) / 293)**5.26 
    gamma = 0.665e-3 * P
    
    # 4. Vapor Pressure Deficit (es - ea)
    es_tmax = 0.6108 * math.exp(17.27 * T_max / (T_max + 237.3))
    es_tmin = 0.6108 * math.exp(17.27 * T_min / (T_min + 237.3))
    es = (es_tmax + es_tmin) / 2
    ea = es * (RH_mean / 100)
    
    # 5. Solar Radiation (Rs) & Net Radiation (Rn)
    # Estimasi Ra (Extraterrestrial Radiation) Harian Rata-rata untuk Tropis
    Ra_list = [15.0, 15.5, 15.7, 15.3, 14.5, 14.0, 14.2, 14.8, 15.4, 15.6, 15.2, 14.8] 
    # Karena kita hitung per baris (bulan ke-n), kita pakai angka pendekatan Ra = 37 MJ/m2 (Rata2 Khatulistiwa)
    # Agar lebih presisi, idealnya pakai urutan bulan, tapi untuk simplifikasi kita pakai konstanta rata-rata tropis.
    Ra = 37.0 
    
    N = 12.0 # Siang hari di khatulistiwa
    Rs = (0.25 + 0.50 * (n_sun / N)) * Ra 
    
    Rns = (1 - 0.23) * Rs
    
    sigma = 4.903e-9
    Rnl = sigma * ((T_max + 273.16)**4 + (T_min + 273.16)**4) / 2 * (0.34 - 0.14 * math.sqrt(ea)) * (1.35 * (Rs / (0.75 * Ra)) - 0.35)
    
    Rn = Rns - Rnl
    G = 0 
    
    # 6. FINAL FORMULA ETo
    term1 = 0.408 * delta * (Rn - G)
    term2 = gamma * (900 / (T_mean + 273)) * u2 * (es - ea)
    div = delta + gamma * (1 + 0.34 * u2)
    
    ETo = (term1 + term2) / div
    return max(0, ETo)

# ==========================================
# 2. SESSION STATE
# ==========================================
if 'df_iklim' not in st.session_state:
    st.session_state['df_iklim'] = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'T Min (°C)': [24.0]*12,
        'T Max (°C)': [31.0]*12,
        'RH Mean (%)': [80.0]*12,
        'Angin u2 (m/s)': [2.0]*12,
        'Sinar (jam)': [6.0]*12
    })
if 'params_loc' not in st.session_state:
    st.session_state['params_loc'] = {'nama': 'Stasiun Branti', 'lat': -5.4, 'elev': 100}

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.title("⚙️ Lokasi Stasiun")
    st.session_state['params_loc']['nama'] = st.text_input("Nama Stasiun", st.session_state['params_loc']['nama'])
    
    st.markdown("---")
    st.info("Parameter Geografis:")
    st.session_state['params_loc']['lat'] = st.number_input("Lintang (Latitude)", value=st.session_state['params_loc']['lat'], step=0.1)
    st.session_state['params_loc']['elev'] = st.number_input("Elevasi (MDPL)", value=st.session_state['params_loc']['elev'], step=10)
    
    st.markdown("---")
    st.subheader("📂 File Manager")
    
    # Save
    data_save = {'loc': st.session_state['params_loc'], 'iklim': st.session_state['df_iklim'].to_dict(orient='records')}
    st.download_button("💾 Simpan Data", json.dumps(data_save), "data_iklim_eto.json", "application/json")
    
    # Load
    upload = st.file_uploader("📂 Buka Data", type=['json'])
    if upload:
        try:
            d = json.load(upload)
            st.session_state['params_loc'] = d['loc']
            st.session_state['df_iklim'] = pd.DataFrame(d['iklim'])
            st.success("Data Loaded!")
        except:
            st.error("File Salah!")

# ==========================================
# 4. MAIN CONTENT
# ==========================================
st.title("☀️ ETo Smart Calculator")
st.markdown("Metode: **FAO-56 Penman-Monteith**")
st.markdown("---")

col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader("1. Input Data Iklim")
    st.caption("Edit data di bawah ini:")
    
    edited_df = st.data_editor(
        st.session_state['df_iklim'],
        column_config={
            "T Min (°C)": st.column_config.NumberColumn(format="%.1f"),
            "T Max (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Angin u2 (m/s)": st.column_config.NumberColumn(format="%.2f"),
        },
        height=460,
        use_container_width=True,
        key='editor_iklim'
    )
    st.session_state['df_iklim'] = edited_df

# HITUNG
results = []
for idx, row in st.session_state['df_iklim'].iterrows():
    eto = calc_eto_fao56(row, st.session_state['params_loc']['lat'], st.session_state['params_loc']['elev'])
    results.append(eto)

df_result = st.session_state['df_iklim'].copy()
df_result['ETo (mm/hari)'] = results
eto_avg = sum(results) / 12

with col2:
    st.subheader("2. Hasil ETo")
    st.metric("Rata-rata Tahunan", f"{eto_avg:.2f} mm/hari")
    
    # Tabel Hasil (Tanpa Background Gradient biar gak error)
    st.dataframe(
        df_result[['Bulan', 'ETo (mm/hari)']].style.format({"ETo (mm/hari)": "{:.2f}"}),
        use_container_width=True,
        height=460
    )

# GRAFIK
st.markdown("---")
st.subheader("3. Grafik Pola Evapotranspirasi")
chart = alt.Chart(df_result).mark_bar(color='orange').encode(
    x=alt.X('Bulan', sort=None), y='ETo (mm/hari)', tooltip=['Bulan', alt.Tooltip('ETo (mm/hari)', format='.2f')]
).properties(height=300)
line = alt.Chart(df_result).mark_rule(color='red').encode(y=alt.datum(eto_avg))
st.altair_chart((chart + line).interactive(), use_container_width=True)
