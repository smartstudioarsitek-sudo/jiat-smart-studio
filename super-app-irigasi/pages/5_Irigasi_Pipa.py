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
        background: linear-gradient(120deg, #37474f 0%, #455a64 50%, #607d8b 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 16px; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🚰 Desain Pipa & Pompa</h1>
    <p style="opacity: 0.9;">Analisa Jaringan Pipa Tekan, Head Loss, & Kebutuhan Daya</p>
</div>
""", unsafe_allow_html=True)

# --- 3. LINK DATA (AUTO-DETECT) ---
# Cek NFR
if 'nfr_global' in st.session_state:
    nfr_val = st.session_state['nfr_global']
    status_nfr = f"✅ Terhubung: {nfr_val} l/s/ha"
else:
    nfr_val = 1.25 # Default
    status_nfr = "⚠️ Default (Data Pola Tanam Kosong)"

# Cek Debit Andalan
if 'data_debit_mock' in st.session_state:
    debit_list = st.session_state['data_debit_mock']
    q_andalan = np.percentile(debit_list, 20)
    status_mock = f"✅ Terhubung: {q_andalan*1000:.2f} l/s"
else:
    q_andalan = 0.050 # Default 50 l/s
    status_mock = "⚠️ Default (Data Mock Kosong)"

# --- 4. DATA INPUT GLOBAL ---
st.info("ℹ️ **Status Data:** " + status_nfr + " | " + status_mock)

# Input Luas (Global karena dipakai semua tab)
col_glob1, col_glob2 = st.columns([1, 2])
with col_glob1:
    luas_lahan = st.number_input("Luas Lahan (ha)", value=25.0, step=0.5)
with col_glob2:
    # Hitung Demand Real-time
    q_req_ls = luas_lahan * nfr_val
    q_req_m3s = q_req_ls / 1000
    
    # Cek Neraca
    if q_req_m3s > q_andalan:
        st.error(f"❌ **DEFISIT!** Supply ({q_andalan*1000:.1f} l/s) < Kebutuhan ({q_req_ls:.1f} l/s)")
    else:
        st.success(f"✅ **SURPLUS.** Kebutuhan: {q_req_ls:.2f} l/s (Aman)")

st.divider()

# --- 5. TAB MENU UTAMA (SUB-PAGES) ---
tab1, tab2, tab3 = st.tabs(["🌍 Parameter Geologi", "🚰 Jaringan Pipa", "⚡ Desain Pompa"])

# === TAB 1: PARAMETER GEOLOGI & JALUR ===
with tab1:
    st.subheader("1. Kondisi Geografis Jalur Pipa")
    col_geo1, col_geo2 = st.columns(2)
    
    with col_geo1:
        st.write("#### Elevasi (Head Statis)")
        elev_ambil = st.number_input("Elevasi Muka Air Pengambilan (m)", value=100.0)
        elev_keluar = st.number_input("Elevasi Outlet / Bak Penampung (m)", value=125.0)
        hs = elev_keluar - elev_ambil
        st.metric("Head Statis (Hs)", f"{hs:.2f} m", help="Beda tinggi total yang harus dilawan pompa")
        
    with col_geo2:
        st.write("#### Jarak & Panjang")
        panjang_pipa = st.number_input("Panjang Pipa Total (L)", value=650.0, help="Total panjang pipa dari intake ke outlet")
        tek_sisa = st.number_input("Sisa Tekan di Outlet (m)", value=10.0, help="Tekanan yang dibutuhkan di ujung pipa (misal untuk sprinkler = 10-15m)")

# === TAB 2: JARINGAN PIPA ===
with tab2:
    st.subheader("2. Hidrolika & Head Loss")
    col_pipa1, col_pipa2 = st.columns(2)
    
    with col_pipa1:
        st.write("#### Spesifikasi Material")
        jenis_pipa = st.selectbox("Material Pipa", ["PVC (C=150)", "HDPE (C=140)", "GIP (C=120)", "Steel (C=100)"])
        # Parse C value
        if "150" in jenis_pipa: c_hw = 150
        elif "140" in jenis_pipa: c_hw = 140
        elif "120" in jenis_pipa: c_hw = 120
        else: c_hw = 100
        
        d_inch = st.selectbox("Diameter Pipa (Inch)", [2, 3, 4, 6, 8, 10, 12, 14, 16], index=3)
        d_m = d_inch * 0.0254
        
    with col_pipa2:
        st.write("#### Analisa Kecepatan")
        # Hitung V
        area = np.pi * (d_m/2)**2
        v = q_req_m3s / area
        
        # Cek V
        if 0.3 <= v <= 2.5: status_v, col_v = "✅ Ideal", "normal"
        elif v < 0.3: status_v, col_v = "⚠️ Endapan", "inverse"
        else: status_v, col_v = "⛔ Erosi/Waterhammer", "inverse"
            
        st.metric("Kecepatan Aliran (V)", f"{v:.2f} m/s", status_v, delta_color=col_v)
        st.caption("Range ideal: 0.3 - 2.5 m/s")

    # Hitung Head Loss (Major + Minor)
    hf_major = 10.67 * panjang_pipa * (q_req_m3s**1.852) / ((c_hw**1.852) * (d_m**4.87))
    hf_minor = 0.1 * hf_major # Asumsi 10%
    hf_total = hf_major + hf_minor
    
    st.info(f"📉 **Total Kehilangan Tekanan (Head Loss):** {hf_total:.2f} m (Gesekan Pipa + Fitting)")

# === TAB 3: DESAIN POMPA ===
with tab3:
    st.subheader("3. Kebutuhan Daya Pompa")
    
    # Hitung TDH
    tdh = hs + hf_total + tek_sisa
    
    col_pump1, col_pump2 = st.columns(2)
    with col_pump1:
        eff_pompa = st.slider("Efisiensi Pompa (%)", 40, 90, 75) / 100
        sf_head = st.number_input("Safety Factor Head (%)", value=10) / 100
        
        tdh_safe = tdh * (1 + sf_head)
        
    with col_pump2:
        # Power Calculation
        # P = (rho * g * Q * H) / eff
        p_kw = (9.81 * q_req_m3s * tdh_safe) / eff_pompa
        p_hp = p_kw * 1.341
        
        st.metric("Total Dynamic Head (TDH)", f"{tdh_safe:.2f} m", f"Termasuk Safety {int(sf_head*100)}%")
        st.metric("Daya Poros (Power)", f"{p_kw:.2f} kW", f"Setara {p_hp:.2f} HP")

# --- 6. VISUALISASI FINAL (GLOBAL) ---
st.divider()
st.subheader("📈 Profil Hidrolis Sistem (HGL)")

fig, ax = plt.subplots(figsize=(10, 4))

# Koordinat
x = [0, panjang_pipa]
y_tanah = [elev_ambil, elev_keluar]
y_hgl_start = elev_ambil + tdh # Energi di pompa
y_hgl_end = elev_keluar + tek_sisa # Energi di outlet

# Plot Tanah
ax.plot(x, y_tanah, 'k-', linewidth=2, label='Elevasi Tanah')
ax.fill_between(x, y_tanah, min(y_tanah)-5, color='#795548', alpha=0.3)

# Plot HGL
ax.plot(x, [y_hgl_start, y_hgl_end], 'b--', linewidth=2, label='HGL (Tekanan)')

# Annotasi
ax.annotate(f'Pompa\n(+{tdh_safe:.1f}m)', xy=(0, elev_ambil), xytext=(20, elev_ambil+10),
            arrowprops=dict(facecolor='red', shrink=0.05))
ax.annotate(f'Outlet\n(Sisa {tek_sisa}m)', xy=(panjang_pipa, elev_keluar), xytext=(panjang_pipa-50, elev_keluar+10),
            arrowprops=dict(facecolor='blue', shrink=0.05))

ax.set_title(f"Profil Memanjang Pipa {d_inch}\" (Material: {jenis_pipa.split()[0]})")
ax.set_ylabel("Elevasi (m)")
ax.set_xlabel("Jarak (m)")
ax.legend()
ax.grid(True, linestyle=':', alpha=0.5)

st.pyplot(fig)

# Tombol Simpan (Opsional)
if st.button("💾 Simpan Desain Pompa"):
    st.toast("Desain Pompa tersimpan!", icon="✅")
