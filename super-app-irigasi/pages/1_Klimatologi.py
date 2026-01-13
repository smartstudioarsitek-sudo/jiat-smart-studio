import streamlit as st
import pandas as pd
import numpy as np
import json
import math
import time

# ==========================================
# 1. CONFIG & CSS (TAMPILAN PREMIUM)
# ==========================================
st.set_page_config(page_title="Hydro Planner Pro", page_icon="💧", layout="wide")

st.markdown("""
<style>
    /* Import Font Google */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&family=Pacifico&display=swap');

    /* Global Font */
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }

    /* Judul Utama Gradient */
    .main-title {
        font-family: 'Poppins', sans-serif;
        font-size: 50px;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #0984e3, #00cec9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: -10px;
    }

    /* Signature Styles */
    .branding-tag {
        font-family: 'Pacifico', cursive;
        font-size: 16px;
        color: #ff7675;
        margin-left: 10px;
        transform: rotate(-5deg);
        display: inline-block;
    }

    /* Card Box Style */
    .project-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid #f1f2f6;
        margin-bottom: 20px;
    }

    /* Button Styling */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        height: 45px;
        transition: all 0.3s ease;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LOGIKA MATEMATIKA (ENGINEERING CORE)
# ==========================================

# --- A. Fungsi Save/Load ---
def serialize_session():
    """Mengubah data session menjadi JSON untuk disimpan"""
    export = {}
    for k, v in st.session_state.items():
        if k.startswith(("Form", "editor", "uploaded", "btn")): continue
        if isinstance(v, pd.DataFrame):
            export[k] = {'__type__': 'df', 'data': v.to_dict(orient='records')}
        else:
            try:
                json.dumps(v)
                export[k] = v
            except: pass
    return json.dumps(export, indent=2)

def load_session(json_file):
    """Mengembalikan JSON ke Session State"""
    try:
        data = json.load(json_file)
        count = 0
        for k, v in data.items():
            if isinstance(v, dict) and v.get('__type__') == 'df':
                st.session_state[k] = pd.DataFrame(v['data'])
            else:
                st.session_state[k] = v
            count += 1
        return True, count
    except Exception as e: return False, str(e)

# --- B. Fungsi Klimatologi (KP-01 Presisi) ---
def get_julian_day(period_index):
    """Konversi Periode (0-23) ke Julian Day"""
    days = [15, 31, 45, 59, 74, 90, 105, 120, 135, 151, 166, 181, 
            196, 212, 227, 243, 258, 273, 288, 304, 319, 334, 349, 365]
    return days[period_index] if period_index < 24 else 365

def hitung_ra_astronomis(lat_deg, period_index):
    """Hitung Radiasi Ekstraterestrial Dinamis"""
    J = get_julian_day(period_index)
    lat_rad = math.radians(lat_deg)
    
    dr = 1 + 0.033 * math.cos(2 * math.pi * J / 365)
    solar_decl = 0.409 * math.sin((2 * math.pi * J / 365) - 1.39)
    
    tan_val = -math.tan(lat_rad) * math.tan(solar_decl)
    if tan_val < -1: ws = math.pi
    elif tan_val > 1: ws = 0
    else: ws = math.acos(tan_val)
    
    Gsc = 0.0820
    Ra_MJ = (24 * 60 / math.pi) * Gsc * dr * (
        ws * math.sin(lat_rad) * math.sin(solar_decl) +
        math.cos(lat_rad) * math.cos(solar_decl) * math.sin(ws)
    )
    return Ra_MJ * 0.408

def hitung_penman_modifikasi_presisi(df, lat, elev, c_factor):
    """Engine Utama Penman Modifikasi"""
    results_eto = []
    for idx, row in df.iterrows():
        try:
            T = float(row['Suhu (°C)'])
            RH = float(row['Kelembaban (%)'])
            n_sun = float(row['Penyinaran (%)']) 
            u_ms = float(row['Angin (m/s)'])
            
            ea = 6.11 * math.exp((17.27 * T) / (T + 237.3))
            ed = ea * (RH / 100)
            fu = 0.27 * (1 + 0.864 * u_ms)
            
            delta = 4098 * (0.6108 * math.exp(17.27 * T / (T + 237.3))) / ((T + 237.3)**2)
            P = 101.3 * ((293 - 0.0065 * elev) / 293)**5.26
            gamma = 0.665e-3 * P * 10 
            W = delta / (delta + gamma)
            
            Ra = hitung_ra_astronomis(lat, idx)
            Rs = (0.25 + 0.54 * (n_sun / 100)) * Ra
            Rns = (1 - 0.25) * Rs
            
            sigma_mm = 2.043e-10 
            ft = sigma_mm * ((T + 273.16)**4)
            fed = 0.34 - 0.044 * math.sqrt(ed)
            fsun = 0.1 + 0.9 * (n_sun / 100)
            Rnl = ft * fed * fsun
            Rn = Rns - Rnl
            
            ETo_val = c_factor * (W * Rn + (1 - W) * fu * (ea - ed))
            results_eto.append(max(0, ETo_val))
        except:
            results_eto.append(0)
    return results_eto

# ==========================================
# 3. INIT STATE (DATABASE SEMENTARA)
# ==========================================
if 'nama_proyek' not in st.session_state: st.session_state['nama_proyek'] = "Proyek Irigasi Baru"
if 'lokasi' not in st.session_state: st.session_state['lokasi'] = "Desa Sukamaju"
if 'tahun' not in st.session_state: st.session_state['tahun'] = 2026

# Init Dataframe Klimatologi (Default 24 Periode)
periods = [f"{m}-{p}" for m in ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'] for p in [1, 2]]
if 'df_iklim_24' not in st.session_state:
    st.session_state['df_iklim_24'] = pd.DataFrame({
        'Periode': periods,
        'Suhu (°C)': [27.5]*24, 
        'Kelembaban (%)': [80.0]*24, 
        'Penyinaran (%)': [60.0]*24, 
        'Angin (m/s)': [1.5]*24
    })

# ==========================================
# 4. SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("### 🧭 Navigasi")
    page = st.radio("Pilih Modul:", 
        ["🏠 Dashboard", "🌦️ Klimatologi (ETo)", "🌾 Pola Tanam (Coming Soon)"]
    )
    st.markdown("---")
    st.caption("Hydro Planner v1.0")

# ==========================================
# 5. HALAMAN UTAMA (SWITCH PAGE)
# ==========================================

# --- A. HALAMAN DASHBOARD ---
if page == "🏠 Dashboard":
    # Header
    st.markdown('<div><span class="main-title">HYDRO PLANNER</span><span class="branding-tag">by Smart Studio</span></div>', unsafe_allow_html=True)
    st.markdown("##### Integrated Irrigation & Drainage Engineering Suite")
    st.divider()

    # Input Identitas Proyek
    st.markdown("### 1️⃣ Identitas Proyek")
    with st.container():
        st.markdown('<div class="project-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1: st.session_state['nama_proyek'] = st.text_input("Nama Pekerjaan", value=st.session_state['nama_proyek'])
        with c2: st.session_state['lokasi'] = st.text_input("Lokasi / Desa", value=st.session_state['lokasi'])
        with c3: st.session_state['tahun'] = st.number_input("Tahun", value=st.session_state['tahun'])
        st.markdown('</div>', unsafe_allow_html=True)

    # Menu Save/Load
    c_left, c_right = st.columns(2)
    with c_left:
        st.info("📂 **Load Proyek:** Upload file JSON hasil simpanan sebelumnya.")
        uploaded = st.file_uploader("", type=['json'], label_visibility="collapsed")
        if uploaded and st.button("Buka File Project"):
            ok, msg = load_session(uploaded)
            if ok: st.success(f"Berhasil memuat {msg} data!"); time.sleep(1); st.rerun()
            else: st.error(f"Gagal: {msg}")

    with c_right:
        st.success("💾 **Simpan Proyek:** Download seluruh data pekerjaan.")
        file_label = f"{str(st.session_state['nama_proyek']).replace(' ', '_')}.json"
        st.download_button("Download JSON Backup", data=serialize_session(), file_name=file_label, mime="application/json")

    # Status Check
    st.divider()
    st.markdown("### 📊 Status Data")
    col_status = st.columns(4)
    
    # Cek Klimatologi
    with col_status[0]:
        if 'hasil_eto' in st.session_state:
            st.success("**Klimatologi**\n\n✅ Selesai")
        else:
            st.warning("**Klimatologi**\n\n⬜ Belum Dihitung")
            
    # Cek Modul Lain (Placeholder)
    with col_status[1]: st.markdown("**Pola Tanam**\n\n⬜ Kosong")

# --- B. HALAMAN KLIMATOLOGI ---
elif page == "🌦️ Klimatologi (ETo)":
    st.markdown("## ☀️ Analisa Evapotranspirasi (ETo)")
    st.caption("Metode: **Penman Modifikasi (KP-01)** dengan Koreksi Astronomis Dinamis (Julian Day)")

    # 1. Parameter Input
    with st.expander("⚙️ Parameter Lokasi & Kalibrasi", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: 
            lat_input = st.number_input("Lintang (Latitude)", value=-6.2, step=0.1, help="Gunakan (-) untuk Lintang Selatan")
        with c2: 
            elev_input = st.number_input("Elevasi (m dpl)", value=10.0, step=10.0)
        with c3:
            c_factor = st.number_input("Faktor C (Koreksi)", value=0.90, step=0.05, 
                                     help="Basah: 0.8 | Sedang: 0.9 | Kering/Angin Kencang: 1.1")

    # 2. Data Editor
    st.markdown("### 📝 Input Data Klimatologi (24 Periode)")
    st.info("💡 Tip: Anda bisa copy-paste langsung dari Excel ke tabel di bawah ini.")
    
    edited_df = st.data_editor(
        st.session_state['df_iklim_24'], 
        height=300, 
        hide_index=True,
        use_container_width=True,
        column_config={
            "Periode": st.column_config.TextColumn(disabled=True),
            "Suhu (°C)": st.column_config.NumberColumn(format="%.1f", required=True),
            "Kelembaban (%)": st.column_config.NumberColumn(format="%.0f", required=True),
            "Penyinaran (%)": st.column_config.NumberColumn(format="%.0f", required=True),
            "Angin (m/s)": st.column_config.NumberColumn(format="%.2f", required=True),
        }
    )
    # Penting: Update state setelah edit
    st.session_state['df_iklim_24'] = edited_df

    # 3. Tombol Eksekusi
    if st.button("🚀 HITUNG ETo SEKARANG", type="primary"):
        with st.spinner("Sedang menghitung radiasi matahari & aerodinamika..."):
            time.sleep(0.5) # Efek loading
            eto_results = hitung_penman_modifikasi_presisi(edited_df, lat_input, elev_input, c_factor)
            
            # Simpan hasil
            df_res = edited_df[['Periode']].copy()
            df_res['ETo (mm/hari)'] = np.round(eto_results, 2)
            st.session_state['hasil_eto'] = df_res 
            
            # Tampilkan
            st.divider()
            r1, r2 = st.columns([1, 2])
            
            with r1:
                st.subheader("📋 Hasil Perhitungan")
                st.dataframe(df_res.style.background_gradient(cmap="Blues"), use_container_width=True, height=400)
                avg_eto = np.mean(eto_results)
                st.success(f"**Rata-rata ETo:**\n# {avg_eto:.2f} mm/hari")
                
            with r2:
                st.subheader("📈 Grafik ETo")
                st.bar_chart(df_res.set_index('Periode'))

# --- C. HALAMAN COMING SOON ---
elif page == "🌾 Pola Tanam (Coming Soon)":
    st.empty()
    st.markdown("## 🚧 Sedang Dalam Pengembangan")
    st.info("Modul ini akan berisi perhitungan Kebutuhan Air di Sawah (NFR) berdasarkan Pola Tanam (Padi-Padi-Palawija).")
