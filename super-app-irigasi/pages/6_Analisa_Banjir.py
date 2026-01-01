import streamlit as st
import pandas as pd
import numpy as np
import math
from scipy.stats import gumbel_r, pearson3

# --- CONFIG ---
st.set_page_config(page_title="Analisa Banjir & Frekuensi", layout="wide", page_icon="⛈️")

st.markdown("""
<style>
    .metric-card {background-color: #fce4ec; padding: 15px; border-radius: 10px; border-left: 5px solid #c2185b;}
    .result-card {background-color: #e8f5e9; padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32;}
</style>
""", unsafe_allow_html=True)

# --- FUNGSI STATISTIK ---
def hitung_statistik(df):
    data = df['R Max (mm)'].values
    n = len(data)
    if n < 2: return None
    
    # Logaritma untuk Log Pearson
    log_data = np.log10(data)
    
    stats = {
        'n': n,
        'R_rata': np.mean(data),
        'Sd': np.std(data, ddof=1),
        'Cs': pd.Series(data).skew(),
        'Ck': pd.Series(data).kurt() + 3, # Pandas kurtosis is Fisher's (normal=0), we want Pearson's (normal=3)
        
        # Statistik Log
        'Log_rata': np.mean(log_data),
        'Log_Sd': np.std(log_data, ddof=1),
        'Log_Cs': pd.Series(log_data).skew(),
        'Log_Ck': pd.Series(log_data).kurt() + 3
    }
    return stats

# --- FUNGSI DISTRIBUSI ---
def hitung_gumbel(stats, return_periods):
    # Reduced variate (Yt) and mean/std of reduced variate (Yn, Sn) approx
    n = stats['n']
    # Tabel pendekatan untuk Yn dan Sn (Simplified for dynamic n)
    # Di real app, sebaiknya pakai tabel lengkap atau rumus pendekatan
    Yn = 0.577 # Euler constant approx for large n, or dynamic lookup
    Sn = 1.2825 / np.sqrt(1) # Rough approx, better use library or lookup table
    
    # Using scipy for precision
    loc = stats['R_rata'] - 0.45005 * stats['Sd']
    scale = 0.7797 * stats['Sd']
    
    results = {}
    for t in return_periods:
        # Xt = Mean + K * Sd
        # K_gumbel = (Yt - Yn) / Sn
        # Scipy ppf is inverse cdf
        prob = 1 - (1/t)
        val = gumbel_r.ppf(prob, loc=loc, scale=scale)
        results[t] = val
    return results

def hitung_log_pearson(stats, return_periods):
    results = {}
    for t in return_periods:
        prob = 1 - (1/t)
        # K untuk Log Pearson III (Tergantung Cs)
        # Menggunakan pendekatan Scipy Pearson3 (Skewed Normal)
        # Pearson3 in scipy is standardized. 
        # R_log = Mean_log + K * Sd_log
        
        # Scipy pearson3 arguments: skew, loc, scale
        # Warning: Scipy pearson3 definition might differ slightly in sign of skew
        val_log = pearson3.ppf(prob, skew=stats['Log_Cs'], loc=stats['Log_rata'], scale=stats['Log_Sd'])
        results[t] = 10**val_log
    return results

# --- INIT STATE ---
if 'df_banjir' not in st.session_state:
    # Dummy Data: Hujan Harian Maksimum 10 Tahun Terakhir
    years = list(range(2015, 2025))
    r_max = [95, 110, 85, 120, 105, 130, 90, 115, 100, 125]
    st.session_state['df_banjir'] = pd.DataFrame({'Tahun': years, 'R Max (mm)': r_max})

# --- SIDEBAR ---
with st.sidebar:
    st.title("📂 Data Hujan Ekstrim")
    st.caption("Input data curah hujan harian maksimum tahunan.")
    
    # Template CSV
    df_temp = pd.DataFrame({'Tahun': [2020, 2021], 'R_Max': [100, 120]})
    st.download_button("📥 Template CSV", df_temp.to_csv(index=False).encode('utf-8'), "template_banjir.csv", "text/csv")
    
    uploaded = st.file_uploader("Upload CSV", type=['csv'])
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
            else: st.error("CSV harus minimal 2 kolom angka (Tahun, R Max)")
        except Exception as e: st.error(f"Error: {e}")

# --- MAIN CONTENT ---
st.title("⛈️ Analisa Hujan Rancangan")
st.info(f"**Proyek:** {st.session_state.get('nama_proyek', '-')} | Mode: Analisa Frekuensi")

c1, c2 = st.columns([1, 2])

# 1. INPUT DATA
with c1:
    st.subheader("1. Data Hujan Harian Maks")
    edited_df = st.data_editor(st.session_state['df_banjir'], num_rows="dynamic", use_container_width=True)
    st.session_state['df_banjir'] = edited_df
    
    # Hitung Statistik
    stats = hitung_statistik(edited_df)

