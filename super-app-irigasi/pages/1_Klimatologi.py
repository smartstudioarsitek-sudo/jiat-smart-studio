import streamlit as st
import pandas as pd
import numpy as np
import json

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Analisa Klimatologi", layout="wide", page_icon="🌦️")

st.markdown("""
<style>
    @media print {
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
    .metric-card {
        background-color: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; border-radius: 5px; margin-bottom: 10px;
    }
    .success-box {
        padding: 10px; background-color: #d4edda; color: #155724;
        border: 1px solid #c3e6cb; border-radius: 5px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. RUMUS PENMAN MODIFIKASI (Standar KP-01) ---
def hitung_penman_modifikasi(temp, hum, sun, wind, lat_deg=-7.0, c_factor=1.1):
    def to_float(arr):
        return np.array([float(x) for x in arr])

    try:
        T = to_float(temp)
        RH = to_float(hum)
        n = to_float(sun)
        u_km_jam = to_float(wind) 
        u_km_day = u_km_jam * 24 

        # 1. Tekanan Uap
        ea = 6.11 * np.exp((17.27 * T) / (T + 237.3))
        ed = ea * (RH / 100)
        
        # 2. Faktor Pembobot (W)
        W = 0.4025 + 0.013 * T - 0.0001 * (T**2)
        
        # 3. Fungsi Angin f(u) KP-01
        fu = 0.27 * (1 + u_km_day / 100)
        
        # 4. Radiasi
        Ra = np.array([15.8, 16.0, 15.8, 15.3, 14.4, 13.9, 14.1, 14.8, 15.6, 16.0, 15.9, 15.7])
        Rs = (0.25 + 0.54 * (n/100)) * Ra
        Rns = (1 - 0.20) * Rs
        
        # Rnl (KP-01 Approach)
        func_t = 11.0 + 0.22 * T 
        func_ed = 0.34 - 0.044 * np.sqrt(ed)
        func_n = 0.1 + 0.9 * (n/100)
        Rnl = func_t * func_ed * func_n
        
        Rn = Rns - Rnl
        
        # 5. ETo
        ETo_star = W * Rn + (1 - W) * fu * (ea - ed)
        ETo = c_factor * ETo_star
        return ETo
        
    except Exception as e:
        return np.zeros(12)

# --- 3. STATE MANAGEMENT (DEFAULT DATA) ---
if 'df_iklim' not in st.session_state:
    st.session_state['df_iklim'] = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'Suhu (°C)': [27.1, 27.2, 27.5, 28.0, 27.8, 27.2, 26.8, 27.0, 27.5, 28.1, 27.8, 27.3],
        'Kelembaban (%)': [82.0, 83.0, 81.0, 80.0, 78.0, 76.0, 72.0, 70.0, 72.0, 75.0, 79.0, 81.0],
        'Penyinaran (%)': [45.0, 48.0, 52.0, 60.0, 75.0, 80.0, 85.0, 88.0, 80.0, 70.0, 55.0, 48.0],
        'Angin (km/jam)': [12.0, 11.0, 10.0, 9.0, 10.0, 11.0, 13.0, 14.0, 13.0, 11.0, 10.0, 11.0]
    })

# --- 4. SIDEBAR (FILE MANAGER & INPUT) ---
with st.sidebar:
    st.header("📂 File Manager")
    
    # A. OPEN FILE (LOAD)
    uploaded_file = st.file_uploader("Buka File Data (.json)", type=["json"])
    if uploaded_file is not None:
        try:
            # Baca file JSON
            data_load = json.load(uploaded_file)
            
            # Masukkan ke Session State
            if 'df_iklim_data' in data_load:
                st.session_state['df_iklim'] = pd.DataFrame(data_load['df_iklim_data'])
            
            # Tips: Kita pakai session state sementara untuk parameter scalar, 
            # nanti di-assign ke widget lewat argument 'value' atau session state key
            st.session_state['temp_c_factor'] = data_load.get('c_factor', 1.1)
            
            st.success("✅ File Berhasil Dimuat!")
            st.rerun() # Refresh halaman agar tabel terupdate
        except Exception as e:
            st.error(f"File rusak: {e}")

    st.divider()
    
    # B. PARAMETER INPUT
    st.header("🌍 Parameter KP-01")
    
    # Cek apakah ada data loadan untuk c_factor
    def_c = st.session_state.get('temp_c_factor', 1.1)
    
    c_factor = st.number_input("Faktor Koreksi (c)", 0.8, 1.4, def_c, 0.1)
    
    st.divider()
    
    # C. SAVE FILE (DOWNLOAD)
    st.subheader("💾 Simpan Pekerjaan")
    nama_file = st.text_input("Nama File", "Data_Klimatologi_Proyek_A")
    
    # Siapkan data untuk disimpan
    data_save = {
        'df_iklim_data': st.session_state['df_iklim'].to_dict(orient='records'),
        'c_factor': c_factor,
        'tipe': 'klimatologi_kp01'
    }
    json_str = json.dumps(data_save, indent=2)
    
    st.download_button(
        label="⬇️ Download File (.json)",
        data=json_str,
        file_name=f"{nama_file}.json",
        mime="application/json",
        help="Simpan data input ini ke laptop agar bisa dibuka lagi nanti."
    )

# --- 5. MAIN CONTENT ---
st.title("🌦️ Klimatologi (Penman Modifikasi)")
st.caption("Metode Standar KP-01 (Kriteria Perencanaan Irigasi)")

# A. Input Data
st.subheader("1. Input Data Iklim")
edited_df = st.data_editor(st.session_state['df_iklim'], num_rows="fixed", use_container_width=True, hide_index=True)
st.session_state['df_iklim'] = edited_df

# B. Proses Hitung
try:
    suhu = edited_df['Suhu (°C)'].tolist()
    hum = edited_df['Kelembaban (%)'].tolist()
    sun = edited_df['Penyinaran (%)'].tolist()
    wind = edited_df['Angin (km/jam)'].tolist()

    eto_result = hitung_penman_modifikasi(suhu, hum, sun, wind, c_factor=c_factor)
    
    # Hasil
    df_hasil = edited_df[['Bulan']].copy()
    df_hasil['ETo (mm/hari)'] = np.round(eto_result, 2)
    
    # --- FITUR KIRIM DATA (LINKING) ---
    st.session_state['data_eto_transfer'] = df_hasil['ETo (mm/hari)'].tolist()
    
    st.subheader("2. Hasil Perhitungan")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        numeric_cols = df_hasil.select_dtypes(include=[np.number]).columns
        st.dataframe(
            df_hasil.style.background_gradient(cmap="Oranges", subset=['ETo (mm/hari)'])
            .format("{:.2f}", subset=numeric_cols), 
            use_container_width=True
        )
        
        # Tombol Indikator Kirim Data
        st.markdown(f"""
        <div class="success-box">
            <b>🔗 Status Link Data:</b><br>
            Data ETo berhasil dikirim ke modul <i>Pola Tanam</i> & <i>JIAT</i> secara otomatis.<br>
            (Nilai Rata-rata: {np.mean(eto_result):.2f} mm/hari)
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        rata_eto = np.mean(eto_result)
        st.markdown(f"""
        <div class="metric-card">
            <h4>Rata-rata ETo</h4>
            <h2 style="margin:0;">{rata_eto:.2f} <span style="font-size:16px">mm/hari</span></h2>
            <small>✅ KP-01 (Modified)</small>
        </div>
        """, unsafe_allow_html=True)
        st.bar_chart(df_hasil.set_index('Bulan')['ETo (mm/hari)'])

except Exception as e:
    st.error(f"⚠️ Terjadi kesalahan input: {e}")

# --- 6. CETAK ---
st.divider()
import streamlit.components.v1 as components
components.html(
    """<button onclick="window.print()" style="background:#ff9800;color:white;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;cursor:pointer;">🖨️ Cetak PDF</button>""", 
    height=50
)
