import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Irigasi Pipa & Pompa", layout="wide", page_icon="🚰")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #455a64 0%, #607d8b 50%, #90a4ae 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🚰 Desain Pipa & Pompa</h1>
    <p style="opacity: 0.9;">Analisa Jaringan Pipa Tekan & Kebutuhan Daya Pompa</p>
</div>
""", unsafe_allow_html=True)

# --- 3. LOGIKA LINK DATA (AUTO-DETECT) ---
# Cek NFR (Kebutuhan Air)
if 'nfr_global' in st.session_state:
    nfr_val = st.session_state['nfr_global']
    status_nfr = f"✅ Terhubung: {nfr_val} l/s/ha"
    link_nfr_ok = True
else:
    nfr_val = 1.25 # Default
    status_nfr = "⚠️ Data Hilang (Habis Reboot)"
    link_nfr_ok = False

# Cek Debit Andalan (Supply Air)
if 'data_debit_mock' in st.session_state:
    debit_list = st.session_state['data_debit_mock']
    q_andalan = np.percentile(debit_list, 20) # Q80
    status_mock = f"✅ Terhubung: {q_andalan*1000:.2f} l/s"
    link_mock_ok = True
else:
    q_andalan = 0.050 # Default 50 l/s
    status_mock = "⚠️ Data Hilang (Habis Reboot)"
    link_mock_ok = False

# --- 4. PERINGATAN REBOOT (JIKA DATA PUTUS) ---
if not link_nfr_ok or not link_mock_ok:
    st.warning("""
    ⚠️ **PERHATIAN: Koneksi Data Terputus!**
    
    Karena aplikasi baru saja di-Reboot, data dari modul sebelumnya hilang dari memori.
    Agar hasil akurat, mohon lakukan langkah ini (sekali saja):
    1. Buka **Modul 2 (Pola Tanam)** -> Klik tombol **"🚀 Kirim Data"**.
    2. Buka **Modul 3 (FJ Mock)** -> Klik tombol **"🚀 Simpan Hasil Debit"**.
    3. Kembali ke halaman ini.
    """)

# --- 5. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("⚙️ Spesifikasi Pipa")
    jenis_pipa = st.selectbox("Jenis Material", ["PVC (Plastik)", "HDPE (Hitam)", "GIP (Galvanis)", "Steel (Baja)"])
    
    if "PVC" in jenis_pipa: c_hw = 150
    elif "HDPE" in jenis_pipa: c_hw = 140
    elif "GIP" in jenis_pipa: c_hw = 120
    else: c_hw = 100
    
    st.caption(f"C-Factor: {c_hw}")
    eff_pompa = st.slider("Efisiensi Pompa (%)", 50, 90, 75) / 100
    safety_head = st.number_input("Safety Head (%)", value=10) / 100

# --- 6. INPUT DATA UTAMA ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("1. Kebutuhan & Supply Air")
    
    # Input Luas
    luas_lahan = st.number_input("Luas Lahan (ha)", value=25.0, step=0.5)
    
    # Hitung Demand
    q_demand_ls = luas_lahan * nfr_val
    q_demand_m3s = q_demand_ls / 1000
    
    st.markdown("---")
    st.write("#### 📊 Neraca Air")
    
    c_a, c_b = st.columns(2)
    c_a.metric("Kebutuhan (NFR)", f"{q_demand_ls:.2f} l/s", status_nfr)
    c_b.metric("Supply (Andalan)", f"{q_andalan*1000:.2f} l/s", status_mock)
    
    stop_calc = False
    if q_demand_m3s > q_andalan:
        st.error(f"❌ **DEFISIT!** Supply ({q_andalan*1000:.1f} l/s) < Kebutuhan ({q_demand_ls:.1f} l/s).")
        stop_calc = True
    else:
        st.success("✅ **SURPLUS.** Air cukup.")

with col2:
    st.subheader("2. Geometri Pipa")
    c1, c2 = st.columns(2)
    panjang_pipa = c1.number_input("Panjang Pipa (m)", value=500.0)
    beda_elevasi = c2.number_input("Beda Tinggi (m)", value=15.0)
    
    st.write("#### 🔧 Dimensi Pipa")
    d_inch = st.selectbox("Diameter (Inch)", [2, 3, 4, 6, 8, 10, 12], index=3)
    d_m = d_inch * 0.0254

# --- 7. HASIL PERHITUNGAN ---
if not stop_calc:
    # Hidrolika
    area = np.pi * (d_m/2)**2
    v = q_demand_m3s / area
    
    # Hazen-Williams
    hf_major = 10.67 * panjang_pipa * (q_demand_m3s**1.852) / ((c_hw**1.852) * (d_m**4.87))
    hf_minor = 0.10 * hf_major
    
    # Total Head
    tdh = beda_elevasi + hf_major + hf_minor + 10.0 # Sisa tekan 10m
    tdh_safe = tdh * (1 + safety_head)
    
    # Power
    power_kw = (9.81 * q_demand_m3s * tdh_safe) / eff_pompa
    
    st.divider()
    st.subheader("3. Hasil Desain")
    
    r1, r2, r3 = st.columns(3)
    
    # Cek Kecepatan
    if 0.3 <= v <= 2.5: 
        status_v = "✅ Ideal"
        col_v = "normal"
    else: 
        status_v = "⚠️ Kritis"
        col_v = "inverse"
        
    r1.metric("Kecepatan (V)", f"{v:.2f} m/s", status_v, delta_color=col_v)
    r2.metric("Total Head (H)", f"{tdh_safe:.1f} m", f"Losses: {hf_major+hf_minor:.1f} m")
    r3.metric("Daya Pompa", f"{power_kw:.2f} kW", f"Efisiensi {eff_pompa*100}%")
    
    # Visualisasi HGL
    st.write("#### 📈 Profil Hidrolis (HGL)")
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot([0, panjang_pipa], [0, beda_elevasi], 'k-', label='Tanah')
    ax.fill_between([0, panjang_pipa], [0, beda_elevasi], color='brown', alpha=0.3)
    
    # Garis HGL
    ax.plot([0, panjang_pipa], [tdh, beda_elevasi+10], 'b--', label='HGL (Tekanan)')
    
    ax.set_title(f"Pipa {d_inch} Inch - Q = {q_demand_ls:.1f} l/s")
    ax.set_xlabel("Jarak (m)")
    ax.set_ylabel("Elevasi (m)")
    ax.legend()
    st.pyplot(fig)
