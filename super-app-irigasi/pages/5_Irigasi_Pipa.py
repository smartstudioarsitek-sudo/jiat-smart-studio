import streamlit as st
import pandas as pd
import math
import altair as alt
import json

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
    .tooltip {font-size: 12px; color: #555; font-style: italic;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. INISIALISASI DATA (DEFAULT VALUE)
# ==========================================
def init_state():
    if 'df_hujan' not in st.session_state:
        st.session_state['df_hujan'] = pd.DataFrame({
            'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
            'CH (mm)': [282, 240, 248, 174, 103, 70, 87, 48, 58, 98, 163, 286],
            'ETo (mm/hari)': [4.0, 4.0, 5.0, 6.0, 6.0, 6.0, 6.0, 6.0, 5.0, 5.0, 4.0, 4.0],
            'Kc': [0.8]*12
        })
    if 'df_pipa' not in st.session_state:
        st.session_state['df_pipa'] = pd.DataFrame({
            'Segmen': ['S1', 'S2', 'S3'],
            'Panjang (m)': [5, 102, 43],
            'Diameter (mm)': [75, 75, 75],
            'C (Hazen)': [140, 140, 140],
            'Debit (L/s)': [1.96, 1.05, 0.50]
        })
    defaults = {
        'nama_proyek': "JIAT Lampung Timur", 'lokasi': "Desa Hargomulyo", 'tahun': "2025",
        'luas_ha': 2.0, 'perkolasi': 2.0, 'efisiensi': 65,
        'kedalaman_m': 95, 'head_statis_m': 63,
        'drawdown_izin_m': 10, 'radius_m': 0.15, 'safety_factor': 80,
        'tebal_akuifer_m': 20, 'k_perm': 4.32
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()

# ==========================================
# 2. SIDEBAR (INPUT & FILE MANAGER)
# ==========================================
with st.sidebar:
    st.title("📂 File Manager")
    
    clean_params = {}
    for key, value in st.session_state.items():
        if not isinstance(value, pd.DataFrame): 
            clean_params[key] = value

    current_data = {
        'params': clean_params,
        'hujan': st.session_state['df_hujan'].to_dict(orient='records'),
        'pipa': st.session_state['df_pipa'].to_dict(orient='records')
    }
    
    st.download_button(
        "💾 Simpan Proyek (Save)", json.dumps(current_data, indent=2), "proyek_jiat.json", "application/json",
        help="Simpan pekerjaan ke file JSON."
    )
    
    uploaded = st.file_uploader("📂 Buka Proyek (Open)", type=["json"])
    if uploaded:
        try:
            data = json.load(uploaded)
            for k, v in data['params'].items(): st.session_state[k] = v
            st.session_state['df_hujan'] = pd.DataFrame(data['hujan'])
            st.session_state['df_pipa'] = pd.DataFrame(data['pipa'])
            st.success("Data berhasil dimuat!")
        except: st.error("File rusak!")

    st.markdown("---")
    st.header("1. Input Parameter")
    
    st.session_state['nama_proyek'] = st.text_input("Nama Proyek", st.session_state['nama_proyek'], help="Nama pekerjaan.")
    st.session_state['lokasi'] = st.text_input("Lokasi", st.session_state['lokasi'])
    st.session_state['tahun'] = st.text_input("Tahun", st.session_state['tahun'])
    
    st.markdown("---")
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=st.session_state['luas_ha'], help="Luas lahan (Ha).")
    
    with st.expander("🌊 Faktor Kebutuhan", expanded=True):
        st.session_state['perkolasi'] = st.number_input("Perkolasi (mm)", value=st.session_state['perkolasi'], help="Kehilangan air (mm/hari).")
        st.session_state['efisiensi'] = st.number_input("Efisiensi (%)", value=st.session_state['efisiensi'], help="Efisiensi jaringan (%).")
    
    st.markdown("---")
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'], help="Beda tinggi (m).")
    
    with st.expander("⛰️ Faktor Geologi", expanded=True):
        st.session_state['safety_factor'] = st.number_input("Safety Factor (%)", value=st.session_state['safety_factor'], help="% Pengambilan aman.")
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal Akuifer (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("Permeabilitas K", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("Drawdown Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Jari-jari Sumur (m)", value=st.session_state['radius_m'])

# ==========================================
# 3. KONTEN UTAMA
# ==========================================
st.title(f"💧 {st.session_state['nama_proyek']}")
st.markdown(f"**Lokasi:** {st.session_state['lokasi']} | **Tahun:** {st.session_state['tahun']}")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT DATA", "💧 KEBUTUHAN AIR", "⚙️ PIPA & HIDROLIKA", "📊 HASIL & GRAFIK"])

# --- TAB 1: INPUT TABEL ---
with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("A. Data Hujan")
        st.data_editor(st.session_state['df_hujan'], key='editor_hujan', num_rows="dynamic", use_container_width=True, on_change=lambda: st.session_state.update({'df_hujan': st.session_state.editor_hujan}))
        with st.expander("ℹ️ Keterangan"): st.caption("Masukkan data hujan dan klimatologi.")
    with c2:
        st.subheader("B. Jaringan Pipa")
        st.data_editor(st.session_state['df_pipa'], key='editor_pipa', num_rows="dynamic", use_container_width=True, on_change=lambda: st.session_state.update({'df_pipa': st.session_state.editor_pipa}))
        with st.expander("ℹ️ Keterangan"): st.caption("Urutkan dari Sumur ke Lahan.")

# ==========================================
# 4. ENGINE HITUNGAN (GLOBAL) - FIX VARIABLE
# ==========================================
# 1. Demand
df_calc = st.session_state['df_hujan'].copy()
df_calc['Re (mm)'] = df_calc['CH (mm)'].apply(lambda x: (0.8 * x)/30 if x < 250 else (125 + 0.1*(x-250))/30)
df_calc['ETc (mm)'] = df_calc['ETo (mm/hari)'] * df_calc['Kc']
df_calc['NFR (mm)'] = (df_calc['ETc (mm)'] + st.session_state['perkolasi'] - df_calc['Re (mm)']).clip(lower=0)
eff = st.session_state['efisiensi'] / 100
df_calc['Q Req (L/s)'] = (df_calc['NFR (mm)'] * 0.1157 * st.session_state['luas_ha']) / eff

q_desain = df_calc['Q Req (L/s)'].max()
bln_puncak = df_calc.loc[df_calc['Q Req (L/s)'].idxmax(), 'Bulan']

# 2. Supply
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# 3. Pipa
df_pipa_res = st.session_state['df_pipa'].copy()
hf_total = 0
v_list, hf_list = [], []
for i, row in df_pipa_res.iterrows():
    L, Dm, Qm3, C = row['Panjang (m)'], row['Diameter (mm)']/1000, row['Debit (L/s)']/1000, row['C (Hazen)']
    Area = 0.25 * 3.14 * (Dm**2)
    V = Qm3/Area if Area > 0 else 0
    hf = 10.67 * L * (Qm3**1.852) / ((C**1.852)*(Dm**4.87)) if Qm3 > 0 else 0
    v_list.append(V); hf_list.append(hf); hf_total += hf

df_pipa_res['V (m/s)'] = v_list
df_pipa_res['Hf (m)'] = hf_list
head_total = st.session_state['head_statis_m'] + hf_total + (0.1 * hf_total)

# --- PERBAIKAN: Hitung daya_kw dulu baru daya_watt ---
daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70  # Daya Poros
daya_watt = (daya_kw / 0.85) * 1000                     # Daya Listrik

# ==========================================
# 5. OUTPUT
# ==========================================

# --- TAB 2: KEBUTUHAN ---
with tab2:
    st.subheader("Analisa Neraca Air")
    st.dataframe(df_calc.set_index('Bulan').style.format("{:.2f}"), use_container_width=True)
    st.info(f"Debit Puncak: **{q_desain:.2f} L/s** (Bulan {bln_puncak})")

# --- TAB 3: PIPA ---
with tab3:
    st.subheader("Analisa Hidrolika")
    st.dataframe(df_pipa_res.style.format({'V (m/s)': '{:.2f}', 'Hf (m)': '{:.3f}'}), use_container_width=True)
    
    st.markdown("### 🚦 Cek Kecepatan")
    aman = True
    for i, row in df_pipa_res.iterrows():
        v = row['V (m/s)']
        if v < 0.6: 
            st.warning(f"⚠️ {row['Segmen']} (V={v:.2f}): Terlalu Pelan (<0.6).")
            aman = False
        elif v > 2.0: 
            st.error(f"⛔ {row['Segmen']} (V={v:.2f}): Terlalu Cepat (>2.0).")
            aman = False
    if aman: st.success("✅ Kecepatan Aliran Pipa AMAN.")

# --- TAB 4: HASIL (LENGKAP) ---
with tab4:
    st.markdown("## LAPORAN HASIL PERENCANAAN")
    st.info("💡 Tekan **Ctrl + P** untuk Print.")
    
    # A. Grafik
    source = df_calc.copy()
    source['Limit Sumur'] = q_safe
    bar = alt.Chart(source).mark_bar(color='#29B5E8').encode(x='Bulan', y=alt.Y('Q Req (L/s)', title='Debit (L/s)'), tooltip=['Q Req (L/s)'])
    line = alt.Chart(source).mark_rule(color='red').encode(y='Limit Sumur', tooltip=['Limit Sumur'])
    st.altair_chart((bar+line).interactive(), use_container_width=True)
    st.caption("🟦 Balok: Kebutuhan | 🟥 Garis: Batas Aman Sumur")

    # B. Rangkuman
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div class="box-hasil" style="border-left:5px solid #2196F3">
        <b>1. SUPPLY (SUMUR)</b><br>Safe Yield: <b>{q_safe:.2f} L/s</b><br>(SF: {st.session_state['safety_factor']}%)</div>""", unsafe_allow_html=True)
    with c2:
        warna = "green" if q_safe >= q_desain else "red"
        status = "AMAN" if q_safe >= q_desain else "DEFISIT"
        st.markdown(f"""<div class="box-hasil" style="border-left:5px solid {warna}">
        <b>2. DEMAND (KEBUTUHAN)</b><br>Max: <b>{q_desain:.2f} L/s</b><br>Status: <b style="color:{warna}">{status}</b></div>""", unsafe_allow_html=True)
    
    # C. Rekomendasi
    st.markdown("### Rekomendasi Pompa")
    st.success(f"""
    ✅ **Spesifikasi:**
    - Debit (Q): **{q_desain:.2f} L/s**
    - Head (H): **{head_total:.2f} m**
    - Power: **{daya_kw:.2f} kW** ({daya_watt:.0f} W)
    """)
    with st.expander("Detail Head"):
        st.write(f"Statis: {st.session_state['head_statis_m']} m | Mayor: {hf_total:.2f} m | Minor: {hf_total*0.1:.2f} m")
