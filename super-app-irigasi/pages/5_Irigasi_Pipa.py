import streamlit as st
import pandas as pd
import math
import altair as alt
import json
import numpy as np

st.set_page_config(page_title="JIAT Smart Studio", layout="wide", page_icon="💧")

# --- CSS UI (LAYOUT PROFESIONAL) ---
st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="stHeader"] {display: none !important;}
        .no-print {display: none !important;}
        * {-webkit-print-color-adjust: exact !important; print-color-adjust: exact !important;}
    }
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
    
    /* BOX STYLE */
    .box-hasil {
        padding: 15px; 
        background-color: #f8f9fa; 
        border: 1px solid #ccc; 
        border-radius: 5px; 
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .box-header {
        font-size: 14px; font-weight: bold; color: #555; margin-bottom: 5px; text-transform: uppercase;
    }
    .box-value {
        font-size: 24px; font-weight: bold; color: #333;
    }
    .box-sub {
        font-size: 12px; color: #777;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. INISIALISASI DATA
# ==========================================
def init_state():
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])

    # Default Data Neraca
    if 'df_neraca_24' not in st.session_state:
        st.session_state['df_neraca_24'] = pd.DataFrame({
            'Periode': periods,
            'ETo (mm/hari)': [4.0]*24,
            'Q Req (L/s/ha)': [0.0]*24
        })

    # Default Data Pipa
    if 'df_pipa' not in st.session_state:
        st.session_state['df_pipa'] = pd.DataFrame({
            'Segmen': ['S1', 'S2', 'S3'],
            'Panjang (m)': [5, 102, 43],
            'Diameter (mm)': [75, 75, 75],
            'C (Hazen)': [140, 140, 140],
            'Debit (L/s)': [1.96, 1.05, 0.50]
        })

    # Parameter Teknis
    defaults = {
        'nama_proyek': "JIAT Lampung Timur", 'lokasi': "Desa Hargomulyo", 'tahun': "2025",
        'luas_ha': 2.0, 'efisiensi': 65, 'head_statis_m': 63, 'safety_factor': 80,
        'tebal_akuifer_m': 20, 'k_perm': 4.32, 'drawdown_izin_m': 10, 'radius_m': 0.15
    }
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val

init_state()

