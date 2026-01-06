import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# ==========================================
# 1. FUNGSI PERHITUNGAN HIDROLIS
# ==========================================

def get_freeboard_kp03(Q):
    """Menghitung Tinggi Jagaan sesuai KP-03"""
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.25
    elif Q < 5.0: return 0.30
    elif Q < 10.0: return 0.40
    elif Q < 15.0: return 0.50
    else: return 0.60

def solve_manning_y(Q, b, m, n, S):
    """Menghitung tinggi muka air (y) dengan iterasi Manning"""
    if Q <= 0 or b <= 0 or S <= 0: return 0.0
    y = 0.5
    for _ in range(50):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        Q_calc = (1/n) * A * (R**(2/3)) * (S**0.5)
        if abs(Q_calc - Q) < 0.0001: break
        if Q_calc == 0: y += 0.1
        else: y = y * (Q / Q_calc) ** 0.6
    return y

# ==========================================
# 2. FUNGSI VISUALISASI
# ==========================================

def gambar_penampang_saluran(row):
    """Visualisasi Potongan Melintang (Cross Section)"""
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air, w_jagaan = row['Tinggi Total (h)'], row['Tinggi Air (y)'], row['Jagaan (w)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Geometri Koordinat
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Koordinat Dinding Saluran
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    # Gambar Dinding
    ax.add_patch(patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor='#333', facecolor='none', linewidth=3))
    
    # Gambar Air
    wa1 = (x_talud_total - x_talud_air, y_air)
    wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0)
    wa4 = (x_talud_total + b + x_talud_air, y_air)
    ax.add_patch(patches.Polygon([wa1, wa2, wa3, wa4], closed=True, color='#00BFFF', alpha=0.6))
    
    # Garis Tanah
    ax.plot([-1, 0], [h_total, h_total], 'k--', lw=1)
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], 'k--', lw=1)

    # Label Dimensi
    ax.text(x_talud_total + b/2, y_air/2, f"y={y_air}m", ha='center', color='white', fontweight='bold')
    ax.set_title(f"Penampang: {nama}")
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_ylim(-0.2, h_total * 1.3); ax.set_xlim(-1, p4[0]+1)
    return fig

def gambar_profil_memanjang(df_hasil):
    """Visualisasi Profil Memanjang (Long Section)"""
    fig, ax = plt.subplots(figsize=(10, 4))
    
    stas = []
    elvs_dasar = []
    elvs_air = []
    
    for i, row in df_hasil.iterrows():
        # Titik Awal Saluran
        stas.append(row['STA Awal'])
        elvs_dasar.append(row['Elv Dasar Awal'])
        elvs_air.append(row['Elv Dasar Awal'] + row['Tinggi Air (y)'])
        
        # Titik Akhir Saluran
        stas.append(row['STA Akhir'])
        elvs_dasar.append(row['Elv Dasar Akhir'])
        elvs_air.append(row['Elv Dasar Akhir'] + row['Tinggi Air (y)'])

    # Plot Garis
    ax.plot(stas, elvs_dasar, color='brown', linewidth=2, label='Dasar Saluran')
    ax.plot(stas, elvs_air, color='blue', linewidth=1, linestyle='-', label='Muka Air')
    
    # Arsir Air
    ax.fill_between(stas, elvs_dasar, elvs_air, color='cyan', alpha=0.3)
    
    ax.set_xlabel("Stationing / Jarak (m)")
    ax.set_ylabel("Elevasi (m)")
    ax.set_title("Profil Memanjang (Long Section)", fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend()
    
    return fig

# ==========================================
# 3. KONFIGURASI HALAMAN
# ==========================================

st.set_page_config(page_title="Desain Irigasi Lengkap", layout="wide")
st.title("Desain Irigasi: Hidrolis & Elevasi")

# --- SIDEBAR: KONFIGURASI & EXCEL ---
with st.sidebar:
    st.header("⚙️ Konfigurasi Awal")
    st.info("Tentukan titik mulai (Start Point) saluran pertama.")
    
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Dasar Awal (+m)", value=322.00, help="Elevasi di titik 0")
    
    st.divider()
    st.header("📂 Menu Excel")
    
    # Template
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran 1', 'Saluran 2'],
        'Panjang (m)': [50.0, 100.0],
        'Offset (m)': [-0.5, -0.5], # Minus untuk turun
        'Debit (Q)': [1.5, 1.5], 
        'Lebar (b)': [1.0, 1.0], 
        'Talud (m)': [1.0, 1.0], 
        'Slope (S)': [0.001, 0.001], 
        'Manning (n)': [0.017, 0.017]
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer: df_template.to_excel(writer, index=False)
    st.download_button("📥 Download Template", buffer.getvalue(), "template_irigasi.xlsx")
    
    # Upload
    uploaded = st.file_uploader("Upload Excel", type=['xlsx'])
    if uploaded:
        try:
            st.session_state.df_input = pd.read_excel(uploaded)
            st.success("Data Excel berhasil dimuat!")
        except: st.error("Gagal membaca file Excel.")

# ==========================================
# 4. EDITOR DATA
# ==========================================

if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran A', 'Saluran B', 'Saluran C'],
        'Panjang (m)': [50.0, 50.0, 50.0],
        'Offset (m)': [-1.50, -1.50, -1.50], # Gunakan Minus agar turun
        'Debit (Q)': [2.00, 2.00, 2.00],
        'Lebar (b)': [1.00, 1.00, 1.00],
        'Talud (m)': [1.0, 1.0, 1.0],
        'Slope (S)': [0.003, 0.003, 0.003], 
        'Manning (n)': [0.017, 0.017, 0.017]
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

st.subheader("1. Input Data Berantai")
st.info("💡 **Tips:** Isi 'Offset' dengan nilai **Negatif (misal -1.5)** agar elevasi turun (terjunan).")

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Panjang (m)": st.column_config.NumberColumn(format="%.1f"),
        "Offset (m)": st.column_config.NumberColumn(format="%.2f", help="Beda tinggi ke saluran berikutnya (Pakai minus untuk turun)"),
        "Debit (Q)": st.column_config.NumberColumn(format="%.3f"),
        "Slope (S)": st.column_config.NumberColumn(format="%.5f"),
    },
    hide_index=True
)

