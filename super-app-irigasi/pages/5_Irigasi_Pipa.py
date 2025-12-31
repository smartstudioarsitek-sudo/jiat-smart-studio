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
            'CH (mm)': [0.0]*12,       # Nanti diisi otomatis dari Mock
            'ETo (mm/hari)': [0.0]*12, # Nanti diisi otomatis dari Klimatologi
            'Kc': [1.0, 1.0, 1.0, 0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0] # Default Pola Tanam
        })

    # B. LOGIKA AUTO-FILL (Link Data Antar Halaman)
    status_link = []
    
    # 1. Ambil ETo dari Modul 1 (Klimatologi)
    if 'data_eto_transfer' in st.session_state:
        data_eto = st.session_state['data_eto_transfer']
        # Pastikan data ada 12 bulan (atau 24 periode, kita ambil rata2 per bulan jika perlu, tapi asumsi format sama)
        if len(data_eto) == 12:
            st.session_state['df_hujan']['ETo (mm/hari)'] = data_eto
            status_link.append("✅ ETo (Klimatologi)")

    # 2. Ambil CH dari Modul 3 (FJ Mock)
    if 'df_mock' in st.session_state:
        try:
            # Mengambil kolom hujan dari dataframe Mock
            # Asumsi Modul Mock menyimpan tabel bulanan dengan kolom 'Curah Hujan (mm)'
            hujan_mock = st.session_state['df_mock']['Curah Hujan (mm)'].tolist()
            if len(hujan_mock) == 12:
                st.session_state['df_hujan']['CH (mm)'] = hujan_mock
                status_link.append("✅ CH (FJ Mock)")
        except: 
            pass

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
        'luas_ha': 2.0, 'perkolasi': 2.0, 'efisiensi': 65,
        'head_statis_m': 63, 'safety_factor': 80,
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

q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_
