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
    .status-box {padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em;}
    .status-ok {background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;}
    .status-warn {background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. FUNGSI UTILITIES (ANTI-ERROR)
# ==========================================
def safe_float(val):
    """Memaksa konversi ke float yang aman."""
    try:
        return float(val)
    except:
        return 0.0

def load_external_data():
    """Mencoba menarik data dari Session State Modul Lain."""
    status_msg = []
    
    # 1. Tarik ETo (Klimatologi)
    if 'data_eto_transfer' in st.session_state:
        eto_data = st.session_state['data_eto_transfer']
        if len(eto_data) == 12:
            st.session_state['df_hujan']['ETo (mm/hari)'] = [safe_float(x) for x in eto_data]
            status_msg.append("✅ ETo (Klimatologi)")
        else:
            status_msg.append("⚠️ ETo (Jumlah data tidak 12 bulan)")
    else:
        status_msg.append("❌ ETo (Belum ada data)")

    # 2. Tarik Hujan (FJ Mock)
    if 'df_mock' in st.session_state:
        try:
            # Ambil kolom hujan, pastikan urutannya benar
            hujan_data = st.session_state['df_mock']['Curah Hujan (mm)'].tolist()
            if len(hujan_data) == 12:
                st.session_state['df_hujan']['CH (mm)'] = [safe_float(x) for x in hujan_data]
                status_msg.append("✅ Hujan (FJ Mock)")
            else:
                status_msg.append("⚠️ Hujan (Jumlah data tidak 12 bulan)")
        except:
            status_msg.append("❌ Hujan (Format salah)")
    else:
        status_msg.append("❌ Hujan (Belum ada data)")
        
    return " | ".join(status_msg)

# ==========================================
# 3. INISIALISASI STATE
# ==========================================
def init_state():
    if 'df_hujan' not in st.session_state:
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
        st.session_state['df_hujan'] = pd.DataFrame({
            'Bulan': months,
            'CH (mm)': [0.0]*12,
            'ETo (mm/hari)': [0.0]*12,
            'Kc': [1.0, 1.0, 1.0, 0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0]
        })

    # Coba tarik data saat inisialisasi
    st.session_state['link_status_log'] = load_external_data()

    if 'df_pipa' not in st.session_state:
        st.session_state['df_pipa'] = pd.DataFrame({
            'Segmen': ['Jalur Utama', 'Sub-S1', 'Sub-S2'],
            'Panjang (m)': [500.0, 200.0, 150.0],
            'Diameter (mm)': [90.0, 63.0, 63.0],
            'C (Hazen)': [150, 150, 150],
            'Debit (L/s)': [5.0, 2.5, 2.5]
        })
    
    defaults = {
        'nama_proyek': "JIAT Lampung Timur", 'lokasi': "Desa Hargomulyo", 'tahun': "2025",
        'luas_ha': 5.0, 'perkolasi': 2.0, 'efisiensi': 80,
        'head_statis_m': 25.0, 'safety_factor': 80,
        'tebal_akuifer_m': 20.0, 'k_perm': 4.32, 
        'drawdown_izin_m': 10.0, 'radius_m': 0.15
    }
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val

init_state()

# ==========================================
# 4. SIDEBAR
# ==========================================
with st.sidebar:
    st.title("📂 File Manager")
    
    # Tombol Paksa Update Data
    if st.button("🔄 Tarik Data Terbaru", help="Klik jika data Hujan/ETo masih 0"):
        st.session_state['link_status_log'] = load_external_data()
        st.toast("Mencoba menarik data dari modul lain...", icon="🔄")
    
    # Status Koneksi
    st.caption("Status Koneksi Data:")
    st.info(st.session_state.get('link_status_log', '-'))

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
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=float(st.session_state['luas_ha']))
    
    with st.expander("⚙️ Faktor Kebutuhan Air"):
        st.session_state['perkolasi'] = st.number_input("Perkolasi (mm/hari)", value=float(st.session_state['perkolasi']))
        st.session_state['efisiensi'] = st.number_input("Efisiensi Irigasi (%)", value=float(st.session_state['efisiensi']))

    st.markdown("---")
    with st.expander("⛰️ Parameter Sumur (Geologi)"):
        st.session_state['tebal_akuifer_m'] = st.number_input("Tebal Akuifer (m)", value=float(st.session_state['tebal_akuifer_m']))
        st.session_state['k_perm'] = st.number_input("Permeabilitas K (m/hari)", value=float(st.session_state['k_perm']))
        st.session_state['drawdown_izin_m'] = st.number_input("Drawdown Izin (m)", value=float(st.session_state['drawdown_izin_m']))
        st.session_state['radius_m'] = st.number_input("Jari-jari Sumur (m)", value=float(st.session_state['radius_m']))
        st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=float(st.session_state['head_statis_m']))
        st.session_state['safety_factor'] = st.number_input("Safety Factor (%)", value=float(st.session_state['safety_factor']))

# ==========================================
# 5. ENGINE HITUNGAN
# ==========================================
# A. Supply
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# B. Demand (Pastikan semua tipe data Float untuk menghindari ArrowError)
df_calc = st.session_state['df_hujan'].copy()
num_cols = ['CH (mm)', 'ETo (mm/hari)', 'Kc']
# Konversi paksa ke numeric
for c in num_cols:
    df_calc[c] = pd.to_numeric(df_calc[c], errors='coerce').fillna(0.0)

# Hitungan
df_calc['Re (mm)'] = df_calc['CH (mm)'].apply(lambda x: (0.8 * x)/30 if x < 250 else (125 + 0.1*(x-250))/30)
df_calc['ETc (mm)'] = df_calc['ETo (mm/hari)'] * df_calc['Kc']
perkolasi = st.session_state['perkolasi']
df_calc['NFR (mm)'] = (df_calc['ETc (mm)'] + perkolasi - df_calc['Re (mm)']).clip(lower=0)

