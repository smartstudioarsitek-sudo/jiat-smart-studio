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
</style>
""", unsafe_allow_html=True)

# --- 2. RUMUS KP-01 (VAN DE GOOR & ZIJLSTRA) ---
def hitung_lp_vande_goor(eto, p, s=250, t=30):
    """
    Rumus LP Van de Goor (KP-01)
    M = ETo + P
    k = M * T / S
    IR = M * e^k / (e^k - 1)
    """
    M = eto + p
    try:
        if M <= 0: return 0
        k = (M * t) / s
        ek = math.exp(k)
        if ek == 1: return M
        LP = M * ek / (ek - 1)
        return LP
    except:
        return 0

def get_kc_padi_15hari(umur_periode, varietas='unggul'):
    """
    Kc Padi per Periode 15 Hari (Nedeco/KP-01)
    Total 8 Periode (4 Bulan)
    """
    # Pola Nedeco: 1.1, 1.1, 1.1, 1.1, 1.1, 1.05, 0.95, 0.0 (Panen)
    # Ini angka pendekatan umum
    kc_values = [1.10, 1.10, 1.10, 1.10, 1.05, 1.05, 0.95, 0.00]
    if 0 <= umur_periode < len(kc_values):
        return kc_values[umur_periode]
    return 0

def get_kc_palawija_15hari(umur_periode):
    """Kc Palawija (Jagung/Kedelai) per 15 Hari (Total 3 Bulan / 6 Periode)"""
    # Pola: 0.5, 0.75, 0.9, 1.0, 0.9, 0.7
    kc_vals = [0.50, 0.75, 0.90, 1.00, 0.90, 0.70]
    if 0 <= umur_periode < len(kc_vals):
        return kc_vals[umur_periode]
    return 0

# --- 3. STATE MANAGEMENT ---
def init_data_24_periode():
    # Buat label periode Jan-1, Jan-2, dst
    periods = []
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    for m in months:
        periods.append(f"{m}-1")
        periods.append(f"{m}-2")
    
    # 1. Tarik Data ETo (Bulanan -> Konversi ke 24 Periode)
    eto_24 = []
    if 'data_eto_transfer' in st.session_state:
        eto_bulan = st.session_state['data_eto_transfer']
        # Expand: Jan -> Jan-1, Jan-2 (Nilai sama)
        for val in eto_bulan:
            eto_24.append(val) # Periode 1
            eto_24.append(val) # Periode 2
    else:
        eto_24 = [4.5] * 24 # Dummy

    # 2. DataFrame Default Hujan 24 Periode
    if 'df_hujan_24' not in st.session_state:
        # Pola hujan dummy (tinggi di awal/akhir tahun)
        ch_pola = [100, 100, 90, 90, 120, 120, 70, 70, 50, 50, 25, 25, 
                   10, 10, 5, 5, 40, 40, 75, 75, 110, 110, 120, 120]
        st.session_state['df_hujan_24'] = pd.DataFrame({
            'Periode': periods,
            'CH (mm)': [float(x) for x in ch_pola]
        })
        
    return periods, eto_24

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🚜 Parameter Tanam (KP-01)")
    
    st.subheader("1. Jadwal Tanam")
    # Pilihan Awal Tanam (24 Periode)
    periods_opts, _ = init_data_24_periode()
    awal_tanam_label = st.selectbox("Awal Tanam", periods_opts, index=18) # Default Okt-1
    
    pola = st.selectbox("Pola Tata Tanam", ["Padi - Padi - Palawija", "Padi - Padi - Bero"])
    
    st.subheader("2. Faktor Tanah")
    perkolasi = st.number_input("Perkolasi (mm/hari)", 1.0, 5.0, 2.0, 0.1)
    wlr_val = st.number_input("WLR (mm/hari)", 0.0, 10.0, 3.3, 0.1, help="Ganti Air (50mm / 15 hari = 3.33)")
    lp_sat = st.number_input("Penjenuhan (S) mm", 200, 300, 250)
    durasi_lp = st.selectbox("Durasi LP (Hari)", [30, 45], index=0)
    
    st.divider()
    efisiensi = st.slider("Efisiensi (%)", 50, 90, 65) / 100

# --- 5. MAIN CONTENT ---
st.title("🌾 Pola Tanam (Periode 15 Harian)")
st.caption("Analisa Kebutuhan Air Irigasi Standar KP-01")

periods, eto_vals = init_data_24_periode()

# A. Input Hujan 24 Periode
with st.expander("🌧️ Input Curah Hujan (24 Periode)", expanded=True):
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.info("💡 Masukkan R80 per setengah bulan.")
    with col_b:
        edited_hujan = st.data_editor(st.session_state['df_hujan_24'], height=300, hide_index=True, use_container_width=True)
        st.session_state['df_hujan_24'] = edited_hujan

# B. Engine Perhitungan
# Mapping start index
idx_start = periods.index(awal_tanam_label)

list_kc, list_keb, list_wlr, list_re, list_nfr, list_fase = [], [], [], [], [], []

# Konversi durasi LP ke jumlah periode (30 hari = 2 periode, 45 hari = 3 periode)
jml_per_lp = int(durasi_lp / 15) 

# Ambil data hujan dari editor
ch_vals = edited_hujan['CH (mm)'].tolist()

# LOOP 24 PERIODE (1 TAHUN)
for i in range(24):
    # Rotating index (untuk ambil data iklim sesuai bulan kalender)
    curr_idx = (idx_start + i) % 24
    
    eto_now = eto_vals[curr_idx]
    ch_now = ch_vals[curr_idx]
    
    fase = ""
    kc = 0
    butuh = 0
    wlr = 0
    
    # --- LOGIKA POLA TANAM (PADI-PADI-PALAWIJA) ---
    # Asumsi:
    # LP 1: Periode 0 s.d jml_per_lp
    # Padi 1: 4 Bulan (8 Periode)
    # LP 2: ...
    # Padi 2: ...
    # Palawija: 3 Bulan (6 Periode)
    
    idx_padi1_start = jml_per_lp
    idx_lp2_start = idx_padi1_start + 8
    idx_padi2_start = idx_lp2_start + jml_per_lp
    idx_palawija_start = idx_padi2_start + 8
    idx_end = idx_palawija_start + 6

    # 1. MT 1 (LP & PADI I)
    if i < idx_padi1_start:
        fase = "LP Padi I"
        butuh = hitung_lp_vande_goor(eto_now, perkolasi, s=lp_sat, t=durasi_lp)
    
    elif idx_padi1_start <= i < idx_lp2_start:
        fase = "Padi I"
        umur = i - idx_padi1_start
        kc = get_kc_padi_15hari(umur)
        butuh = kc * eto_now + perkolasi
        # WLR di 1 bulan dan 2 bulan setelah tanam (Periode ke-2 dan ke-4 tanam)
        if umur == 2 or umur == 4: wlr = wlr_val
        
    # 2. MT 2 (LP & PADI II)
    elif idx_lp2_start <= i < idx_padi2_start:
        fase = "LP Padi II"
        butuh = hitung_lp_vande_goor(eto_now, perkolasi, s=lp_sat, t=durasi_lp)
        
    elif idx_padi2_start <= i < idx_palawija_start:
        fase = "Padi II"
        umur = i - idx_padi2_start
        kc = get_kc_padi_15hari(umur)
        butuh = kc * eto_now + perkolasi
        if umur == 2 or umur == 4: wlr = wlr_val
        
    # 3. MT 3 (PALAWIJA / BERO)
    elif idx_palawija_start <= i < idx_end:
        if "Palawija" in pola:
            fase = "Palawija"
            umur = i - idx_palawija_start
            kc = get_kc_palawija_15hari(umur)
            butuh = kc * eto_now # Palawija tanpa perkolasi
        else:
            fase = "Bero"
            butuh = 0
    else:
        fase = "Bero"
        butuh = 0

    # Hitung Re (Hujan Efektif 15 Harian)
    # KP-01: Re Padi = 70% * R80 (setengah bulanan)
    re = 0
    if "Padi" in fase or "LP" in fase:
        re = (0.7 * ch_now) / 15
    elif "Palawija" in fase:
        re = (0.5 * ch_now) / 15
    
    # NFR
    nfr = butuh + wlr - re
    if nfr < 0: nfr = 0
    
    list_fase.append(fase)
    list_kc.append(kc)
    list_keb.append(butuh)
    list_wlr.append(wlr)
    list_re.append(re)
    list_nfr.append(nfr)

# Susun Data Frame Hasil (Urut Kalender)
final_data = []
for m_idx in range(24):
    # Cari step ke-berapa dalam loop tanam tadi yg periodenya m_idx?
    # Logic putaran:
    # m_idx = (idx_start + i) % 24
    # i (step) = (m_idx - idx_start) % 24
    
    step_i = (m_idx - idx_start) % 24
    
    # Q Irigasi (l/s/ha)
    # Faktor konversi mm/hari ke l/s/ha = 10000 / (24*3600) = 0.1157
    q_req = (list_nfr[step_i] * 0.1157) / efisiensi
    
    final_data.append({
        'Periode': periods[m_idx],
        'Fase': list_fase[step_i],
        'ETo': eto_vals[m_idx],
        'Kc': list_kc[step_i],
        'Keb. Air': list_keb[step_i],
        'WLR': list_wlr[step_i],
        'Re': list_re[step_i],
        'NFR (mm/hr)': list_nfr[step_i],
        'Q (l/s/ha)': q_req
    })

df_res = pd.DataFrame(final_data)

# Simpan Global NFR Max untuk Desain Saluran
st.session_state['nfr_global'] = df_res['Q (l/s/ha)'].max()

# --- 6. DISPLAY ---
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("📊 Neraca Air 24 Periode")
    numeric_cols = ['ETo', 'Kc', 'Keb. Air', 'WLR', 'Re', 'NFR (mm/hr)', 'Q (l/s/ha)']
    
    st.dataframe(
        df_res.style
        .background_gradient(cmap="Greens", subset=['Q (l/s/ha)'])
        .format("{:.2f}", subset=numeric_cols),
        use_container_width=True,
        height=600
    )

with col2:
    q_max = df_res['Q (l/s/ha)'].max()
    idx_max = df_res['Q (l/s/ha)'].idxmax()
    p_max = df_res.loc[idx_max, 'Periode']
    
    st.markdown(f"""
    <div class="metric-box">
        <b>NFR Desain (Q Max):</b><br>
        <span style="font-size: 28px; font-weight: bold;">{q_max:.3f}</span> l/det/ha<br>
        <small>Periode: {p_max}</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("#### 📈 Grafik Kebutuhan")
    st.line_chart(df_res.set_index('Periode')['Q (l/s/ha)'])

# --- 7. CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#558b2f;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)

st.divider()
st.subheader("📤 Kirim Data ke Irigasi Pipa")

col_kirim1, col_kirim2 = st.columns([3, 1])
with col_kirim1:
    st.info("Klik tombol ini agar Debit Kebutuhan (NFR Max) bisa dipakai di halaman Irigasi Pipa.")

with col_kirim2:
    if st.button("🚀 KIRIM Q DESAIN", type="primary", use_container_width=True):
        # Simpan Nilai Max ke Session State
        q_max_kirim = df_res['Q (l/s/ha)'].max()
        st.session_state['data_nfr_manual'] = q_max_kirim
        
        st.success(f"✅ Data Q ({q_max_kirim:.3f}) Terkirim!")
