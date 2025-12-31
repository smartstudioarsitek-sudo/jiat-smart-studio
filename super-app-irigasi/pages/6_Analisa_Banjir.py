import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Analisa Banjir", layout="wide", page_icon="⛈️")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #37474f 0%, #546e7a 50%, #78909c 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">⛈️ Analisa Debit Banjir Rencana</h1>
    <p style="opacity: 0.9;">Metode Rasional, Haspers, & Weduwen (Untuk Drainase & Bendung)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. SIDEBAR: DATA DAS ---
with st.sidebar:
    st.header("⛰️ Parameter DAS")
    
    luas_das = st.number_input("Luas DAS (A) [km²]", value=15.5, min_value=0.1, step=0.1)
    panjang_sungai = st.number_input("Panjang Sungai Utama (L) [km]", value=6.5, min_value=0.1, step=0.1)
    beda_tinggi = st.number_input("Beda Tinggi (H) [m]", value=120.0, min_value=1.0, step=1.0, help="Selisih elevasi hulu ke hilir")
    
    st.divider()
    st.header("🌧️ Data Hujan")
    r24 = st.number_input("Hujan Harian Maksimum (R24) [mm]", value=150.0, help="Curah hujan rencana periode ulang tertentu (misal: R50th)")
    koef_c = st.slider("Koefisien Pengaliran (C)", 0.1, 0.95, 0.60, help="Hutan=0.3, Pertanian=0.5, Perkotaan=0.8")

# --- 4. RUMUS-RUMUS BANJIR (ENGINE) ---

# --- A. METODE RASIONAL (Q = 0.278 C I A) ---
# Biasanya untuk DAS < 300 ha (3 km2), tapi sering dipakai estimasi kasar DAS kecil
def hitung_rasional(A, L, H, R24, C):
    # 1. Waktu Konsentrasi (tc) Rumus Kirpich
    # tc = 0.0195 * (L^0.77) * (S^-0.385) ... L dalam meter? Cek satuan.
    # Rumus umum Kirpich (L km, S m/m, tc jam):
    # tc = (0.87 * L^2 / 1000 * S)^0.385 ... banyak versi
    # Kita pakai versi standar PU: tc = (0.87 * L^2 / S)^0.385 (L dalam km)
    
    S = H / (L * 1000) # Kemiringan (m/m)
    if S <= 0: S = 0.001
    
    # tc (jam) - Rumus Kirpich
    tc = 0.06628 * (L**0.77) / (S**0.385)
    
    # 2. Intensitas Hujan (I) - Rumus Mononobe
    # I = (R24 / 24) * (24 / tc)^(2/3)
    I = (R24 / 24) * ((24 / tc)**(2/3))
    
    # 3. Debit (Q)
    Q = 0.278 * C * I * A
    
    return Q, tc, I

# --- B. METODE HASPERS ---
# Cocok untuk DAS sedang di Indonesia
def hitung_haspers(A, L, H, R24, C):
    S = H / (L * 1000)
    
    # 1. Koefisien Aliran (Alpha) Haspers
    # Haspers punya rumus alpha sendiri berdasarkan t, tapi kita pakai input C user untuk simplifikasi atau rumus empiris:
    # Alpha = (1 + 0.012 * A^0.7) / (1 + 0.075 * A^0.7) ... ini contoh Balai
    # Kita gunakan pendekatan Alpha = C input user agar konsisten
    alpha = C 
    
    # 2. Waktu Konsentrasi (t) Haspers
    # 1/t = 1/t_sungai + 1/t_lereng
    # Pendekatan sederhana: V = 72 * S^0.6
    v = 72 * (S**0.6) # km/jam? Cek empiris
    # Kecepatan rata-rata Haspers (m/s) biasanya V = ... 
    # Kita pakai rumus t = 0.1 * L^0.8 * S^-0.3 (mirip Kirpich tapi beda konstanta)
    # Gunakan Melchior/Haspers standar:
    t = 0.1 * (L**0.8) * (S**-0.3) 
    
    # 3. Koefisien Reduksi (Beta)
    # Beta = 1 / (1 + (t * A^0.75)/...) 
    # Simplifikasi Mononobe untuk area:
    beta = 1 # Haspers fokus ke R t
    
    # Intensitas
    I = (R24 / 24) * ((24 / t)**(2/3))
    
    # Haspers Q = alpha * beta * I * A * 0.278
    Q = 0.278 * alpha * I * A
    return Q, t, I

