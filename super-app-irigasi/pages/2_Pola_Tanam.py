import streamlit as st
import pandas as pd
import numpy as np
import math

# --- CONFIG ---
st.set_page_config(page_title="Pola Tanam (15 Harian)", layout="wide", page_icon="🌾")

# --- RUMUS ---
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

# --- INIT STATE ---
def init_data_24_periode():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])
    
    eto_24 = [4.5] * 24
    if 'data_eto_manual' in st.session_state:
        data = st.session_state['data_eto_manual']
        if len(data) == 24: eto_24 = data
        elif len(data) == 12: 
            eto_24 = []
            for v in data: eto_24.extend([v, v])
            
    # Auto-Heal Nama Kolom
    if 'df_hujan_24' in st.session_state:
        cols = st.session_state['df_hujan_24'].columns
        if 'CH (mm)' in cols and 'CH Rata-rata (mm)' not in cols:
            st.session_state['df_hujan_24'].rename(columns={'CH (mm)': 'CH Rata-rata (mm)'}, inplace=True)
            
    if 'df_hujan_24' not in st.session_state:
        st.session_state['df_hujan_24'] = pd.DataFrame({
            'Periode': periods, 
            'CH Rata-rata (mm)': [100.0] * 24
        })
    return periods, eto_24

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Hujan")
    uploaded = st.file_uploader("Upload CSV Hujan", type=["csv"])
    if uploaded and st.button("🔄 Baca CSV"):
        try:
            try: df = pd.read_csv(uploaded)
            except: 
                uploaded.seek(0)
                df = pd.read_csv(uploaded, sep=';')
            
            num = df.select_dtypes(include=[np.number])
            if num.shape[1] > 0:
                raw = num.iloc[:, 0].values
                new_h = []
                if len(raw) == 12:
                    for v in raw: new_h.extend([v, v])
                elif len(raw) >= 24: new_h = raw[:24]
                
                st.session_state['df_hujan_24']['CH Rata-rata (mm)'] = new_h
                st.rerun()
        except Exception as e: st.error(f"Error: {e}")
        
    st.divider()
    st.header("Parameter")
    periods_opts, _ = init_data_24_periode()
    awal_tanam = st.selectbox("Awal Tanam", periods_opts, index=18)
    pola = st.selectbox("Pola", ["Padi - Padi - Palawija", "Padi - Padi - Bero"])
    faktor_r80 = st.number_input("Faktor R80", 0.5, 1.0, 0.8)
    
    perkolasi = st.number_input("Perkolasi", 1.0, 5.0, 2.0)
    wlr_val = st.number_input("WLR", 0.0, 10.0, 3.3)
    lp_sat = st.number_input("S (mm)", 200, 300, 250)
    durasi_lp = st.selectbox("Durasi LP", [30, 45])
    efisiensi = st.slider("Efisiensi (%)", 50, 90, 65) / 100

# --- MAIN ---
st.title("🌾 Pola Tanam (15 Harian)")
periods, eto_vals = init_data_24_periode()

# Info Project
nm = st.session_state.get('nama_proyek', '-')
if 'data_eto_manual' in st.session_state: st.success(f"✅ Proyek: {nm} | Data Iklim Terhubung")
else: st.warning(f"⚠️ Proyek: {nm} | Data Iklim Kosong (Pakai Default)")

# Input Table
with st.expander("🌧️ Input Curah Hujan", expanded=True):
    edited = st.data_editor(st.session_state['df_hujan_24'], hide_index=True, use_container_width=True)
    st.session_state['df_hujan_24'] = edited
    try:
        ch_vals = edited['CH Rata-rata (mm)'].tolist()
        r80_vals = [x * faktor_r80 for x in ch_vals]
    except KeyError:
        st.error("Error kolom. Coba refresh halaman.")
        st.stop()

# Calculation Logic
idx_start = periods.index(awal_tanam)
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
    res.append({'Periode': periods[curr], 'Fase': fase, 'CH Rata2': ch_vals[curr], 'R80': r80, 'NFR (L/s/ha)': (nfr * 0.1157) / efisiensi})

# Result
df_res = pd.DataFrame(res)
# Sorting
urutan_map = {val: i for i, val in enumerate(periods)}
df_res['sort_key'] = df_res['Periode'].map(urutan_map)
df_res = df_res.sort_values('sort_key').drop(columns=['sort_key'])

# --- TAMPILAN SESUAI REQUEST ---
st.divider()

c1, c2 = st.columns([1.5, 1])

with c1:
    st.subheader("Hasil Perhitungan NFR")
    st.dataframe(
        df_res.style.format({
            "CH Rata2": "{:.1f}", 
            "R80": "{:.2f}", 
            "NFR (L/s/ha)": "{:.4f}"
        }), 
        use_container_width=True, 
        height=500
    )
    
    # Tombol Kirim Besar Merah
    if st.button("🚀 KIRIM DATA KE IRIGASI PIPA", type="primary", use_container_width=True):
        st.session_state['data_nfr_manual'] = df_res['NFR (L/s/ha)'].tolist()
        st.success("✅ Data Terkirim! Silakan buka menu Irigasi Pipa.")

with c2:
    st.subheader("Grafik Kebutuhan Air")
    
    # Metric NFR Rerata & Max
    rata_nfr = df_res['NFR (L/s/ha)'].mean()
    max_nfr = df_res['NFR (L/s/ha)'].max()
    
    m1, m2 = st.columns(2)
    m1.metric("NFR Rerata", f"{rata_nfr:.3f} L/s/ha")
    m2.metric("NFR Max", f"{max_nfr:.3f} L/s/ha")
    
    # Simple Table samping grafik (Sesuai screenshot)
    st.dataframe(df_res[['Periode', 'NFR (L/s/ha)']], use_container_width=True, height=400)

st.markdown("""
<div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 5px solid #2e7d32; margin-bottom: 20px;">
    <strong>ℹ️ METODOLOGI: Neraca Air Irigasi (Standar KP-01)</strong><br>
    <ul>
        <li><strong>Penyiapan Lahan (LP):</strong> Metode Van de Goor & Zijlstra</li>
        <li><strong>Kebutuhan Tanaman (ETc):</strong> Kc × ETo</li>
        <li><strong>Curah Hujan Efektif (Re):</strong> R80 (Padi) & R50 (Palawija)</li>
    </ul>
</div>
""", unsafe_allow_html=True)
