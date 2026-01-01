import streamlit as st
import pandas as pd
import numpy as np
import math
import altair as alt
import json

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="ETo Calculator (Hydro Planner) - ETo", layout="wide", page_icon="💧")

# ==========================================
# CSS UI & BRANDING SMARTSTUDIO
# ==========================================
st.markdown("""
<style>
    /* Footer Branding SmartStudio - Pojok Kanan Bawah */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: rgba(255, 255, 255, 0.9); /* Sedikit transparan */
        color: #666;
        text-align: right;
        padding-right: 20px;
        padding-bottom: 5px;
        padding-top: 5px;
        font-size: 11px;
        font-family: 'Source Sans Pro', sans-serif;
        border-top: 1px solid #eee;
        z-index: 9999;
    }
    .footer span {
        font-weight: 700;
        color: #FF4B4B; /* Aksen Merah */
    }
    .footer-email {
        color: #555;
        font-style: italic;
        margin-right: 10px;
    }
    .footer-app-name {
        font-weight: 600;
        color: #444;
        margin-right: 5px;
    }

    /* Print settings */
    @media print {
        [data-testid="stSidebar"] {display: none !important;}
        .footer {display: none !important;}
        .no-print {display: none !important;}
    }

    /* Styling Box Hasil */
    .box-hasil {
        padding: 20px; 
        background: linear-gradient(to right, #f8f9fa, #e9ecef); 
        border-radius: 12px; 
        border-left: 5px solid #0068c9;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. ENGINE: PENMAN MODIFIKASI (KP-01)
# ==========================================

def calc_ra_daily(lat_deg, month_idx):
    """Menghitung Radiasi Ekstraterestrial (Ra) mm/hari ekuivalen"""
    days_cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    J = days_cum[month_idx] + 15 
    lat_rad = math.radians(lat_deg)
    
    dr = 1 + 0.033 * math.cos(2 * math.pi * J / 365)
    solar_decl = 0.409 * math.sin((2 * math.pi * J / 365) - 1.39)
    
    tan_val = -math.tan(lat_rad) * math.tan(solar_decl)
    if tan_val < -1: ws = math.pi
    elif tan_val > 1: ws = 0
    else: ws = math.acos(tan_val)
    
    Gsc = 0.0820
    # Ra dalam MJ/m2/hari
    Ra_MJ = (24 * 60 / math.pi) * Gsc * dr * (
        ws * math.sin(lat_rad) * math.sin(solar_decl) +
        math.cos(lat_rad) * math.cos(solar_decl) * math.sin(ws)
    )
    # Konversi ke mm/hari (1 MJ/m2 = 0.408 mm)
    return Ra_MJ * 0.408

def calc_penman_modif(row, lat_deg, elev_m, month_idx):
    """
    Rumus Penman Modifikasi sesuai Standar KP-01
    ETo = c * [W * Rn + (1-W) * f(u) * (ea - ed)]
    """
    # 1. Data Input
    T_mean = row['T Mean (°C)']
    RH = row['RH Mean (%)']
    u2 = row['Angin u2 (m/s)']
    n_sun = row['Sinar (jam)']
    c_factor = row['Faktor C'] # Angka Koreksi Penman

    # 2. Parameter Uap Air (ea, ed)
    # Tekanan uap jenuh (ea) dalam mbar
    ea = 6.11 * math.exp((17.27 * T_mean) / (T_mean + 237.3))
    # Tekanan uap aktual (ed)
    ed = ea * (RH / 100)
    
    # 3. Fungsi Angin f(u)
    # Rumus umum KP-01: f(u) = 0.27 * (1 + 0.864 * u2)
    fu = 0.27 * (1 + 0.864 * u2)

    # 4. Faktor Pembobot (Weighting Factor W)
    # Hitung Delta
    delta = 4098 * (0.6108 * math.exp(17.27 * T_mean / (T_mean + 237.3))) / ((T_mean + 237.3)**2)
    # Hitung Gamma (Psychrometric constant)
    P = 101.3 * ((293 - 0.0065 * elev_m) / 293)**5.26
    gamma = 0.665e-3 * P * 10 # dikali 10 agar satuan konsisten mbar
    
    # Rumus W
    W = delta / (delta + gamma)

    # 5. Radiasi (Rn)
    # Ra (Ekstraterestrial)
    Ra = calc_ra_daily(lat_deg, month_idx)
    
    # Durasi maksimum penyinaran (N)
    lat_rad = math.radians(lat_deg)
    # Hitung sudut jam matahari terbenam
    val_acos = -math.tan(lat_rad) * math.tan(0.409 * math.sin((2*math.pi*(month_idx*30+15)/365)-1.39))
    # Clip value untuk menghindari domain error acos
    val_acos = max(-1.0, min(1.0, val_acos))
    ws_val = math.acos(val_acos)
    
    N = (24 / math.pi) * ws_val
    
    # Rs (Radiasi Gelombang Pendek) - KP-01: a=0.25, b=0.54
    Rs = (0.25 + 0.54 * (n_sun / N)) * Ra
    
    # Rns (Net Shortwave) - Albedo 0.25
    Rns = (1 - 0.25) * Rs
    
    # Rnl (Net Longwave)
    sigma_mm = 2.043e-10 # Konstanta Stefan-Boltzmann dlm mm/hari
    ft = sigma_mm * ((T_mean + 273.16)**4)
    fed = 0.34 - 0.044 * math.sqrt(ed)
    f_sun = 0.1 + 0.9 * (n_sun / N)
    Rnl = ft * fed * f_sun
    
    # Rn (Radiasi Bersih)
    Rn = Rns - Rnl

    # 6. ETo* (Unadjusted)
    ETo_star = (W * Rn) + ((1 - W) * fu * (ea - ed))
    
    # 7. ETo Final (Adjusted with c)
    ETo = c_factor * ETo_star
    
    return max(0, ETo)

# ==========================================
# 2. SESSION STATE
# ==========================================
if 'df_iklim' not in st.session_state:
    st.session_state['df_iklim'] = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'T Mean (°C)': [26.5]*12,
        'RH Mean (%)': [85.0]*12,
        'Angin u2 (m/s)': [1.5]*12,
        'Sinar (jam)': [5.0]*12,
        'Faktor C': [1.1]*12 # Default angka koreksi Penman Modif
    })

if 'params_loc' not in st.session_state:
    st.session_state['params_loc'] = {'nama': 'Bendung Argoguruh', 'lat': -5.4, 'elev': 100}

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.title("⚙️ Lokasi Studi")
    st.session_state['params_loc']['nama'] = st.text_input("Nama Lokasi/Bendung", st.session_state['params_loc']['nama'])
    
    st.markdown("---")
    st.info("Parameter Geografis:")
    st.session_state['params_loc']['lat'] = st.number_input("Lintang (LS = negatif)", value=st.session_state['params_loc']['lat'], step=0.1)
    st.session_state['params_loc']['elev'] = st.number_input("Elevasi (m dpl)", value=st.session_state['params_loc']['elev'], step=10)
    
    st.markdown("---")
    st.subheader("📂 File Manager")
    
    # Save Feature
    data_save = {'loc': st.session_state['params_loc'], 'iklim': st.session_state['df_iklim'].to_dict(orient='records')}
    st.download_button("💾 Simpan Data (JSON)", json.dumps(data_save), "data_eto_kp01.json", "application/json")
    
    # Load Feature
    upload = st.file_uploader("📂 Buka Data", type=['json'])
    if upload:
        try:
            d = json.load(upload)
            st.session_state['params_loc'] = d['loc']
            st.session_state['df_iklim'] = pd.DataFrame(d['iklim'])
            st.success("Data Berhasil Dimuat!")
            st.rerun()
        except:
            st.error("Format File Salah!")

    st.markdown("---")
    if st.button("🔄 Reset ke Default"):
        st.session_state['df_iklim'] = pd.DataFrame({
            'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
            'T Mean (°C)': [26.5]*12,
            'RH Mean (%)': [85.0]*12,
            'Angin u2 (m/s)': [1.5]*12,
            'Sinar (jam)': [5.0]*12,
            'Faktor C': [1.1]*12
        })
        st.rerun()

# ==========================================
# 4. MAIN LAYOUT
# ==========================================
st.title("🌊 HYDRO PLANNER")
st.markdown(f"**Modul Evapotranspirasi (ETo)** | Metode: **Penman Modifikasi (KP-01)**")
st.markdown("---")

col1, col2 = st.columns([1.6, 1])

with col1:
    st.subheader("1. Input Data Klimatologi")
    st.caption("Sesuaikan **Faktor C** (Angka Koreksi) sesuai karakteristik bulan basah/kering wilayah studi.")
    
    edited_df = st.data_editor(
        st.session_state['df_iklim'],
        column_config={
            "Bulan": st.column_config.TextColumn(disabled=True),
            "T Mean (°C)": st.column_config.NumberColumn(format="%.1f", max_value=45, min_value=10),
            "RH Mean (%)": st.column_config.NumberColumn(format="%.0f", max_value=100, min_value=0),
            "Angin u2 (m/s)": st.column_config.NumberColumn(format="%.2f", min_value=0, help="Kecepatan angin pada ketinggian 2m"),
            "Sinar (jam)": st.column_config.NumberColumn(format="%.1f", min_value=0, max_value=12),
            "Faktor C": st.column_config.NumberColumn(format="%.2f", min_value=0.1, max_value=2.0, help="Angka Koreksi Penman (KP-01)"),
        },
        height=460,
        use_container_width=True,
        key='editor_kp01'
    )
    
    if not edited_df.equals(st.session_state['df_iklim']):
         st.session_state['df_iklim'] = edited_df
         st.rerun()

# --- PROSES HITUNG ---
results = []
lat = st.session_state['params_loc']['lat']
elev = st.session_state['params_loc']['elev']

for idx, row in st.session_state['df_iklim'].iterrows():
    eto = calc_penman_modif(row, lat, elev, idx)
    results.append(eto)

df_result = st.session_state['df_iklim'].copy()
df_result['ETo (mm/hari)'] = results
eto_avg = sum(results) / 12

with col2:
    st.subheader("2. Hasil Analisis")
    
    # Summary Box
    st.markdown(f"""
    <div class="box-hasil">
        <div style="font-size:12px; color:#666; margin-bottom:5px;">Rata-rata ETo Tahunan</div>
        <div style="font-size:28px; font-weight:bold; color:#2c3e50;">{eto_avg:.2f} <span style="font-size:14px;">mm/hari</span></div>
        <div style="font-size:10px; color:#888; margin-top:5px;">*Metode Penman Modifikasi</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Tabel Hasil Ringkas
    st.dataframe(
        df_result[['Bulan', 'Faktor C', 'ETo (mm/hari)']].style.format({"ETo (mm/hari)": "{:.2f}", "Faktor C": "{:.1f}"})
                                              .background_gradient(cmap='Blues', subset=['ETo (mm/hari)']),
        use_container_width=True,
        height=300
    )

# ==========================================
# 5. GRAFIK (Fixed Schema)
# ==========================================
st.markdown("---")
st.subheader("3. Grafik Hidrologi")

# Menyiapkan data agar chart stabil
df_chart = df_result.copy()
df_chart['Rata-rata'] = eto_avg  # Kolom helper untuk garis rata-rata

# Base Chart
base = alt.Chart(df_chart).encode(
    x=alt.X('Bulan', sort=None) 
)

# 1. Bar Chart (ETo Bulanan)
bar = base.mark_bar(color='#4facfe', cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
    y=alt.Y('ETo (mm/hari)', title='Evapotranspirasi (mm/hr)'),
    tooltip=[
        alt.Tooltip('Bulan', title='Bulan'),
        alt.Tooltip('ETo (mm/hari)', format='.2f', title='ETo (mm)')
    ]
)

# 2. Rule Chart (Garis Rata-rata)
rule = base.mark_rule(color='#FF6B6B', strokeDash=[5, 5]).encode(
    y='Rata-rata',
    tooltip=[alt.Tooltip('Rata-rata', format='.2f', title='Rata-rata Tahunan')]
)

# Render Grafik
st.altair_chart((bar + rule).interactive(), use_container_width=True)

# ==========================================
# FOOTER
# ==========================================
st.markdown("""
<div class="footer">
    <span class="footer-app-name">ETo Calculator (Hydro Planner)</span> | 
    <span class="footer-email">smartstudioarsitek@gmail.com-donasi:dana dan gopay 081271859610</span> | 
    by <span>SmartStudio</span>
</div>
""", unsafe_allow_html=True)