# ==========================================
# 2. SIDEBAR (LINK DATA)
# ==========================================
with st.sidebar:
    st.title("📂 Link Data")
    
    # --- TOMBOL 1: AMBIL ETo ---
    if st.button("🌦️ Ambil Data ETo"):
        if 'data_eto_manual' in st.session_state:
            data_eto = st.session_state['data_eto_manual']
            if len(data_eto) == 12: # 12 -> 24
                eto_24 = []
                for val in data_eto: eto_24.extend([val, val])
                st.session_state['df_neraca_24']['ETo (mm/hari)'] = eto_24
            elif len(data_eto) == 24:
                st.session_state['df_neraca_24']['ETo (mm/hari)'] = data_eto
            st.success("✅ ETo Masuk!")
            st.rerun()
        else:
            st.error("⚠️ Data Klimatologi belum dikirim!")

    # --- TOMBOL 2: AMBIL NFR ---
    if st.button("🌾 Ambil Q Desain"):
        if 'data_nfr_manual' in st.session_state:
            q_max = st.session_state['data_nfr_manual']
            st.session_state['df_neraca_24']['Q Req (L/s/ha)'] = [q_max] * 24
            st.success(f"✅ Q Desain ({q_max:.3f}) Masuk!")
            st.rerun()
        else:
            st.error("⚠️ Data Pola Tanam belum dikirim!")

    st.markdown("---")
    st.header("⚙️ Parameter")
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=st.session_state['luas_ha'])
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
    
    with st.expander("Faktor Geologi"):
        st.session_state['safety_factor'] = st.number_input("SF (%)", value=st.session_state['safety_factor'])
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("K (m/hari)", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("DD Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Radius (m)", value=st.session_state['radius_m'])

# ==========================================
# 3. GLOBAL CALCULATION
# ==========================================
# A. Supply (Geologi)
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# B. Demand (Neraca)
df_calc = st.session_state['df_neraca_24'].copy()
df_calc['Q Total (L/s)'] = df_calc['Q Req (L/s/ha)'] * st.session_state['luas_ha']
q_desain = df_calc['Q Total (L/s)'].max()
idx_puncak = df_calc['Q Total (L/s)'].idxmax()
bln_puncak = df_calc.loc[idx_puncak, 'Periode']

# C. Pipa (Head & Power)
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

# ==========================================
# 4. KONTEN UTAMA
# ==========================================
st.title(f"💧 {st.session_state['nama_proyek']}")
st.caption(f"Lokasi: {st.session_state['lokasi']} | Mode: 15 Harian (KP-01)")

# Status Link Data
c_stat1, c_stat2 = st.columns(2)
with c_stat1:
    if 'data_eto_manual' in st.session_state: st.success("✅ Data Klimatologi Terhubung")
    else: st.info("ℹ️ Menggunakan Data ETo Manual/Default")
with c_stat2:
    if 'data_nfr_manual' in st.session_state: st.success("✅ Data Pola Tanam Terhubung")
    else: st.info("ℹ️ Menggunakan Data NFR Manual/Default")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT DATA", "📊 HASIL DEBIT", "⚙️ PIPA & HIDROLIKA", "📑 LAPORAN"])

# --- TAB 1: INPUT DATA ---
with tab1:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("A. Kebutuhan Air (15 Harian)")
        st.info("💡 Input manual atau klik tombol 'Ambil Q Desain' di sidebar.")
        edited_neraca = st.data_editor(
            st.session_state['df_neraca_24'], height=350, use_container_width=True,
            column_config={"Q Req (L/s/ha)": st.column_config.NumberColumn(format="%.3f")}
        )
        st.session_state['df_neraca_24'] = edited_neraca
    with c2:
        st.subheader("B. Jaringan Pipa")
        st.info("💡 Edit diameter dan panjang pipa distribusi.")
        edited_pipa = st.data_editor(st.session_state['df_pipa'], height=350, use_container_width=True)
        st.session_state['df_pipa'] = edited_pipa

# --- TAB 2: HASIL DEBIT (FIX ERROR FORMATTING) ---
with tab2:
    st.subheader("Analisa Neraca Air & Kebutuhan")
    
    # 1. SCORECARD RINGKASAN
    col_sum1, col_sum2 = st.columns(2)
    with col_sum1:
        st.markdown(f"""
        <div class="box-hasil" style="border-left:5px solid #2196F3">
            <div class="box-header">1. Supply (Kapasitas Sumur)</div>
            <div class="box-value">{q_safe:.2f} L/s</div>
            <div class="box-sub">Safe Yield (SF: {st.session_state['safety_factor']}%)</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_sum2:
        warna_border = "#4CAF50" if q_safe >= q_desain else "#F44336"
        warna_text = "green" if q_safe >= q_desain else "red"
        status_text = "SURPLUS (AMAN)" if q_safe >= q_desain else "DEFISIT (KURANG)"
        
        st.markdown(f"""
        <div class="box-hasil" style="border-left:5px solid {warna_border}">
            <div class="box-header">2. Demand (Kebutuhan Max)</div>
            <div class="box-value">{q_desain:.2f} L/s</div>
            <div class="box-sub" style="color:{warna_text}; font-weight:bold;">Status: {status_text}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. GRAFIK INTERAKTIF
    st.write("#### 📈 Grafik Ketersediaan vs Kebutuhan")
    source = df_calc.copy()
    source['Limit Sumur'] = q_safe
    
    bar = alt.Chart(source).mark_bar(color='#29B5E8').encode(
        x=alt.X('Periode', sort=None, axis=alt.Axis(labelAngle=-90)), 
        y=alt.Y('Q Total (L/s)', title='Debit (L/s)'),
        tooltip=['Periode', 'Q Total (L/s)']
    )
    line = alt.Chart(source).mark_rule(color='red', strokeWidth=2).encode(
        y='Limit Sumur', tooltip=['Limit Sumur']
    )
    st.altair_chart((bar+line).interactive(), use_container_width=True)
    st.caption("Garis Merah = Batas Aman Pengambilan Air (Safe Yield).")

    # 3. TABEL DATA DETAIL (FIX: Filter kolom numeric saja)
    st.write("#### 📋 Data Detail Per Periode")
    
    # [FIX ERROR DISINI] Hanya format kolom angka
    numeric_cols_calc = df_calc.select_dtypes(include=[np.number]).columns
    
    st.dataframe(
        df_calc.style.format("{:.3f}", subset=numeric_cols_calc), 
        use_container_width=True
    )

# --- TAB 3: PIPA & HIDROLIKA ---
with tab3:
    st.subheader("Analisa Hidrolika Pipa")
    
    numeric_cols = df_pipa_res.select_dtypes(include=[np.number]).columns
    st.dataframe(df_pipa_res.style.format("{:.3f}", subset=numeric_cols), use_container_width=True)
    
    # Cek Kecepatan
    col_cek = st.columns(3)
    for i, r in df_pipa_res.iterrows():
        if r['V (m/s)'] < 0.6: st.warning(f"⚠️ {r['Segmen']} Pelan ({r['V (m/s)']})")
        elif r['V (m/s)'] > 2.0: st.error(f"⛔ {r['Segmen']} Cepat ({r['V (m/s)']})")
        else: st.success(f"✅ {r['Segmen']} OK")

# --- TAB 4: LAPORAN ---
with tab4:
    st.markdown("## LAPORAN HASIL PERENCANAAN")
    st.info("💡 Tekan **Ctrl + P** untuk Print.")
    
    # Layout sama persis dengan Tab 2 tapi format laporan
    source = df_calc.copy()
    source['Limit Sumur'] = q_safe
    
    bar = alt.Chart(source).mark_bar(color='#29B5E8').encode(
        x=alt.X('Periode', sort=None, axis=alt.Axis(labelAngle=-90)), 
        y=alt.Y('Q Total (L/s)', title='Debit (L/s)')
    )
    line = alt.Chart(source).mark_rule(color='red', strokeWidth=2).encode(y='Limit Sumur')
    st.altair_chart((bar+line).interactive(), use_container_width=True)
    
    st.markdown("""<small><span style='color:#29B5E8'>■</span> Kebutuhan &nbsp; <span style='color:red'>▬</span> Safe Yield</small><br><br>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="box-hasil" style="border-left:5px solid #2196F3">
            <b>SUPPLY (SUMUR)</b><br>
            Safe Yield: <b>{q_safe:.2f} L/s</b><br>
            (SF: {st.session_state['safety_factor']}%)
        </div>
        """, unsafe_allow_html=True)
    with c2:
        warna = "#4CAF50" if q_safe >= q_desain else "#F44336"
        status = "AMAN" if q_safe >= q_desain else "DEFISIT"
        st.markdown(f"""
        <div class="box-hasil" style="border-left:5px solid {warna}">
            <b>DEMAND (KEBUTUHAN)</b><br>
            Max: <b>{q_desain:.2f} L/s</b><br>
            Status: <b style="color:{warna}">{status}</b>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Rekomendasi Pompa")
    st.success(f"""
    ✅ **Spesifikasi:**
    * **Debit (Q):** {q_desain:.2f} L/s
    * **Head Total (H):** {head_total:.2f} m
    * **Power:** {daya_kw:.2f} kW ({daya_watt:.0f} W)
    """)
    
    with st.expander("Detail Head"):
        st.write(f"Statis: {st.session_state['head_statis_m']} m | Mayor: {hf_total:.3f} m | Minor: {hf_total*0.1:.3f} m")