# 2. ANALISA STATISTIK
with c2:
    if stats:
        st.subheader("2. Parameter Statistik")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Rata-rata", f"{stats['R_rata']:.1f}")
        sc2.metric("Std Dev (Sd)", f"{stats['Sd']:.2f}")
        sc3.metric("Skew (Cs)", f"{stats['Cs']:.3f}")
        sc4.metric("Kurt (Ck)", f"{stats['Ck']:.3f}")
        
        st.markdown("---")
        st.caption("Statistik Logaritma (Untuk Log Pearson III):")
        lc1, lc2, lc3 = st.columns(3)
        lc1.metric("Log Rata", f"{stats['Log_rata']:.3f}")
        lc2.metric("Log Cs (G)", f"{stats['Log_Cs']:.3f}")
        lc3.metric("Log Ck", f"{stats['Log_Ck']:.3f}")
        
        # REKOMENDASI METODE
        # Syarat Gumbel: Cs ≈ 1.14, Ck ≈ 5.4
        # Syarat Log Pearson: Cs bebas (tapi biasanya Log Cs mendekati 0 untuk Log Normal)
        
        gumbel_score = abs(stats['Cs'] - 1.14) + abs(stats['Ck'] - 5.4)
        # Simple logic: kalau jauh dari syarat Gumbel, sarankan Log Pearson
        rekomendasi = "Gumbel" if gumbel_score < 1.5 else "Log Pearson III"
        
        st.markdown(f"""
        <div class="metric-card">
            <b>💡 Rekomendasi Distribusi:</b> {rekomendasi}<br>
            <small>Berdasarkan nilai Cs dan Ck data Anda.</small>
        </div>
        """, unsafe_allow_html=True)

# 3. HASIL HUJAN RANCANGAN
st.divider()
st.subheader("3. Hasil Hujan Rancangan (R2 - R100)")

if stats:
    periods = [2, 5, 10, 25, 50, 100]
    
    # Hitung kedua metode
    res_gumbel = hitung_gumbel(stats, periods)
    res_lp3 = hitung_log_pearson(stats, periods)
    
    # Buat Tabel Komparasi
    df_res = pd.DataFrame({
        'Kala Ulang (Tahun)': periods,
        'Gumbel (mm)': [res_gumbel[t] for t in periods],
        'Log Pearson III (mm)': [res_lp3[t] for t in periods]
    })
    
    c_res1, c_res2 = st.columns([1, 2])
    
    with c_res1:
        st.dataframe(df_res.style.format("{:.1f}", subset=['Gumbel (mm)', 'Log Pearson III (mm)'])
                     .background_gradient(cmap="Reds"), use_container_width=True)
        
        # Pilihan Final
        pilihan = st.radio("Pilih Metode untuk Desain:", ["Gumbel", "Log Pearson III"], horizontal=True)
        nilai_desain = res_gumbel if pilihan == "Gumbel" else res_lp3
        
        # Simpan ke Session State (untuk dipakai di Desain Saluran nanti)
        st.session_state['hujan_rancangan'] = nilai_desain

    with c_res2:
        # Grafik
        chart_data = df_res.melt('Kala Ulang (Tahun)', var_name='Metode', value_name='Hujan (mm)')
        import altair as alt
        chart = alt.Chart(chart_data).mark_line(point=True).encode(
            x='Kala Ulang (Tahun):O',
            y='Hujan (mm)',
            color='Metode',
            tooltip=['Kala Ulang (Tahun)', 'Hujan (mm)', 'Metode']
        ).interactive()
        st.altair_chart(chart, use_container_width=True)

    # OUTPUT INTENSITAS
    st.markdown("---")
    st.markdown("### 4. Intensitas Hujan (Mononobe)")
    st.caption("Digunakan untuk menghitung Debit Banjir (Q = 0.278 C I A)")
    
    col_tc, col_r_pilih = st.columns(2)
    tc = col_tc.number_input("Waktu Konsentrasi (Tc) - Jam", 0.1, 24.0, 2.0, 0.1)
    t_pilih = col_r_pilih.selectbox("Kala Ulang Desain", periods, index=1) # Default 5 tahun
    
    r_desain = nilai_desain[t_pilih]
    # Rumus Mononobe: I = (R24 / 24) * (24 / Tc)^(2/3)
    I = (r_desain / 24) * ((24 / tc)**(2/3))
    
    st.markdown(f"""
    <div class="result-card">
        <h4>🌧️ Intensitas Hujan (I) = {I:.2f} mm/jam</h4>
        <ul>
            <li>Hujan Rancangan (R{t_pilih}): <b>{r_desain:.1f} mm</b></li>
            <li>Metode: <b>{pilihan}</b></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
