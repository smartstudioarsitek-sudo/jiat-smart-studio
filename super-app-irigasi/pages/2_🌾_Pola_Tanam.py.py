import streamlit as st
import pandas as pd
import altair as alt

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="NFR Smart Planner", layout="wide", page_icon="🌾")

# --- CSS BIAR TABEL RAPI ---
st.markdown("""
<style>
    .header-box {padding:10px; background-color:#e3f2fd; border-radius:5px; margin-bottom:10px;}
    .big-font {font-size:18px !important; font-weight:bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. DATABASE STANDAR (KP-01)
# ==========================================
def get_pola_tanam_default():
    return [
        {'Jenis': 'Pengolahan Tanah 1', 'Durasi': 3, 'WLR': 1.2, 'Kc': 0},  # 1.5 Bulan
        {'Jenis': 'Padi 1',             'Durasi': 7, 'WLR': 0,   'Kc': 'V'}, # 3.5 Bulan
        {'Jenis': 'Pengolahan Tanah 2', 'Durasi': 1, 'WLR': 1.2, 'Kc': 0},  # 0.5 Bulan
        {'Jenis': 'Padi 2',             'Durasi': 7, 'WLR': 0,   'Kc': 'V'}, # 3.5 Bulan
        {'Jenis': 'Palawija/Bera',      'Durasi': 6, 'WLR': 0,   'Kc': 0.8}  # Sisa (3 Bulan)
    ]

kc_padi_values = [1.1, 1.1, 1.05, 1.05, 0.95, 0.0, 0.0]

# Nama Periode Setengah Bulanan
periode_labels = []
bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
for b in bulan:
    periode_labels.append(f"{b}-1")
    periode_labels.append(f"{b}-2")

# ==========================================
# 2. STATE MANAGEMENT (Perbaikan Cache)
# ==========================================
# Kita ganti nama key session-nya jadi 'df_nfr_baru' biar data lama terhapus otomatis
if 'df_nfr_baru' not in st.session_state:
    data = []
    for p in periode_labels:
        # Default ETo 4.5 dan CH Rata-rata 100
        data.append({'Periode': p, 'ETo (mm/hr)': 4.5, 'CH Rata-rata (mm)': 100}) 
    st.session_state['df_nfr_baru'] = pd.DataFrame(data)

# ==========================================
# 3. SIDEBAR - PENGATURAN
# ==========================================
with st.sidebar:
    st.title("🌾 Pengaturan Tanam")
    
    start_idx = st.selectbox("Mulai Tanam (Awal MT-1)", options=range(24), format_func=lambda x: periode_labels[x], index=18)
    st.caption(f"Jadwal Tanam dimulai: **{periode_labels[start_idx]}**")
    
    st.markdown("---")
    st.subheader("⚙️ Analisa Hujan (R80)")
    faktor_r80 = st.slider("Faktor Estimasi R80 (%)", 50, 90, 80)
    st.caption(f"R80 = **{faktor_r80}%** x Hujan Rata-rata.")
    
    st.markdown("---")
    st.subheader("💧 Parameter Kebutuhan")
    kebutuhan_air_penyiapan = st.number_input("Air Penyiapan Lahan (mm/hari)", value=11.5)
    perkolasi = st.number_input("Perkolasi (mm/hari)", value=2.0)
    efisiensi = st.slider("Efisiensi Irigasi (%)", 50, 90, 65)

# ==========================================
# 4. LOGIKA HITUNGAN (ENGINE)
# ==========================================
def hitung_nfr(df_input, start_index):
    # 1. Analisa R80 (Otomatis dari Rata-rata)
    df = df_input.copy()
    
    # Pastikan kolomnya angka (float) biar aman
    df['CH Rata-rata (mm)'] = df['CH Rata-rata (mm)'].astype(float)
    df['CH R80 (Analisa)'] = df['CH Rata-rata (mm)'] * (faktor_r80 / 100)
    
    # 2. Rotasi Jadwal
    df_rotasi = pd.concat([df.iloc[start_index:], df.iloc[:start_index]]).reset_index(drop=True)
    
    pola = get_pola_tanam_default()
    
    list_kegiatan = []
    list_nfr = []
    list_kc = []
    counter = 0
    
    for tahap in pola:
        durasi = tahap['Durasi']
        jenis = tahap['Jenis']
        for i in range(durasi):
            if counter >= 24: break 
            row = df_rotasi.iloc[counter]
            eto = row['ETo (mm/hr)']
            ch_r80 = row['CH R80 (Analisa)']
            
            re = (0.7 * ch_r80) / 15 
            nfr = 0
            kc_val = 0
            
            if "Pengolahan" in jenis:
                kebutuhan = kebutuhan_air_penyiapan
                nfr = kebutuhan - re
                kc_val = 0
            elif "Padi" in jenis:
                idx_kc = min(i, len(kc_padi_values)-1)
                kc_val = kc_padi_values[idx_kc]
                etc = eto * kc_val
                kebutuhan = etc + perkolasi
                nfr = kebutuhan - re 
            else:
                kc_val = tahap['Kc']
                etc = eto * kc_val
                kebutuhan = etc + perkolasi
                nfr = kebutuhan - re
            
            if nfr < 0: nfr = 0
            dr_lps = (nfr * 0.1157) / (efisiensi/100)
            
            list_kegiatan.append(jenis)
            list_nfr.append(dr_lps)
            list_kc.append(kc_val)
            counter += 1
            
    df_rotasi['Kegiatan'] = list_kegiatan + [''] * (24 - len(list_kegiatan))
    df_rotasi['DR (L/s/ha)'] = list_nfr + [0] * (24 - len(list_nfr))
    df_rotasi['Kc'] = list_kc + [0] * (24 - len(list_kc))
    
    return df_rotasi

# Jalankan Hitungan
# Gunakan key baru 'df_nfr_baru'
df_hasil = hitung_nfr(st.session_state['df_nfr_baru'], start_idx)
max_dr = df_hasil['DR (L/s/ha)'].max()

# ==========================================
# 5. TAMPILAN UTAMA
# ==========================================
st.title("🌾 Perencanaan Pola Tanam & Kebutuhan Air")
st.markdown(f"**Awal Tanam:** {periode_labels[start_idx]} | **Max DR:** {max_dr:.3f} L/det/ha")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Input Data (Rata-rata)")
    st.info("ℹ️ Masukkan Curah Hujan Rata-rata.")
    
    # Editor menggunakan key baru
    edited_df = st.data_editor(
        st.session_state['df_nfr_baru'],
        height=600,
        use_container_width=True,
        hide_index=True,
        column_config={
            "CH Rata-rata (mm)": st.column_config.NumberColumn("CH Rata-rata (mm)")
        }
    )
    st.session_state['df_nfr_baru'] = edited_df

with col2:
    st.subheader("2. Grafik Kebutuhan Air (DR)")
    
    bar = alt.Chart(df_hasil).mark_bar().encode(
        x=alt.X('Periode', sort=None),
        y=alt.Y('DR (L/s/ha)', title='Kebutuhan Air (L/det/ha)'),
        color=alt.Color('Kegiatan', legend=alt.Legend(title="Fase Tanam")),
        tooltip=['Periode', 'Kegiatan', alt.Tooltip('DR (L/s/ha)', format='.3f')]
    )
    line = alt.Chart(df_hasil).mark_line(color='red', strokeDash=[5,5]).encode(
        x=alt.X('Periode', sort=None),
        y=alt.Y('Kc', title='Koefisien Tanaman (Kc)'),
    )
    st.altair_chart((bar + line).resolve_scale(y='independent').interactive(), use_container_width=True)
    
    st.subheader("3. Hasil Analisa Sistem")
    
    # Memilih kolom spesifik untuk ditampilkan
    tabel_final = df_hasil[['Periode', 'Kegiatan', 'CH Rata-rata (mm)', 'CH R80 (Analisa)', 'DR (L/s/ha)']]
    
    st.dataframe(
        tabel_final.style.format({
            'CH Rata-rata (mm)': '{:.1f}',
            'CH R80 (Analisa)': '{:.1f}',
            'DR (L/s/ha)': '{:.3f}'
        }),
        use_container_width=True, 
        height=300
    )