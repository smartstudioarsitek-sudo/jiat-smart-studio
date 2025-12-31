import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="JIAT Design", layout="wide", page_icon="💧")

# --- 2. SIDEBAR: PROJECT MANAGER ---
with st.sidebar:
    st.header("📂 File Manager")
    st.text_input("Nama Proyek", value="JIAT Lampung Timur")
    st.text_input("Lokasi", value="Desa Hargomulyo")
    st.number_input("Tahun Anggaran", value=2025, step=1)
    
    st.divider()
    st.header("1. Input Parameter")
    
    # Input Debit Geologi (PENGGANTI FJ MOCK)
    st.info("💧 **Sumber Air (Sumur)**")
    q_sumur = st.number_input("Debit Izin / Q Sumur (l/det)", value=15.0, help="Kapasitas sumur bor berdasarkan uji pemompaan (Pumping Test).")
    
    st.info("🚜 **Lahan Irigasi**")
    luas_layanan = st.number_input("Luas Potensial (ha)", value=10.0, step=0.1)

# --- 3. HEADER UTAMA ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #1e88e5 0%, #42a5f5 50%, #90caf9 100%);
        padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;
    }
    .metric-card {
        border: 1px solid #eee; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); text-align: center;
    }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 32px;">💧 JIAT Lampung Timur</h1>
    <p style="opacity: 0.9;">Desain Jaringan Irigasi Air Tanah & Perpipaan</p>
