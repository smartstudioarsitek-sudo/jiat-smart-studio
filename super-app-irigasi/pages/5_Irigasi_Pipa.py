import streamlit as st
import pandas as pd
import math
import altair as alt
import json
import numpy as np

st.set_page_config(page_title="JIAT Smart Studio", layout="wide", page_icon="💧")

# --- CSS ---
st.markdown("""
<style>
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
    .box-hasil {padding: 15px; background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px; margin-bottom: 15px;}
    .box-header {font-size: 14px; font-weight: bold; color: #555; margin-bottom: 5px; text-transform: uppercase;}
    .box-value {font-size: 24px; font-weight: bold; color: #333;}
    .box-sub {font-size: 12px; color: #777;}
    .success-box {padding: 10px; background-color: #d1e7dd; color: #0f5132; border-radius: 5px;}
    .info-box {padding: 10px; background-color: #cff4fc; color: #055160; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# --- INIT ---
def init_state():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])

    if 'df_neraca_24' not in st.session_state:
        st.session_state['df_neraca_24'] = pd.DataFrame({
            'Periode': periods,
            'ETo (mm/hari)': [4.0]*24,
            'Q Req (L/s/ha)': [0.0]*24
        })

    if 'df_pipa' not in st.session_state:
        st.session_state['df_pipa'] = pd.DataFrame({
            'Segmen': ['S1', 'S2', 'S3'],
            'Panjang (m)': [5, 102, 43],
            'Diameter (mm)': [75, 75, 75],
            'C (Hazen)': [140, 140, 140],
            'Debit (L/s)': [1.96, 1.05, 0.50]
        })

    # Cek apakah nama proyek sudah ada? Jika belum, pakai default
    if 'nama_proyek' not in st.session_state: st.session_state['nama_proyek'] = "JIAT Lampung Timur"
    if 'lokasi' not in st.session_state: st.session_state['lokasi'] = "Desa Hargomulyo"
    
    defaults = {
        'tahun': "2025",
        'luas_ha': 2.0, 'efisiensi': 65, 'head_statis_m': 63, 'safety_factor': 80,
        'tebal_akuifer_m': 20, 'k_perm': 4.32, 'drawdown_izin_m': 10, 'radius_m': 0.15
    }
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val

init_state()

# --- SIDEBAR (UPDATE FITUR EDIT NAMA) ---
with st.sidebar:
    st.title("🗂️ Info Proyek")
    
    # Input Nama Proyek (Realtime Update)
    st.session_state['nama_proyek'] = st.text_input("Nama Proyek:", value=st.session_state['nama_proyek'])
    st.session_state['lokasi'] = st.text_input("Lokasi:", value=st.session_state['lokasi'])
    
    st.divider()
    
    st.header("📥 Link Data")
    
    # 1. AMBIL ETo
    if st.button("🌦️ Ambil Data ETo"):
        if 'data_eto_manual' in st.session_state:
            data_eto = st.session_state['data_eto_manual']
            if len(data_eto) == 12: 
                eto_24 = []
                for val in data_eto: eto_24.extend([val, val])
                st.session_state['df_neraca_24']['ETo (mm/hari)'] = eto_24
            elif len(data_eto) == 24:
                st.session_state['df_neraca_24']['ETo (mm/hari)'] = data_eto
            st.success("✅ ETo Masuk!")
            st.rerun()
        else: st.error("⚠️ Data Klimatologi kosong!")

    # 2. AMBIL Q DESAIN
    if st.button("🌾 Ambil Q Desain"):
        if 'data_nfr_manual' in st.session_state:
            raw_data = st.session_state['data_nfr_manual']
            if isinstance(raw_data, list) and len(raw_data) == 24:
                st.session_state['df_neraca_24']['Q Req (L/s/ha)'] = raw_data
                st.success("✅ Q Pola Tanam (Full Pattern) Masuk!")
            else:
                try:
                    val = float(raw_data)
                    st.session_state['df_neraca_24']['Q Req (L/s/ha)'] = [val] * 24
                    st.warning("⚠️ Data hanya nilai Max (Flat).")
                except:
                    st.error("Format data salah.")
            st.rerun()
        else: st.error("⚠️ Data Pola Tanam kosong!")

    st.markdown("---")
    st.header("⚙️ Parameter")
    st.session_state['luas_ha'] = st.number_input("Luas (Ha)", value=st.session_state['luas_ha'])
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
    
    with st.expander("Faktor Geologi"):
        st.session_state['safety_factor'] = st.number_input("SF (%)", value=st.session_state['safety_factor'])
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("K (m/hari)", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("DD Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Radius (m)", value=st.session_state['radius_m'])

# --- CALCULATION ---
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

df_calc = st.session_state['df_neraca_24'].copy()
df_calc['Q Total (L/s)'] = df_calc['Q Req (L/s/ha)'] * st.session_state['luas_ha']
q_desain = df_calc['Q Total (L/s)'].max()

df_pipa_res = st.session_state['df_pipa'].copy()
hf_total = 0
v_list, hf_list = [], []
for i, row in df_pipa_res.iterrows():
    L, Dm, Qm3, C = row['Panjang (m)'], row['Diameter (mm)']/1000, row['Debit (L/s)']/1000, row['C (Hazen)']
    Area = 0.25 * 3.14 * (Dm**2)
    V = Qm3/Area if Area > 0 else 0
    hf = 10.67 * L * (Qm3**1.852) / ((C**1.852)*(Dm**4.87)) if Qm3 > 0 else 0
    v_list.append(V); hf_list.append(hf); hf_total += hf
df_pipa_res['V (m/s)'] = v_list; df_pipa_res['Hf (m)'] = hf_list
head_total = st.session_state['head_statis_m'] + hf_total + (0.1 * hf_total)
daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70  
daya_watt = (daya_kw / 0.85) * 1000

# --- UI CONTENT ---
# Judul Mengambil dari Session State (Yang diinput di Sidebar)
st.title(f"💧 {st.session_state['nama_proyek']}")
st.caption(f"Lokasi: {st.session_state['lokasi']} | Mode: 15 Harian")

c1, c2 = st.columns(2)
with c1:
    if 'data_eto_manual' in st.session_state: st.markdown('<div class="success-box">✅ Klimatologi Terhubung</div>', unsafe_allow_html=True)
    else: st.markdown('<div class="info-box">ℹ️ Data ETo Manual</div>', unsafe_allow_html=True)
with c2:
    if 'data_nfr_manual' in st.session_state: st.markdown('<div class="success-box">✅ Pola Tanam Terhubung</div>', unsafe_allow_html=True)
    else: st.markdown('<div class="info-box">ℹ️ Data NFR Manual</div>', unsafe_allow_html=True)

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT DATA", "📊 HASIL DEBIT", "⚙️ PIPA & HIDROLIKA", "📑 LAPORAN"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("A. Kebutuhan Air")
        edited_neraca = st.data_editor(st.session_state['df_neraca_24'], height=350, use_container_width=True, column_config={"Q Req (L/s/ha)": st.column_config.NumberColumn(format="%.3f")})
        st.session_state['df_neraca_24'] = edited_neraca
    with c2:
        st.subheader("B. Jaringan Pipa")
        edited_pipa = st.data_editor(st.session_state['df_pipa'], height=350, use_container_width=True)
        st.session_state['df_pipa'] = edited_pipa

with tab2:
    st.subheader("Analisa Neraca Air")
    c1, c2 = st.columns(2)
    with c1: st.markdown(f'<div class="box-hasil"><div class="box-header">Supply</div><div class="box-value">{q_safe:.2f} L/s</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="box-hasil"><div class="box-header">Demand Max</div><div class="box-value">{q_desain:.2f} L/s</div></div>', unsafe_allow_html=True)
    
    source = df_calc.copy()
    source['Limit'] = q_safe
    bar = alt.Chart(source).mark_bar(color='#29B5E8').encode(x='Periode', y='Q Total (L/s)', tooltip=['Periode', 'Q Total (L/s)'])
    line = alt.Chart(source).mark_rule(color='red').encode(y='Limit')
    st.altair_chart((bar+line).interactive(), use_container_width=True)
    
    num_cols = df_calc.select_dtypes(include=[np.number]).columns
    st.dataframe(df_calc.style.format("{:.3f}", subset=num_cols), use_container_width=True)

with tab3:
    st.subheader("Analisa Hidrolika")
    num_cols = df_pipa_res.select_dtypes(include=[np.number]).columns
    st.dataframe(df_pipa_res.style.format("{:.3f}", subset=num_cols), use_container_width=True)
    col = st.columns(3)
    for i, r in df_pipa_res.iterrows():
        if r['V (m/s)'] < 0.6: st.warning(f"⚠️ {r['Segmen']} Pelan")
        elif r['V (m/s)'] > 2.0: st.error(f"⛔ {r['Segmen']} Cepat")
        else: st.success(f"✅ {r['Segmen']} Aman")

with tab4:
    st.markdown("## LAPORAN HASIL")
    import streamlit.components.v1 as components
    components.html("""<button onclick="window.print()" style="background:blue;color:white;border:none;padding:5px 10px;">Print PDF</button>""", height=40)
    
    source = df_calc.copy()
    source['Limit'] = q_safe
    bar = alt.Chart(source).mark_bar(color='#29B5E8').encode(x='Periode', y='Q Total (L/s)')
    line = alt.Chart(source).mark_rule(color='red').encode(y='Limit')
    st.altair_chart((bar+line).interactive(), use_container_width=True)
    
    c1, c2 = st.columns(2)
    with c1: st.info(f"**Supply:** {q_safe:.2f} L/s")
    with c2: 
        if q_safe >= q_desain: st.success(f"**Demand:** {q_desain:.2f} L/s (AMAN)")
        else: st.error(f"**Demand:** {q_desain:.2f} L/s (DEFISIT)")
    
    st.success(f"**Rekomendasi Pompa:** Q={q_desain:.2f} L/s, H={head_total:.2f} m, P={daya_kw:.2f} kW")
# ==========================================
# 2. SIDEBAR (HANYA LINK DATA)
# ==========================================
with st.sidebar:
    # TAMPILKAN INFO SAJA (Bukan Input)
    st.title("🗂️ Info Proyek")
    st.info(f"""
    **Proyek:** {st.session_state.get('nama_proyek', '-')}
    **Lokasi:** {st.session_state.get('lokasi', '-')}
    """)
    st.caption("✏️ Edit nama proyek di Halaman Utama (Home)")
    
    st.divider()
    
    st.header("📥 Link Data")
    # ... (Lanjutkan tombol Ambil Data ETo & Q Desain seperti biasa) ...
