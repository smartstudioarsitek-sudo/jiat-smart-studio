import streamlit as st
import pandas as pd
import numpy as np
import calendar

st.set_page_config(page_title="Analisa Ketersediaan Air (FJ Mock)", layout="wide", page_icon="🌊")

# --- CSS ---
st.markdown("""
<style>
    .metric-card {background-color: #e3f2fd; padding: 15px; border-radius: 10px; border-left: 5px solid #1976d2;}
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- INIT STATE ---
def init_mock_state():
    months = list(calendar.month_abbr)[1:] # ['Jan', 'Feb', ...]
    
    # Data Default (Dummy)
    if 'df_mock_input' not in st.session_state:
        st.session_state['df_mock_input'] = pd.DataFrame({
            'Bulan': months,
            'Curah Hujan (mm)': [346, 303, 360, 243, 142, 91, 74, 57, 102, 219, 298, 305],
            'Hari Hujan':       [18,  16,  17,  13,  9,   6,  4,  3,  6,   12,  15,  17]
        })
    
    # Ambil ETo dari Page 1 (Rata-rata bulanan)
    if 'data_eto_transfer' in st.session_state and len(st.session_state['data_eto_transfer']) == 24:
        # Konversi 24 periode -> 12 Bulan (Rata-rata)
        eto_24 = np.array(st.session_state['data_eto_transfer'])
        eto_12 = eto_24.reshape(-1, 2).mean(axis=1)
    else:
        eto_12 = [4.5] * 12 # Default
        
    # Masukkan ETo ke tabel input untuk referensi (Read Only di logika hitungan)
    st.session_state['df_mock_input']['ETo (mm/hari)'] = np.round(eto_12, 2)

init_mock_state()

# --- SIDEBAR: SMART CSV UPLOAD ---
with st.sidebar:
    st.header("📂 Input Data")
    
    # Template Download
    df_temp = pd.DataFrame({'Bulan':['Jan','Feb'], 'Hujan':[200,150], 'Hari_Hujan':[15,10]})
    st.download_button("📥 Template CSV", df_temp.to_csv(index=False).encode('utf-8'), "template_fjmock.csv", "text/csv")
    
    st.divider()
    
    # Uploader
    uploaded = st.file_uploader("Upload CSV (Hujan & HH)", type=['csv'])
    if uploaded and st.button("🔄 Baca CSV"):
        try:
            try: df = pd.read_csv(uploaded)
            except: 
                uploaded.seek(0)
                df = pd.read_csv(uploaded, sep=';')
            
            # Cari Kolom Angka
            num = df.select_dtypes(include=[np.number])
            
            # Logika Cerdas: 
            # Jika ada >= 2 kolom angka, asumsi: Kolom 1 = Hujan, Kolom 2 = Hari Hujan
            if num.shape[1] >= 2:
                hujan_vals = num.iloc[:, 0].values[:12] # Ambil 12 bulan
                hh_vals = num.iloc[:, 1].values[:12]
                
                # Validasi HH (Gak boleh > jumlah hari)
                hh_vals = np.where(hh_vals > 31, 31, hh_vals)
                
                st.session_state['df_mock_input']['Curah Hujan (mm)'] = hujan_vals
                st.session_state['df_mock_input']['Hari Hujan'] = hh_vals
                st.success(f"✅ Berhasil load: Hujan & {num.columns[1]}")
                st.rerun()
            elif num.shape[1] == 1:
                st.session_state['df_mock_input']['Curah Hujan (mm)'] = num.iloc[:, 0].values[:12]
                st.warning("⚠️ Hanya kolom Curah Hujan yang ditemukan. Hari Hujan tidak berubah.")
                st.rerun()
            else:
                st.error("❌ Format CSV tidak dikenali.")
                
        except Exception as e: st.error(f"Error: {e}")

    st.header("⚙️ Parameter Mock")
    luas_das = st.number_input("Luas DAS (km2)", value=150.0)
    i_s = st.slider("Infiltration Coeff (i)", 0.0, 1.0, 0.4)
    k_rec = st.slider("Recession Factor (k)", 0.0, 1.0, 0.6)
    pf = st.number_input("Faktor Lahan Terbuka (m)", 0.0, 50.0, 10.0, step=5.0)

# --- MAIN CONTENT ---
st.title("🌊 Analisa Ketersediaan Air (FJ Mock)")
st.info(f"**Proyek:** {st.session_state.get('nama_proyek','-')} | **Lokasi:** {st.session_state.get('lokasi','-')}")

# 1. INPUT TABLE
st.subheader("1. Input Data Bulanan")
edited_df = st.data_editor(st.session_state['df_mock_input'], hide_index=True, use_container_width=True)
st.session_state['df_mock_input'] = edited_df

# 2. CALCULATION ENGINE (FJ MOCK)
# Ambil data
R = edited_df['Curah Hujan (mm)'].values
n = edited_df['Hari Hujan'].values
ETo = edited_df['ETo (mm/hari)'].values
nd = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]) # Jumlah hari

# Hitung
Et_pot = ETo * 30 # Asumsi Eto Bulanan
dE = Et_pot * (n / 18) # Limited Evapo (Simplified Mock)
E_act = Et_pot - dE 
WS = R - E_act # Water Surplus

# Storage & Runoff (Iterasi)
Vn_list, Baseflow, Direct, Total_Q = [], [], [], []
V_prev = 100 # Initial Storage

for i in range(12):
    ws = WS[i]
    
    # Soil Storage
    Vn = V_prev + ws
    if Vn < 0: Vn = 0
    # Cap storage (simplified SMC)
    if Vn > 200: Vn = 200 # Kapasitas lapang asumsi
    dV = Vn - V_prev
    V_prev = Vn
    Vn_list.append(Vn)
    
    # Runoff
    ws_net = ws - dV
    if ws_net < 0: ws_net = 0
    
    i_val = ws_net * i_s
    DRO = ws_net - i_val # Direct Runoff
    BF = i_val * 0.5 + (k_rec * 10) # Baseflow simplified
    
    Q_mm = DRO + BF
    Q_m3s = (Q_mm * 0.001 * luas_das * 1000000) / (nd[i] * 86400)
    
    Total_Q.append(Q_m3s)

# 3. HASIL
df_res = pd.DataFrame({
    'Bulan': edited_df['Bulan'],
    'Hujan (mm)': R,
    'E.Act (mm)': np.round(E_act, 1),
    'Surplus (mm)': np.round(WS, 1),
    'Debit (m³/s)': np.round(Total_Q, 3)
})

st.divider()
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("2. Hasil Debit Andalan")
    st.dataframe(df_res.style.background_gradient(cmap="Blues", subset=['Debit (m³/s)']), use_container_width=True)
    
    # Hitung Q80 (Probabilitas 80%)
    q_sorted = sorted(Total_Q)
    idx_80 = int(0.2 * 12) # 80% exceedance = 20% rank from bottom
    q80_val = q_sorted[idx_80]
    
    st.success(f"💧 **Debit Andalan (Q80): {q80_val:.3f} m³/s**")

with c2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.write("Grafik Hidrograf")
    st.area_chart(df_res.set_index('Bulan')['Debit (m³/s)'])
    st.markdown('</div>', unsafe_allow_html=True)