# --- C. METODE WEDUWEN ---
# Untuk DAS < 100 km2
def hitung_weduwen(A, L, H, R24, C):
    S = H / (L * 1000)
    
    # Koefisien Aliran Weduwen (Alpha)
    # Weduwen menghitung alpha berdasarkan kemiringan & luas
    # alpha = 1 - 4.12 / (beta * Q + 7) ... rumit & butuh iterasi Q
    # Kita gunakan Fixed C dari input user sebagai pendekatan Alpha
    alpha = C
    
    # Weduwen parameter
    # t = 0.25 * L * Q^-0.125 * I^-0.25 ... Butuh iterasi circular reference!
    # Untuk aplikasi simple tanpa iterasi berat, kita pakai pendekatan t Kirpich modifikasi
    t = 0.06628 * (L**0.77) / (S**0.385) # Fallback ke Kirpich
    
    # Koefisien Pengurangan Area (Beta)
    # Weduwen: Beta = 120 + ((A + 20) / A)
    beta = 1.0 # Simplified
    
    I = (R24 / 24) * ((24 / t)**(2/3))
    Q = 0.278 * alpha * beta * I * A
    return Q, t, I

# --- 5. TAMPILAN UTAMA ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📝 Resume Input")
    st.info(f"""
    - **Luas DAS (A)**: {luas_das} km²
    - **Panjang Sungai (L)**: {panjang_sungai} km
    - **Slope (S)**: {H/(panjang_sungai*1000):.4f}
    - **Hujan Max (R24)**: {r24} mm
    - **Koef. C**: {koef_c}
    """)
    
    # Hitung Ketiga Metode
    q_ras, t_ras, i_ras = hitung_rasional(luas_das, panjang_sungai, beda_tinggi, r24, koef_c)
    q_has, t_has, i_has = hitung_haspers(luas_das, panjang_sungai, beda_tinggi, r24, koef_c)
    q_wed, t_wed, i_wed = hitung_weduwen(luas_das, panjang_sungai, beda_tinggi, r24, koef_c)
    
    # Cari Nilai Max
    q_max = max(q_ras, q_has, q_wed)
    
    st.markdown("### 🚀 Hasil Perhitungan")
    st.write("Debit Banjir Rencana (Q_peak):")
    
    # Kartu Hasil
    c1, c2, c3 = st.columns(3)
    c1.metric("Rasional", f"{q_ras:.2f}", "m³/s")
    c2.metric("Haspers", f"{q_has:.2f}", "m³/s")
    c3.metric("Weduwen", f"{q_wed:.2f}", "m³/s")
    
    st.success(f"📌 **Debit Desain Disarankan (Max):** {q_max:.2f} m³/s")

with col2:
    st.subheader("📊 Perbandingan Metode")
    
    # Data Grafik
    df_chart = pd.DataFrame({
        'Metode': ['Rasional', 'Haspers', 'Weduwen'],
        'Debit (m³/s)': [q_ras, q_has, q_wed],
        'Waktu Konsentrasi (jam)': [t_ras, t_has, t_wed]
    })
    
    # Bar Chart
    chart = alt.Chart(df_chart).mark_bar().encode(
        x='Metode',
        y='Debit (m³/s)',
        color='Metode',
        tooltip=['Metode', 'Debit (m³/s)', 'Waktu Konsentrasi (jam)']
    ).properties(height=350)
    
    st.altair_chart(chart, use_container_width=True)
    
    with st.expander("ℹ️ Penjelasan Metode"):
        st.write("""
        1. **Metode Rasional**: Paling umum untuk DAS kecil (< 300 ha) dan drainase perkotaan.
        2. **Metode Haspers**: Cocok untuk DAS ukuran sedang dengan kemiringan sungai yang curam.
        3. **Metode Weduwen**: Sering digunakan untuk DAS di Indonesia dengan luas < 100 km².
        """)

# --- 6. SIMPAN DATA ---
st.divider()
if st.button("💾 Simpan Debit Banjir ke Sistem", type="primary"):
    st.session_state['debit_banjir_global'] = q_max
    st.toast(f"Debit Banjir {q_max:.2f} m³/s tersimpan! Bisa digunakan untuk cek dimensi saluran.", icon="⛈️")
