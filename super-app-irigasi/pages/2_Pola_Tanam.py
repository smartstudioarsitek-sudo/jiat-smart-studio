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
    
    /* Metric Card Custom */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        color: #0984e3;
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
    days = [15, 31, 45, 59, 74, 90, 105, 120, 135, 151, 166, 181, 
            196, 212, 227, 243, 258, 273, 288, 304, 319, 334, 349, 365]
    return days[period_index] if period_index < 24 else 365

def hitung_ra_astronomis(lat_deg, period_index):
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
        except: results_eto.append(0)
    return results_eto

# --- C. Fungsi Pola Tanam & NFR ---
def hitung_lp_vande_goor(eto, p, s=250, t=30):
    M = eto + p
    try:
        if M <= 0: return 0
        k = (M * t) / s
        ek = math.exp(k)
        if ek == 1: return M
        LP = M * ek / (ek - 1)
        return LP
    except: return 0

def get_kc_padi_15hari(umur_periode):
    kc_values = [1.10, 1.10, 1.10, 1.10, 1.05, 1.05, 0.95, 0.00]
    if 0 <= umur_periode < len(kc_values): return kc_values[umur_periode]
    return 0

def get_kc_palawija_15hari(umur_periode):
    kc_vals = [0.50, 0.75, 0.90, 1.00, 0.90, 0.70]
    if 0 <= umur_periode < len(kc_vals): return kc_vals[umur_periode]
    return 0

# ==========================================
# 3. INIT STATE (DATABASE SEMENTARA)
# ==========================================
if 'nama_proyek' not in st.session_state: st.session_state['nama_proyek'] = "Proyek Irigasi Baru"
if 'lokasi' not in st.session_state: st.session_state['lokasi'] = "Desa Sukamaju"
if 'tahun' not in st.session_state: st.session_state['tahun'] = 2026

