import streamlit as st
import pandas as pd
import numpy as np
import math
import json

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
    .info-box {
        padding: 10px; background-color: #e3f2fd; color: #0d47a1; 
        border-radius: 5px; margin-bottom: 10px; font-size: 0.9em;
    }
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
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
        data_eto = st.session_state['data_eto_manual']
        if len(data_eto) == 24: eto_24 = data_eto
        elif len(data_eto) == 12: 
            eto_24 = []
            for v in data_eto: eto_24.extend([v, v])
    elif 'data_eto_transfer' in st.session_state:
        data_eto = st.session_state['data_eto_transfer']
        if len(data_eto) == 24: eto_24 = data_eto
        elif len(data_eto) == 12:
            eto_24 = []
            for v in data_eto: eto_24.extend([v, v])

    # Default Hujan (Rata-rata)
    if 'df_hujan_24' not in st.session_state:
        # Dummy data hujan rata-rata
        ch_pola = [120, 120, 110, 110, 150, 150, 90, 90, 60, 60, 30, 30, 15, 15, 10, 10, 50, 50, 90, 90, 130, 130, 140, 140]
        st.session_state['df_hujan_24'] = pd.DataFrame({
            'Periode': periods, 
            'CH Rata-rata (mm)': [float(x) for x in ch_pola]
        })
        
    return periods, eto_24

