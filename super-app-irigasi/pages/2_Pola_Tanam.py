import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Pola Tanam & NFR", layout="wide", page_icon="🌾")

# --- 2. HEADER STYLE ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #2e7d32 0%, #43a047 50%, #66bb6a 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .stExpander { border: 1px solid #ddd; border-radius: 5px; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🌾 Pola Tanam & Kebutuhan Air</h1>
    <p style="opacity: 0.9;">Analisa NFR dengan Data ETo Penman & Curah Hujan Efektif</p>
</div>
""", unsafe_allow_html=True)

# --- 3. FUNGSI DATA DEFAULT & RESET ---
def get_default_pola():
    # Cek apakah ada data kiriman dari Modul 1 (Penman)
    if 'data_eto_transfer' in st.session_state:
        eto_12 = st.session_state['data_eto_transfer']
        # Expand 12 bulan jadi 24 periode (Setengah Bulanan)
        eto_24 = [val for val in eto_12 for _ in range(2)]
        sumber = "✅ Terhubung: Modul Klimatologi (Penman)"
    else:
        eto_24 = [4.5] * 24 # Dummy default
        sumber = "⚠️ Default (Data Klimatologi Belum Disimpan)"
    
    # Label Periode (Jan-1, Jan-2, dst)
    periode_labels = []
    for b in ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des']:
        periode_labels.extend([f"{b}-1", f"{b}-2"])
        
    # Dummy Hujan
    ch_default = [150, 140, 130, 120, 100, 90, 80, 60, 50, 40, 30, 20, 
                  10, 5, 10, 20, 40, 60, 100, 150, 200, 220, 240, 250]
    
    df = pd.DataFrame({
        'Periode': periode_labels,
        'ETo (mm/hr)': eto_24,
        'CH Rata-rata (mm)': ch_default
    })
    return df, sumber

# Inisialisasi State
if 'df_pola_tanam' not in st.session_state:
    df_init, status_init = get_default_pola()
    st.session_state.df_pola_tanam = df_init
    st.session_state.status_sumber = status_init

# --- 4. SIDEBAR PENGATURAN ---
with st.sidebar:
    st.header("🔧 Pengaturan Tanam")
    
    # Tombol Reset
    if st.button("🔄 Reset Data Tabel", type="secondary"):
        df_new, status_new = get_default_pola()
        st.session_state.df_pola_tanam = df_new
        st.session_state.status_sumber = status_new
        st.rerun()
        
    st.divider()
    # Parameter Jadwal
    awal_tanam = st.selectbox("Mulai Tanam (Awal MT-1)", 
                              ["Okt-1", "Okt-2", "Nov-1", "Nov-2", "Des-1", "Des-2", "Jan-1"],
                              index=2) # Default Nov-1
    
    with st.expander("⚙️ Parameter Kebutuhan Air"):
        faktor_r80 = st.slider("Probabilitas Hujan (R80)", 50, 90, 80) / 100
        lp_req = st.number_input("Air Penyiapan Lahan (LP)", value=11.5, help="mm/hari")
        wlr = st.number_input("Penggantian Air (WLR)", value=1.1, help="mm/hari")
        eff_irigasi = st.number_input("Efisiensi Irigasi", value=0.65, help="0.65 untuk Tersier")

# --- 5. INPUT DATA ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("1. Input Curah Hujan")
    
    # Info Status Data
    st.caption(st.session_state.get('status_sumber', "Status: Menunggu Data"))
    
    # Tips Excel
    st.info("💡 **Tips Excel:** Copy data **Curah Hujan** (1 kolom, 24 baris) dari Excel, klik sel 'CH Rata-rata' pertama, lalu **Ctrl+V**.")
    
    edited_df = st.data_editor(
        st.session_state.df_pola_tanam,
        height=550,
        use_container_width=True,
        column_config={
            "Periode": st.column_config.TextColumn(disabled=True),
            "ETo (mm/hr)": st.column_config.NumberColumn(disabled=True, help="Otomatis dari Modul Klimatologi"),
            "CH Rata-rata (mm)": st.column_config.NumberColumn(required=True, min_value=0)
        }
    )
    st.session_state.df_pola_tanam = edited_df

# --- 6. ENGINE PERHITUNGAN NFR ---
hasil_analisa = []
max_dr = 0

# Logika Rotasi Periode Tanam
periode_labels = list(edited_df['Periode'])
start_idx = periode_labels.index(awal_tanam)
# Putar urutan index berdasarkan awal tanam (misal mulai Nov-1, maka list dimulai dari index Nov-1)
rotated_indices = list(range(start_idx, 24)) + list(range(0, start_idx))

for i, idx in enumerate(rotated_indices):
    row = edited_df.iloc[idx]
    eto = row['ETo (mm/hr)']
    ch_r80 = row['CH Rata-rata (mm)'] * faktor_r80
    # Hujan Efektif (Re) untuk Padi (70% probabilitas dan maks limit)
    # Ini rumus pendekatan umum, bisa disesuaikan
    ch_eff = min(ch_r80, 0.7 * eto * 15) 
    
    # Simulasi Fase Tanam (Padi-Padi-Palawija)
    # Durasi: LP(3) -> Padi1(6) -> LP2(2) -> Padi2(6) -> Palawija(7)
    if i < 3: 
        fase = "Pengolahan Tanah 1"; kc = 0; needs = lp_req; color="red"
    elif i < 9: 
        fase = "Padi 1 (Vegetatif-Generatif)"; kc = 1.1; needs = (eto * kc) + wlr; color="blue"
    elif i < 11: 
        fase = "Pengolahan Tanah 2"; kc = 0; needs = lp_req; color="orange"
    elif i < 17: 
        fase = "Padi 2 (Vegetatif-Generatif)"; kc = 1.15; needs = (eto * kc) + wlr; color="green"
    else: 
        fase = "Palawija / Bera"; kc = 0.8; needs = (eto * kc); color="yellow"
    
    # Hitung Kebutuhan Bersih (NFR)
    # Konversi: (mm/hari - mm/hari) * konstanta -> l/s/ha
    # 1 mm/hari = 0.1157 l/s/ha
    net_needs_mm = max(0, needs - (ch_eff/15)) # ch_eff dibagi 15 karena satuan curah hujan per periode
    dr = net_needs_mm * 0.1157 / eff_irigasi
    
    if dr > max_dr: max_dr = dr
    
    hasil_analisa.append({
        'Periode': row['Periode'], 
        'Kegiatan': fase, 
        'Kebutuhan Air (L/s/ha)': round(dr, 3), 
        'Warna': color,
        'CH R80 (mm)': round(ch_r80, 1)
    })

df_hasil = pd.DataFrame(hasil_analisa)

# --- 7. VISUALISASI HASIL ---
with col2:
    st.subheader("2. Grafik Kebutuhan Air (NFR)")
    
    # Grafik Bar Chart (DR)
    chart = alt.Chart(df_hasil).mark_bar().encode(
        x=alt.X('Periode', sort=periode_labels),
        y=alt.Y('Kebutuhan Air (L/s/ha)', title='Kebutuhan Air (l/det/ha)'),
        color=alt.Color('Kegiatan', scale=alt.Scale(scheme='category10')),
        tooltip=['Periode', 'Kegiatan', 'Kebutuhan Air (L/s/ha)', 'CH R80 (mm)']
    ).properties(height=400)
    
    # Grafik Garis (Curah Hujan)
    line = alt.Chart(df_hasil).mark_line(color='red', strokeDash=[5,5]).encode(
        x=alt.X('Periode', sort=periode_labels),
        y=alt.Y('CH R80 (mm)', axis=alt.Axis(title='Hujan Andalan R80 (mm)', titleColor='red'))
    )
    
    combined_chart = alt.layer(chart, line).resolve_scale(y='independent')
    st.altair_chart(combined_chart, use_container_width=True)

# --- 8. TOMBOL SIMPAN & KIRIM ---
st.divider()
col_final1, col_final2 = st.columns([3, 1])

with col_final1:
    st.dataframe(df_hasil[['Periode', 'Kegiatan', 'CH R80 (mm)', 'Kebutuhan Air (L/s/ha)']].T, use_container_width=True)

with col_final2:
    st.metric("NFR Maksimum", f"{round(max_dr, 3)} L/det/ha")
    
    if st.button("🚀 Kirim Data ke Desain Saluran", type="primary"):
        # Kunci data ke session state
        st.session_state['nfr_global'] = round(max_dr, 3)
        st.toast(f"✅ Sukses! NFR {round(max_dr, 3)} l/s/ha dikunci untuk Desain Saluran.", icon="🏗️")
