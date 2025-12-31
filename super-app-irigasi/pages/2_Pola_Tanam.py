import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Pola Tanam & NFR", layout="wide", page_icon="🌾")

# --- 2. SIDEBAR PENGATURAN ---
with st.sidebar:
    st.header("🌾 Pengaturan Tanam")
    awal_tanam = st.selectbox("Mulai Tanam (Awal MT-1)", 
                              ["Okt-1", "Okt-2", "Nov-1", "Nov-2", "Des-1", "Des-2"], 
                              index=0)
    
    st.divider()
    st.subheader("⚙️ Analisa Hujan (R80)")
    faktor_r80 = st.slider("Faktor Estimasi R80 (%)", 50, 90, 80) / 100
    st.caption(f"R80 = {int(faktor_r80*100)}% x Hujan Rata-rata")
    
    st.divider()
    st.subheader("💧 Parameter Kebutuhan")
    lp_req = st.number_input("Air Penyiapan Lahan (mm/hari)", value=11.5, step=0.5)
    wlr = st.number_input("Penggantian Lapisan Air (WLR) mm/hari", value=1.1, step=0.1)

# --- 3. HEADER UTAMA ---
st.markdown("""
<style>
    .hero-title { font-size: 40px; font-weight: 700; color: #2e7d32; margin-bottom: 0px; }
    .hero-sub { font-size: 18px; color: #555; margin-bottom: 20px; }
</style>
<div style="text-align: center;">
    <div class="hero-title">🌾 Perencanaan Pola Tanam & Kebutuhan Air</div>
    <div class="hero-sub">Analisa Kebutuhan Air Irigasi (NFR) Berdasarkan Pola Tanam Padi-Padi-Palawija</div>
</div>
""", unsafe_allow_html=True)

# --- 4. PERSIAPAN DATA (AUTO-EXPAND 12 BULAN KE 24 PERIODE) ---
periode_labels = []
bulan_base = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des']
for b in bulan_base:
    periode_labels.extend([f"{b}-1", f"{b}-2"]) # Jan-1, Jan-2, dst.

# Ambil data ETo dari Modul Klimatologi
if 'data_eto_transfer' in st.session_state:
    eto_12 = st.session_state['data_eto_transfer']
    # Duplikasi data bulanan menjadi setengah bulanan (Jan -> Jan-1 & Jan-2)
    eto_24 = [val for val in eto_12 for _ in range(2)]
    st.toast("✅ Data ETo berhasil disinkronisasi dari Modul Klimatologi!", icon="🔗")
else:
    eto_24 = [4.5] * 24 # Default dummy

# Data Curah Hujan Default
ch_default = [120, 130, 110, 100, 150, 140, 90, 80, 60, 50, 40, 30, 
              20, 15, 10, 5, 20, 30, 80, 100, 150, 180, 200, 210]

# --- 5. LAYOUT UTAMA ---
col_input, col_grafik = st.columns([1, 2])

with col_input:
    st.subheader("1. Input Data (Rata-rata)")
    st.info("💡 Masukkan data Curah Hujan Rata-rata per periode.")
    
    df_input = pd.DataFrame({
        'Periode': periode_labels,
        'ETo (mm/hr)': eto_24,
        'CH Rata-rata (mm)': ch_default
    })
    
    edited_df = st.data_editor(
        df_input, 
        height=600, 
        use_container_width=True,
        column_config={
            "Periode": st.column_config.TextColumn(disabled=True),
            "ETo (mm/hr)": st.column_config.NumberColumn(disabled=True, help="Otomatis dari Modul 1")
        }
    )

# --- 6. PROSES PERHITUNGAN NFR ---
# Logika Sederhana Simulasi Pola Tanam (Padi-Padi-Palawija)
hasil_analisa = []
max_dr = 0

# Urutkan periode berdasarkan Awal Tanam
start_idx = periode_labels.index(awal_tanam)
rotated_indices = list(range(start_idx, 24)) + list(range(0, start_idx))

