import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import pickle

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #134E5E, #71B280); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .stDataFrame { border: 1px solid #ddd; border-radius: 5px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .status-safe { color: green; font-weight: bold; }
    .status-danger { color: red; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. ENGINE HIDROLIKA (FIXED TYPE ERROR) ---
def get_critical_depth(Q, b, m):
    """Menghitung kedalaman kritis (yc)"""
    y_min, y_max = 0.01, 20.0
    for _ in range(30):
        y = (y_min + y_max) / 2
        A = (b + m * y) * y
        T = b + 2 * m * y
        if A <= 0: A = 0.001
        f_val = 9.81 * (A**3) - (Q**2) * T
        if abs(f_val) < 1e-5: break
        if f_val < 0: y_min = y
        else: y_max = y
    return y

def get_normal_depth(Q, b, m, n, S):
    """Menghitung kedalaman normal (yn) dengan Manning"""
    # Pastikan S adalah float untuk mencegah TypeError
    try:
        S = float(S)
        Q = float(Q)
        b = float(b)
        m = float(m)
        n = float(n)
    except:
        return 0.01

    if S <= 0: return 0.01 # Slope 0 atau negatif dianggap datar/genangan
    
    y_min, y_max = 0.01, 20.0
    for _ in range(30):
        y = (y_min + y_max) / 2
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        Q_calc = (1/n) * A * (R**(2/3)) * (S**0.5)
        if abs(Q_calc - Q) < 1e-5: break
        if Q_calc < Q: y_min = y
        else: y_max = y
    return y

def calc_froude(Q, A, T):
    if A <= 0 or T <= 0: return 0
    D = A / T 
    v = Q / A
    fr = v / np.sqrt(9.81 * D)
    return fr

# --- 3. SIDEBAR: PROJECT MANAGEMENT ---
with st.sidebar:
    st.header("📂 Project Menu")
    
    # SAVE PROJECT
    if 'main_data' in st.session_state and st.session_state['main_data'] is not None:
        project_data = {
            "df_input": st.session_state.get('main_data', None),
            "df_terjunan": st.session_state.get('drop_data', None),
            "results_recap": st.session_state.get('results_recap', None),
            "results_detail": st.session_state.get('results_detail', None)
        }
        buffer = io.BytesIO()
        pickle.dump(project_data, buffer)
        st.download_button(
            label="💾 Save Project (.pkl)",
            data=buffer,
            file_name="my_irrigation_project.pkl",
            mime="application/octet-stream"
        )
    
    # OPEN PROJECT
    uploaded_project = st.file_uploader("Buka Project (.pkl)", type=["pkl"])
    if uploaded_project is not None:
        try:
            data = pickle.load(uploaded_project)
            st.session_state['main_data'] = data.get('df_input')
            st.session_state['drop_data'] = data.get('df_terjunan')
            st.session_state['results_recap'] = data.get('results_recap')
            st.session_state['results_detail'] = data.get('results_detail')
            st.success("Project Loaded Successfully!")
        except Exception as e:
            st.error(f"Gagal membuka file: {e}")

# --- 4. MAIN INTERFACE ---
st.markdown('<div class="header-box"><h2>🏗️ SMART HEC-RAS ULTIMATE (Professional Edition)</h2></div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📂 1. Input Data", "⚙️ 2. Parameter", "🚀 3. Eksekusi", "📊 4. Grafik", "📑 5. Laporan Output"])

# --- TAB 1: INPUT DATA ---
with tab1:
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.subheader("1. Upload Data Saluran (Import Nokan)")
        file_saluran = st.file_uploader("Upload 'IMPORT NOKAN.xlsx'", type=["xlsx", "csv"])
        if file_saluran:
            try:
                if file_saluran.name.endswith('.csv'):
                    df_in = pd.read_csv(file_saluran)
                else:
                    df_in = pd.read_excel(file_saluran)
                st.session_state['main_data'] = df_in
                st.success(f"Berhasil load {len(df_in)} baris data.")
                st.dataframe(df_in.head())
            except Exception as e:
                st.error(f"Error reading file: {e}")

    with col_up2:
        st.subheader("2. Upload Data Terjunan (Opsional)")
        file_terjunan = st.file_uploader("Upload 'STA TERJUNAN.xlsx'", type=["xlsx", "csv"])
        if file_terjunan:
            try:
                if file_terjunan.name.endswith('.csv'):
                    df_drop = pd.read_csv(file_terjunan)
                else:
                    df_drop = pd.read_excel(file_terjunan)
                st.session_state['drop_data'] = df_drop
                st.dataframe(df_drop.head())
            except Exception as e:
                st.error(f"Error reading file: {e}")

# --- TAB 2: PARAMETER ---
with tab2:
    if 'main_data' in st.session_state:
        df = st.session_state['main_data']
        
        # Mapping Kolom Otomatis
        cols = df.columns.str.lower()
        col_map = {}
        possible_maps = {
            'sta_awal': ['sta awal', 'sta_awal', 'start'],
            'sta_akhir': ['sta akhir', 'sta_akhir', 'end'],
            'elev_awal': ['elev awal', 'elev_awal'],
            'elev_akhir': ['elev akhir', 'elev_akhir'],
            'b': ['lebar', 'b', 'width'],
            'm': ['talud', 'm', 'slope_side'],
            'n': ['kekasaran', 'n', 'roughness'],
            's': ['slope', 's', 'desain s'],
            'q': ['debit', 'q', 'flow']
        }
        
        missing = []
        for key, candidates in possible_maps.items():
            found = False
            for c in candidates:
                match = [col for col in df.columns if c in col.lower()]
                if match:
                    col_map[key] = match[0]
                    found = True
                    break
            if not found: missing.append(key)
            
        if missing:
            st.warning(f"⚠️ Kolom tidak ditemukan: {missing}. Cek nama header Excel.")
        else:
            st.session_state['col_map'] = col_map
            st.success("✅ Semua kolom terdeteksi!")
            st.write("Mapping Kolom:", col_map)

# --- TAB 3: EKSEKUSI (DENGAN FIX ERROR TYPE) ---
with tab3:
    st.write("Klik tombol di bawah untuk menjalankan analisa.")
    if st.button("🚀 RUN ANALISA HIDROLIKA"):
        if 'main_data' not in st.session_state or 'col_map' not in st.session_state:
            st.error("Data belum siap! Upload di Tab 1 & Cek di Tab 2.")
        else:
            df = st.session_state['main_data'].copy()
            cmap = st.session_state['col_map']
            
            # --- AUTO CLEANING DATA (FIX TYPE ERROR) ---
            # Mengubah semua kolom numerik menjadi float dan handle koma/titik
            numeric_cols = [
                cmap['sta_awal'], cmap['sta_akhir'], cmap['elev_awal'], cmap['elev_akhir'],
                cmap['b'], cmap['m'], cmap['n'], cmap['s'], cmap['q']
            ]
            
            try:
                for col in numeric_cols:
                    # 1. Pastikan jadi string dulu
                    df[col] = df[col].astype(str)
                    # 2. Ganti koma dengan titik (jika ada)
                    df[col] = df[col].str.replace(',', '.', regex=False)
                    # 3. Convert ke angka (coerce error jadi NaN, lalu isi 0)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            except Exception as e:
                st.error(f"Gagal memproses data angka: {e}")
                st.stop()
            
            # --- PROSES PERHITUNGAN ---
            recap_list = []
            detail_list = []
            
            for idx, row in df.iterrows():
                sta_start = row[cmap['sta_awal']]
                sta_end = row[cmap['sta_akhir']]
                elev_start = row[cmap['elev_awal']]
                elev_end = row[cmap['elev_akhir']]
                b = row[cmap['b']]
                m = row[cmap['m']]
                n = row[cmap['n']]
                s_design = row[cmap['s']]
                q = row[cmap['q']]
                
                # Cek Terjunan di Input Utama
                drop_h = 0
                if 'TERJUNAN (m)' in row:
                    val = str(row['TERJUNAN (m)']).replace(',', '.')
                    try: drop_h = float(val) if val.lower() != 'nan' else 0
                    except: drop_h = 0
                
                length = sta_end - sta_start
                
                # Hitung
                yn = get_normal_depth(q, b, m, n, s_design)
                yc = get_critical_depth(q, b, m)
                
                A_n = (b + m * yn) * yn
                T_n = b + 2 * m * yn
                v_n = q / A_n if A_n > 0 else 0
                fr_n = calc_froude(q, A_n, T_n)
                
                status = "✅ Sub-Kritis (Aman)"
                if fr_n > 1: status = "⚠️ Super-Kritis (Bahaya)"
                if 0.9 <= fr_n <= 1.1: status = "⚡ Kritis (Gelombang)"
                
                recap_list.append({
                    "STA Awal": sta_start,
                    "STA Akhir": sta_end,
                    "Panjang (m)": length,
                    "Drop (m)": drop_h,
                    "Slope Desain": s_design,
                    "Debit (Q)": q,
                    "Y Normal (m)": round(yn, 3),
                    "Y Kritis (m)": round(yc, 3),
                    "Kecepatan (m/s)": round(v_n, 3),
                    "Froude": round(fr_n, 3),
                    "Status": status
                })
                
                # Interpolasi Detail (Interval 25m)
                current_sta = sta_start
                while current_sta <= sta_end:
                    ratio = (current_sta - sta_start) / length if length > 0 else 0
                    z_ground = elev_start - (elev_start - elev_end) * ratio
                    ws_elev = z_ground + yn
                    
                    # Logic Note
                    drop_note = "Saluran"
                    # Cek jika STA ini ada drop (logic sederhana di akhir segmen)
                    if abs(current_sta - sta_end) < 0.1 and drop_h < 0:
                         drop_note = f"Bottom Drop {abs(drop_h)}m"

                    detail_list.append({
                        "STA": current_sta,
                        "Elev Tanah": round(z_ground, 3),
                        "Elev Muka Air": round(ws_elev, 3),
                        "Tinggi Air (h)": round(yn, 3),
                        "Keterangan": drop_note
                    })
                    
                    if current_sta == sta_end: break
                    current_sta += 25
                    if current_sta > sta_end: current_sta = sta_end

            df_recap = pd.DataFrame(recap_list)
            df_detail = pd.DataFrame(detail_list)
            
            st.session_state['results_recap'] = df_recap
            st.session_state['results_detail'] = df_detail
            
            st.success("✅ Perhitungan Selesai! Data sudah dibersihkan dan dihitung.")

# --- TAB 4: GRAFIK ---
with tab4:
    if 'results_detail' in st.session_state:
        df_det = st.session_state['results_detail']
        
        st.subheader("Long Section (Profil Memanjang)")
        fig, ax = plt.subplots(figsize=(15, 6))
        ax.plot(df_det['STA'], df_det['Elev Tanah'], label='Elevasi Dasar', color='brown', linewidth=2)
        ax.plot(df_det['STA'], df_det['Elev Muka Air'], label='Muka Air', color='blue', linewidth=1.5)
        
        ax.set_xlabel("Station (m)")
        ax.set_ylabel("Elevation (m)")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)
        st.pyplot(fig)
    else:
        st.info("Jalankan analisa di Tab 3 dulu.")

# --- TAB 5: LAPORAN ---
with tab5:
    st.subheader("📑 Laporan Hasil Desain")
    
    if 'results_recap' in st.session_state and 'results_detail' in st.session_state:
        df_recap = st.session_state['results_recap']
        df_detail = st.session_state['results_detail']
        
        st.write("### 1. Analisa Hidrolika")
        st.dataframe(df_recap.style.applymap(lambda v: 'color: red;' if 'Super' in str(v) else ('color: orange;' if 'Kritis' in str(v) else 'color: green;'), subset=['Status']))
        
        st.write("### 2. Detail Data")
        st.dataframe(df_detail)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_recap.to_excel(writer, sheet_name='ANALISA_HIDROLIKA', index=False)
            df_detail.to_excel(writer, sheet_name='DETAIL_STA_25', index=False)
            
        output.seek(0)
        
        st.download_button(
            label="📥 Download Excel (LENGKAP)",
            data=output,
            file_name="HASIL_DESAIN_PROFESIONAL.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ Belum ada hasil.")
