import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Pola Tanam & NFR", layout="wide", page_icon="🌾")

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
    .info-box {
        background-color: #fff3e0; border: 1px solid #ffe0b2;
        padding: 10px; border-radius: 5px; font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. RUMUS KP-01 ---

def hitung_lp_vande_goor(eto, p, s=250, t=30):
    """
    Menghitung Kebutuhan Air Penyiapan Lahan (LP)
    Metode: Van de Goor & Zijlstra (Standar KP-01)
    IR = M * e^k / (e^k - 1)
    Dimana:
      M = ETo + P (Perkolasi)
      k = (M * T) / S
      S = Kebutuhan air jenuh (biasanya 200-250 mm)
      T = Jangka waktu penyiapan (biasanya 30 atau 45 hari)
    """
    # ETo dan P dalam mm/hari
    M = eto + p
    try:
        if M <= 0: return 0
        k = (M * t) / s
        ek = math.exp(k)
        if ek == 1: return M # Hindari bagi nol
        LP = M * ek / (ek - 1)
        return LP
    except:
        return 0

def get_kc_padi(umur_bulan, varietas='unggul'):
    """Standar Kc Padi KP-01 (Nedeco) - Basis Bulanan"""
    # Biasanya: 1.1, 1.1, 1.05, 0.95 (Panen)
    if varietas == 'unggul': # Padi 3-4 Bulan
        if umur_bulan == 1: return 1.10
        elif umur_bulan == 2: return 1.10
        elif umur_bulan == 3: return 1.05
        elif umur_bulan == 4: return 0.95
        else: return 0
    else: # Padi Biasa (Varietas Lokal)
        if umur_bulan == 1: return 1.10
        elif umur_bulan == 2: return 1.10
        elif umur_bulan == 3: return 1.05
        elif umur_bulan == 4: return 0.95 # Asumsi disamakan utk simplifikasi bulanan
        else: return 0

def get_kc_palawija(umur_bulan):
    """Standar Kc Palawija (Jagung/Kedelai) KP-01"""
    # Pola: 0.5 -> 0.75 -> 1.0 -> 0.7
    if umur_bulan == 1: return 0.60
    elif umur_bulan == 2: return 0.90
    elif umur_bulan == 3: return 0.85
    else: return 0

# --- 3. STATE MANAGEMENT (DATA LOAD) ---
def load_data():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    
    # 1. Ambil ETo dari Page 1 (Klimatologi)
    if 'data_eto_transfer' in st.session_state:
        eto_data = st.session_state['data_eto_transfer']
    else:
        # Dummy jika belum ada data
        eto_data = [4.5] * 12
    
    # 2. Ambil Hujan dari Mock (jika ada) atau Manual
    if 'df_hujan_manual' not in st.session_state:
        st.session_state['df_hujan_manual'] = pd.DataFrame({
            'Bulan': months,
            'CH (mm)': [200.0, 180.0, 250.0, 150.0, 100.0, 50.0, 20.0, 10.0, 80.0, 150.0, 220.0, 240.0]
        })

    return months, eto_data

# --- 4. SIDEBAR INPUT ---
with st.sidebar:
    st.header("🚜 Parameter Pola Tanam")
    
    st.subheader("1. Jadwal Tanam")
    awal_tanam = st.selectbox("Awal Tanam (Bulan)", 
                              ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
                              index=9) # Default Oktober (Awal Musim Hujan umumnya)
    
    pola = st.selectbox("Jenis Pola Tanam", ["Padi - Padi - Palawija", "Padi - Padi - Bero", "Padi - Palawija - Palawija"])
    
    st.subheader("2. Faktor Tanah & Air")
    perkolasi = st.number_input("Perkolasi (mm/hari)", 1.0, 5.0, 2.0, 0.1, help="Lempung: 1-2, Pasir: >3")
    wlr_val = st.number_input("WLR (mm/hari)", 0.0, 10.0, 3.3, 0.1, help="Penggantian Lapisan Air (50mm/15hari = 3.3)")
    lp_sat = st.number_input("Air Jenuh (S) mm", 150, 300, 250, help="Air untuk penjenuhan tanah (KP-01: 200-250mm)")
    
    st.divider()
    efisiensi = st.slider("Efisiensi Irigasi Total (%)", 40, 90, 65) / 100

# --- 5. MAIN LOGIC ---
months, eto_vals = load_data()
df_calc = pd.DataFrame({'Bulan': months, 'ETo': eto_vals})

# A. Input Hujan (Karena NFR butuh Hujan Efektif)
st.title("🌾 Pola Tanam & Kebutuhan Air (KP-01)")

with st.expander("🌧️ Data Curah Hujan (R80)", expanded=True):
    st.info("Masukkan Curah Hujan R80 (Probabilitas 80%) atau Rerata.")
    edited_hujan = st.data_editor(st.session_state['df_hujan_manual'], num_rows="fixed", hide_index=True, use_container_width=True)
    st.session_state['df_hujan_manual'] = edited_hujan
    df_calc['CH'] = edited_hujan['CH (mm)']

# B. Perhitungan NFR
# Cari index bulan awal tanam
bulan_map = {m: i for i, m in enumerate(months)}
idx_start = bulan_map[awal_tanam]

# Array Hasil
list_kc = []
list_kebutuhan = [] # Ini bisa LP, atau ETc
list_wlr = []
list_re = []
list_nfr = []
list_keterangan = []

# Logic Looping 12 Bulan (Siklus)
for i in range(12):
    # Index berputar (Jan..Des..Jan)
    curr_idx = (idx_start + i) % 12
    
    # Ambil Data Iklim Bulan ini
    eto_harian = df_calc.loc[curr_idx, 'ETo']
    ch_bulanan = df_calc.loc[curr_idx, 'CH']
    
    # Tentukan Fase Tanam berdasarkan "i" (Bulan ke-berapa sejak start)
    # Asumsi Pola: Padi (4 bln) - Padi (4 bln) - Palawija (3 bln) - Bero (1 bln)
    
    kc = 0
    jenis_tanaman = ""
    butuh_air = 0
    wlr = 0
    
    # --- LOGIKA FASE TANAMAN (CONTOH: PADI-PADI-PALAWIJA) ---
    if pola == "Padi - Padi - Palawija":
        # MT 1: PADI (Bulan 0 s/d 3)
        if i == 0: 
            jenis_tanaman = "LP Padi I"
            # Hitung LP Van de Goor
            butuh_air = hitung_lp_vande_goor(eto_harian, perkolasi, s=lp_sat)
            kc = 0 # Masa penyiapan lahan belum ada tanaman
        elif 1 <= i <= 4:
            jenis_tanaman = "Padi I"
            umur = i 
            kc = get_kc_padi(umur)
            butuh_air = kc * eto_harian + perkolasi # ETc + P
            if i in [2, 3]: wlr = wlr_val # WLR biasanya 1-2 bulan setelah tanam
            
        # MT 2: PADI (Bulan 4 s/d 8)
        elif i == 5:
            jenis_tanaman = "LP Padi II"
            butuh_air = hitung_lp_vande_goor(eto_harian, perkolasi, s=lp_sat)
        elif 6 <= i <= 9:
            jenis_tanaman = "Padi II"
            umur = i - 5
            kc = get_kc_padi(umur)
            butuh_air = kc * eto_harian + perkolasi
            if i in [7, 8]: wlr = wlr_val
            
        # MT 3: PALAWIJA (Bulan 9 s/d 11)
        elif 10 <= i <= 11:
            jenis_tanaman = "Palawija"
            umur = i - 9
            kc = get_kc_palawija(umur)
            butuh_air = kc * eto_harian # Palawija tidak ada perkolasi (biasanya)
        else:
            jenis_tanaman = "Bero"
            butuh_air = 0
            
    # Simpan Logic Sederhana (Bisa dikembangkan untuk pola lain)
    else:
        # Default fallback jika pola lain belum diset detail
        jenis_tanaman = "Custom"
        kc = 1.0
        butuh_air = eto_harian
    
    # Hitung Hujan Efektif (Re)
    # KP-01: Re Padi = 70% * CH R80. Re Palawija = 50% * CH.
    re = 0
    if "Padi" in jenis_tanaman and "LP" not in jenis_tanaman:
        re = (0.7 * ch_bulanan) / 30 # mm/hari
    elif "Palawija" in jenis_tanaman:
        re = (0.5 * ch_bulanan) / 30
    elif "LP" in jenis_tanaman:
        re = (0.7 * ch_bulanan) / 30 # Saat LP masih dianggap genangan
        
    # NFR (Net Field Requirement)
    # NFR = Kebutuhan + WLR - Re
    nfr = butuh_air + wlr - re
    if nfr < 0: nfr = 0
    
    list_kc.append(kc)
    list_kebutuhan.append(butuh_air)
    list_wlr.append(wlr)
    list_re.append(re)
    list_nfr.append(nfr)
    list_keterangan.append(jenis_tanaman)

# Re-mapping hasil ke urutan bulan kalender (Jan-Des)
final_data = []
for m_idx in range(12):
    # Kita harus cari data yang bulannya sesuai dengan m_idx
    # Karena loop tadi dimulai dari 'idx_start', kita harus urutkan ulang
    
    # Cari di langkah ke-berapa (i) bulan m_idx ini diproses?
    # curr_idx = (idx_start + i) % 12  ==> Kita cari i
    # i = (m_idx - idx_start) % 12
    step_i = (m_idx - idx_start) % 12
    
    final_data.append({
        'Bulan': months[m_idx],
        'Fase': list_keterangan[step_i],
        'ETo': df_calc.loc[m_idx, 'ETo'],
        'Kc': list_kc[step_i],
        'Kebutuhan Air': list_kebutuhan[step_i], # Ini (ETc + P) atau LP
        'WLR': list_wlr[step_i],
        'Re': list_re[step_i],
        'NFR (mm/hr)': list_nfr[step_i],
        'Q (l/s/ha)': list_nfr[step_i] * 0.1157 / efisiensi # 1/8.64 = 0.1157
    })

df_final = pd.DataFrame(final_data)
st.session_state['nfr_global'] = df_final['Q (l/s/ha)'].max()

# --- 6. DISPLAY HASIL ---
col_res1, col_res2 = st.columns([3, 1])

with col_res1:
    st.subheader("📊 Tabel Perhitungan NFR")
    
    # Formatting
    numeric_cols = ['ETo', 'Kc', 'Kebutuhan Air', 'WLR', 'Re', 'NFR (mm/hr)', 'Q (l/s/ha)']
    st.dataframe(
        df_final.style
        .background_gradient(cmap="Greens", subset=['Q (l/s/ha)'])
        .format("{:.2f}", subset=numeric_cols),
        use_container_width=True,
        height=500
    )

with col_res2:
    q_max = df_final['Q (l/s/ha)'].max()
    bln_max = df_final.loc[df_final['Q (l/s/ha)'].idxmax(), 'Bulan']
    
    st.markdown(f"""
    <div class="metric-box">
        <b>Kebutuhan Maksimum (NFR):</b><br>
        <span style="font-size: 28px; font-weight: bold;">{q_max:.3f}</span> l/det/ha<br>
        <small>Terjadi pada bulan: {bln_max}</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("#### 📈 Grafik NFR")
    st.bar_chart(df_final.set_index('Bulan')['Q (l/s/ha)'])
    
    with st.expander("ℹ️ Keterangan Rumus KP-01"):
        st.markdown("""
        1. **LP (Penyiapan Lahan):** Metode *Van de Goor & Zijlstra*.
        2. **ETc Padi:** $Kc \\times ETo + Perkolasi$.
        3. **WLR:** Penggantian air 3.3 mm/hari (50mm/15hari).
        4. **Re (Hujan Efektif):** Padi (70%), Palawija (50%).
        """)

# --- 7. TOMBOL CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#558b2f;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)
