import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import math

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Analisa Banjir & Frekuensi", layout="wide", page_icon="⛈️")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #37474f 0%, #546e7a 50%, #78909c 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-weight: bold; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">⛈️ Analisa Frekuensi & Banjir</h1>
    <p style="opacity: 0.9;">Analisa Kala Ulang (Return Period) 2, 5, 10, 25, 50, 100 Tahun</p>
</div>
""", unsafe_allow_html=True)

# --- 3. FUNGSI ENGINE HIDROLOGI ---

# A. Analisa Frekuensi (Metode Gumbel Tipe I)
def analisa_gumbel(df_hujan):
    # Data
    data = df_hujan['R_max (mm)'].values
    n = len(data)
    if n < 2: return None # Data kurang
    
    # Statistik Dasar
    rata = np.mean(data)
    std = np.std(data, ddof=1) # Standar Deviasi Sampel
    
    # Parameter Gumbel (Yn & Sn - Simplified approximation for code without lookup table)
    # Pendekatan rumus Yn dan Sn berdasarkan jumlah data (n)
    # Sumber: Tabel Gumbel (Approximation)
    yt_dict = {
        2: 0.3665, 5: 1.4999, 10: 2.2502, 25: 3.1985, 50: 3.9019, 100: 4.6001
    }
    
    # Sn & Yn (Approximation logic or Lookup)
    # Agar akurat kita pakai rumus regresi sederhana untuk Sn Yn berdasarkan N
    # Atau pakai nilai standar N=10 s/d 100
    yn = -0.5772 - np.log(np.log(n/(n-1))) # Approximation basic Euler
    # Lebih baik pakai Hardcoded tabel umum Indonesia (Subarkah) untuk N=10-20
    # Kita pakai pendekatan N=15 (Rata-rata data proyek) jika tabel tidak lengkap, 
    # TAPI agar scientific, kita hitung exact Gumbel Formula: X_T = X_bar + K * S
    
    # K = (Yt - Yn) / Sn
    # Yt = -ln(-ln((T-1)/T))
    
    # Tabel Yn Sn Standard (Source: Soewarno)
    gumbel_table = {
        10: (0.4952, 0.9497), 11: (0.4996, 0.9676), 12: (0.5035, 0.9833),
        13: (0.5070, 0.9971), 14: (0.5100, 1.0095), 15: (0.5128, 1.0206),
        16: (0.5157, 1.0316), 17: (0.5181, 1.0411), 18: (0.5202, 1.0493),
        19: (0.5220, 1.0565), 20: (0.5236, 1.0628), 25: (0.5309, 1.0915),
        30: (0.5362, 1.1124), 100: (0.5600, 1.2065)
    }
    
    # Cari N terdekat
    closest_n = min(gumbel_table.keys(), key=lambda k: abs(k-n))
    yn_val, sn_val = gumbel_table[closest_n]
    
    kala_ulang = [2, 5, 10, 25, 50, 100]
    hasil_hujan = {}
    
    for t in kala_ulang:
        yt = -np.log(-np.log((t-1)/t))
        k = (yt - yn_val) / sn_val
        xt = rata + k * std
        hasil_hujan[t] = xt
        
    return hasil_hujan, rata, std

# B. Rumus Banjir (Rasional, Haspers, Weduwen)
def hitung_banjir_all(A, L, H, R24, C):
    S = H / (L * 1000)
    if S <= 0: S = 0.001
    
    # 1. Rasional
    tc_ras = 0.06628 * (L**0.77) / (S**0.385)
    i_ras = (R24 / 24) * ((24 / tc_ras)**(2/3))
    q_ras = 0.278 * C * i_ras * A
    
    # 2. Haspers
    t_has = 0.1 * (L**0.8) * (S**-0.3)
    i_has = (R24 / 24) * ((24 / t_has)**(2/3))
    q_has = 0.278 * C * i_has * A
    
    # 3. Weduwen
    t_wed = 0.06628 * (L**0.77) / (S**0.385) # Simplify
    i_wed = (R24 / 24) * ((24 / t_wed)**(2/3))
    q_wed = 0.278 * C * 1.0 * i_wed * A # Beta=1
    
    return q_ras, q_has, q_wed

# --- 4. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("⛰️ Parameter DAS")
    luas_das = st.number_input("Luas DAS (A) [km²]", value=15.5, min_value=0.1)
    panjang_sungai = st.number_input("Panjang Sungai (L) [km]", value=6.5, min_value=0.1)
    beda_tinggi = st.number_input("Beda Tinggi (H) [m]", value=120.0, min_value=1.0)
    koef_c = st.slider("Koefisien Pengaliran (C)", 0.1, 0.95, 0.60)
    
    st.divider()
    mode_input = st.radio("Sumber Data Hujan:", ["💾 Punya Data Series (10 Thn)", "✏️ Input Manual Rencana"])

# --- 5. MAIN CONTENT ---

# --- LOGIKA 1: JIKA PUNYA DATA SERIES (ANALISA FREKUENSI) ---
if mode_input == "💾 Punya Data Series (10 Thn)":
    st.subheader("1. Analisa Frekuensi Hujan (Metode Gumbel)")
    
    col_input, col_result = st.columns([1, 1.5])
    
    with col_input:
        st.info("Masukkan Data Hujan Harian Maksimum Tahunan (Min. 10 Tahun).")
        
        # Template Data 10 Tahun
        if 'df_hujan_series' not in st.session_state:
            years = list(range(2015, 2025))
            # Data dummy acak normal
            r_vals = [90, 110, 85, 150, 95, 120, 135, 100, 180, 115]
            st.session_state.df_hujan_series = pd.DataFrame({'Tahun': years, 'R_max (mm)': r_vals})
            
        edited_hujan = st.data_editor(
            st.session_state.df_hujan_series, 
            num_rows="dynamic", 
            use_container_width=True,
            key="editor_hujan_series"
        )
        st.session_state.df_hujan_series = edited_hujan
        
    with col_result:
        # Lakukan Analisa Gumbel
        hasil_gumbel, rata, std = analisa_gumbel(edited_hujan)
        
        if hasil_gumbel:
            st.write("#### 📊 Hasil Probabilitas Hujan")
            st.caption(f"Statistik: Mean = {rata:.1f} mm | StdDev = {std:.1f}")
            
            # Buat DataFrame Hasil Hujan Rencana
            df_r_plan = pd.DataFrame.from_dict(hasil_gumbel, orient='index', columns=['Rencana Hujan (mm)'])
            df_r_plan.index.name = 'Kala Ulang (Tahun)'
            
            st.dataframe(df_r_plan.style.format("{:.1f}"), use_container_width=True)
            
            # Gunakan hasil ini untuk perhitungan banjir
            r_dict = hasil_gumbel
        else:
            st.error("Data kurang! Masukkan minimal 2 tahun data.")
            r_dict = None

# --- LOGIKA 2: INPUT MANUAL RENCANA (JIKA TIDAK ADA DATA) ---
else:
    st.subheader("1. Input Hujan Rencana Manual")
    st.info("Masukkan nilai hujan rencana yang sudah dihitung sebelumnya.")
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    r2 = c1.number_input("R2 th", value=100.0)
    r5 = c2.number_input("R5 th", value=125.0)
    r10 = c3.number_input("R10 th", value=150.0)
    r25 = c4.number_input("R25 th", value=175.0)
    r50 = c5.number_input("R50 th", value=200.0)
    r100 = c6.number_input("R100 th", value=225.0)
    
    r_dict = {2: r2, 5: r5, 10: r10, 25: r25, 50: r50, 100: r100}

# --- 6. HITUNG DEBIT BANJIR (MULTI KALA ULANG) ---
st.divider()
st.subheader("2. Rekapitulasi Debit Banjir (Q2 - Q100)")

if r_dict:
    rekap_banjir = []
    
    for t, r_val in r_dict.items():
        q_r, q_h, q_w = hitung_banjir_all(luas_das, panjang_sungai, beda_tinggi, r_val, koef_c)
        q_max = max(q_r, q_h, q_w)
        
        rekap_banjir.append({
            'Kala Ulang (T)': f"{t} Tahun",
            'Hujan Rencana (mm)': round(r_val, 1),
            'Q Rasional': round(q_r, 2),
            'Q Haspers': round(q_h, 2),
            'Q Weduwen': round(q_w, 2),
            'Q Desain (Max)': round(q_max, 2)
        })
        
    df_rekap = pd.DataFrame(rekap_banjir)
    
    # Tampilkan Tabel
    st.dataframe(
        df_rekap.style.highlight_max(subset=['Q Desain (Max)'], color='#e8f5e9', axis=0),
        use_container_width=True
    )
    
    # --- 7. GRAFIK LOGARITMIK (KURVA LENGKUNG FREKUENSI) ---
    st.write("### 📈 Grafik Lengkung Frekuensi Banjir")
    
    # Prepare data for Altair
    df_chart = df_rekap.melt('Kala Ulang (T)', measure_vars=['Q Rasional', 'Q Haspers', 'Q Weduwen'], 
                             var_name='Metode', value_name='Debit (m3/s)')
    
    chart = alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X('Kala Ulang (T)', sort=['2 Tahun', '5 Tahun', '10 Tahun', '25 Tahun', '50 Tahun', '100 Tahun']),
        y='Debit (m3/s)',
        color='Metode',
        tooltip=['Kala Ulang (T)', 'Metode', 'Debit (m3/s)']
    ).properties(height=400)
    
    st.altair_chart(chart, use_container_width=True)

    # --- 8. SIMPAN DATA (PILIH KALA ULANG) ---
    st.divider()
    col_save1, col_save2 = st.columns([2, 1])
    with col_save1:
        st.write("#### 💾 Simpan Debit Desain")
        pilih_t = st.selectbox("Pilih Kala Ulang untuk Desain Saluran:", [2, 5, 10, 25, 50, 100], index=3)
        
        # Ambil nilai Q Max pada T terpilih
        q_selected = df_rekap[df_rekap['Kala Ulang (T)'] == f"{pilih_t} Tahun"]['Q Desain (Max)'].values[0]
        st.caption(f"Debit Banjir Q{pilih_t} = **{q_selected} m³/s** akan disimpan untuk cek keamanan.")
        
    with col_save2:
        st.write("") # Spacer
        st.write("")
        if st.button("🚀 Simpan Debit Terpilih", type="primary", use_container_width=True):
            st.session_state['debit_banjir_global'] = float(q_selected)
            st.toast(f"Debit Q{pilih_t} ({q_selected} m³/s) Tersimpan!", icon="✅")

else:
    st.warning("Silakan lengkapi data hujan terlebih dahulu.")
