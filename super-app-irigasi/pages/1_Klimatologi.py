import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 1. CONFIG HALAMAN ---
st.set_page_config(page_title="Analisa Klimatologi Pro", layout="wide", page_icon="🌦️")

# --- 2. ENGINE PERHITUNGAN (HIGH ACCURACY - KP-01) ---

def get_julian_day(period_index):
    """
    Mengubah index periode (0-23) menjadi estimasi Julian Day (Hari ke-n dalam setahun).
    Asumsi: Periode 1 = tgl 15, Periode 2 = akhir bulan.
    """
    # Perkiraan hari pertengahan untuk setiap periode 2 mingguan
    # Jan-1 (15), Jan-2 (31), Feb-1 (45), dst...
    days = [
        15, 31,   # Jan
        45, 59,   # Feb
        74, 90,   # Mar
        105, 120, # Apr
        135, 151, # Mei
        166, 181, # Jun
        196, 212, # Jul
        227, 243, # Agu
        258, 273, # Sep
        288, 304, # Okt
        319, 334, # Nov
        349, 365  # Des
    ]
    return days[period_index]

def hitung_ra_astronomis(lat_deg, period_index):
    """
    Menghitung Radiasi Ekstraterestrial (Ra) secara presisi
    berdasarkan Lintang dan Hari ke-n (Julian Day).
    Output: mm/hari
    """
    J = get_julian_day(period_index)
    lat_rad = math.radians(lat_deg)
    
    # 1. Inverse relative distance Earth-Sun (dr)
    dr = 1 + 0.033 * math.cos(2 * math.pi * J / 365)
    
    # 2. Solar declination (delta)
    solar_decl = 0.409 * math.sin((2 * math.pi * J / 365) - 1.39)
    
    # 3. Sunset hour angle (ws)
    # Handle kutub (jarang terjadi di Indo, tapi good practice)
    tan_val = -math.tan(lat_rad) * math.tan(solar_decl)
    if tan_val < -1: ws = math.pi
    elif tan_val > 1: ws = 0
    else: ws = math.acos(tan_val)
    
    # 4. Solar constant (Gsc) = 0.0820 MJ m-2 min-1
    Gsc = 0.0820
    
    # 5. Ra (MJ/m2/day)
    Ra_MJ = (24 * 60 / math.pi) * Gsc * dr * (
        ws * math.sin(lat_rad) * math.sin(solar_decl) +
        math.cos(lat_rad) * math.cos(solar_decl) * math.sin(ws)
    )
    
    # 6. Konversi ke mm/hari (1 MJ/m2 = 0.408 mm)
    return Ra_MJ * 0.408

def hitung_penman_modifikasi_presisi(df, lat, elev, c_factor):
    """
    Looping perhitungan Penman Modifikasi (KP-01) untuk setiap baris data.
    """
    results_eto = []
    
    for idx, row in df.iterrows():
        try:
            # Ambil Data
            T = float(row['Suhu (°C)'])
            RH = float(row['Kelembaban (%)'])
            n_sun = float(row['Penyinaran (%)']) # Dalam Persen
            u_ms = float(row['Angin (m/s)'])
            
            # A. Parameter Uap Air
            # ea (Tekanan uap jenuh - mbar)
            ea = 6.11 * math.exp((17.27 * T) / (T + 237.3))
            # ed (Tekanan uap aktual - mbar)
            ed = ea * (RH / 100)
            
            # B. Fungsi Angin f(u) -> Rumus KP-01: 0.27(1 + 0.864 * u2)
            fu = 0.27 * (1 + 0.864 * u_ms)
            
            # C. Faktor Pembobot (W)
            # Delta
            delta = 4098 * (0.6108 * math.exp(17.27 * T / (T + 237.3))) / ((T + 237.3)**2)
            # Gamma (Konstanta Psikrometrik) - Koreksi Elevasi
            P = 101.3 * ((293 - 0.0065 * elev) / 293)**5.26
            gamma = 0.665e-3 * P * 10 # *10 agar scale mbar match
            
            W = delta / (delta + gamma)
            
            # D. Radiasi (Rn)
            # 1. Ra (Astronomis)
            Ra = hitung_ra_astronomis(lat, idx) # idx 0-23
            
            # 2. Rs (Shortwave) - KP01 Indonesia a=0.25, b=0.54
            # n_sun input adalah %, jadi bagi 100 untuk n/N
            Rs = (0.25 + 0.54 * (n_sun / 100)) * Ra
            
            # 3. Rns (Net Shortwave) - Albedo 0.25
            Rns = (1 - 0.25) * Rs
            
            # 4. Rnl (Net Longwave)
            # Stefan-Boltzmann constant convert to mm/day equivalent approx 2.043e-10 * T^4
            # Namun rumus KP-01 sering memakai tabel f(T). Kita pakai pendekatan rumus langsung:
            sigma_mm = 2.043e-10 
            ft = sigma_mm * ((T + 273.16)**4)
            fed = 0.34 - 0.044 * math.sqrt(ed)
            fsun = 0.1 + 0.9 * (n_sun / 100)
            
            Rnl = ft * fed * fsun
            
            # Net Radiation
            Rn = Rns - Rnl
            
            # E. ETo Final
            # Rumus: c * [W.Rn + (1-W).f(u).(ea-ed)]
            ETo_val = c_factor * (W * Rn + (1 - W) * fu * (ea - ed))
            
            results_eto.append(max(0, ETo_val))
            
        except Exception as e:
            results_eto.append(0)
            
    return results_eto

