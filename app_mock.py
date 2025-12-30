import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="FJ Mock Analyzer", layout="wide", page_icon="🌊")

# --- CSS ---
st.markdown("""
<style>
    .metric-box {padding:10px; background-color:#e0f7fa; border-radius:5px; margin-bottom:10px; border-left: 5px solid #00acc1;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. SIDEBAR - PARAMETER DAS
# ==========================================
with st.sidebar:
    st.title("🌊 Parameter DAS")
    
    luas_das = st.number_input("Luas DAS (km²)", value=50.0, help="Luas daerah tangkapan air.")
    
    st.markdown("---")
    st.subheader("⚙️ Kalibrasi Tanah")
    
    smc = st.number_input("Soil Moisture Capacity (mm)", value=200.0, help="Kapasitas tanah menyimpan air (SMC). Hutan lebat >300, Tanah biasa 200.")
    infil = st.slider("Koef. Infiltrasi (i)", 0.1, 1.0, 0.4, help="Persen air yang masuk ke tanah dalam.")
    recession = st.slider("Faktor Resesi (k)", 0.1, 1.0, 0.6, help="Kecepatan air tanah mengalir ke sungai (0.6 - 0.7 standar).")
    
    st.markdown("---")
    pf = st.number_input("Faktor Area Terbuka (m)", value=0.0, max_value=50.0, help="Persentase lahan terbuka (biasanya 0-20%).")

# ==========================================
# 2. DATA INPUT (SIMULASI 1 TAHUN)
# ==========================================
if 'df_mock' not in st.session_state:
    # Data Default Dummy
    bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    data = {
        'Bulan': bulan,
        'Hujan (mm)': [250, 220, 180, 150, 100, 50, 20, 10, 80, 150, 200, 280],
        'ETo (mm)': [120, 110, 130, 125, 120, 115, 110, 125, 130, 135, 120, 115], 
        'Jumlah Hari': [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    }
    st.session_state['df_mock'] = pd.DataFrame(data)

# ==========================================
# 3. ENGINE FJ MOCK
# ==========================================
def hitung_mock(df_input, area, smc_cap, i_fact, k_fact, m_fact):
    df = df_input.copy()
    
    # Inisialisasi List
    ea_list, ws_list, ss_list, vn_list = [], [], [], []
    total_runoff_list = []
    q_list = []
    
    # Kondisi Awal
    ss_prev = smc_cap 
    vn_prev = 10.0 
    
    for idx, row in df.iterrows():
        # 1. Evapotranspirasi (Simplifikasi)
        hujan = row['Hujan (mm)']
        eto = row['ETo (mm)']
        ndays = row['Jumlah Hari']
        
        calc_ea = eto 
        water_avail = hujan - calc_ea
        
        # 2. Soil Storage (SS)
        ss_curr = 0
        water_surplus = 0
        
        if water_avail > 0: # Surplus
            ss_curr = ss_prev + water_avail
            if ss_curr > smc_cap:
                water_surplus = ss_curr - smc_cap
                ss_curr = smc_cap
            else:
                water_surplus = 0
        else: # Defisit
            ss_curr = ss_prev + water_avail
            if ss_curr < 0: ss_curr = 0
            water_surplus = 0
            
        # 3. Infiltrasi & Groundwater (Vn)
        infiltrasi = water_surplus * i_fact
        vn_curr = (0.5 * (1 + k_fact) * infiltrasi) + (k_fact * vn_prev)
        
        # 4. Runoff
        baseflow = vn_curr - vn_prev + infiltrasi 
        if baseflow < 0: baseflow = 0 
        
        direct_runoff = water_surplus - infiltrasi
        total_depth = baseflow + direct_runoff
        
        # 5. Konversi Debit (m3/s)
        q_m3s = (total_depth * area * 1000000) / (1000 * ndays * 86400)
        
        ss_list.append(ss_curr)
        ws_list.append(water_surplus)
        vn_list.append(vn_curr)
        total_runoff_list.append(total_depth)
        q_list.append(q_m3s)
        
        ss_prev = ss_curr
        vn_prev = vn_curr

    # Masukkan ke DataFrame
    df['Soil Storage'] = ss_list
    df['Water Surplus'] = ws_list
    df['Total Runoff (mm)'] = total_runoff_list
    df['Debit (m³/s)'] = q_list
    
    return df

# Jalankan Kalkulasi
df_hasil = hitung_mock(st.session_state['df_mock'], luas_das, smc, infil, recession, pf)

# Hitung Q80
q_sorted = sorted(df_hasil['Debit (m³/s)'], reverse=True)
idx_80 = int(0.8 * len(q_sorted))
q_80 = q_sorted[idx_80] if len(q_sorted) > 0 else 0
q_avg = df_hasil['Debit (m³/s)'].mean()

# ==========================================
# 4. TAMPILAN VISUAL
# ==========================================
st.title("🌊 Analisis Ketersediaan Air (F.J. Mock)")
st.markdown(f"**Luas DAS:** {luas_das} km² | **Q Rata-rata:** {q_avg:.2f} m³/s")

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("1. Input Data Bulanan")
    st.caption("Masukkan data Hujan & ETo.")
    edited = st.data_editor(st.session_state['df_mock'], num_rows="dynamic", hide_index=True, use_container_width=True)
    st.session_state['df_mock'] = edited
    
    st.markdown("---")
    st.markdown(f"""
    <div class="metric-box">
    <h3>💧 Debit Andalan (Q80)</h3>
    <h2>{q_80:.3f} m³/s</h2>
    <p>Probabilitas 80% (Aman untuk Irigasi).</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.subheader("2. Hidrograf Aliran")
    
    base = alt.Chart(df_hasil).encode(x=alt.X('Bulan', sort=None))
    
    bar = base.mark_bar(color='#4fc3f7', opacity=0.3).encode(
        y=alt.Y('Hujan (mm)', axis=alt.Axis(title='Hujan (mm)')),
        tooltip=['Bulan', 'Hujan (mm)']
    )
    
    line = base.mark_line(color='#0d47a1', strokeWidth=3).encode(
        y=alt.Y('Debit (m³/s)', axis=alt.Axis(title='Debit Sungai (m³/s)')),
        tooltip=['Bulan', alt.Tooltip('Debit (m³/s)', format='.3f')]
    )
    
    st.altair_chart((bar + line).resolve_scale(y='independent').interactive(), use_container_width=True)

    st.subheader("3. Detail Perhitungan")
    
    # --- PERBAIKAN DI SINI (FORMATTING AMAN) ---
    # Kita pisahkan kolom angka dan kolom teks
    
    format_dict = {
        'Hujan (mm)': '{:.1f}',
        'Water Surplus': '{:.1f}',
        'Soil Storage': '{:.1f}',
        'Total Runoff (mm)': '{:.1f}',
        'Debit (m³/s)': '{:.3f}'
    }
    
    tabel_show = df_hasil[['Bulan', 'Hujan (mm)', 'Water Surplus', 'Soil Storage', 'Total Runoff (mm)', 'Debit (m³/s)']]
    
    st.dataframe(
        tabel_show.style.format(format_dict), # Format hanya diterapkan ke kolom yang ada di kamus
        use_container_width=True
    )