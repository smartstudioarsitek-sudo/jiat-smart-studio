import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Pola Tanam (15 Harian)", layout="wide", page_icon="🌾")

st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
    .metric-box {
        padding: 15px; background-color: #f1f8e9; 
        border-left: 5px solid #558b2f; border-radius: 5px;
        margin-bottom: 10px;
    }
    .success-box {
        padding: 10px; background-color: #d1e7dd; color: #0f5132; 
        border: 1px solid #badbcc; border-radius: 5px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. RUMUS KP-01 ---
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

# --- 3. STATE MANAGEMENT ---
def init_data_24_periode():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])
    
    # Ambil ETo dari Page 1 (jika ada)
    eto_24 = [4.5] * 24
    if 'data_eto_manual' in st.session_state:
        # Prioritas Data Manual (Tombol Kirim)
        data_eto = st.session_state['data_eto_manual']
        if len(data_eto) == 24: eto_24 = data_eto
        elif len(data_eto) == 12: 
            eto_24 = []
            for v in data_eto: eto_24.extend([v, v])
            
    elif 'data_eto_transfer' in st.session_state:
        # Fallback Auto Link
        data_eto = st.session_state['data_eto_transfer']
        if len(data_eto) == 24: eto_24 = data_eto
        elif len(data_eto) == 12:
            eto_24 = []
            for v in data_eto: eto_24.extend([v, v])

    # Default Hujan
    if 'df_hujan_24' not in st.session_state:
        ch_pola = [100, 100, 90, 90, 120, 120, 70, 70, 50, 50, 25, 25, 10, 10, 5, 5, 40, 40, 75, 75, 110, 110, 120, 120]
        st.session_state['df_hujan_24'] = pd.DataFrame({'Periode': periods, 'CH (mm)': [float(x) for x in ch_pola]})
        
    return periods, eto_24

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🚜 Parameter Tanam")
    periods_opts, _ = init_data_24_periode()
    awal_tanam_label = st.selectbox("Awal Tanam", periods_opts, index=18)
    pola = st.selectbox("Pola Tata Tanam", ["Padi - Padi - Palawija", "Padi - Padi - Bero"])
    
    st.subheader("Faktor Tanah")
    perkolasi = st.number_input("Perkolasi (mm/hari)", 1.0, 5.0, 2.0, 0.1)
    wlr_val = st.number_input("WLR (mm/hari)", 0.0, 10.0, 3.3, 0.1)
    lp_sat = st.number_input("Penjenuhan (S) mm", 200, 300, 250)
    durasi_lp = st.selectbox("Durasi LP (Hari)", [30, 45], index=0)
    efisiensi = st.slider("Efisiensi (%)", 50, 90, 65) / 100

# --- 5. MAIN CONTENT ---
st.title("🌾 Pola Tanam (15 Harian)")
st.caption("Analisa Kebutuhan Air Irigasi Standar KP-01")

# Cek Data ETo
if 'data_eto_manual' in st.session_state:
    st.markdown('<div class="success-box">✅ Data Klimatologi Terhubung (24 Periode)</div>', unsafe_allow_html=True)

periods, eto_vals = init_data_24_periode()

# A. Input Hujan
with st.expander("🌧️ Input Curah Hujan (24 Periode)", expanded=True):
    c1, c2 = st.columns([1, 2])
    with c1: st.info("Masukkan R80 per setengah bulan.")
    with c2:
        edited_hujan = st.data_editor(st.session_state['df_hujan_24'], height=300, hide_index=True, use_container_width=True)
        st.session_state['df_hujan_24'] = edited_hujan

# B. Engine Hitungan
idx_start = periods.index(awal_tanam_label)
jml_per_lp = int(durasi_lp / 15) 
ch_vals = edited_hujan['CH (mm)'].tolist()