# --- 3. INIT STATE ---
def init_state():
    # 24 Periode (Jan-1 s/d Des-2)
    periods = [f"{m}-{p}" for m in ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'] for p in [1, 2]]
    
    if 'df_iklim_24' not in st.session_state:
        st.session_state['df_iklim_24'] = pd.DataFrame({
            'Periode': periods,
            'Suhu (°C)': [27.5]*24, 
            'Kelembaban (%)': [82.0]*24, 
            'Penyinaran (%)': [65.0]*24, 
            'Angin (m/s)': [1.8]*24
        })

init_state()

# --- 4. SIDEBAR (PARAMETER LOKASI & KALIBRASI) ---
with st.sidebar:
    st.header("⚙️ Parameter Lokasi")
    
    lat_input = st.number_input("Lintang (Latitude)", value=-6.2, step=0.1, help="Gunakan minus (-) untuk LS.")
    elev_input = st.number_input("Elevasi (m dpl)", value=10.0, step=10.0)

    st.divider()
    st.header("🎚️ Kalibrasi (KP-01)")
    
    # PANDUAN FAKTOR C (Baru)
    st.info("💡 **Tips Faktor C:**\n- Basah/Hujan (RH>80%): **0.8 - 0.9**\n- Sedang (RH 60-80%): **0.9 - 1.0**\n- Kering/Panas (RH<60%): **1.0 - 1.1**")
    
    # Default saya turunkan ke 0.9 (Aman untuk Indonesia)
    c_factor = st.number_input("Faktor Koreksi (c)", value=0.90, step=0.05, min_value=0.5, max_value=1.5)

    st.divider()
    st.header("📂 Data Input")
    uploaded_file = st.file_uploader("Upload Excel / CSV", type=["xlsx", "csv"])
    
    # ... (Sisa kode logika upload file biarkan sama) ...
    if uploaded_file and st.button("🔄 PROSES FILE", type="primary"):
        # Copy-paste logika baca file dari kode sebelumnya di sini
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df_up = pd.read_excel(uploaded_file)
            else:
                df_up = pd.read_csv(uploaded_file, sep=None, engine='python')
                
            df_num = df_up.select_dtypes(include=[np.number])
            if df_num.shape[1] >= 4:
                vals = df_num.iloc[:, :4].values
                if len(vals) == 12:
                    new_vals = np.repeat(vals, 2, axis=0)
                else:
                    new_vals = vals[:24]
                
                limit = min(len(new_vals), 24)
                st.session_state['df_iklim_24'].iloc[:limit, 1] = new_vals[:limit, 0] # Suhu
                st.session_state['df_iklim_24'].iloc[:limit, 2] = new_vals[:limit, 1] # RH
                st.session_state['df_iklim_24'].iloc[:limit, 3] = new_vals[:limit, 2] # Sun
                st.session_state['df_iklim_24'].iloc[:limit, 4] = new_vals[:limit, 3] # Wind
                
                st.success("Data berhasil dimuat!")
                st.rerun()
        except Exception as e:
            st.error(f"Gagal baca file: {e}")

# --- 5. MAIN CONTENT ---
st.title("🌦️ Analisa Klimatologi (Presisi)")
st.markdown(f"""
**Metode:** Penman Modifikasi (KP-01) dengan **Koreksi Astronomis**.  
Lokasi Studi: Lat **{lat_input}°**, Elev **{elev_input} m**, Faktor C **{c_factor}**
""")

# DATA EDITOR
edited_df = st.data_editor(
    st.session_state['df_iklim_24'], 
    height=400, 
    hide_index=True,
    column_config={
        "Periode": st.column_config.TextColumn(disabled=True),
        "Suhu (°C)": st.column_config.NumberColumn(format="%.1f"),
        "Kelembaban (%)": st.column_config.NumberColumn(format="%.0f"),
        "Penyinaran (%)": st.column_config.NumberColumn(format="%.0f"),
        "Angin (m/s)": st.column_config.NumberColumn(format="%.2f"),
    }
)

# SYNC BACK TO STATE
st.session_state['df_iklim_24'] = edited_df

# --- HITUNG ETo ---
# Panggil fungsi presisi
eto_results = hitung_penman_modifikasi_presisi(
    edited_df, 
    lat_input, 
    elev_input, 
    c_factor
)

# PREPARE RESULT DATAFRAME
df_res = edited_df[['Periode']].copy()
df_res['ETo (mm/hari)'] = np.round(eto_results, 2)

# --- VISUALISASI ---
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("Hasil Perhitungan")
    st.dataframe(
        df_res.style.background_gradient(cmap="Blues", subset=['ETo (mm/hari)']), 
        height=400, 
        use_container_width=True
    )
    
    if st.button("🚀 KIRIM DATA KE MODUL LAIN", type="primary"):
        st.session_state['data_eto_fix'] = df_res['ETo (mm/hari)'].tolist()
        st.success(f"✅ {len(df_res)} Data ETo berhasil disimpan ke memori aplikasi!")

with c2:
    avg_eto = np.mean(eto_results)
    st.metric("Rata-rata ETo Tahunan", f"{avg_eto:.2f} mm/hari")
    
    # Grafik Simple
    st.caption("Grafik Distribusi ETo")
    st.bar_chart(df_res.set_index('Periode')['ETo (mm/hari)'])

# FOOTER EXPLANATION
st.info("""
**ℹ️ Note Akurasi Tinggi:** Berbeda dengan tabel Ra statis, modul ini menghitung **Radiasi Ekstraterestrial (Ra)** secara dinamis berdasarkan input **Lintang (Latitude)** dan **Tanggal (Periode)**. 
Ini memastikan nilai radiasi sesuai dengan posisi matahari sebenarnya terhadap lokasi bendung/irigasi Anda (Standar Engineering).
""")

