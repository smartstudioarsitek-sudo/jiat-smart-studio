import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Desain Saluran", layout="wide", page_icon="🏗️")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #546e7a 0%, #78909c 50%, #90a4ae 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .status-safe { color: #2e7d32; font-weight: bold; }
    .status-danger { color: #c62828; font-weight: bold; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🏗️ Desain Hidrolika Saluran</h1>
    <p style="opacity: 0.9;">Analisa Dimensi & Kapasitas Penampang (Manning)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. AMBIL DATA DARI MODUL SEBELUMNYA ---
if 'nfr_global' in st.session_state:
    modulus_link = st.session_state['nfr_global']
    status_link = "✅ Terhubung: Modul Pola Tanam"
    link_active = True
else:
    modulus_link = 1.25 # Default standar jika belum ada data
    status_link = "⚠️ Default (Modul Pola Tanam belum dijalankan)"
    link_active = False

# --- 4. DATA DEFAULT ---
if 'df_saluran' not in st.session_state:
    st.session_state.df_saluran = pd.DataFrame({
        'Nama Saluran': ['Saluran Induk', 'Sekunder A', 'Sekunder B', 'Tersier 1'],
        'Luas Areal (ha)': [500.0, 250.0, 250.0, 50.0],
        'Modulus (l/s/ha)': [modulus_link] * 4, # Otomatis terisi link
        'Lebar Bawah b (m)': [1.5, 1.0, 1.0, 0.5],
        'Tinggi Air h (m)': [1.0, 0.8, 0.8, 0.4],
        'Kemiringan m (1:m)': [1.0, 1.0, 1.0, 1.0],
        'Slope S (%)': [0.05, 0.08, 0.08, 0.1],
        'Kekasaran n': [0.025, 0.025, 0.025, 0.030] # Pasangan batu vs Tanah
    })

# Tombol Refresh Link NFR
if link_active:
    # Update nilai modulus di tabel jika user ingin sinkronisasi ulang
    if st.button("🔄 Update Modulus dari Pola Tanam"):
        st.session_state.df_saluran['Modulus (l/s/ha)'] = modulus_link
        st.toast(f"Semua saluran diupdate ke Modulus: {modulus_link}", icon="🔄")

# --- 5. INPUT TABEL ---
st.subheader("1. Input Dimensi Saluran")

col_info1, col_info2 = st.columns([2, 1])
with col_info1:
    st.info(f"ℹ️ **Status Data:** {status_link} \n\nNilai Modulus saat ini: **{modulus_link} l/det/ha**")

edited_df = st.data_editor(
    st.session_state.df_saluran,
    use_container_width=True,
    num_rows="dynamic",
    key="editor_saluran_v1",
    column_config={
        "Nama Saluran": st.column_config.TextColumn(required=True),
        "Luas Areal (ha)": st.column_config.NumberColumn(required=True, min_value=0),
        "Modulus (l/s/ha)": st.column_config.NumberColumn(required=True, help="Kebutuhan air per hektar"),
        "Lebar Bawah b (m)": st.column_config.NumberColumn(min_value=0.1, format="%.2f"),
        "Tinggi Air h (m)": st.column_config.NumberColumn(min_value=0.1, format="%.2f"),
        "Slope S (%)": st.column_config.NumberColumn(help="Kemiringan dasar saluran dalam Persen (%)", format="%.3f"),
        "Kekasaran n": st.column_config.NumberColumn(help="Koefisien Manning (Beton=0.015, Batu=0.025, Tanah=0.030)", format="%.3f")
    }
)
st.session_state.df_saluran = edited_df

# --- 6. ENGINE PERHITUNGAN HIDROLIKA ---
hasil_analisa = []

for idx, row in edited_df.iterrows():
    # Ambil variabel
    A_req_ha = row['Luas Areal (ha)']
    mod = row['Modulus (l/s/ha)']
    b = row['Lebar Bawah b (m)']
    h = row['Tinggi Air h (m)']
    m = row['Kemiringan m (1:m)']
    S_percent = row['Slope S (%)']
    n = row['Kekasaran n']
    
    # 1. Hitung Debit Rencana (Q_req)
    # Q = Areal x Modulus / 1000 (konversi l/s ke m3/s)
    q_req = (A_req_ha * mod) / 1000
    
    # 2. Hitung Properti Geometri
    A_wet = (b + m * h) * h  # Luas Basah
    P_wet = b + 2 * h * np.sqrt(1 + m**2) # Keliling Basah
    R = A_wet / P_wet if P_wet > 0 else 0 # Jari-jari Hidrolis
    
    # 3. Hitung Kecepatan & Kapasitas (Manning)
    # V = 1/n * R^(2/3) * S^(1/2)
    # S harus dalam desimal (0.05% -> 0.0005)
    S_decimal = S_percent / 100
    V = (1/n) * (R**(2/3)) * (S_decimal**0.5)
    q_cap = A_wet * V
    
    # 4. Cek Status
    safety_factor = q_cap / q_req if q_req > 0 else 0
    if q_cap >= q_req:
        status = "✅ AMAN"
        note = "OK"
    else:
        status = "❌ BANJIR"
        note = f"Kurang {round(q_req - q_cap, 3)} m³/s"
        
    # Froude Number (Cek Aliran Kritis)
    # T (Lebar Atas) = b + 2*m*h
    T = b + 2 * m * h
    D = A_wet / T # Hydraulic Depth
    Fr = V / np.sqrt(9.81 * D)
    flow_type = "Subkritis (Tenang)" if Fr < 1 else "Superkritis (Cepat)"

    hasil_analisa.append({
        'Nama Saluran': row['Nama Saluran'],
        'Q Rencana (m³/s)': round(q_req, 3),
        'Q Kapasitas (m³/s)': round(q_cap, 3),
        'Kecepatan V (m/s)': round(V, 2),
        'Status': status,
        'Catatan': note,
        'Tipe Aliran': flow_type,
        'Fr': round(Fr, 2)
    })

df_hasil = pd.DataFrame(hasil_analisa)

# --- 7. TAMPILAN HASIL ---
st.divider()
st.subheader("2. Hasil Analisa Kapasitas")

# Highlight Error di Tabel
def highlight_status(val):
    color = '#d4edda' if 'AMAN' in val else '#f8d7da' # Hijau vs Merah
    return f'background-color: {color}'

st.dataframe(
    df_hasil.style.map(highlight_status, subset=['Status']),
    use_container_width=True
)

# --- 8. VISUALISASI PENAMPANG (FITUR BARU) ---
col_vis1, col_vis2 = st.columns([1, 2])

with col_vis1:
    st.markdown("### 🔍 Cek Visual")
    selected_channel = st.selectbox("Pilih Saluran untuk Dilihat:", edited_df['Nama Saluran'])
    
    # Ambil data saluran terpilih
    row_sel = edited_df[edited_df['Nama Saluran'] == selected_channel].iloc[0]
    res_sel = df_hasil[df_hasil['Nama Saluran'] == selected_channel].iloc[0]
    
    st.metric("Kapasitas Saluran", f"{res_sel['Q Kapasitas (m³/s)']} m³/s", delta=res_sel['Status'])
    st.caption(f"Dimensi: b={row_sel['Lebar Bawah b (m)']} m, h={row_sel['Tinggi Air h (m)']} m")

with col_vis2:
    # Plotting Matplotlib Sederhana untuk Penampang
    b = row_sel['Lebar Bawah b (m)']
    h = row_sel['Tinggi Air h (m)']
    m = row_sel['Kemiringan m (1:m)']
    t_atas = b + 2 * m * h
    
    fig, ax = plt.subplots(figsize=(6, 3))
    
    # Koordinat Trapesium
    x = [0, m*h, m*h + b, m*h + b + m*h]
    y = [h, 0, 0, h]
    
    # Gambar Tanah
    ax.plot(x, y, 'k-', linewidth=2, label='Tanah Asli') # Garis Saluran
    ax.fill(x, y, '#8d6e63', alpha=0.3) # Warna tanah
    
    # Gambar Air
    # Misal tinggi jagaan 0.3m (asumsi visual saja)
    h_air = h
    x_air = [0, m*h_air, m*h_air + b, m*h_air + b + m*h_air]
    y_air = [h_air, 0, 0, h_air]
    ax.fill(x_air, y_air, '#29b6f6', alpha=0.6, label='Air')
    
    ax.set_title(f"Penampang Melintang: {selected_channel}")
    ax.set_aspect('equal')
    ax.grid(True, linestyle='--', alpha=0.5)
    
    st.pyplot(fig)