</div>
""", unsafe_allow_html=True)

# --- 4. DATA LINKING (NFR ONLY) ---
if 'nfr_global' in st.session_state:
    nfr_val = st.session_state['nfr_global']
    status_nfr = f"✅ Terhubung: {nfr_val:.3f} l/s/ha"
else:
    nfr_val = 1.25 # Default
    status_nfr = "⚠️ Default (Modul Pola Tanam Kosong)"

# --- 5. TABS SYSTEM (RESTORING UI) ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 INPUT DATA", 
    "💧 KEBUTUHAN AIR", 
    "⚙️ PIPA & HIDROLIKA", 
    "📊 HASIL & GRAFIK"
])

# === TAB 1: DATA GEOLOGI & ELEVASI ===
with tab1:
    col_geo1, col_geo2 = st.columns(2)
    with col_geo1:
        st.subheader("A. Data Sumur & Geologi")
        st.write("Parameter hidrolika sumur dalam:")
        swl = st.number_input("Muka Air Statis / SWL (m)", value=15.0, help="Jarak permukaan tanah ke muka air saat pompa mati")
        dwl = st.number_input("Muka Air Dinamis / DWL (m)", value=25.0, help="Jarak permukaan tanah ke muka air saat pompa nyala")
        posisi_pompa = st.number_input("Posisi Pemasangan Pompa (m)", value=30.0)
        
    with col_geo2:
        st.subheader("B. Elevasi & Topografi")
        elev_sumur = st.number_input("Elevasi Tanah Titik Sumur (mdpl)", value=100.0)
        elev_reservoir = st.number_input("Elevasi Tanah Reservoir/Outlet (mdpl)", value=115.0)
        tinggi_reservoir = st.number_input("Tinggi Menara/Reservoir (m)", value=6.0, help="Tinggi bak penampung dari tanah")
        
        # Hitung Head Statis Total
        # H_statis = (Elev_Res + T_Res - Elev_Sumur) + DWL
        # Atau simpelnya beda tinggi air ke air
        elev_air_keluar = elev_reservoir + tinggi_reservoir
        beda_tinggi_geodetik = elev_air_keluar - elev_sumur
        h_statis_total = beda_tinggi_geodetik + dwl
        
        st.success(f"📏 **Head Statis Total (Hs): {h_statis_total:.2f} m**")

# === TAB 2: KEBUTUHAN AIR (NERACA) ===
with tab2:
    st.subheader("Analisa Ketersediaan vs Kebutuhan")
    
    col_bal1, col_bal2 = st.columns(2)
    with col_bal1:
        st.markdown("### 1. Kebutuhan (Demand)")
        st.caption(f"Sumber NFR: {status_nfr}")
        
        q_kebutuhan = luas_layanan * nfr_val
        st.metric("Debit Kebutuhan (Q Req)", f"{q_kebutuhan:.2f} l/det")
        
    with col_bal2:
        st.markdown("### 2. Ketersediaan (Supply)")
        st.caption("Sumber: Data Uji Pemompaan (Geologi)")
        
        st.metric("Debit Sumur (Q Geologi)", f"{q_sumur:.2f} l/det")
        
    # NERACA
    st.divider()
    balance = q_sumur - q_kebutuhan
    if balance >= 0:
        st.success(f"✅ **SURPLUS AIR (+{balance:.2f} l/det)**. Debit sumur mencukupi untuk mengairi {luas_layanan} ha.")
        q_desain = q_kebutuhan # Desain pipa pakai kebutuhan
    else:
        st.error(f"❌ **DEFISIT AIR ({balance:.2f} l/det)**. Debit sumur KURANG. Maksimal area layanan: {q_sumur/nfr_val:.1f} ha.")
        q_desain = q_sumur # Desain pipa dipaksa pakai supply max

# === TAB 3: PIPA & HIDROLIKA (MULTI-SEGMEN) ===
with tab3:
    st.subheader("Perhitungan Hidrolis Jaringan Pipa")
    st.info(f"💡 **Debit Desain Pipa:** {q_desain:.2f} l/det (Berdasarkan Neraca Air)")
    
    # Template Data Segmen Pipa
    if 'df_pipa' not in st.session_state:
        st.session_state.df_pipa = pd.DataFrame([
            {"Segmen": "Pompa-Res", "Panjang (m)": 10.0, "Diameter (mm)": 90, "C (Hazen)": 150},
            {"Segmen": "Jalur Utama", "Panjang (m)": 500.0, "Diameter (mm)": 90, "C (Hazen)": 150},
            {"Segmen": "Distribusi 1", "Panjang (m)": 200.0, "Diameter (mm)": 63, "C (Hazen)": 150},
        ])

    # Editor Tabel
    edited_pipa = st.data_editor(
        st.session_state.df_pipa,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_pipa_jiat",
        column_config={
            "Diameter (mm)": st.column_config.NumberColumn(help="Diameter luar (OD)"),
            "C (Hazen)": st.column_config.NumberColumn(help="PVC=150, HDPE=140, GIP=120")
        }
    )
    st.session_state.df_pipa = edited_pipa
    
    # Hitung Head Loss per Segmen
    total_hf = 0
    results_pipa = []
    
    for idx, row in edited_pipa.iterrows():
        L = row['Panjang (m)']
        D_mm = row['Diameter (mm)']
        C = row['C (Hazen)']
        
        # Konversi ke SI
        Q_m3s = q_desain / 1000
        D_m = D_mm / 1000
        
        # Hazen-Williams Formula
        if D_m > 0 and C > 0:
            Hf = 10.67 * L * (Q_m3s**1.852) / ((C**1.852) * (D_m**4.87))
            
            # Cek Kecepatan (V)
            Area = np.pi * (D_m/2)**2
            V = Q_m3s / Area
        else:
            Hf = 0
            V = 0
            
        total_hf += Hf
        
        results_pipa.append({
            "Segmen": row['Segmen'],
            "V (m/s)": round(V, 2),
            "Head Loss (m)": round(Hf, 3)
        })
        
    st.write("#### 🔍 Hasil Analisa Per Segmen")
    st.dataframe(pd.DataFrame(results_pipa), use_container_width=True)

# === TAB 4: HASIL & GRAFIK (POMPA) ===
with tab4:
    st.subheader("Resume Kebutuhan Pompa (Submersible)")
    
    # Hitung Total Head (H)
    # H_total = H_statis + H_friction + H_minor (10%) + Sisa Tekan
    h_minor = 0.10 * total_hf
    sisa_tekan = 10.0 # m (Asumsi untuk outlet keran/sprinkler)
    
    h_manometrik = h_statis_total + total_hf + h_minor + sisa_tekan
    
    col_res1, col_res2 = st.columns(2)
    
    with col_res1:
        st.markdown("#### 📐 Head Sistem")
        st.write(f"- Head Statis (Hs): **{h_statis_total:.2f} m**")
        st.write(f"- Friction Loss (Hf): **{total_hf:.2f} m**")
        st.write(f"- Minor Loss (10%): **{h_minor:.2f} m**")
        st.write(f"- Sisa Tekan Outlet: **{sisa_tekan:.2f} m**")
        st.markdown("---")
        st.metric("TOTAL HEAD (H)", f"{h_manometrik:.2f} m")
        
    with col_res2:
        st.markdown("#### ⚡ Spesifikasi Pompa")
        eff = st.slider("Efisiensi Pompa", 0.4, 0.9, 0.75)
        
        # Power (kW) = (rho * g * Q * H) / eff
        # Q dalam m3/s, H dalam m
        power_kw = (9.81 * (q_desain/1000) * h_manometrik) / eff
        power_hp = power_kw * 1.341
        
        st.metric("Debit Desain (Q)", f"{q_desain:.2f} l/det")
        st.metric("Daya Poros (P)", f"{power_kw:.2f} kW ({power_hp:.2f} HP)")
        
        st.info(f"💡 **Rekomendasi:** Cari pompa Submersible dengan Q ≥ {q_desain:.1f} l/det pada Head {h_manometrik:.0f} m.")

    # Grafik Sederhana
    st.divider()
    st.write("#### 📉 Grafik Sistem")
    
    fig, ax = plt.subplots(figsize=(8, 3))
    # Bar Chart Head Breakdown
    components = ['Statis', 'Gesekan', 'Minor', 'Sisa Tekan']
    values = [h_statis_total, total_hf, h_minor, sisa_tekan]
    colors = ['#795548', '#f44336', '#ff9800', '#2196f3']
    
    ax.barh(components, values, color=colors)
    ax.set_xlabel("Head (meter)")
    ax.set_title("Komponen Head Loss Sistem JIAT")
    
    for i, v in enumerate(values):
        ax.text(v + 0.1, i, f"{v:.1f}m", va='center')
        
    st.pyplot(fig)