eff_dec = st.session_state['efisiensi'] / 100
# Rumus: Q(l/s) = (NFR * Ha * 10000) / (Eff * 24*3600) -> 0.1157 adalah faktor konversi mm/hari/ha ke l/s
df_calc['Q Req (L/s)'] = (df_calc['NFR (mm)'] * 0.1157 * st.session_state['luas_ha']) / eff_dec

q_desain = df_calc['Q Req (L/s)'].max()
try:
    idx_max = df_calc['Q Req (L/s)'].idxmax()
    bln_max = df_calc.loc[idx_max, 'Bulan']
except:
    bln_max = "-"

# ==========================================
# 6. TAMPILAN TABS
# ==========================================
st.title(f"💧 {st.session_state['nama_proyek']}")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT DATA", "💧 KEBUTUHAN AIR", "⚙️ PIPA & HIDROLIKA", "📊 HASIL & GRAFIK"])

# --- TAB 1: INPUT ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("A. Data Hujan & Klimatologi")
        
        # Cek Data Kosong
        sum_ch = df_calc['CH (mm)'].sum()
        sum_eto = df_calc['ETo (mm/hari)'].sum()
        
        if sum_ch == 0 or sum_eto == 0:
            st.warning("""
            ⚠️ **Data Masih Kosong (0)**
            Pastikan Anda sudah menjalankan:
            1. **Page Klimatologi** (Klik 'Simpan' di sana)
            2. **Page FJ Mock** (Klik 'Simpan' di sana)
            Lalu klik tombol **'🔄 Tarik Data Terbaru'** di Sidebar kiri.
            """)
        else:
            st.success("✅ Data Hujan & ETo berhasil ditarik otomatis!")

        st.data_editor(st.session_state['df_hujan'], key='editor_hujan', num_rows="dynamic", use_container_width=True,
                       on_change=lambda: st.session_state.update({'df_hujan': st.session_state.editor_hujan}))
    with col2:
        st.subheader("B. Jaringan Pipa")
        st.data_editor(st.session_state['df_pipa'], key='editor_pipa', num_rows="dynamic", use_container_width=True,
                       on_change=lambda: st.session_state.update({'df_pipa': st.session_state.editor_pipa}))

# --- TAB 2: NERACA ---
with tab2:
    st.subheader("Analisa Neraca Air")
    
    # Format Tabel (Pastikan kolom Bulan tidak ikut diformat float)
    display_cols = ['CH (mm)', 'ETo (mm/hari)', 'Kc', 'Re (mm)', 'ETc (mm)', 'NFR (mm)', 'Q Req (L/s)']
    
    # Trik Anti-ArrowError: Set index sebelum style, dan format spesifik
    df_show = df_calc.set_index('Bulan')
    
    st.dataframe(
        df_show.style.format("{:.2f}", subset=display_cols)
               .highlight_max(subset=['Q Req (L/s)'], color='#cce5ff', axis=0),
        use_container_width=True
    )
    
    st.info(f"👉 **Debit Puncak:** {q_desain:.2f} L/s pada bulan **{bln_max}**")

# --- TAB 3: PIPA ---
with tab3:
    st.subheader("Perhitungan Hidrolis Pipa")
    
    # Hitung Pipa
    df_pipa_res = st.session_state['df_pipa'].copy()
    
    # Konversi ke numerik
    for c in ['Panjang (m)', 'Diameter (mm)', 'Debit (L/s)', 'C (Hazen)']:
        df_pipa_res[c] = pd.to_numeric(df_pipa_res[c], errors='coerce').fillna(0.0)

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
            V, Hf = 0.0, 0.0
            
        v_list.append(V)
        hf_list.append(Hf)
        hf_total += Hf

    df_pipa_res['V (m/s)'] = v_list
    df_pipa_res['Hf (m)'] = hf_list

    st.dataframe(df_pipa_res.style.format({
        'Panjang (m)': '{:.1f}', 'Diameter (mm)': '{:.0f}', 'Debit (L/s)': '{:.2f}',
        'V (m/s)': '{:.2f}', 'Hf (m)': '{:.3f}'
    }), use_container_width=True)
    
    # Cek Kecepatan
    st.write("#### 🚦 Cek Kecepatan")
    cols = st.columns(3)
    idx_col = 0
    for i, row in df_pipa_res.iterrows():
        v = row['V (m/s)']
        seg = row['Segmen']
        if v < 0.3: st.warning(f"⚠️ {seg}: Endapan (V={v:.2f})")
        elif v > 2.5: st.error(f"⛔ {seg}: Erosi (V={v:.2f})")
        else: st.success(f"✅ {seg}: Aman (V={v:.2f})")

# --- TAB 4: HASIL ---
with tab4:
    head_total = st.session_state['head_statis_m'] + hf_total + (0.1 * hf_total)
    daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.success(f"**Rekomendasi Pompa**\n\nQ: {q_desain:.2f} L/s\nH: {head_total:.2f} m\nP: {daya_kw:.2f} kW")
        st.write(f"Supply Sumur: {q_safe:.2f} L/s")
        if q_safe < q_desain: st.error("❌ DEFISIT AIR")
        else: st.success("✅ SUPPLY AMAN")
        
    with c2:
        source = df_calc.copy()
        bar = alt.Chart(source).mark_bar().encode(x='Bulan', y='Q Req (L/s)')
        line = alt.Chart(source).mark_rule(color='red').encode(y=alt.datum(q_safe))
        st.altair_chart((bar + line).interactive(), use_container_width=True)
