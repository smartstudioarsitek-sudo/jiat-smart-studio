import streamlit as st
import pandas as pd
import math
import altair as alt
import json
import numpy as np # Tambahkan numpy untuk deteksi tipe data

st.set_page_config(page_title="JIAT Smart Studio", layout="wide", page_icon="💧")

# --- CSS ---
st.markdown("""
<style>
    .stButton button {border: 2px solid #007bff; font-weight: bold;}
    .box-hasil {padding: 15px; background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. INISIALISASI (MANUAL MODE)
# ==========================================
def init_state():
    # Struktur 24 Periode (Jan-1 s/d Des-2)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months: periods.extend([f"{m}-1", f"{m}-2"])

    # Default Data (Kosong/Dummy)
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
# 2. SIDEBAR (TOMBOL AMBIL DATA)
# ==========================================
with st.sidebar:
    st.header("📥 Ambil Data (Receive)")
    st.caption("Klik tombol di bawah untuk mengambil data yang dikirim dari modul lain.")
    
    # --- TOMBOL 1: AMBIL ETo ---
    if st.button("🌦️ Ambil Data ETo (Klimatologi)"):
        if 'data_eto_manual' in st.session_state:
            data_eto = st.session_state['data_eto_manual']
            
            # Konversi Bulanan (12) -> Periode (24)
            if len(data_eto) == 12:
                eto_24 = []
                for val in data_eto: eto_24.extend([val, val])
                st.session_state['df_neraca_24']['ETo (mm/hari)'] = eto_24
                st.success("✅ ETo Masuk!")
                st.rerun()
            elif len(data_eto) == 24:
                st.session_state['df_neraca_24']['ETo (mm/hari)'] = data_eto
                st.success("✅ ETo Masuk!")
                st.rerun()
        else:
            st.error("⚠️ Data Klimatologi belum dikirim! (Klik 'Kirim' di Page 1 dulu)")

    # --- TOMBOL 2: AMBIL NFR ---
    if st.button("🌾 Ambil Q Desain (Pola Tanam)"):
        if 'data_nfr_manual' in st.session_state:
            q_max = st.session_state['data_nfr_manual']
            # Isi kolom Q Req dengan nilai Max (Desain Aman)
            st.session_state['df_neraca_24']['Q Req (L/s/ha)'] = [q_max] * 24
            st.success(f"✅ Q Desain ({q_max:.3f}) Masuk!")
            st.rerun()
        else:
            st.error("⚠️ Data Pola Tanam belum dikirim! (Klik 'Kirim' di Page 2 dulu)")

    st.markdown("---")
    st.header("⚙️ Parameter")
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=st.session_state['luas_ha'])
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
    
    with st.expander("Faktor Geologi"):
        st.session_state['safety_factor'] = st.number_input("Safety Factor (%)", value=st.session_state['safety_factor'])
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal Akuifer (m)", value=st.session_state['tebal_akuifer_m'])
        st.session_state['k_perm'] = st.number_input("Permeabilitas K", value=st.session_state['k_perm'])
        st.session_state['drawdown_izin_m'] = st.number_input("Drawdown Izin (m)", value=st.session_state['drawdown_izin_m'])
        st.session_state['radius_m'] = st.number_input("Jari-jari Sumur (m)", value=st.session_state['radius_m'])

# ==========================================
# 3. KONTEN UTAMA
# ==========================================
st.title(f"💧 {st.session_state['nama_proyek']}")
st.caption(f"Lokasi: {st.session_state['lokasi']} | Mode: 15 Harian (KP-01)")

# --- STATUS DATA ---
if 'data_eto_manual' in st.session_state:
    st.info("💡 Info: Data Klimatologi tersedia di memori. Klik tombol di sidebar untuk mengambil.")
else:
    st.warning("⚠️ Info: Data Klimatologi belum dikirim dari Page 1.")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT & NERACA", "💧 HASIL DEBIT", "⚙️ PIPA & HIDROLIKA", "📊 LAPORAN"])

# --- ENGINE SUPPLY ---
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# --- TAB 1: INPUT ---
with tab1:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("A. Kebutuhan Air")
        # Tabel 15 Harian
        edited = st.data_editor(
            st.session_state['df_neraca_24'], 
            height=400, 
            use_container_width=True,
            column_config={"Q Req (L/s/ha)": st.column_config.NumberColumn(format="%.3f")}
        )
        st.session_state['df_neraca_24'] = edited
        
        # Hitung Total
        df_calc = edited.copy()
        df_calc['Q Total (L/s)'] = df_calc['Q Req (L/s/ha)'] * st.session_state['luas_ha']
        q_desain = df_calc['Q Total (L/s)'].max()
        idx_puncak = df_calc['Q Total (L/s)'].idxmax()
        bln_puncak = df_calc.loc[idx_puncak, 'Periode']
        
    with c2:
        st.markdown(f"""
        <div class="box-hasil">
            <b>Debit Sumur (Q Safe):</b><br>
            <span style="font-size:24px; color:blue;">{q_safe:.2f} L/s</span>
        </div>
        """, unsafe_allow_html=True)
        if q_safe >= q_desain:
            st.success(f"✅ Surplus: {q_safe - q_desain:.2f} L/s")
        else:
            st.error(f"⛔ Defisit: {q_desain - q_safe:.2f} L/s")

# --- TAB 2: GRAFIK ---
with tab2:
    source = df_calc.copy()
    source['Limit'] = q_safe
    bar = alt.Chart(source).mark_bar().encode(x='Periode', y='Q Total (L/s)', tooltip=['Periode', 'Q Total (L/s)'])
    rule = alt.Chart(source).mark_rule(color='red').encode(y='Limit')
    st.altair_chart((bar+rule).interactive(), use_container_width=True)

# --- TAB 3: PIPA ---
with tab3:
    st.subheader("B. Desain Pipa")
    st.data_editor(st.session_state['df_pipa'], key='ed_pipa', num_rows="dynamic", use_container_width=True, on_change=lambda: st.session_state.update({'df_pipa': st.session_state.ed_pipa}))
    
    # Engine Pipa
    df_res = st.session_state['df_pipa'].copy()
    hf_total = 0
    v_list, hf_list = [], []
    for i, row in df_res.iterrows():
        L, Dm, Qm3, C = row['Panjang (m)'], row['Diameter (mm)']/1000, row['Debit (L/s)']/1000, row['C (Hazen)']
        Area = 0.25 * 3.14 * (Dm**2)
        V = Qm3/Area if Area > 0 else 0
        hf = 10.67 * L * (Qm3**1.852) / ((C**1.852)*(Dm**4.87)) if Qm3 > 0 else 0
        v_list.append(V); hf_list.append(hf); hf_total += hf
    
    df_res['V (m/s)'] = v_list; df_res['Hf (m)'] = hf_list
    head_total = st.session_state['head_statis_m'] + hf_total + (0.1 * hf_total)
    daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70  
    
    # --- [FIX CRASH ERROR] ---
    # Filter hanya kolom ANGKA untuk diformat desimal
    numeric_cols = df_res.select_dtypes(include=[np.number]).columns
    
    st.dataframe(
        df_res.style.format("{:.3f}", subset=numeric_cols), # <--- PERBAIKAN DI SINI
        use_container_width=True
    )
    
    # Cek V
    aman = True
    for i, r in df_res.iterrows():
        if r['V (m/s)'] < 0.6: st.warning(f"⚠️ {r['Segmen']} Pelan"); aman=False
        if r['V (m/s)'] > 2.0: st.error(f"⛔ {r['Segmen']} Cepat"); aman=False
    if aman: st.success("✅ Kecepatan Aman")

# --- TAB 4: LAPORAN ---
with tab4:
    st.markdown("## LAPORAN JIAT")
    import streamlit.components.v1 as components
    components.html("""<button onclick="window.print()" style="background:blue;color:white;">Cetak PDF</button>""", height=40)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Q Max", f"{q_desain:.2f} L/s", bln_puncak)
    with c2: st.metric("Head Total", f"{head_total:.2f} m")
    with c3: st.metric("Power", f"{daya_kw:.2f} kW")