list_res = []
for i in range(24):
    curr_idx = (idx_start + i) % 24
    eto_now = eto_vals[curr_idx]
    ch_now = ch_vals[curr_idx]
    
    fase, kc, butuh, wlr = "", 0, 0, 0
    
    idx_padi1_start = jml_per_lp
    idx_lp2_start = idx_padi1_start + 8
    idx_padi2_start = idx_lp2_start + jml_per_lp
    idx_palawija_start = idx_padi2_start + 8
    idx_end = idx_palawija_start + 6

    # Logika Fase
    if i < idx_padi1_start:
        fase = "LP Padi I"
        butuh = hitung_lp_vande_goor(eto_now, perkolasi, s=lp_sat, t=durasi_lp)
    elif idx_padi1_start <= i < idx_lp2_start:
        fase = "Padi I"
        umur = i - idx_padi1_start
        kc = get_kc_padi_15hari(umur)
        butuh = kc * eto_now + perkolasi
        if umur == 2 or umur == 4: wlr = wlr_val
    elif idx_lp2_start <= i < idx_padi2_start:
        fase = "LP Padi II"
        butuh = hitung_lp_vande_goor(eto_now, perkolasi, s=lp_sat, t=durasi_lp)
    elif idx_padi2_start <= i < idx_palawija_start:
        fase = "Padi II"
        umur = i - idx_padi2_start
        kc = get_kc_padi_15hari(umur)
        butuh = kc * eto_now + perkolasi
        if umur == 2 or umur == 4: wlr = wlr_val
    elif idx_palawija_start <= i < idx_end:
        if "Palawija" in pola:
            fase = "Palawija"
            umur = i - idx_palawija_start
            kc = get_kc_palawija_15hari(umur)
            butuh = kc * eto_now
        else: fase, butuh = "Bero", 0
    else: fase, butuh = "Bero", 0

    # Re (Hujan Efektif)
    re = 0
    if "Padi" in fase or "LP" in fase: re = (0.7 * ch_now) / 15
    elif "Palawija" in fase: re = (0.5 * ch_now) / 15
    
    nfr = max(0, butuh + wlr - re)
    list_res.append({'fase': fase, 'kc': kc, 'nfr': nfr, 'wlr': wlr, 're': re, 'butuh': butuh})

# Re-map ke Kalender
final_data = []
for m_idx in range(24):
    step_i = (m_idx - idx_start) % 24
    d = list_res[step_i]
    q_req = (d['nfr'] * 0.1157) / efisiensi
    
    final_data.append({
        'Periode': periods[m_idx],
        'Fase': d['fase'],
        'ETo': eto_vals[m_idx],
        'Kc': d['kc'],
        'NFR (mm/hr)': d['nfr'],
        'Q (l/s/ha)': q_req
    })

df_res = pd.DataFrame(final_data)

# C. Tampilan
col1, col2 = st.columns([3, 1])
with col1:
    st.dataframe(df_res.style.background_gradient(cmap="Greens", subset=['Q (l/s/ha)']).format("{:.3f}", subset=['NFR (mm/hr)', 'Q (l/s/ha)']), use_container_width=True, height=500)
    
    # --- TOMBOL KIRIM UPDATE ---
    st.divider()
    st.info("👇 Kirim Data Lengkap (24 Periode) ke Irigasi Pipa")
    if st.button("🚀 KIRIM POLA TANAM (FULL)", type="primary", use_container_width=True):
        # KIRIM LIST LENGKAP, BUKAN CUMA MAX
        data_full = df_res['Q (l/s/ha)'].tolist()
        st.session_state['data_nfr_manual'] = data_full 
        
        st.markdown(f"""
        <div class="success-box">
            <b>✅ Data Terkirim!</b><br>
            Data 24 Periode (naik-turun) sudah dikirim. Silakan 'Ambil Data' di Page Irigasi Pipa.
        </div>
        """, unsafe_allow_html=True)

with col2:
    q_max = df_res['Q (l/s/ha)'].max()
    st.markdown(f"""<div class="metric-box"><b>NFR Max:</b><br><h2>{q_max:.3f} l/s/ha</h2></div>""", unsafe_allow_html=True)
    st.line_chart(df_res.set_index('Periode')['Q (l/s/ha)'])

st.divider()
import streamlit.components.v1 as components
components.html("""<button onclick="window.print()" style="background:#558b2f;color:white;border:none;padding:10px;">🖨️ Cetak</button>""", height=50)
