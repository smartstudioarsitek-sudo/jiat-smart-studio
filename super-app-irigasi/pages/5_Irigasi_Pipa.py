import streamlit as st
import pandas as pd
import math
import altair as alt
import json
import numpy as np

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="JIAT Smart Studio", layout="wide", page_icon="💧")

# --- CSS UI ---
st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="stHeader"] {display: none !important;}
        .no-print {display: none !important;}
        * {-webkit-print-color-adjust: exact !important; print-color-adjust: exact !important;}
    }
    .box-hasil {padding: 15px; background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px; margin-bottom: 10px;}
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. INISIALISASI DATA & LINKING
# ==========================================
def init_state():
    # A. Buat DataFrame Hujan Kosong (Default)
    if 'df_hujan' not in st.session_state:
        st.session_state['df_hujan'] = pd.DataFrame({
            'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
            'CH (mm)': [0.0]*12,
            'ETo (mm/hari)': [0.0]*12,
            'Kc': [0.8]*12
        })

    # B. LOGIKA LINKING (Tarik Data dari Modul Lain)
    
    # 1. Ambil ETo dari Modul 1 (Klimatologi)
    if 'data_eto_transfer' in st.session_state:
        data_eto = st.session_state['data_eto_transfer']
        # Pastikan jumlah datanya 12 bulan
        if len(data_eto) == 12:
            st.session_state['df_hujan']['ETo (mm/hari)'] = data_eto

    # 2. Ambil Curah Hujan dari Modul 3 (FJ Mock)
    if 'df_mock' in st.session_state:
        try:
            # Coba ambil kolom hujan dari tabel Mock
            hujan_mock = st.session_state['df_mock']['Curah Hujan (mm)'].tolist()
            if len(hujan_mock) == 12:
                st.session_state['df_hujan']['CH (mm)'] = hujan_mock
        except:
            pass # Jika gagal, biarkan 0

    # C. Data Pipa Default
    if 'df_pipa' not in st.session_state:
        st.session_state['df_pipa'] = pd.DataFrame({
            'Segmen': ['Jalur Utama', 'Sub-S1', 'Sub-S2'],
            'Panjang (m)': [500, 200, 150],
            'Diameter (mm)': [90, 63, 63],
            'C (Hazen)': [150, 150, 150],
            'Debit (L/s)': [5.0, 2.5, 2.5]
        })
    
    # D. Parameter Default
    defaults = {
        'nama_proyek': "JIAT Lampung Timur", 'lokasi': "Desa Hargomulyo", 'tahun': "2025",
        'luas_ha': 5.0, 'perkolasi': 2.0, 'efisiensi': 80,
        'head_statis_m': 25, 'safety_factor': 80,
        'tebal_akuifer_m': 20, 'k_perm': 4.32, 
        'drawdown_izin_m': 10, 'radius_m': 0.15
    }
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val

# Jalankan Inisialisasi
init_state()

