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

# --- 3. INIT ---
def init_state():
    periods = [f"{m}-{p}" for m in ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'] for p in [1, 2]]
    if 'df_iklim_24' not in st.session_state:
        st.session_state['df_iklim_24'] = pd.DataFrame({
            'Periode': periods,
            'Suhu (°C)': [27.0]*24, 'Kelembaban (%)': [80.0]*24, 
            'Penyinaran (%)': [50.0]*24, 'Angin (m/s)': [1.5]*24
        })
init_state()

# --- 4. SIDEBAR (ULTIMATE READER) ---
with st.sidebar:
    st.header("📂 Data Input")
    
    # Satu Pintu untuk Semua File
    uploaded_file = st.file_uploader("Upload File (CSV / Excel)", type=["csv", "xlsx", "xls"])
    
    if uploaded_file and st.button("🔄 PROSES FILE", type="primary"):
        df = None
        try:
            # A. COBA BACA EXCEL (.xlsx)
            if uploaded_file.name.endswith('.xlsx'):
                try:
                    # Paksa pakai engine openpyxl (standar xlsx)
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                except ImportError:
                    st.error("⚠️ Server belum install 'openpyxl'. Coba upload file CSV saja.")
            
            # B. COBA BACA EXCEL LAMA (.xls)
            elif uploaded_file.name.endswith('.xls'):
                try:
                    df = pd.read_excel(uploaded_file, engine='xlrd')
                except ImportError:
                    st.error("⚠️ Server belum install 'xlrd'. Coba Save As Excel ke .csv")

            # C. COBA BACA CSV (METODE MANUAL PARSING) - PALING KUAT
            elif uploaded_file.name.endswith('.csv'):
                # Kita baca sebagai text mentah dulu biar gak kena error encoding aneh2
                try:
                    import io
                    # Coba decode utf-8 dulu, kalau gagal pake cp1252 (windows)
                    bytes_data = uploaded_file.getvalue()
                    try:
                        string_data = bytes_data.decode('utf-8')
                    except:
                        string_data = bytes_data.decode('cp1252')
                    
                    # Manual Split (Anti-Pandas Error)
                    lines = string_data.split('\n')
                    data_rows = []
                    for line in lines:
                        # Cek delimiter ; atau ,
                        if ';' in line: parts = line.split(';')
                        else: parts = line.split(',')
                        
                        # Ambil hanya yang isinya angka valid
                        row_nums = []
                        for p in parts:
                            try: row_nums.append(float(p.strip()))
                            except: pass
                        
                        if len(row_nums) >= 4: # Minimal 4 angka sebaris
                            data_rows.append(row_nums[:4])
                    
                    if len(data_rows) > 0:
                        df = pd.DataFrame(data_rows)
                    
                except Exception as e_csv:
                    st.error(f"Gagal baca CSV Manual: {e_csv}")

            # D. PROSES DATAFRAME (JIKA BERHASIL DIBACA)
            if df is not None and df.shape[1] >= 4:
                # Ambil 4 kolom angka pertama (apapun nama headernya)
                df_numeric = df.select_dtypes(include=[np.number])
                
                # Fallback jika select_dtypes gagal (misal kolom masih object)
                if df_numeric.shape[1] < 4:
                     df_numeric = df # Asumsi csv manual parsing sudah angka semua
                
                vals = df_numeric.iloc[:, :4].values
                
                # Paksa mapping (Suhu, RH, Sinar, Angin)
                raw_suhu = vals[:, 0]
                raw_rh   = vals[:, 1]
                raw_sun  = vals[:, 2]
                raw_wind = vals[:, 3]

                # Expand 12 -> 24
                new_suhu, new_rh, new_sun, new_wind = [], [], [], []
                limit = min(len(vals), 12)
                for i in range(limit):
                    new_suhu.extend([raw_suhu[i]]*2)
                    new_rh.extend([raw_rh[i]]*2)
                    new_sun.extend([raw_sun[i]]*2)
                    new_wind.extend([raw_wind[i]]*2)

                st.session_state['df_iklim_24']['Suhu (°C)'] = new_suhu
                st.session_state['df_iklim_24']['Kelembaban (%)'] = new_rh
                st.session_state['df_iklim_24']['Penyinaran (%)'] = new_sun
                st.session_state['df_iklim_24']['Angin (m/s)'] = new_wind
                
                st.success("✅ DATA MASUK! (Akhirnya...)")
                st.rerun()
            else:
                st.error(f"❌ Gagal ekstrak data. Pastikan file berisi minimal 4 kolom angka.")
                
        except Exception as e:
            st.error(f"System Error: {e}")

    st.divider()
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, 0.9, 0.1)

# --- 5. MAIN ---
st.title("🌦️ Klimatologi")
st.caption("Input Data -> Hitung ETo")

edited_df = st.data_editor(st.session_state['df_iklim_24'], height=400, hide_index=True)
st.session_state['df_iklim_24'] = edited_df

suhu = edited_df['Suhu (°C)'].tolist()
hum = edited_df['Kelembaban (%)'].tolist()
sun = edited_df['Penyinaran (%)'].tolist()
wind = [x * 3.6 for x in edited_df['Angin (m/s)'].tolist()]

eto = hitung_penman_modifikasi(suhu, hum, sun, wind, c_factor)

df_res = edited_df[['Periode']].copy()
df_res['ETo'] = np.round(eto, 2)
st.session_state['data_eto_transfer'] = df_res['ETo'].tolist()

c1, c2 = st.columns([2, 1])
with c1:
    st.dataframe(df_res.style.background_gradient(cmap="Oranges"), height=400, use_container_width=True)
    if st.button("🚀 KIRIM DATA ETo", type="primary"):
        st.session_state['data_eto_manual'] = df_res['ETo'].tolist()
        st.success("✅ Data Terkirim!")
with c2:
    st.metric("Rata-rata ETo", f"{np.mean(eto):.2f} mm/hari")
    st.bar_chart(df_res.set_index('Periode')['ETo'])
