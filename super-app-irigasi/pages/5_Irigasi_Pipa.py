import streamlit as st
import pandas as pd
import math
import altair as alt
import json
import numpy as np

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="JIAT Smart Studio", layout="wide", page_icon="💧")

# --- CSS UI ---
st.markdown("""
<style>
    .box-hasil {padding: 15px; background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px; margin-bottom: 10px;}
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI & TARIK DATA (LINKING)
# ==========================================
def init_state():
    # A. DataFrame Default (12 Bulan)
    if 'df_hujan' not in st.session_state:
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
        st.session_state['df_hujan'] = pd.DataFrame({
            'Bulan': months,
            'CH (mm)': [0.0]*12,       # Akan diisi dari Modul FJ Mock
            'ETo (mm/hari)': [0.0]*12, # Akan diisi dari Modul Klimatologi
            'Kc': [1.0, 1.0, 1.0, 0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0] # Default Pola Tanam
        })

    # B. LOGIKA AUTO-FILL (Link Data)
    status_link = []
    
    # 1. Ambil ETo dari Modul 1 (Klimatologi)
    if 'data_eto_transfer' in st.session_state:
        data_eto = st.session_state['data_eto_transfer']
        if len(data_eto) == 12:
            st.session_state['df_hujan']['ETo (mm/hari)'] = data_eto
            status_link.append("✅ ETo (Klimatologi)")

    # 2. Ambil CH dari Modul 3 (FJ Mock)
    if 'df_mock' in st.session_state:
        try:
            # Ambil kolom 'Curah Hujan (mm)' dari dataframe Mock
            hujan_mock = st.session_state['df_mock']['Curah Hujan (mm)'].tolist()
            if len(hujan_mock) == 12:
                st.session_state['df_hujan']['CH (mm)'] = hujan_mock
                status_link.append("✅ CH (FJ Mock)")
        except: pass

    st.session_state['link_status'] = " | ".join(status_link) if status_link else "⚠️ Input Manual"

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

init_state()

# ==========================================
# 3. SIDEBAR (PARAMETER)
# ==========================================
with st.sidebar:
    st.title("📂 File Manager")
    
    # Save/Load
    clean_params = {k:v for k,v in st.session_state.items() if not isinstance(v, pd.DataFrame)}
    current_data = {
        'params': clean_params,
        'hujan': st.session_state['df_hujan'].to_dict(orient='records'),
        'pipa': st.session_state['df_pipa'].to_dict(orient='records')
    }
    st.download_button("💾 Simpan Proyek", json.dumps(current_data, indent=2), "jiat_project.json", "application/json")
    
    st.markdown("---")
    st.header("1. Input Parameter")
    st.session_state['nama_proyek'] = st.text_input("Proyek", st.session_state['nama_proyek'])
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=st.session_state['luas_ha'])
    
    with st.expander("⚙️ Faktor Kebutuhan Air"):
        st.session_state['perkolasi'] = st.number_input("Perkolasi (mm/hari)", value=st.session_state['perkolasi'])
        st.session_state['efisiensi'] = st.number_input("Efisiensi Irigasi (%)", value=st.session_state['efisiensi'])

    st.markdown("---")
    with st.expander("⛰️ Parameter Sumur (Geologi)"):
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal Akuifer (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("Permeabilitas K (m/hari)", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("Drawdown Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Jari-jari Sumur (m)", value=st.session_state['radius_m'])
        st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
        st.session_state['safety_factor'] = st.number_input("Safety Factor (%)", value=st.session_state['safety_factor'])

# ==========================================
# 4. ENGINE HITUNGAN (NERACA AIR)
# ==========================================
# A. Hitung Supply (Air Tanah)
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10

q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# B. Hitung Demand (Tabel Neraca Air)
df_calc = st.session_state['df_hujan'].copy()

# 1. Hujan Efektif (Re) - Metode F.A.O / Oldeman sederhana
# Re = 80% CH / 30 hari (Asumsi curah hujan efektif untuk tanaman palawija/umum)
# Logic: Jika CH < 250 -> Re = 0.8 * CH. Jika > 250 -> Re = ...
df_calc['Re (mm)'] = df_calc['CH (mm)'].apply(lambda x: (0.8 * x)/30 if x < 250 else (125 + 0.1*(x-250))/30)

# 2. Kebutuhan Tanaman (ETc)
df_calc['ETc (mm)'] = df_calc['ETo (mm/hari)'] * df_calc['Kc']

# 3. Kebutuhan Bersih (NFR) = ETc + Perkolasi - Re
perkolasi = st.session_state['perkolasi']
df_calc['NFR (mm)'] = (df_calc['ETc (mm)'] + perkolasi - df_calc['Re (mm)']).clip(lower=0)

# 4. Kebutuhan Debit (Q Req)
# Q (l/s) = (NFR * Ha * 10000) / (Eff * 24 * 3600 * 30) -> Konversi 1 mm/hari/ha ~= 0.1157 l/s
eff_dec = st.session_state['efisiensi'] / 100
df_calc['Q Req (L/s)'] = (df_calc['NFR (mm)'] * 0.1157 * st.session_state['luas_ha']) / eff_dec

# Ambil Nilai Maksimum
q_desain = df_calc['Q Req (L/s)'].max()
idx_max = df_calc['Q Req (L/s)'].idxmax()
bln_max = df_calc.loc[idx_max, 'Bulan']

# ==========================================
# 5. TAMPILAN TABS
# ==========================================
st.title(f"💧 {st.session_state['nama_proyek']}")
st.caption(f"Lokasi: {st.session_state['lokasi']} | Status Data: {st.session_state['link_status']}")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT DATA", "💧 KEBUTUHAN AIR", "⚙️ PIPA & HIDROLIKA", "📊 HASIL & GRAFIK"])

# --- TAB 1: INPUT ---
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("A. Data Hujan & Klimatologi")
        if "Manual" not in st.session_state['link_status']:
            st.info(f"💡 Data **CH** dan **ETo** otomatis terisi dari Modul sebelumnya. Silakan sesuaikan **Kc (Pola Tanam)** jika perlu.")
        
        st.data_editor(st.session_state['df_hujan'], key='editor_hujan', num_rows="dynamic", use_container_width=True,
                       on_change=lambda: st.session_state.update({'df_hujan': st.session_state.editor_hujan}))
    with col2:
        st.subheader("B. Jaringan Pipa")
        st.data_editor(st.session_state['df_pipa'], key='editor_pipa', num_rows="dynamic", use_container_width=True,
                       on_change=lambda: st.session_state.update({'df_pipa': st.session_state.editor_pipa}))

# --- TAB 2: KEBUTUHAN AIR (TABEL HITUNGAN) ---
with tab2:
    st.subheader("Analisa Neraca Air")
    
    # Filter hanya kolom angka untuk diformat agar tidak error
    numeric_cols = ['CH (mm)', 'ETo (mm/hari)', 'Kc', 'Re (mm)', 'ETc (mm)', 'NFR (mm)', 'Q Req (L/s)']
    
    # Tampilkan Tabel Full
    st.dataframe(
        df_calc.style.format("{:.2f}", subset=numeric_cols)
               .highlight_max(subset=['Q Req (L/s)'], color='#e3f2fd', axis=0),
        use_container_width=True
    )
    
    st.info(f"👉 **Debit Puncak (Kebutuhan Desain):** {q_desain:.2f} L/s pada bulan **{bln_max}**")

# --- TAB 3: PIPA & HIDROLIKA ---
with tab3:
    st.subheader("Perhitungan Hidrolis Pipa")
    
    # Hitung Pipa
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
            V, Hf = 0, 0
            
        v_list.append(V)
        hf_list.append(Hf)
        hf_total += Hf

    df_pipa_res['V (m/s)'] = v_list
    df_pipa_res['Hf (m)'] = hf_list

    # Tampilkan Tabel
    num_cols_pipa = ['Panjang (m)', 'Diameter (mm)', 'C (Hazen)', 'Debit (L/s)', 'V (m/s)', 'Hf (m)']
    st.dataframe(df_pipa_res.style.format("{:.3f}", subset=num_cols_pipa), use_container_width=True)
    
    # Cek Kecepatan
    st.write("#### 🚦 Cek Kecepatan")
    col_cek = st.columns(3)
    for i, row in df_pipa_res.iterrows():
        v = row['V (m/s)']
        seg = row['Segmen']
        if v < 0.3: st.warning(f"⚠️ {seg}: Endapan (V={v:.2f})")
        elif v > 2.5: st.error(f"⛔ {seg}: Erosi (V={v:.2f})")
        else: st.success(f"✅ {seg}: Aman (V={v:.2f})")

# --- TAB 4: HASIL ---
with tab4:
    st.markdown("## 📊 Resume Desain")
    
    head_total = st.session_state['head_statis_m'] + hf_total + (0.1 * hf_total)
    daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.markdown("### ⚡ Pompa")
        st.write(f"- Debit Desain: **{q_desain:.2f} L/s**")
        st.write(f"- Supply Sumur: **{q_safe:.2f} L/s**")
        st.write(f"- Total Head: **{head_total:.2f} m**")
        st.write(f"- Daya Poros: **{daya_kw:.2f} kW**")
        
        if q_safe >= q_desain:
            st.success("✅ **STATUS: AMAN (Surplus)**")
        else:
            st.error(f"❌ **STATUS: DEFISIT ({q_safe - q_desain:.2f} L/s)**")
            
    with c2:
        # Grafik
        source = df_calc.copy()
        bar = alt.Chart(source).mark_bar().encode(x='Bulan', y=alt.Y('Q Req (L/s)', title='Debit (L/s)'))
        line = alt.Chart(source).mark_rule(color='red').encode(y=alt.datum(q_safe))
        st.altair_chart((bar + line).interactive(), use_container_width=True)