# ==========================================
# 2. SIDEBAR (FILE MANAGER & PARAMETER)
# ==========================================
with st.sidebar:
    st.title("📂 File Manager")
    
    # Fitur Save/Load JSON
    clean_params = {k:v for k,v in st.session_state.items() if not isinstance(v, pd.DataFrame)}
    current_data = {
        'params': clean_params,
        'hujan': st.session_state['df_hujan'].to_dict(orient='records'),
        'pipa': st.session_state['df_pipa'].to_dict(orient='records')
    }
    
    c_dl, c_up = st.columns(2)
    c_dl.download_button("💾 Save", json.dumps(current_data, indent=2), "proyek_jiat.json", "application/json")
    uploaded = st.file_uploader("📂 Open", type=["json"], label_visibility="collapsed")
    if uploaded:
        try:
            data = json.load(uploaded)
            for k, v in data['params'].items(): st.session_state[k] = v
            st.session_state['df_hujan'] = pd.DataFrame(data['hujan'])
            st.session_state['df_pipa'] = pd.DataFrame(data['pipa'])
            st.toast("Proyek berhasil dimuat!", icon="✅")
        except: st.error("File korup!")

    st.markdown("---")
    st.header("1. Input Parameter")
    
    st.session_state['nama_proyek'] = st.text_input("Nama Proyek", st.session_state['nama_proyek'])
    st.session_state['lokasi'] = st.text_input("Lokasi", st.session_state['lokasi'])
    
    st.markdown("---")
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=st.session_state['luas_ha'])
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
    
    with st.expander("⛰️ Parameter Sumur (Geologi)", expanded=False):
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal Akuifer (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("Permeabilitas K (m/hari)", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("Drawdown Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Jari-jari Sumur (m)", value=st.session_state['radius_m'])
        st.session_state['safety_factor'] = st.number_input("Safety Factor Debit (%)", value=st.session_state['safety_factor'])

# ==========================================
# 3. HEADER
# ==========================================
st.title(f"💧 {st.session_state['nama_proyek']}")
st.caption(f"📍 {st.session_state['lokasi']} | 🗓️ Tahun {st.session_state['tahun']}")
st.markdown("---")

# ==========================================
# 4. ENGINE HITUNGAN
# ==========================================

# --- A. Hitung Supply (Air Tanah) ---
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10

q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# --- B. Hitung Demand (Kebutuhan Air) ---
# Cek NFR Link (Prioritas Utama)
link_nfr = False
nfr_linked_val = 0

if 'nfr_global' in st.session_state and st.session_state['nfr_global'] > 0:
    link_nfr = True
    nfr_linked_val = st.session_state['nfr_global']
    q_desain = nfr_linked_val * st.session_state['luas_ha']
    sumber_nfr = f"🔗 Terhubung Modul Pola Tanam ({nfr_linked_val:.3f} l/s/ha)"
    
    # Buat tabel dummy untuk visualisasi grafik saja
    df_calc = st.session_state['df_hujan'].copy()
    df_calc['Q_Req'] = q_desain 
else:
    # Hitung Manual dari Tabel Internal
    df_calc = st.session_state['df_hujan'].copy()
    df_calc['Re'] = df_calc['CH (mm)'].apply(lambda x: (0.8 * x)/30 if x < 250 else (125 + 0.1*(x-250))/30)
    df_calc['ETc'] = df_calc['ETo (mm/hari)'] * df_calc['Kc']
    df_calc['NFR_mm'] = (df_calc['ETc'] + st.session_state['perkolasi'] - df_calc['Re']).clip(lower=0)
    
    eff_dec = st.session_state['efisiensi'] / 100
    df_calc['Q_Req'] = (df_calc['NFR_mm'] * 0.1157 * st.session_state['luas_ha']) / eff_dec
    
    q_desain = df_calc['Q_Req'].max()
    sumber_nfr = "✏️ Perhitungan Internal (Tabel)"

# --- C. Hitung Hidrolika Pipa ---
df_pipa_res = st.session_state['df_pipa'].copy()
hf_total = 0
v_list, hf_list = [], []

for i, row in df_pipa_res.iterrows():
    L = row['Panjang (m)']
    D_mm = row['Diameter (mm)']
    Q_ls = row['Debit (L/s)']
    C = row['C (Hazen)']
    
    D_m = D_mm / 1000
    Q_m3s = Q_ls / 1000
    
    if D_m > 0 and Q_m3s > 0:
        Area = 0.25 * math.pi * (D_m**2)
        V = Q_m3s / Area
        Hf = 10.67 * L * (Q_m3s**1.852) / ((C**1.852)*(D_m**4.87))
    else:
        V = 0
        Hf = 0
        
    v_list.append(V)
    hf_list.append(Hf)
    hf_total += Hf

df_pipa_res['V (m/s)'] = v_list
df_pipa_res['Hf (m)'] = hf_list

head_total = st.session_state['head_statis_m'] + hf_total + (0.1 * hf_total)
daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70
daya_hp = daya_kw * 1.341

# ==========================================
# 5. TAMPILAN TABS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT DATA", "💧 KEBUTUHAN AIR", "⚙️ PIPA & HIDROLIKA", "📊 HASIL & LAPORAN"])

# === TAB 1: INPUT ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("A. Data Hujan & ETo")
        
        # Info Koneksi Data
        if 'data_eto_transfer' in st.session_state:
            st.success("✅ ETo terhubung dengan Modul Klimatologi.")
        if 'df_mock' in st.session_state:
            st.success("✅ Curah Hujan terhubung dengan Modul Mock.")
            
        st.data_editor(st.session_state['df_hujan'], key='editor_hujan', num_rows="dynamic", use_container_width=True,
                       on_change=lambda: st.session_state.update({'df_hujan': st.session_state.editor_hujan}))
    with col2:
        st.subheader("B. Segmen Pipa")
        st.data_editor(st.session_state['df_pipa'], key='editor_pipa', num_rows="dynamic", use_container_width=True,
                       on_change=lambda: st.session_state.update({'df_pipa': st.session_state.editor_pipa}))

# === TAB 2: KEBUTUHAN ===
with tab2:
    st.subheader("Analisa Neraca Air")
    
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.markdown(f"""<div class="box-hasil" style="border-left: 5px solid #2196F3;">
            <h4>💧 Kebutuhan (Demand)</h4><div style="font-size: 24px; font-weight: bold;">{q_desain:.2f} L/detik</div>
            <small>{sumber_nfr}</small></div>""", unsafe_allow_html=True)
        
    with col_k2:
        color_sup = "green" if q_safe >= q_desain else "red"
        st.markdown(f"""<div class="box-hasil" style="border-left: 5px solid {color_sup};">
            <h4>🚰 Ketersediaan Sumur (Supply)</h4><div style="font-size: 24px; font-weight: bold; color: {color_sup}">{q_safe:.2f} L/detik</div>
            <small>Safe Yield (SF: {st.session_state['safety_factor']}%)</small></div>""", unsafe_allow_html=True)

    if q_safe < q_desain:
        st.error("❌ **DEFISIT AIR!**")
    else:
        st.success("✅ **SURPLUS AIR.**")

    if not link_nfr:
        st.write("#### 📅 Detail Perhitungan Bulanan (Manual)")
        # [SOLUSI ANTI-ERROR]: Filter hanya kolom angka untuk diformat
        numeric_cols = df_calc.select_dtypes(include=[np.number]).columns
        st.dataframe(df_calc.style.format("{:.2f}", subset=numeric_cols), use_container_width=True)

# === TAB 3: PIPA ===
with tab3:
    st.subheader("Analisa Hidrolis Pipa")
    # [SOLUSI ANTI-ERROR]: Filter kolom angka
    num_cols_pipa = df_pipa_res.select_dtypes(include=[np.number]).columns
    st.dataframe(df_pipa_res.style.format("{:.3f}", subset=num_cols_pipa), use_container_width=True)
    
    st.write("#### 🚦 Cek Kecepatan")
    for i, row in df_pipa_res.iterrows():
        v = row['V (m/s)']
        seg = row['Segmen']
        if v < 0.3: st.warning(f"⚠️ {seg}: Endapan (V={v:.2f} m/s)")
        elif v > 2.5: st.error(f"⛔ {seg}: Erosi (V={v:.2f} m/s)")
        else: st.success(f"✅ {seg}: Aman (V={v:.2f} m/s)")

# === TAB 4: HASIL ===
with tab4:
    st.markdown("## 📑 Laporan Desain")
    c_res1, c_res2 = st.columns([1, 1.5])
    
    with c_res1:
        st.success(f"""**Rekomendasi Pompa:**
        * Q: {q_desain:.2f} L/s
        * H: {head_total:.2f} m
        * P: {daya_kw:.2f} kW""")
        st.write(f"Statis: {st.session_state['head_statis_m']} m | Loss: {hf_total*1.1:.2f} m")
    
    with c_res2:
        base = alt.Chart(df_calc).encode(x='Bulan')
        bar = base.mark_bar().encode(y='Q_Req')
        line = base.mark_rule(color='red').encode(y=alt.datum(q_safe))
        st.altair_chart((bar + line).interactive(), use_container_width=True)
