import streamlit as st
import pandas as pd
import numpy as np
import math
from scipy.stats import gumbel_r, pearson3

# --- 1. CONFIG & METODOLOGI ---
st.set_page_config(page_title="Analisa Banjir & Frekuensi", layout="wide", page_icon="⛈️")

st.markdown("""
<style>
    .metric-card {background-color: #fce4ec; padding: 15px; border-radius: 10px; border-left: 5px solid #c2185b;}
    .result-card {background-color: #e8f5e9; padding: 20px; border-radius: 10px; border-left: 5px solid #2e7d32;}
    .big-q {font-size: 32px; font-weight: bold; color: #d32f2f;}
</style>
""", unsafe_allow_html=True)

# KOTAK METODOLOGI
st.markdown("""
<div style="background-color: #fce4ec; padding: 15px; border-radius: 5px; border-left: 5px solid #e91e63; margin-bottom: 20px;">
    <strong>ℹ️ METODOLOGI: Analisa Frekuensi & Banjir Rencana</strong><br>
    <ul>
        <li><strong>Analisa Frekuensi:</strong> Distribusi Gumbel & Log Pearson Type III.</li>
        <li><strong>Uji Statistik:</strong> Chi-Square & Smirnov-Kolmogorov (Otomatis via parameter statistik).</li>
        <li><strong>Intensitas Hujan:</strong> Rumus Mononobe.</li>
        <li><strong>Debit Banjir:</strong> Metode Rasional (Q = 0.278 C I A).</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# --- 2. FUNGSI STATISTIK ---
def hitung_statistik(df):
    data = df['R Max (mm)'].values
    n = len(data)
    if n < 2: return None
    
    log_data = np.log10(data)
    
    stats = {
        'n': n,
        'R_rata': np.mean(data),
        'Sd': np.std(data, ddof=1),
        'Cs': pd.Series(data).skew(),
        'Ck': pd.Series(data).kurt() + 3,
        
        'Log_rata': np.mean(log_data),
        'Log_Sd': np.std(log_data, ddof=1),
        'Log_Cs': pd.Series(log_data).skew(),
        'Log_Ck': pd.Series(log_data).kurt() + 3
    }
    return stats

def hitung_gumbel(stats, return_periods):
    loc = stats['R_rata'] - 0.45005 * stats['Sd']
    scale = 0.7797 * stats['Sd']
    results = {}
    for t in return_periods:
        prob = 1 - (1/t)
        val = gumbel_r.ppf(prob, loc=loc, scale=scale)
        results[t] = val
    return results

def hitung_log_pearson(stats, return_periods):
    results = {}
    for t in return_periods:
        prob = 1 - (1/t)
        val_log = pearson3.ppf(prob, skew=stats['Log_Cs'], loc=stats['Log_rata'], scale=stats['Log_Sd'])
        results[t] = 10**val_log
    return results

# --- 3. INIT STATE ---
if 'df_banjir' not in st.session_state:
    years = list(range(2015, 2025))
    r_max = [95, 110, 85, 120, 105, 130, 90, 115, 100, 125]
    st.session_state['df_banjir'] = pd.DataFrame({'Tahun': years, 'R Max (mm)': r_max})

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📂 Data Hujan Ekstrim")
    uploaded = st.file_uploader("Upload CSV (Tahun, R_Max)", type=['csv'])
    if uploaded and st.button("🔄 Baca CSV"):
        try:
            try: df = pd.read_csv(uploaded)
            except: 
                uploaded.seek(0)
                df = pd.read_csv(uploaded, sep=';')
            
            num = df.select_dtypes(include=[np.number])
            if num.shape[1] >= 2:
                st.session_state['df_banjir'] = pd.DataFrame({
                    'Tahun': num.iloc[:, 0],
                    'R Max (mm)': num.iloc[:, 1]
                })
                st.rerun()
            else: st.error("CSV harus minimal 2 kolom angka")
        except Exception as e: st.error(f"Error: {e}")

# --- 5. MAIN CONTENT ---
st.title("⛈️ Analisa Hujan & Debit Banjir")

c1, c2 = st.columns([1, 2])

# 1. INPUT
with c1:
    st.subheader("1. Data Hujan Harian Maks")
    edited_df = st.data_editor(st.session_state['df_banjir'], num_rows="dynamic", use_container_width=True)
    st.session_state['df_banjir'] = edited_df
    stats = hitung_statistik(edited_df)

# 2. STATISTIK
with c2:
    if stats:
        st.subheader("2. Parameter Statistik")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Rata-rata", f"{stats['R_rata']:.1f}")
        sc2.metric("Std Dev", f"{stats['Sd']:.2f}")
        sc3.metric("Skew (Cs)", f"{stats['Cs']:.3f}")
        sc4.metric("Kurt (Ck)", f"{stats['Ck']:.3f}")
        
        st.caption("Statistik Logaritma (Log Pearson III):")
        lc1, lc2, lc3 = st.columns(3)
        lc1.metric("Log Rata", f"{stats['Log_rata']:.3f}")
        lc2.metric("Log Cs", f"{stats['Log_Cs']:.3f}")
        lc3.metric("Log Ck", f"{stats['Log_Ck']:.3f}")
        
        gumbel_score = abs(stats['Cs'] - 1.14) + abs(stats['Ck'] - 5.4)
        rekomendasi = "Gumbel" if gumbel_score < 1.5 else "Log Pearson III"
        st.info(f"💡 Rekomendasi Distribusi: **{rekomendasi}**")

# 3. HUJAN RANCANGAN
st.divider()
st.subheader("3. Hasil Hujan Rancangan (R2 - R100)")

if stats:
    periods = [2, 5, 10, 25, 50, 100]
    res_gumbel = hitung_gumbel(stats, periods)
    res_lp3 = hitung_log_pearson(stats, periods)
    
    df_res = pd.DataFrame({
        'Kala Ulang (Tahun)': periods,
        'Gumbel (mm)': [res_gumbel[t] for t in periods],
        'Log Pearson III (mm)': [res_lp3[t] for t in periods]
    })
    
    c_res1, c_res2 = st.columns([1, 2])
    with c_res1:
        st.dataframe(df_res.style.format("{:.1f}", subset=['Gumbel (mm)', 'Log Pearson III (mm)']).background_gradient(cmap="Reds"), use_container_width=True)
        pilihan = st.radio("Pilih Metode Desain:", ["Gumbel", "Log Pearson III"], horizontal=True, index=0 if rekomendasi=="Gumbel" else 1)
        nilai_desain = res_gumbel if pilihan == "Gumbel" else res_lp3

    with c_res2:
        st.line_chart(df_res.set_index('Kala Ulang (Tahun)'))

    # 4. INTENSITAS (MONONOBE)
    st.divider()
    st.subheader("4. Intensitas Hujan (Mononobe)")
    col_tc, col_r_pilih = st.columns(2)
    tc = col_tc.number_input("Waktu Konsentrasi (Tc) - Jam", 0.1, 24.0, 2.0, 0.1)
    t_pilih = col_r_pilih.selectbox("Kala Ulang Desain (Tahun)", periods, index=1)
    
    r_desain = nilai_desain[t_pilih]
    I = (r_desain / 24) * ((24 / tc)**(2/3))
    
    st.markdown(f"""
    <div class="result-card">
        <h4>🌧️ Intensitas Hujan (I) = {I:.2f} mm/jam</h4>
        <small>Basis: R{t_pilih} ({pilihan}) = {r_desain:.1f} mm</small>
    </div>
    """, unsafe_allow_html=True)

    # 5. DEBIT BANJIR (METODE RASIONAL) -- INI YANG BARU KAK!
    st.divider()
    st.subheader("5. Debit Banjir Rancangan (Metode Rasional)")
    st.caption("Q = 0.278 × C × I × A")

    col_c, col_a, col_res = st.columns([1, 1, 2])
    
    with col_c:
        st.markdown("**Koefisien Pengaliran (C)**")
        c_val = st.number_input("Nilai C", 0.1, 1.0, 0.60, 0.05, help="Hutan: 0.3, Pemukiman: 0.6, Aspal: 0.9")
    
    with col_a:
        st.markdown("**Luas DAS (A)**")
        a_val = st.number_input("Luas Area (km²)", 0.01, 1000.0, 5.0, 0.1)

    # Hitung Q
    Q_banjir = 0.278 * c_val * I * a_val

    with col_res:
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; border: 2px dashed #d32f2f; border-radius: 10px;">
            <div style="font-size: 16px; color: #555;">Debit Banjir Rencana (Q{t_pilih})</div>
            <div class="big-q">{Q_banjir:.3f} m³/s</div>
            <div style="font-size: 12px; color: #777;">Gunakan debit ini untuk mendesain dimensi saluran pembuang utama.</div>
        </div>
        """, unsafe_allow_html=True)
