import streamlit as st
import pandas as pd
import math
import altair as alt
import numpy as np

st.set_page_config(page_title="JIAT Smart Studio", layout="wide", page_icon="💧")

# --- CSS KEREN UNTUK CARD ---
st.markdown("""
<style>
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
    .card-supply {
        padding: 20px; background-color: #ffffff; border-left: 5px solid #0099ff;
        border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;
    }
    .card-demand {
        padding: 20px; background-color: #ffffff; border-left: 5px solid #00cc00;
        border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;
    }
    .card-pump {
        padding: 20px; background-color: #e6fffa; border: 1px solid #b2f5ea;
        border-radius: 8px; margin-top: 20px;
    }
    .pump-header {font-size: 18px; font-weight: bold; color: #006666; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- INIT ---
def init_state():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])

    if 'df_neraca_24' not in st.session_state:
        st.session_state['df_neraca_24'] = pd.DataFrame({'Periode': periods, 'ETo (mm/hari)': [4.0]*24, 'Q Req (L/s/ha)': [0.0]*24})
    if 'df_pipa' not in st.session_state:
        st.session_state['df_pipa'] = pd.DataFrame({'Segmen': ['S1', 'S2', 'S3'], 'Panjang (m)': [5, 102, 43], 'Diameter (mm)': [75, 75, 75], 'C (Hazen)': [140, 140, 140], 'Debit (L/s)': [1.96, 1.05, 0.50]})
    
    defaults = {'nama_proyek': "-", 'lokasi': "-", 'luas_ha': 2.0, 'efisiensi': 65, 'head_statis_m': 63, 'safety_factor': 80, 'tebal_akuifer_m': 20, 'k_perm': 4.32, 'drawdown_izin_m': 10, 'radius_m': 0.15}
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val
init_state()

# --- SIDEBAR ---
with st.sidebar:
    st.title("🗂️ Info Proyek")
    st.info(f"**{st.session_state['nama_proyek']}**\n\nLokasi: {st.session_state['lokasi']}")
    st.caption("✏️ Edit nama di Halaman Utama (Home)")
    st.divider()
    st.header("📥 Link Data")
    
    if st.button("🌦️ Ambil Data ETo"):
        if 'data_eto_manual' in st.session_state:
            data = st.session_state['data_eto_manual']
            target = []
            if len(data) == 12: 
                for v in data: target.extend([v, v])
            elif len(data) == 24: target = data
            st.session_state['df_neraca_24']['ETo (mm/hari)'] = target
            st.success("✅ ETo Masuk!")
            st.rerun()
        else: st.error("Data kosong!")

    if st.button("🌾 Ambil Q Desain"):
        if 'data_nfr_manual' in st.session_state:
            raw = st.session_state['data_nfr_manual']
            if isinstance(raw, list) and len(raw) == 24:
                st.session_state['df_neraca_24']['Q Req (L/s/ha)'] = raw
                st.success("✅ Pola Tanam Masuk!")
            else: st.warning("Format data salah/flat.")
            st.rerun()
        else: st.error("Data kosong!")
    
    st.divider()
    st.header("⚙️ Parameter")
    st.session_state['luas_ha'] = st.number_input("Luas (Ha)", value=st.session_state['luas_ha'])
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
    with st.expander("Geologi"):
        st.session_state['safety_factor'] = st.number_input("SF (%)", value=st.session_state['safety_factor'])
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("K (m/hari)", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("DD Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Radius (m)", value=st.session_state['radius_m'])

# --- CALC ---
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

df_calc = st.session_state['df_neraca_24'].copy()
df_calc['Q Total (L/s)'] = df_calc['Q Req (L/s/ha)'] * st.session_state['luas_ha']
q_desain = df_calc['Q Total (L/s)'].max()

df_pipa = st.session_state['df_pipa'].copy()
hf_total, v_list, hf_list = 0, [], []
for i, r in df_pipa.iterrows():
    L, Dm, Qm3, C = r['Panjang (m)'], r['Diameter (mm)']/1000, r['Debit (L/s)']/1000, r['C (Hazen)']
    Area = 0.25 * 3.14 * (Dm**2)
    V = Qm3/Area if Area > 0 else 0
    hf = 10.67 * L * (Qm3**1.852) / ((C**1.852)*(Dm**4.87)) if Qm3 > 0 else 0
    v_list.append(V); hf_list.append(hf); hf_total += hf
df_pipa['V (m/s)'] = v_list; df_pipa['Hf (m)'] = hf_list
head_total = st.session_state['head_statis_m'] + hf_total*1.1
daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70
daya_watt = daya_kw / 0.85 * 1000

# --- VIEW ---
st.title(f"💧 {st.session_state['nama_proyek']}")
st.caption(f"Lokasi: {st.session_state['lokasi']}")

c1, c2 = st.columns(2)
with c1: st.markdown(f'<div class="{ "success-box" if "data_eto_manual" in st.session_state else "info-box" }">{"✅ Klimatologi Terhubung" if "data_eto_manual" in st.session_state else "ℹ️ Data ETo Manual"}</div>', unsafe_allow_html=True)
with c2: st.markdown(f'<div class="{ "success-box" if "data_nfr_manual" in st.session_state else "info-box" }">{"✅ Pola Tanam Terhubung" if "data_nfr_manual" in st.session_state else "ℹ️ Data NFR Manual"}</div>', unsafe_allow_html=True)

st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT", "📊 HASIL DEBIT", "⚙️ PIPA", "📑 LAPORAN"])

with tab1:
    c1, c2 = st.columns(2)
    with c1: st.subheader("A. Kebutuhan Air"); st.session_state['df_neraca_24'] = st.data_editor(st.session_state['df_neraca_24'], height=350, use_container_width=True)
    with c2: st.subheader("B. Jaringan Pipa"); st.session_state['df_pipa'] = st.data_editor(st.session_state['df_pipa'], height=350, use_container_width=True)

with tab2:
    # --- CHART & CARDS SEPERTI SCREENSHOT ---
    src = df_calc.copy()
    src['Limit'] = q_safe
    
    chart = alt.Chart(src).mark_bar(color='#29B5E8').encode(
        x=alt.X('Periode', axis=alt.Axis(labelAngle=-90)), 
        y='Q Total (L/s)',
        tooltip=['Periode', 'Q Total (L/s)']
    ) + alt.Chart(src).mark_rule(color='red', strokeDash=[5, 5]).encode(y='Limit')
    
    st.altair_chart(chart.interactive(), use_container_width=True)
    
    st.markdown(f"""
    <div style="display: flex; gap: 20px;">
        <div class="card-supply" style="flex: 1;">
            <h4>1. SUPPLY (SUMUR)</h4>
            <div>Safe Yield: <b>{q_safe:.2f} L/s</b></div>
            <small>(SF: {st.session_state['safety_factor']}%)</small>
        </div>
        <div class="card-demand" style="flex: 1;">
            <h4>2. DEMAND (KEBUTUHAN)</h4>
            <div>Max: <b>{q_desain:.2f} L/s</b></div>
            <div>Status: <b style="color: {'green' if q_safe >= q_desain else 'red'}">{'AMAN' if q_safe >= q_desain else 'DEFISIT'}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # REKOMENDASI POMPA (STYLE SCREENSHOT)
    st.markdown('<div class="pump-header">Rekomendasi Pompa</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="card-pump">
        <p>✅ <b>Spesifikasi:</b></p>
        <ul>
            <li>Debit (Q): <b>{q_desain:.2f} L/s</b></li>
            <li>Head (H): <b>{head_total:.2f} m</b></li>
            <li>Power: <b>{daya_kw:.2f} kW</b> ({daya_watt:.0f} W)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("v Detail Head"):
        st.write(f"Statis: {st.session_state['head_statis_m']} m | Mayor: {hf_total:.2f} m | Minor: {hf_total*0.1:.2f} m")

with tab3:
    st.subheader("Analisa Pipa")
    st.dataframe(df_pipa.style.format("{:.3f}", subset=df_pipa.select_dtypes(include=[np.number]).columns), use_container_width=True)
    for i, r in df_pipa.iterrows():
        if r['V (m/s)'] < 0.6: st.warning(f"⚠️ {r['Segmen']} Pelan")
        elif r['V (m/s)'] > 2.0: st.error(f"⛔ {r['Segmen']} Cepat")
        else: st.success(f"✅ {r['Segmen']} Aman")

with tab4:
    # --- TAB LAPORAN JUGA DISAMAKAN ---
    st.markdown("## LAPORAN HASIL"); st.caption("Tekan Ctrl+P untuk print PDF")
    
    # Copy layout tab 2
    st.altair_chart(chart, use_container_width=True)
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.info(f"**SUPPLY:** {q_safe:.2f} L/s")
    with col_b:
        if q_safe >= q_desain: st.success(f"**DEMAND:** {q_desain:.2f} L/s (AMAN)")
        else: st.error(f"**DEMAND:** {q_desain:.2f} L/s (DEFISIT)")
        
    st.success(f"""
    **Rekomendasi Pompa:**
    - Q = {q_desain:.2f} L/s
    - H = {head_total:.2f} m
    - P = {daya_kw:.2f} kW
    """)