# Pola Tanam Dummy Logic (Untuk Visualisasi)
# 0-3: Pengolahan Tanah (LP), 4-9: Padi 1, 10-13: Padi 2 (LP), 14-19: Padi 2, 20-23: Palawija
for i, idx in enumerate(rotated_indices):
    row = edited_df.iloc[idx]
    eto = row['ETo (mm/hr)']
    ch_r80 = row['CH Rata-rata (mm)'] * faktor_r80
    ch_eff = min(ch_r80, 0.7 * eto * 15) # Asumsi sederhana Re
    
    # Tentukan Fase Tanam & Koefisien (Simulasi)
    if i < 3: 
        fase = "Pengolahan Tanah 1"
        kc = 0; needs = lp_req
        color = "red"
    elif i < 9:
        fase = "Padi 1"
        kc = 1.1; needs = (eto * kc) + wlr
        color = "blue"
    elif i < 11:
        fase = "Pengolahan Tanah 2"
        kc = 0; needs = lp_req
        color = "orange"
    elif i < 17:
        fase = "Padi 2"
        kc = 1.15; needs = (eto * kc) + wlr
        color = "green"
    else:
        fase = "Palawija/Bera"
        kc = 0.8; needs = (eto * kc)
        color = "yellow"
    
    # Hitung DR (Debit Requirement) l/s/ha
    # Konversi mm/hari ke l/s/ha (1 mm/hari = 0.1157 l/s/ha)
    net_needs_mm = max(0, needs - (ch_eff/15))
    dr_lsha = net_needs_mm * 0.1157 / 0.65 # Efisiensi 65%
    
    if dr_lsha > max_dr: max_dr = dr_lsha
    
    hasil_analisa.append({
        'Periode': row['Periode'],
        'Urutan': i, # Helper untuk sorting grafik
        'Kegiatan': fase,
        'CH R80 (mm)': round(ch_r80, 1),
        'Kebutuhan Air (L/s/ha)': round(dr_lsha, 3),
        'Warna': color
    })

df_hasil = pd.DataFrame(hasil_analisa)

# --- 7. VISUALISASI GRAFIK ---
with col_grafik:
    st.subheader(f"2. Grafik Kebutuhan Air (Max DR: {round(max_dr, 3)} L/det/ha)")
    
    # Grafik Bar Chart (DR)
    chart = alt.Chart(df_hasil).mark_bar().encode(
        x=alt.X('Periode', sort=list(df_hasil['Periode'])),
        y=alt.Y('Kebutuhan Air (L/s/ha)', title='Kebutuhan Air (L/det/ha)'),
        color=alt.Color('Kegiatan', scale=alt.Scale(scheme='category10')),
        tooltip=['Periode', 'Kegiatan', 'Kebutuhan Air (L/s/ha)', 'CH R80 (mm)']
    ).properties(height=400)
    
    # Grafik Line Chart (Curah Hujan)
    line = alt.Chart(df_hasil).mark_line(color='red', strokeDash=[5,5]).encode(
        x=alt.X('Periode', sort=list(df_hasil['Periode'])),
        y=alt.Y('CH R80 (mm)', axis=alt.Axis(title='Curah Hujan R80 (mm)', titleColor='red'))
    )
    
    st.altair_chart(alt.layer(chart, line).resolve_scale(y='independent'), use_container_width=True)

# --- 8. TABEL HASIL AKHIR ---
st.subheader("3. Hasil Analisa Sistem & Ekspor")
col_res1, col_res2 = st.columns([3, 1])

with col_res1:
    st.dataframe(
        df_hasil[['Periode', 'Kegiatan', 'CH R80 (mm)', 'Kebutuhan Air (L/s/ha)']], 
        use_container_width=True,
        height=300
    )

with col_res2:
    st.metric("Max DR (L/s/ha)", f"{round(max_dr, 3)}")
    st.caption("Gunakan nilai ini untuk Desain Saluran")
    
    if st.button("🚀 Kirim Data ke Desain Saluran", type="primary"):
        st.session_state['nfr_global'] = round(max_dr, 3)
        st.success(f"Modulus {round(max_dr, 3)} terkunci!")

st.caption("SmartStudio © 2025 | Modul Pola Tanam v2.0")
