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
    .metric-card {
        background-color: #f8f9fa; border: 1px solid #ddd; padding: 15px; border-radius: 10px; text-align: center;
    }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🚰 Desain Pipa & Pompa</h1>
    <p style="opacity: 0.9;">Analisa Jaringan Pipa Tekan & Kebutuhan Daya Pompa</p>
</div>
""", unsafe_allow_html=True)

# --- 3. AMBIL DATA DARI MODUL LAIN ---
# A. Ambil NFR (Kebutuhan)
if 'nfr_global' in st.session_state:
    nfr_val = st.session_state['nfr_global']
    status_nfr = "✅ Terhubung: Modul Pola Tanam"
else:
    nfr_val = 1.25 # Default
    status_nfr = "⚠️ Default (Belum ada data Pola Tanam)"

# B. Ambil Debit Andalan (Ketersediaan)
if 'data_debit_mock' in st.session_state:
    # Ambil Q80 (Debit Andalan probabilitas 80%) dari list debit Mock
    debit_list = st.session_state['data_debit_mock']
    q_andalan = np.percentile(debit_list, 20) # Q80 adalah persentil 20 dari data besar ke kecil
    status_mock = "✅ Terhubung: Modul FJ Mock"
else:
    q_andalan = 0.050 # Default 50 l/s
    status_mock = "⚠️ Default (Belum ada data Mock)"

# --- 4. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("⚙️ Spesifikasi Pipa")
    
    jenis_pipa = st.selectbox("Jenis Material Pipa", 
                              ["PVC (Plastik)", "HDPE (Hitam)", "GIP (Galvanis)", "Steel (Baja)"])
    
    # Tentukan C Hazen-Williams
    if "PVC" in jenis_pipa: c_hw = 150
    elif "HDPE" in jenis_pipa: c_hw = 140
    elif "GIP" in jenis_pipa: c_hw = 120
    else: c_hw = 100
    
    st.info(f"Koefisien Kekasaran (C): {c_hw}")
    
    eff_pompa = st.slider("Efisiensi Pompa (%)", 50, 90, 75) / 100
    safety_head = st.number_input("Safety Factor Head (%)", value=10) / 100

# --- 5. INPUT DATA UTAMA ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("1. Kebutuhan & Supply Air")
    
    # Input Luas Layanan
    luas_lahan = st.number_input("Luas Lahan yang Diairi (ha)", value=25.0, step=0.5)
    
    # Hitung Q Desain (Demand)
    # Q = Luas * NFR
    q_demand_ls = luas_lahan * nfr_val
    q_demand_m3s = q_demand_ls / 1000
    
    st.markdown("---")
    st.write("#### 📊 Neraca Air Sistem")
    
    # Cek Ketersediaan
    col_a, col_b = st.columns(2)
    col_a.metric("Kebutuhan (Q Desain)", f"{q_demand_ls:.2f} l/s", status_nfr)
    col_b.metric("Ketersediaan (Q Andalan)", f"{q_andalan*1000:.2f} l/s", status_mock)
    
    if q_demand_m3s > q_andalan:
        st.error(f"❌ **DEFISIT AIR!** Sumber air ({q_andalan*1000:.1f} l/s) tidak cukup untuk melayani kebutuhan ({q_demand_ls:.1f} l/s). Kurangi luas lahan atau cari sumber lain.")
        stop_calc = True
    else:
        st.success("✅ **AMAN.** Sumber air mencukupi.")
        stop_calc = False

with col2:
    st.subheader("2. Geometri Jalur Pipa")
    
    c_geo1, c_geo2 = st.columns(2)
    panjang_pipa = c_geo1.number_input("Panjang Pipa Total (m)", value=500.0)
    beda_elevasi = c_geo2.number_input("Beda Tinggi Statis (m)", value=15.0, help="Selisih tinggi antara muka air ambil dan muka air keluar.")
    
    st.write("#### 🔧 Dimensi Pipa")
    # Diameter Pipa
    # Suggest diameter based on velocity ~ 1.5 m/s
    # A = Q / V -> D = sqrt(4Q / (pi*V))
    d_suggest_m = np.sqrt(4 * q_demand_m3s / (np.pi * 1.5))
    d_suggest_inch = d_suggest_m * 39.37
    
    st.caption(f"Saran Diameter (v=1.5 m/s): {d_suggest_inch:.1f} inch")
    
    diameter_inch = st.selectbox("Pilih Diameter Pasaran (Inch)", [2, 3, 4, 6, 8, 10, 12], index=3)
    diameter_m = diameter_inch * 0.0254 # Konversi ke meter

# --- 6. ENGINE HITUNGAN HIDROLIKA ---
if not stop_calc:
    # 1. Kecepatan Aliran (Velocity Check)
    area_pipa = np.pi * (diameter_m/2)**2
    velocity = q_demand_m3s / area_pipa
    
    # 2. Head Loss Mayor (Hazen-Williams)
    # hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
    hf_major = 10.67 * panjang_pipa * (q_demand_m3s**1.852) / ((c_hw**1.852) * (diameter_m**4.87))
    
    # 3. Head Loss Minor (Asumsi 10% dari Mayor untuk fitting/belokan)
    hf_minor = 0.10 * hf_major 
    
    # 4. Total Head Dinamis (TDH)
    # TDH = H_statis + H_losses + Sisa Tekan (misal 10m untuk sprinkler)
    tekanan_sisa = 10.0 # m (Standard untuk sprinkler)
    tdh = beda_elevasi + hf_major + hf_minor + tekanan_sisa
    tdh_safe = tdh * (1 + safety_head)
    
    # 5. Daya Pompa (Power)
    # P (kW) = (rho * g * Q * H) / (eff * 1000)
    # rho*g = 9.81 kN/m3
    power_kw = (9.81 * q_demand_m3s * tdh_safe) / eff_pompa
    power_hp = power_kw * 1.341
    
    # --- 7. TAMPILAN HASIL ---
    st.divider()
    st.subheader("3. Hasil Desain & Rekomendasi Pompa")
    
    # -- Row 1: Indikator Kinerja Pipa --
    col_res1, col_res2, col_res3 = st.columns(3)
    
    with col_res1:
        st.markdown("**Kecepatan Aliran (V)**")
        if 0.3 <= velocity <= 2.5:
            st.metric("Velocity", f"{velocity:.2f} m/s", "✅ Ideal")
        elif velocity < 0.3:
            st.metric("Velocity", f"{velocity:.2f} m/s", "⚠️ Terlalu Lambat (Endapan)", delta_color="inverse")
        else:
            st.metric("Velocity", f"{velocity:.2f} m/s", "⛔ Terlalu Cepat (Erosi)", delta_color="inverse")
            
    with col_res2:
        st.markdown("**Total Head Loss (Hf)**")
        st.metric("Gesekan Pipa", f"{hf_major+hf_minor:.2f} m")
        
    with col_res3:
        st.markdown("**Total Head Pompa (TDH)**")
        st.metric("Head Desain", f"{tdh_safe:.2f} m", help=f"Termasuk Safety {int(safety_head*100)}% + Sisa Tekan {tekanan_sisa}m")

    # -- Row 2: Spesifikasi Pompa --
    st.info(f"""
    ⚡ **REKOMENDASI SPESIFIKASI POMPA:**
    * **Debit (Q)**: Minimal **{q_demand_ls:.2f} liter/detik**
    * **Head (H)**: Minimal **{tdh_safe:.1f} meter**
    * **Daya Poros**: **{power_kw:.2f} kW** ({power_hp:.2f} HP)
    """)
    
    # --- 8. VISUALISASI SISTEM (EGL/HGL) ---
    st.divider()
    col_vis1, col_vis2 = st.columns([2, 1])
    
    with col_vis1:
        st.write("#### 📈 Sketsa Garis Energi (HGL)")
        
        # Plotting HGL Sederhana
        x = [0, panjang_pipa]
        y_ground = [0, beda_elevasi] # Tanah
        
        # HGL starts at H_pompa, ends at H_sisa
        h_start = beda_elevasi + hf_major + hf_minor + tekanan_sisa # Head di pompa (dihitung dari elevasi discharge)
        # Revisi Logika Grafik:
        # Titik 0 (Pompa): Elevasi 0. Head Tekanan = TDH. Total Energy = TDH.
        # Titik Akhir: Elevasi = beda_elevasi. Sisa Tekan = 10m.
        # Jadi HGL turun dari TDH sampai (Beda Elevasi + 10m)
        
        y_hgl = [tdh, beda_elevasi + tekanan_sisa]
        
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(x, y_ground, 'k-', linewidth=2, label='Profil Tanah')
        ax.fill_between(x, y_ground, color='#795548', alpha=0.3)
        
        ax.plot(x, y_hgl, 'b--', linewidth=2, label='Hydraulic Grade Line (HGL)')
        
        # Annotations
        ax.annotate('Pompa', xy=(0, 0), xytext=(10, 5), arrowprops=dict(facecolor='black', arrowstyle='->'))
        ax.annotate(f'Outlet ({tekanan_sisa}m sisa)', xy=(panjang_pipa, beda_elevasi), xytext=(panjang_pipa-100, beda_elevasi+5), 
                    arrowprops=dict(facecolor='blue', arrowstyle='->'))
        
        ax.set_title(f"Profil Memanjang Pipa {diameter_inch}\"")
        ax.set_ylabel("Elevasi Head (m)")
        ax.set_xlabel("Jarak (m)")
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.6)
        
        st.pyplot(fig)

    with col_vis2:
        st.write("#### 📝 Ringkasan")
        st.write(f"- Pipa: **{jenis_pipa}**")
        st.write(f"- Diameter: **{diameter_inch} inch**")
        st.write(f"- Panjang: **{panjang_pipa} m**")
        st.write(f"- C-Factor: **{c_hw}**")