# --- 4. SIDEBAR (UPLOAD CSV HUJAN) ---
with st.sidebar:
    st.header("📂 File & Tools")
    
    # Template CSV Download
    df_template = pd.DataFrame({'Bulan': ['Jan', 'Feb', 'Mar'], 'Curah Hujan': [200, 150, 100]})
    csv_template = df_template.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Template CSV Hujan", data=csv_template, file_name="template_hujan.csv", mime="text/csv")

    st.divider()

    # Upload Data Hujan
    uploaded_file = st.file_uploader("Upload CSV Hujan", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("🔄 Proses & Masukkan ke Tabel", type="primary"):
            try:
                # 1. Baca CSV (Cek Separator)
                try:
                    df_csv = pd.read_csv(uploaded_file)
                    if df_csv.shape[1] < 2:
                        uploaded_file.seek(0)
                        df_csv = pd.read_csv(uploaded_file, sep=';')
                except:
                    uploaded_file.seek(0)
                    df_csv = pd.read_csv(uploaded_file, sep=';')
                
                # 2. Cari Kolom Angka (Curah Hujan)
                df_numeric = df_csv.select_dtypes(include=[np.number])
                
                if df_numeric.shape[1] >= 1:
                    raw_hujan = df_numeric.iloc[:, 0].values # Ambil kolom angka pertama
                    
                    new_hujan = []
                    
                    # 3. LOGIKA EXPAND (12 -> 24)
                    if len(raw_hujan) == 12:
                        for val in raw_hujan:
                            new_hujan.extend([val, val]) # Duplikasi
                        st.toast("✅ Data Bulanan (12) di-expand ke 24 Periode!")
                        
                    elif len(raw_hujan) >= 24:
                        new_hujan = raw_hujan[:24]
                        st.toast("✅ Data 24 Periode dimuat!")
                    
                    else:
                        st.error("❌ Jumlah baris data aneh (harus 12 atau 24).")
                        new_hujan = None

                    # 4. Update Session State
                    if new_hujan is not None:
                        st.session_state['df_hujan_24']['CH Rata-rata (mm)'] = new_hujan
                        st.rerun()
                else:
                    st.error("❌ Tidak ditemukan kolom angka di CSV.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    
    st.header("🚜 Parameter Tanam")
    periods_opts, _ = init_data_24_periode()
    awal_tanam_label = st.selectbox("Awal Tanam", periods_opts, index=18)
    pola = st.selectbox("Pola Tata Tanam", ["Padi - Padi - Palawija", "Padi - Padi - Bero"])
    
    st.subheader("🌧️ Faktor Hujan")
    faktor_r80 = st.number_input("Faktor Koreksi R80", 0.5, 1.0, 0.8, 0.05, help="R80 = 0.8 * Rata-rata")
    
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

# A. Input Hujan (RATA-RATA + CSV SUPPORT)
with st.expander("🌧️ Input Curah Hujan (Manual / CSV)", expanded=True):
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"""
        <div class="info-box">
        <b>💡 Info:</b><br>
        Anda bisa mengetik manual di tabel atau <b>Upload CSV</b> di Sidebar.<br>
        Jika upload data bulanan, sistem otomatis membaginya ke 24 periode.<br>
        <br>
        <i>R80 = CH Rata² x {faktor_r80}</i>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        edited_hujan = st.data_editor(
            st.session_state['df_hujan_24'], 
            height=300, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "CH Rata-rata (mm)": st.column_config.NumberColumn(required=True)
            }
        )
        st.session_state['df_hujan_24'] = edited_hujan
        
        # PROSES HITUNG R80
        ch_rata_list = edited_hujan['CH Rata-rata (mm)'].tolist()
        r80_list = [x * faktor_r80 for x in ch_rata_list]

# B. Engine Hitungan (Pakai R80 Hasil Hitungan)
idx_start = periods.index(awal_tanam_label)
jml_per_lp = int(durasi_lp / 15) 

list_res = []
for i in range(24):
    curr_idx = (idx_start + i) % 24
    eto_now = eto_vals[curr_idx]
    r80_now = r80_list[curr_idx] 
    
    fase, kc, butuh, wlr = "", 0, 0, 0
    
    idx_padi1_start = jml_per_lp
    idx_lp2_start = idx_padi1_start + 8
    idx_padi2_start = idx_lp2_start + jml_per_lp
    idx_palawija_start = idx_padi2_start + 8
    idx_end = idx_palawija_start + 6

    # Logika Fase
    if i < idx_padi1_start:
        fase = "LP Padi I"; butuh = hitung_lp_vande_goor(eto_now, perkolasi, s=lp_sat, t=durasi_lp)
    elif idx_padi1_start <= i < idx_lp2_start:
        fase = "Padi I"; umur = i - idx_padi1_start; kc = get_kc_padi_15hari(umur)
        butuh = kc * eto_now + perkolasi
        if umur == 2 or umur == 4: wlr = wlr_val
    elif idx_lp2_start <= i < idx_padi2_start:
        fase = "LP Padi II"; butuh = hitung_lp_vande_goor(eto_now, perkolasi, s=lp_sat, t=durasi_lp)
    elif idx_padi2_start <= i < idx_palawija_start:
        fase = "Padi II"; umur = i - idx_padi2_start; kc = get_kc_padi_15hari(umur)
        butuh = kc * eto_now + perkolasi
        if umur == 2 or umur == 4: wlr = wlr_val
    elif idx_palawija_start <= i < idx_end:
        if "Palawija" in pola:
            fase = "Palawija"; umur = i - idx_palawija_start; kc = get_kc_palawija_15hari(umur)
            butuh = kc * eto_now
        else: fase, butuh = "Bero", 0
    else: fase, butuh = "Bero", 0

    re = 0
    if "Padi" in fase or "LP" in fase: re = (0.7 * r80_now) / 15
    elif "Palawija" in fase: re = (0.5 * r80_now) / 15
    
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
        'CH Rata2': ch_rata_list[m_idx],
        'R80 (Calc)': r80_list[m_idx],
        'Fase': d['fase'],
        'ETo': eto_vals[m_idx],
        'Re': d['re'],
        'NFR (L/s/ha)': q_req
    })

df_res = pd.DataFrame(final_data)

# C. Tampilan
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("Hasil Perhitungan Pola Tanam")
    st.dataframe(
        df_res.style.background_gradient(cmap="Greens", subset=['NFR (L/s/ha)'])
        .format({
            "CH Rata2": "{:.1f}", "R80 (Calc)": "{:.1f}", 
            "ETo": "{:.2f}", "Re": "{:.2f}", "NFR (L/s/ha)": "{:.3f}"
        }), 
        use_container_width=True, 
        height=500
    )
    
    st.divider()
    st.info("👇 Kirim Data Lengkap (24 Periode) ke Irigasi Pipa")
    if st.button("🚀 KIRIM POLA TANAM (FULL)", type="primary", use_container_width=True):
        data_full = df_res['NFR (L/s/ha)'].tolist()
        st.session_state['data_nfr_manual'] = data_full 
        
        st.markdown(f"""
        <div class="success-box">
            <b>✅ Data Terkirim!</b><br>
            Data 24 Periode (naik-turun) sudah dikirim. Silakan 'Ambil Data' di Page Irigasi Pipa.
        </div>
        """, unsafe_allow_html=True)

with col2:
    q_max = df_res['NFR (L/s/ha)'].max()
    st.markdown(f"""<div class="metric-box"><b>NFR Max:</b><br><h2>{q_max:.3f} l/s/ha</h2></div>""", unsafe_allow_html=True)
    st.line_chart(df_res.set_index('Periode')['NFR (L/s/ha)'])

st.divider()
import streamlit.components.v1 as components
components.html("""<button onclick="window.print()" style="background:#558b2f;color:white;border:none;padding:10px;">🖨️ Cetak</button>""", height=50)