if not edited_df.equals(st.session_state.df_input):
    st.session_state.df_input = edited_df

# ==========================================
# 5. LOGIKA RUNNING (DIPERBAIKI)
# ==========================================

btn_run = st.button("▶️ HITUNG SEMUA (RUN)", type="primary", use_container_width=True)

if btn_run:
    hasil_list = []
    
    # Inisialisasi Estafet
    current_sta = start_sta
    current_elv = start_elv
    
    for index, row in edited_df.iterrows():
        # 1. Ambil Data
        L = row['Panjang (m)']
        offset_input = row['Offset (m)'] 
        Q = row['Debit (Q)']
        b = row['Lebar (b)']
        m = row['Talud (m)']
        S = row['Slope (S)']
        n = row['Manning (n)']
        
        # 2. Hitung Hidrolis
        y_calc = solve_manning_y(Q, b, m, n, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        area_wet = (b + m * y_calc) * y_calc
        v_calc = Q / area_wet if area_wet > 0 else 0
        
        # 3. Hitung Elevasi & STA
        sta_awal = current_sta
        sta_akhir = current_sta + L
        
        elv_dasar_awal = current_elv
        elv_dasar_akhir = elv_dasar_awal - (L * S) # Turun karena kemiringan
        
        hasil_list.append({
            'Nama Saluran': row['Nama Saluran'],
            'STA Awal': round(sta_awal, 1),
            'STA Akhir': round(sta_akhir, 1),
            'Elv Dasar Awal': round(elv_dasar_awal, 3),
            'Elv Dasar Akhir': round(elv_dasar_akhir, 3),
            'Drop/Offset': offset_input,
            'Tinggi Air (y)': round(y_calc, 3),
            'Tinggi Total (h)': round(h_calc, 2),
            'Kecepatan (V)': round(v_calc, 2),
            # Simpan data mentah
            'Lebar (b)': b, 'Talud (m)': m, 'Jagaan (w)': round(w_calc, 2)
        })
        
        # 4. Update Titik Start Berikutnya
        current_sta = sta_akhir
        # REVISI LOGIKA: Dijumlahkan. Jika offset minus (-1.5), dia akan turun.
        current_elv = elv_dasar_akhir + offset_input 

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    st.success("Selesai! Elevasi sekarang sudah valid (Turun jika offset negatif).")

# ==========================================
# 6. OUTPUT HASIL
# ==========================================

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    
    st.divider()
    st.subheader("2. Tabel Hasil (Long Section)")
    cols_show = ['Nama Saluran', 'STA Awal', 'STA Akhir', 'Elv Dasar Awal', 'Elv Dasar Akhir', 'Drop/Offset', 'Tinggi Air (y)', 'Kecepatan (V)']
    st.dataframe(df_res[cols_show], use_container_width=True, hide_index=True)
    
    st.subheader("3. Grafik Profil Memanjang")
    st.pyplot(gambar_profil_memanjang(df_res))
    
    st.subheader("4. Detail Penampang")
    pilihan = st.selectbox("Pilih Saluran:", df_res['Nama Saluran'])
    if pilihan:
        row_vis = df_res[df_res['Nama Saluran'] == pilihan].iloc[0]
        col1, col2 = st.columns([2, 1])
        with col1: st.pyplot(gambar_penampang_saluran(row_vis))
        with col2:
            st.info(f"Posisi: STA {row_vis['STA Awal']} - {row_vis['STA Akhir']}")
            st.metric("Elevasi Hulu", f"+{row_vis['Elv Dasar Awal']}")
            st.metric("Elevasi Hilir", f"+{row_vis['Elv Dasar Akhir']}")

    # Save Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer: df_res.to_excel(writer, index=False)
    st.download_button("💾 Download Laporan (.xlsx)", output.getvalue(), "Laporan_Irigasi.xlsx")
