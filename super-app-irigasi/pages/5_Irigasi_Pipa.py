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
    .status-box {padding: 10px; border-radius: 5px; margin-bottom: 20px; font-weight: bold;}
    .status-ok {background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9;}
    .status-info {background-color: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. INISIALISASI DATA (24 PERIODE)
# ==========================================
def init_state():
    # Buat Label Periode (Jan-1, Jan-2, dst...)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    periods = []
    for m in months:
        periods.extend([f"{m}-1", f"{m}-2"])
    
    # --- LOGIKA TARIK DATA ---
    eto_default = [5.0] * 24
    nfr_imported = None
    msg_status = ""
    
    # 1. Cek Data Klimatologi (Untuk ETo)
    if 'data_eto_transfer' in st.session_state:
        data_klimat = st.session_state['data_eto_transfer']
        if len(data_klimat) == 12: # Expand 12 -> 24
            eto_default = []
            for val in data_klimat: eto_default.extend([val, val])
        elif len(data_klimat) == 24:
            eto_default = data_klimat
            
    # 2. Cek Data Pola Tanam (Untuk NFR/Q Req Langsung)
    # Kita cek apakah ada session 'nfr_global' atau dataframe result dari page 2
    # Idealnya Page 2 menyimpan array NFR lengkap. 
    # (Asumsi: Jika user sudah buka Page 2, kita prioritaskan NFR dari sana)
    
    # --- SETUP DATAFRAME ---
    if 'df_neraca_24' not in st.session_state:
        # Default data dummy
        st.session_state['df_neraca_24'] = pd.DataFrame({
            'Periode': periods,
            'ETo (mm/hari)': eto_default,
            'Q Req (L/s/ha)': [0.0]*24  # Nanti diisi manual atau link
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
        'luas_ha': 2.0, 'efisiensi': 65,
        'head_statis_m': 63, 'safety_factor': 80,
        'tebal_akuifer_m': 20, 'k_perm': 4.32,
        'drawdown_izin_m': 10, 'radius_m': 0.15
    }
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val

init_state()

# ==========================================
# 2. SIDEBAR
# ==========================================
with st.sidebar:
    st.title("📂 File Manager")
    
    # Tombol Tarik Data Pola Tanam
    if st.button("🔄 Ambil Q Desain dari Pola Tanam"):
        # Kita cek apakah ada data NFR Global Max dari Page 2?
        # Untuk presisi, kita butuh array lengkap. Tapi jika tidak ada, 
        # kita pakai nilai max saja sebagai flat requirement (konservatif)
        if 'nfr_global' in st.session_state:
            q_max_pola = st.session_state['nfr_global'] # l/s/ha
            
            # Update tabel: Set semua kebutuhan = Q Max (Desain Konservatif)
            # Atau idealnya Page 2 kirim array list_nfr. 
            # (Untuk saat ini kita set MAX agar aman)
            st.session_state['df_neraca_24']['Q Req (L/s/ha)'] = [q_max_pola] * 24
            st.success(f"Berhasil menarik Q Desain: {q_max_pola:.3f} l/s/ha")
            st.rerun()
        else:
            st.error("Belum ada data dari Modul Pola Tanam.")

    # Save/Load
    clean_params = {k:v for k,v in st.session_state.items() if not isinstance(v, pd.DataFrame)}
    current_data = {
        'params': clean_params,
        'neraca': st.session_state['df_neraca_24'].to_dict(orient='records'),
        'pipa': st.session_state['df_pipa'].to_dict(orient='records')
    }
    st.download_button("💾 Simpan Proyek", json.dumps(current_data, indent=2), "jiat_15hari.json", "application/json")
    
    uploaded = st.file_uploader("📂 Buka Proyek", type=["json"])
    if uploaded:
        try:
            data = json.load(uploaded)
            for k, v in data['params'].items(): st.session_state[k] = v
            st.session_state['df_neraca_24'] = pd.DataFrame(data['neraca'])
            st.session_state['df_pipa'] = pd.DataFrame(data['pipa'])
            st.rerun()
        except: st.error("File rusak!")

    st.markdown("---")
    st.header("Parameter Teknis")
    st.session_state['luas_ha'] = st.number_input("Luas Layanan (Ha)", value=st.session_state['luas_ha'])
    st.session_state['head_statis_m'] = st.number_input("Head Statis (m)", value=st.session_state['head_statis_m'])
    
    with st.expander("⛰️ Sumur Dalam"):
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
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📝 INPUT & NERACA", "💧 HASIL DEBIT", "⚙️ PIPA & HIDROLIKA", "📊 LAPORAN"])

# --- ENGINE HITUNGAN SUPPLY ---
T = st.session_state['k_perm'] * st.session_state['tebal_akuifer_m']
k_detik = st.session_state['k_perm'] / 86400
R = 3000 * st.session_state['drawdown_izin_m'] * math.sqrt(k_detik)
if R <= st.session_state['radius_m']: R = st.session_state['radius_m'] + 10
q_teoritis = ((2 * math.pi * T * st.session_state['drawdown_izin_m']) / math.log(R/st.session_state['radius_m'])) * 1000 / 86400
q_safe = q_teoritis * (st.session_state['safety_factor'] / 100)

# --- TAB 1: INPUT NERACA (24 PERIODE) ---
with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("A. Kebutuhan Air (24 Periode)")
        st.info("💡 Kolom `Q Req` bisa diisi manual atau klik tombol **'Ambil Q Desain'** di sidebar.")
        
        # Tabel Input Utama
        edited_neraca = st.data_editor(
            st.session_state['df_neraca_24'],
            height=400,
            use_container_width=True,
            column_config={
                "Q Req (L/s/ha)": st.column_config.NumberColumn("NFR (L/s/ha)", format="%.3f")
            }
        )
        st.session_state['df_neraca_24'] = edited_neraca
        
        # Hitung Q Total (L/s)
        df_calc = edited_neraca.copy()
        df_calc['Q Total (L/s)'] = df_calc['Q Req (L/s/ha)'] * st.session_state['luas_ha']
        
        q_desain = df_calc['Q Total (L/s)'].max()
        idx_puncak = df_calc['Q Total (L/s)'].idxmax()
        bln_puncak = df_calc.loc[idx_puncak, 'Periode']
        
    with col_b:
        st.subheader("Resume Supply")
        st.markdown(f"""
        <div class="box-hasil">
            <b>Debit Sumur (Q Safe):</b><br>
            <span style="font-size:24px; color:blue;">{q_safe:.2f} L/s</span>
        </div>
        """, unsafe_allow_html=True)
        
        if q_safe >= q_desain:
            st.markdown(f"""<div class="status-box status-ok">✅ SUPPLY AMAN<br>Surplus: {q_safe - q_desain:.2f} L/s</div>""", unsafe_allow_html=True)
        else:
            st.error(f"⛔ DEFISIT AIR! (Kurang {q_desain - q_safe:.2f} L/s)")

# --- TAB 2: GRAFIK DEBIT ---
with tab2:
    st.subheader("Grafik Neraca Air (15 Harian)")
    
    source = df_calc.copy()
    source['Limit Sumur'] = q_safe
    
    base = alt.Chart(source).encode(x=alt.X('Periode', sort=None))
    
    bar = base.mark_bar(color='#4caf50').encode(
        y=alt.Y('Q Total (L/s)', title='Debit Kebutuhan (L/s)'),
        tooltip=['Periode', 'Q Total (L/s)']
    )
    
    rule = base.mark_rule(color='red', strokeDash=[5, 5]).encode(
        y='Limit Sumur',
        size=alt.value(2)
    )
    
    st.altair_chart((bar + rule).interactive(), use_container_width=True)
    st.caption("Grafik membandingkan Kebutuhan Air (Hijau) vs Kapasitas Sumur (Merah Garis Putus-putus).")

# --- TAB 3: PIPA & HIDROLIKA (TETAP SAMA) ---
with tab3:
    st.subheader("B. Desain Jaringan Pipa")
    st.data_editor(st.session_state['df_pipa'], key='editor_pipa', num_rows="dynamic", use_container_width=True, on_change=lambda: st.session_state.update({'df_pipa': st.session_state.editor_pipa}))
    
    # Engine Pipa
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
    daya_kw = (9.81 * (q_desain/1000) * head_total) / 0.70  
    daya_watt = (daya_kw / 0.85) * 1000
    
    st.markdown("#### Hasil Analisa Pipa")
    st.dataframe(df_pipa_res.style.format({'V (m/s)': '{:.2f}', 'Hf (m)': '{:.3f}'}), use_container_width=True)
    
    # Cek Kecepatan
    aman = True
    col_cek = st.columns(3)
    for i, row in df_pipa_res.iterrows():
        v = row['V (m/s)']
        if v < 0.6: 
            st.warning(f"⚠️ {row['Segmen']}: Endapan (V={v:.2f})")
            aman = False
        elif v > 2.0: 
            st.error(f"⛔ {row['Segmen']}: Erosi (V={v:.2f})")
            aman = False
    if aman: st.success("✅ Kecepatan Aliran Pipa Ideal.")

# --- TAB 4: LAPORAN ---
with tab4:
    st.markdown("## 📑 RESUME DESAIN JIAT")
    
    # Tombol Cetak
    import streamlit.components.v1 as components
    components.html("""<button onclick="window.print()" style="background:#2196F3;color:white;border:none;padding:8px 15px;border-radius:5px;cursor:pointer;">🖨️ Cetak PDF</button>""", height=45)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="box-hasil" style="border-top:3px solid blue">
        <b>Kebutuhan Air (Q Max)</b><br>
        <h2>{q_desain:.2f} L/s</h2>
        Periode: {bln_puncak}
        </div>""", unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""<div class="box-hasil" style="border-top:3px solid green">
        <b>Total Head Pompa</b><br>
        <h2>{head_total:.2f} m</h2>
        (Statis: {st.session_state['head_statis_m']} m)
        </div>""", unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""<div class="box-hasil" style="border-top:3px solid orange">
        <b>Daya Pompa (Est.)</b><br>
        <h2>{daya_kw:.2f} kW</h2>
        ({daya_watt:.0f} Watt)
        </div>""", unsafe_allow_html=True)