# Init Periode Global
periods_global = [f"{m}-{p}" for m in ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'] for p in [1, 2]]

# Init Data Klimatologi
if 'df_iklim_24' not in st.session_state:
    st.session_state['df_iklim_24'] = pd.DataFrame({
        'Periode': periods_global,
        'Suhu (°C)': [27.5]*24, 'Kelembaban (%)': [80.0]*24, 
        'Penyinaran (%)': [60.0]*24, 'Angin (m/s)': [1.5]*24
    })

# Init Data Hujan
if 'df_hujan_24' not in st.session_state:
    st.session_state['df_hujan_24'] = pd.DataFrame({
        'Periode': periods_global, 
        'CH Rata-rata (mm)': [100.0] * 24
    })

# ==========================================
# 4. SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("### 🧭 Navigasi")
    page = st.radio("Pilih Modul:", 
        ["🏠 Dashboard", "🌦️ Klimatologi (ETo)", "🌾 Pola Tanam & NFR"]
    )
    st.markdown("---")
    st.caption("Hydro Planner v1.2")

# ==========================================
# 5. HALAMAN UTAMA (SWITCH PAGE)
# ==========================================

# --- A. HALAMAN DASHBOARD ---
if page == "🏠 Dashboard":
    st.markdown('<div><span class="main-title">HYDRO PLANNER</span><span class="branding-tag">by Smart Studio</span></div>', unsafe_allow_html=True)
    st.markdown("##### Integrated Irrigation & Drainage Engineering Suite")
    st.divider()

    st.markdown("### 1️⃣ Identitas Proyek")
    with st.container():
        st.markdown('<div class="project-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1: st.session_state['nama_proyek'] = st.text_input("Nama Pekerjaan", value=st.session_state['nama_proyek'])
        with c2: st.session_state['lokasi'] = st.text_input("Lokasi / Desa", value=st.session_state['lokasi'])
        with c3: st.session_state['tahun'] = st.number_input("Tahun", value=st.session_state['tahun'])
        st.markdown('</div>', unsafe_allow_html=True)

    c_left, c_right = st.columns(2)
    with c_left:
        st.info("📂 **Load Proyek:** Upload file JSON hasil simpanan.")
        uploaded = st.file_uploader("", type=['json'], label_visibility="collapsed")
        if uploaded and st.button("Buka File Project"):
            ok, msg = load_session(uploaded)
            if ok: st.success(f"Berhasil memuat {msg} data!"); time.sleep(1); st.rerun()
            else: st.error(f"Gagal: {msg}")

    with c_right:
        st.success("💾 **Simpan Proyek:** Download seluruh data pekerjaan.")
        file_label = f"{str(st.session_state['nama_proyek']).replace(' ', '_')}.json"
        st.download_button("Download JSON Backup", data=serialize_session(), file_name=file_label, mime="application/json")

    st.divider()
    st.markdown("### 📊 Status Data")
    col_status = st.columns(4)
    with col_status[0]:
        st.markdown(f"**Klimatologi**\n\n{'✅ Selesai' if 'hasil_eto' in st.session_state else '⬜ Kosong'}")
    with col_status[1]: 
        st.markdown(f"**Pola Tanam**\n\n{'✅ Selesai' if 'data_nfr_manual' in st.session_state else '⬜ Kosong'}")

# --- B. HALAMAN KLIMATOLOGI ---
elif page == "🌦️ Klimatologi (ETo)":
    st.markdown("## ☀️ Analisa Evapotranspirasi (ETo)")
    
    with st.expander("⚙️ Parameter Lokasi & Kalibrasi", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: lat_input = st.number_input("Lintang (Latitude)", value=-6.2, step=0.1)
        with c2: elev_input = st.number_input("Elevasi (m dpl)", value=10.0, step=10.0)
        with c3: c_factor = st.number_input("Faktor Koreksi (c)", value=0.90, step=0.05)

    st.markdown("### 📝 Input Data Klimatologi")
    edited_df = st.data_editor(st.session_state['df_iklim_24'], height=300, hide_index=True, use_container_width=True)
    st.session_state['df_iklim_24'] = edited_df

    if st.button("🚀 HITUNG ETo SEKARANG", type="primary"):
        eto_results = hitung_penman_modifikasi_presisi(edited_df, lat_input, elev_input, c_factor)
        df_res = edited_df[['Periode']].copy()
        df_res['ETo (mm/hari)'] = np.round(eto_results, 2)
        st.session_state['hasil_eto'] = df_res 
        st.success(f"✅ Rata-rata ETo: {np.mean(eto_results):.2f} mm/hari")
        st.bar_chart(df_res.set_index('Periode'))

# --- C. HALAMAN POLA TANAM & NFR ---
elif page == "🌾 Pola Tanam & NFR":
    st.markdown("## 🌾 Pola Tanam & Kebutuhan Air (NFR)")
    st.caption("Neraca Air Irigasi (Standar KP-01) - 15 Harian")

    # 1. AMBIL DATA ETO
    eto_vals = [4.5] * 24 # Default dummy
    if 'hasil_eto' in st.session_state:
        eto_vals = st.session_state['hasil_eto']['ETo (mm/hari)'].tolist()
        st.info("✅ Menggunakan data ETo dari Modul Klimatologi.")
    else:
        st.warning("⚠️ Data ETo belum dihitung. Menggunakan nilai dummy 4.5 mm/hari.")

    # 2. SETTING PARAMETER
    with st.sidebar:
        st.header("⚙️ Setting Pola Tanam")
        awal_tanam = st.selectbox("Awal Tanam", periods_global, index=18)
        pola = st.selectbox("Pola", ["Padi - Padi - Palawija", "Padi - Padi - Bero"])
        
        st.divider()
        st.markdown("**Koefisien & Efisiensi**")
        perkolasi = st.number_input("Perkolasi (mm/hr)", 1.0, 5.0, 2.0)
        wlr_val = st.number_input("WLR (mm/hr)", 0.0, 10.0, 3.3)
        lp_sat = st.number_input("S (mm)", 200, 300, 250)
        durasi_lp = st.selectbox("Durasi LP (hari)", [30, 45])
        efisiensi = st.slider("Efisiensi (%)", 50, 90, 65) / 100
        faktor_r80 = st.number_input("Faktor R80", 0.1, 1.0, 0.8)

    # 3. INPUT DATA HUJAN
    c_hujan, c_result = st.columns([1, 2])
    
    with c_hujan:
        st.markdown("### 🌧️ Data Curah Hujan")
        st.caption("Input CH Rata-rata (mm) per periode")
        
        # Upload CSV Mini
        up_hujan = st.file_uploader("Upload CSV Hujan", type=["csv"])
        if up_hujan:
            try:
                df_up = pd.read_csv(up_hujan)
                vals = df_up.select_dtypes(include=[np.number]).iloc[:,0].tolist()
                if len(vals) >= 24: st.session_state['df_hujan_24']['CH Rata-rata (mm)'] = vals[:24]; st.rerun()
            except: pass

        edited_hujan = st.data_editor(st.session_state['df_hujan_24'], hide_index=True, height=600)
        st.session_state['df_hujan_24'] = edited_hujan
        
        ch_vals = edited_hujan['CH Rata-rata (mm)'].tolist()
        r80_vals = [x * faktor_r80 for x in ch_vals]

    # 4. ENGINE PERHITUNGAN NFR
    idx_start = periods_global.index(awal_tanam)
    jml_per_lp = int(durasi_lp / 15)
    res = []

    for i in range(24):
        curr = (idx_start + i) % 24
        eto = eto_vals[curr]
        r80 = r80_vals[curr]
        fase, kc, butuh, wlr, re = "", 0, 0, 0, 0
        
        p1_s = jml_per_lp
        lp2_s = p1_s + 8
        p2_s = lp2_s + jml_per_lp
        pal_s = p2_s + 8
        end_s = pal_s + 6
        
        if i < p1_s: 
            fase="LP Padi I"; butuh=hitung_lp_vande_goor(eto, perkolasi, lp_sat, durasi_lp)
        elif p1_s <= i < lp2_s:
            fase="Padi I"; u=i-p1_s; kc=get_kc_padi_15hari(u); butuh=kc*eto+perkolasi
            if u in [2,4]: wlr=wlr_val
        elif lp2_s <= i < p2_s:
            fase="LP Padi II"; butuh=hitung_lp_vande_goor(eto, perkolasi, lp_sat, durasi_lp)
        elif p2_s <= i < pal_s:
            fase="Padi II"; u=i-p2_s; kc=get_kc_padi_15hari(u); butuh=kc*eto+perkolasi
            if u in [2,4]: wlr=wlr_val
        elif pal_s <= i < end_s:
            if "Palawija" in pola: fase="Palawija"; u=i-pal_s; kc=get_kc_palawija_15hari(u); butuh=kc*eto
            else: fase="Bero"
        else: fase="Bero"
        
        if "Padi" in fase or "LP" in fase: re = (0.7 * r80)/15
        elif "Palawija" in fase: re = (0.5 * r80)/15
        
        nfr = max(0, butuh + wlr - re)
        res.append({
            'Periode': periods_global[curr], 
            'Fase': fase, 
            'ETo': eto,
            'CH': ch_vals[curr], 
            'R80': r80, 
            'NFR (l/s/ha)': (nfr * 0.1157) / efisiensi
        })

    # DataFrame Hasil
    df_res = pd.DataFrame(res)
    # Sorting agar urut Periode Januari-Desember
    urutan_map = {val: i for i, val in enumerate(periods_global)}
    df_res['sort_key'] = df_res['Periode'].map(urutan_map)
    df_res = df_res.sort_values('sort_key').drop(columns=['sort_key'])

    # 5. TAMPILAN HASIL (KANAN)
    with c_result:
        st.markdown("### 📈 Hasil Perhitungan NFR")
        
        # Grafik Line Chart
        st.line_chart(df_res.set_index('Periode')['NFR (l/s/ha)'])
        
        # Metric Penting
        rata_nfr = df_res['NFR (l/s/ha)'].mean()
        max_nfr = df_res['NFR (l/s/ha)'].max()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("NFR Rerata", f"{rata_nfr:.3f}", "l/s/ha")
        m2.metric("NFR Maksimum", f"{max_nfr:.3f}", "l/s/ha")
        m3.markdown(f"**Status:**\n\n{'✅ Aman' if max_nfr < 2.5 else '⚠️ Tinggi'}")

        # Tabel Detail
        with st.expander("Lihat Tabel Detail Angka"):
            st.dataframe(df_res.style.format("{:.3f}", subset=['NFR (l/s/ha)']), use_container_width=True)

        # Tombol Kirim Data
        if st.button("🚀 SIMPAN DATA NFR UNTUK DESAIN PIPA", type="primary"):
            st.session_state['data_nfr_manual'] = df_res['NFR (l/s/ha)'].tolist()
            st.success("✅ Data NFR tersimpan! Siap digunakan untuk perhitungan dimensi pipa/saluran.")
