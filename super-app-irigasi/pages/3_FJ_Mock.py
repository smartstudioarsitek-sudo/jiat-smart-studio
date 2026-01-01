import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIG ---
st.set_page_config(page_title="Metode FJ. Mock", layout="wide", page_icon="💧")

st.markdown("""
<style>
    .metric-box {
        padding: 15px; background-color: #e3f2fd; 
        border-left: 5px solid #2196f3; border-radius: 5px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI UTAMA: HANDLING DATA INPUT ---
def get_default_mock():
    # 1. Default Data (Dummy)
    default_eto = [4.14, 4.20, 4.30, 4.10, 3.90, 3.80, 3.90, 4.20, 4.50, 4.60, 4.30, 4.10]
    
    # 2. Cek apakah ada kiriman dari Page 1 (Klimatologi)?
    status_msg = "⚠️ Menggunakan Data Dummy (Belum ada link)"
    
    # Cek 'data_eto_manual' (dari tombol kirim) ATAU 'data_eto_transfer' (auto)
    source_data = st.session_state.get('data_eto_manual') or st.session_state.get('data_eto_transfer')
    
    if source_data:
        # A. Jika datanya pas 12 Bulan -> Pakai langsung
        if len(source_data) == 12:
            default_eto = source_data
            status_msg = "✅ Data ETo Terhubung (12 Bulan)"
            
        # B. Jika datanya 24 Periode (15 Harian) -> Rata-rata jadi 12 Bulan
        elif len(source_data) == 24:
            # Teknik: Ambil rata-rata per 2 data (Jan-1 & Jan-2 = Jan)
            temp_12 = []
            for i in range(0, 24, 2):
                avg = (source_data[i] + source_data[i+1]) / 2
                temp_12.append(avg)
            default_eto = temp_12
            status_msg = "✅ Data ETo Terhubung (Konversi 24 -> 12 Bulan)"

    # 3. Buat DataFrame Awal
    df = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'Curah Hujan (mm)': [346, 303, 360, 243, 142, 91, 74, 57, 102, 219, 311, 311], # Data hujan dummy
        'Hari Hujan': [18, 16, 17, 13, 9, 6, 4, 3, 6, 12, 16, 18],
        'ETo (mm/hari)': default_eto # <--- INI SUDAH AMAN (PASTI 12 DATA)
    })
    
    return df, status_msg

# --- FUNGSI HITUNG FJ MOCK ---
def hitung_fj_mock(df_input, luas_das, params):
    # Unpack Parameter
    sm = params['sm']      # Soil Moisture Capacity
    pf = params['pf']      # Percentage Factor
    i_ws = params['i']     # Infiltrasi
    k = params['k']        # Resesi Aliran Tanah
    
    results = []
    
    # Inisialisasi awal (biasanya asumsi tanah jenuh di akhir tahun sebelumnya)
    vt_prev = sm # Volume tanah bulan lalu (awal asumsi penuh)
    
    for idx, row in df_input.iterrows():
        ch = row['Curah Hujan (mm)']
        hh = row['Hari Hujan']
        eto = row['ETo (mm/hari)']
        nd = 30 # Jumlah hari rata-rata
        
        # 1. Evapotranspirasi Terbatas (Et)
        # Delta S (Exposed Surface) -> Mock: m = 10% - 50%
        # Rumus Mock untuk m: Jumlah hari hujan / Hari sebulan? Atau exposed surface 
        # Simplifikasi Mock: Et = ETo * faktor (tergantung vegetasi/lahan)
        # Kita pakai pendekatan standard Mock:
        # E_pot = ETo * nd
        # dE = E_pot * (m/20) * (18 - hh) ... ini variasi. 
        # Kita pakai simple: Et = ETo * 30 (Potential) -> Actual tergantung air tanah later.
        
        # Et Mock Standard: 
        # E = ETo * (d/30) * m ... agak kompleks variannya.
        # Kita pakai pendekatan: Evapotranspirasi Aktual (Ea)
        # Ea = ETo * 30 jika CH > ETo*30. Jika tidak, Ea = CH + dSm
        
        et_pot = eto * 30
        
        # 2. Water Balance Surface
        # dS = CH - Et
        ds = ch - et_pot
        
        # 3. Soil Moisture (Sm)
        if ds > 0:
            # Surplus
            ss = ds # Kandungan air tanah sementara
        else:
            # Defisit
            ss = ds # Negatif
            
        # Hitung Volume Tanah (Vt)
        vt_curr = vt_prev + ss
        if vt_curr > sm:
            ws = vt_curr - sm # Water Surplus
            vt_curr = sm      # Mentok di kapasitas lapang
        elif vt_curr < 0:
            ws = 0
            vt_curr = 0 # Kering
        else:
            ws = 0
            
        # 4. Infiltrasi (I)
        # I = ws * pf (Percentage Factor infiltration)
        inf = ws * pf
        
        # 5. Volume Aliran Tanah (Vn)
        # Vn = k * Vn-1 + 0.5 * (1+k) * I
        # Asumsi Vn bulan pertama = I
        if idx == 0:
            vn = inf # Simplifikasi awal
        else:
            vn_prev = results[-1]['Vn']
            vn = k * vn_prev + 0.5 * (1 + k) * inf
            
        # 6. Base Flow (BF)
        bf = vn
        
        # 7. Direct Runoff (DRO)
        # DRO = ws - I
        dro = ws - inf
        
        # 8. Total Runoff (TRO)
        tro_mm = bf + dro
        
        # 9. Debit (Q) m3/s
        # Q = (TRO / 1000) * (Luas_DAS_km2 * 10^6) / (30 * 24 * 3600)
        q_m3s = (tro_mm / 1000) * (luas_das * 1e6) / (30 * 86400)
        
        res_row = {
            'Bulan': row['Bulan'],
            'CH': ch,
            'Et': et_pot,
            'dS': ds,
            'Vt': vt_curr,
            'WS': ws,
            'Infiltrasi': inf,
            'Vn': vn,
            'BaseFlow': bf,
            'DRO': dro,
            'TRO (mm)': tro_mm,
            'Q (m3/s)': q_m3s
        }
        results.append(res_row)
        vt_prev = vt_curr # Update untuk bulan depan
        
    return pd.DataFrame(results)

# --- SIDEBAR INPUT ---
with st.sidebar:
    st.header("⚙️ Parameter Mock")
    
    luas_das = st.number_input("Luas DAS (km²)", value=150.0)
    
    st.subheader("Kalibrasi")
    sm_cap = st.number_input("Soil Moisture (SMC) mm", 50, 500, 200, help="Kapasitas kelembaban tanah")
    pf_val = st.slider("Faktor Infiltrasi (PF)", 0.0, 1.0, 0.4, help="Persentase air surplus yang masuk ke tanah")
    k_val  = st.slider("Faktor Resesi (k)", 0.0, 1.0, 0.6, help="Konstanta resesi aliran air tanah")
    i_val  = st.number_input("Infiltrasi Koef (i)", 0.0, 1.0, 0.5)

    params = {'sm': sm_cap, 'pf': pf_val, 'k': k_val, 'i': i_val}
    
    if st.button("🔄 Tarik Ulang Data ETo"):
        st.rerun()

# --- MAIN CONTENT ---
st.title("💧 Analisa Ketersediaan Air (FJ. Mock)")
st.caption("Analisa Debit Andalan Sungai Bulanan")

# 1. LOAD DATA
df_input, status = get_default_mock()

if "✅" in status:
    st.success(status)
else:
    st.warning(status)

st.subheader("1. Input Data Bulanan")
edited_df = st.data_editor(df_input, use_container_width=True, hide_index=True)

# 2. PROSES
df_mock = hitung_fj_mock(edited_df, luas_das, params)

# 3. OUTPUT
st.subheader("2. Hasil Analisa (Debit Andalan)")
col1, col2 = st.columns([3, 1])

with col1:
    # Format Table
    st.dataframe(
        df_mock.style.format({
            'Et': "{:.1f}", 'Vt': "{:.1f}", 'WS': "{:.1f}", 
            'TRO (mm)': "{:.1f}", 'Q (m3/s)': "{:.3f}"
        }),
        use_container_width=True,
        height=400
    )

with col2:
    q_avg = df_mock['Q (m3/s)'].mean()
    q_min = df_mock['Q (m3/s)'].min()
    q_max = df_mock['Q (m3/s)'].max()
    
    st.markdown(f"""
    <div class="metric-box">
        <b>Debit Rata-rata</b><br>
        <h2>{q_avg:.3f} m³/s</h2>
    </div>
    <div class="metric-box" style="background-color:#e8f5e9; border-left-color:#4caf50;">
        <b>Debit Minimum</b><br>
        <h2>{q_min:.3f} m³/s</h2>
    </div>
    """, unsafe_allow_html=True)

st.write("#### 📈 Grafik Hidrograf")
st.line_chart(df_mock.set_index('Bulan')['Q (m3/s)'])

# Cetak
import streamlit.components.v1 as components
st.divider()
components.html("""<button onclick="window.print()" style="background:gray;color:white;border:none;padding:10px;">🖨️ Cetak Laporan</button>""", height=50)
