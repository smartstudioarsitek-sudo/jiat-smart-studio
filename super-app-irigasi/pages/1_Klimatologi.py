import streamlit as st
import pandas as pd
import numpy as np

# --- 1. CONFIG ---
st.set_page_config(page_title="Analisa Klimatologi", layout="wide", page_icon="🌦️")

# --- 2. RUMUS PENMAN ---
def hitung_penman_modifikasi(temp, hum, sun, wind, c_factor=1.1):
    def to_float(arr): return np.array([float(x) for x in arr])
    try:
        T, RH, n, u_km_jam = to_float(temp), to_float(hum), to_float(sun), to_float(wind)
        u_km_day = u_km_jam * 24 
        ea = 6.11 * np.exp((17.27 * T) / (T + 237.3))
        ed = ea * (RH / 100)
        W = 0.4025 + 0.013 * T - 0.0001 * (T**2)
        fu = 0.27 * (1 + u_km_day / 100)
        
        ra_val = [15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7]
        Ra = np.array(ra_val * 2) if len(T) == 24 else np.array(ra_val)
        
        Rs = (0.25 + 0.54 * (n/100)) * Ra
        Rns = 0.8 * Rs
        Rnl = (11.0 + 0.22 * T) * (0.34 - 0.044 * np.sqrt(ed)) * (0.1 + 0.9 * (n/100))
        Rn = Rns - Rnl
        ETo = c_factor * (W * Rn + (1 - W) * fu * (ea - ed))
        return ETo
    except: return np.zeros(len(temp))

# --- 3. INIT STATE ---
def init_state():
    periods = [f"{m}-{p}" for m in ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'] for p in [1, 2]]
    if 'df_iklim_24' not in st.session_state:
        st.session_state['df_iklim_24'] = pd.DataFrame({
            'Periode': periods,
            'Suhu (°C)': [27.0]*24, 'Kelembaban (%)': [80.0]*24, 
            'Penyinaran (%)': [50.0]*24, 'Angin (m/s)': [1.5]*24
        })

init_state()

# --- 4. SIDEBAR (EXCEL UPLOADER) ---
with st.sidebar:
    st.header("📂 Data Input")
    st.info("Sekarang mendukung file Excel (.xlsx)!")
    
    # Uploader khusus Excel
    uploaded_file = st.file_uploader("Upload File Excel", type=["xlsx", "xls"])
    
    if uploaded_file and st.button("🔄 BACA FILE EXCEL", type="primary"):
        try:
            # BACA EXCEL LANGSUNG
            # Engine openpyxl adalah standar untuk .xlsx
            df = pd.read_excel(uploaded_file)
            
            # Validasi Kolom: Minimal 5 Kolom (Bulan, Suhu, RH, Sinar, Angin)
            if df.shape[1] >= 5:
                # Ambil data berdasarkan urutan kolom (Index 1, 2, 3, 4)
                # Kita abaikan nama headernya, yang penting urutannya benar
                
                # Col 0: Bulan (Abaikan)
                # Col 1: Suhu
                # Col 2: RH
                # Col 3: Sinar
                # Col 4: Angin
                
                # Paksa jadi angka (kalau ada teks aneh jadi 0/NaN)
                raw_suhu = pd.to_numeric(df.iloc[:, 1], errors='coerce').fillna(27.0).values
                raw_rh   = pd.to_numeric(df.iloc[:, 2], errors='coerce').fillna(80.0).values
                raw_sun  = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(50.0).values
                raw_wind = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(1.5).values
                
                # Expand 12 Bulan -> 24 Periode
                new_suhu, new_rh, new_sun, new_wind = [], [], [], []
                
                # Ambil max 12 data (jaga-jaga kalau excelnya kepanjangan)
                limit = min(len(df), 12)
                
                for i in range(limit):
                    new_suhu.extend([raw_suhu[i]]*2)
                    new_rh.extend([raw_rh[i]]*2)
                    new_sun.extend([raw_sun[i]]*2)
                    new_wind.extend([raw_wind[i]]*2)

                # Masukkan ke Tabel Aplikasi
                st.session_state['df_iklim_24']['Suhu (°C)'] = new_suhu
                st.session_state['df_iklim_24']['Kelembaban (%)'] = new_rh
                st.session_state['df_iklim_24']['Penyinaran (%)'] = new_sun
                st.session_state['df_iklim_24']['Angin (m/s)'] = new_wind
                
                st.success("✅ MANTAP! Excel berhasil dibaca.")
                st.rerun()
            else:
                st.error(f"❌ Jumlah kolom kurang. Terbaca {df.shape[1]} kolom. Pastikan format Excel sesuai.")
                
        except Exception as e:
            st.error(f"Gagal baca Excel: {e}")
            st.caption("Tips: Pastikan file tidak dipassword dan formatnya .xlsx standar.")

    st.divider()
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, 0.9, 0.1)

# --- 5. MAIN CONTENT ---
st.title("🌦️ Klimatologi")
st.caption("Mode: Input Excel (.xlsx) -> Hitung ETo")

# Table Input
edited_df = st.data_editor(st.session_state['df_iklim_24'], height=400, hide_index=True)
st.session_state['df_iklim_24'] = edited_df

# Proses Hitung
suhu = edited_df['Suhu (°C)'].tolist()
hum = edited_df['Kelembaban (%)'].tolist()
sun = edited_df['Penyinaran (%)'].tolist()
wind = [x * 3.6 for x in edited_df['Angin (m/s)'].tolist()] # Konversi m/s ke km/jam

eto = hitung_penman_modifikasi(suhu, hum, sun, wind, c_factor)

# Table Hasil
df_res = edited_df[['Periode']].copy()
df_res['ETo'] = np.round(eto, 2)
st.session_state['data_eto_transfer'] = df_res['ETo'].tolist()

c1, c2 = st.columns([2, 1])
with c1:
    st.dataframe(df_res.style.background_gradient(cmap="Oranges"), height=400, use_container_width=True)
    if st.button("🚀 KIRIM DATA ETo", type="primary", use_container_width=True):
        st.session_state['data_eto_manual'] = df_res['ETo'].tolist()
        st.success("✅ Data Terkirim!")

with c2:
    st.metric("Rata-rata ETo", f"{np.mean(eto):.2f} mm/hari")
    st.bar_chart(df_res.set_index('Periode')['ETo'])
