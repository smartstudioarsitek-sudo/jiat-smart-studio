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
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.25
    elif Q < 5.0: return 0.30
    elif Q < 10.0: return 0.40
    elif Q < 15.0: return 0.50
    else: return 0.60

def solve_manning_y(Q, b, m, n, S):
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
    """Visualisasi Cross Section (Potongan Melintang)"""
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air, w_jagaan = row['Tinggi Total (h)'], row['Tinggi Air (y)'], row['Jagaan (w)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Geometri
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Koordinat Polygon
    p1 = (0, h_total); p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0); p4 = (x_talud_total + b + x_talud_total, h_total)
    
    # Gambar
    ax.add_patch(patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor='#333', facecolor='none', linewidth=3))
    
    # Air
    wa1 = (x_talud_total - x_talud_air, y_air); wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0); wa4 = (x_talud_total + b + x_talud_air, y_air)
    ax.add_patch(patches.Polygon([wa1, wa2, wa3, wa4], closed=True, color='#00BFFF', alpha=0.6))
    
    # Garis Tanah
    ax.plot([-1, 0], [h_total, h_total], 'k--', lw=1)
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], 'k--', lw=1)

    # Label
    ax.text(x_talud_total + b/2, y_air/2, f"y={y_air}m", ha='center', color='white', fontweight='bold')
    ax.set_title(f"Penampang: {nama}")
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_ylim(-0.2, h_total * 1.3); ax.set_xlim(-1, p4[0]+1)
    return fig

def gambar_profil_memanjang(df_hasil):
    """Visualisasi Long Section (Profil Memanjang)"""
    fig, ax = plt.subplots(figsize=(10, 4))
    
    stas = []
    elvs_dasar = []
    elvs_air = []
    
    # Loop untuk membuat koordinat garis (Start -> End tiap saluran)
    for i, row in df_hasil.iterrows():
        # Titik Awal Saluran
        stas.append(row['STA Awal'])
        elvs_dasar.append(row['Elv Dasar Awal'])
        elvs_air.append(row['Elv Dasar Awal'] + row['Tinggi Air (y)'])
        
        # Titik Akhir Saluran
        stas.append(row['STA Akhir'])
        elvs_dasar.append(row['Elv Dasar Akhir'])
        elvs_air.append(row['Elv Dasar Akhir'] + row['Tinggi Air (y)'])
        
        # Jika ada offset/drop ke saluran berikutnya, buat garis vertikal turun di grafik
        # (Akan otomatis tergambar karena titik berikutnya punya STA sama tapi Elv beda)

    ax.plot(stas, elvs_dasar, color='brown', linewidth=2, label='Dasar Saluran')
    ax.plot(stas, elvs_air, color='blue', linewidth=1, linestyle='-', label='Muka Air')
    
    # Fill area air
    ax.fill_between(stas, elvs_dasar, elvs_air, color='cyan', alpha=0.3)
    
    ax.set_xlabel("Stationing / Jarak (m)")
    ax.set_ylabel("Elevasi (m)")
    ax.set_title("Profil Memanjang (Long Section)", fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend()
    
    return fig

# ==========================================
# 3. SETUP HALAMAN
# ==========================================

st.set_page_config(page_title="Desain Irigasi Lengkap", layout="wide")
st.title("Desain Irigasi: Hidrolis & Elevasi")

# --- SIDEBAR: KONFIGURASI AWAL ---
with st.sidebar:
    st.header("⚙️ Konfigurasi Awal Sistem")
    st.info("Parameter ini menentukan titik mula (Start Point) saluran pertama.")
    
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Dasar Awal (+m)", value=100.00, help="Elevasi dasar saluran di titik 0")
    
    st.divider()
    st.header("📂 File Excel")
    
    # Template Download
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran 1', 'Saluran 2'],
        'Panjang (m)': [50.0, 100.0],
        'Offset (m)': [0.0, 0.5], # 0.5m drop di akhir saluran 1
        'Debit (Q)': [1.5, 1.5], 
        'Lebar (b)': [1.0, 1.0], 
        'Talud (m)': [1.0, 1.0], 
        'Slope (S)': [0.001, 0.001], 
        'Manning (n)': [0.017, 0.017]
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer: df_template.to_excel(writer, index=False)
    st.download_button("📥 Download Template", buffer.getvalue(), "template_lengkap.xlsx")
    
    # Upload
    uploaded = st.file_uploader("Upload Excel", type=['xlsx'])
    if uploaded:
        try:
            st.session_state.df_input = pd.read_excel(uploaded)
            st.success("Data loaded!")
        except: st.error("Error file.")

# ==========================================
# 4. INPUT DATA TABEL
# ==========================================

if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran A (Hulu)', 'Saluran B (Tengah)', 'Saluran C (Hilir)'],
        'Panjang (m)': [100.0, 150.0, 80.0],
        'Offset (m)': [0.0, 0.50, 0.0], # Offset ada di AKHIR saluran (terjunan ke saluran next)
        'Debit (Q)': [2.00, 1.80, 1.50],
        'Lebar (b)': [1.20, 1.00, 0.80],
        'Talud (m)': [1.0, 1.0, 0.0],
        'Slope (S)': [0.0005, 0.001, 0.002], 
        'Manning (n)': [0.022, 0.022, 0.017]
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

st.subheader("1. Input Data Berantai")
st.markdown("""
* **Urutan baris penting!** Baris 1 adalah Hulu, Baris 2 melanjutkan Baris 1, dst.
* **Offset (m)**: Adalah penurunan dasar saluran (drop/terjunan) di **ujung akhir** saluran tersebut sebelum masuk ke saluran berikutnya.
""")

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Panjang (m)": st.column_config.NumberColumn(format="%.1f"),
        "Offset (m)": st.column_config.NumberColumn(format="%.2f", help="Beda tinggi ke saluran berikutnya"),
        "Debit (Q)": st.column_config.NumberColumn(format="%.3f"),
        "Slope (S)": st.column_config.NumberColumn(format="%.5f"),
    },
    hide_index=True,
    key="editor_main"
)

# Update session
if not edited_df.equals(st.session_state.df_input):
    st.session_state.df_input = edited_df

# ==========================================
# 5. LOGIKA PERHITUNGAN BERANTAI (CHAINING)
# ==========================================

btn_run = st.button("▶️ HITUNG SEMUA (RUN)", type="primary", use_container_width=True)

if btn_run:
    hasil_list = []
    
    # Inisialisasi Variable "Estafet"
    current_sta = start_sta
    current_elv = start_elv
    
    for index, row in edited_df.iterrows():
        # 1. Ambil Data Input
        L = row['Panjang (m)']
        drop = row['Offset (m)']
        Q = row['Debit (Q)']
        b = row['Lebar (b)']
        m = row['Talud (m)']
        S = row['Slope (S)']
        n = row['Manning (n)']
        
        # 2. Hitung Hidrolis (Manning)
        y_calc = solve_manning_y(Q, b, m, n, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        v_calc = Q / ((b + m*y_calc)*y_calc) if ((b + m*y_calc)*y_calc) > 0 else 0
        
        # 3. Hitung STA & Elevasi (Logika Berantai)
        sta_awal = current_sta
        sta_akhir = current_sta + L
        
        elv_dasar_awal = current_elv
        # Rumus: Elv Akhir = Elv Awal - (Panjang * Slope)
        elv_dasar_akhir = elv_dasar_awal - (L * S)
        
        # Simpan Hasil
        hasil_list.append({
            'Nama Saluran': row['Nama Saluran'],
            'STA Awal': round(sta_awal, 1),
            'STA Akhir': round(sta_akhir, 1),
            'Elv Dasar Awal': round(elv_dasar_awal, 3),
            'Elv Dasar Akhir': round(elv_dasar_akhir, 3),
            'Drop/Offset': drop,
            'Tinggi Air (y)': round(y_calc, 3),
            'Tinggi Total (h)': round(h_calc, 2),
            'Kecepatan (V)': round(v_calc, 2),
            # Simpan data mentah untuk visualisasi
            'Lebar (b)': b, 'Talud (m)': m, 'Jagaan (w)': round(w_calc, 2)
        })
        
        # 4. Update Titik Start untuk Saluran Berikutnya
        current_sta = sta_akhir
        # Elv Start Next = Elv Akhir Current - Offset Drop
        current_elv = elv_dasar_akhir - drop

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    st.success("Perhitungan Berantai Selesai!")

# ==========================================
# 6. OUTPUT HASIL
# ==========================================

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    
    st.divider()
    st.subheader("2. Tabel Hasil (Long Section)")
    
    # Tampilkan kolom-kolom krusial saja
    cols_show = ['Nama Saluran', 'STA Awal', 'STA Akhir', 
                 'Elv Dasar Awal', 'Elv Dasar Akhir', 
                 'Drop/Offset', 'Tinggi Air (y)', 'Kecepatan (V)']
    
    st.dataframe(df_res[cols_show], use_container_width=True, hide_index=True)
    
    # Plot Grafik Profil Memanjang
    st.subheader("3. Grafik Profil Memanjang")
    st.caption("Grafik ini menunjukkan penurunan dasar saluran dari Hulu ke Hilir.")
    fig_long = gambar_profil_memanjang(df_res)
    st.pyplot(fig_long)
    
    st.divider()
    
    # Plot Penampang Melintang (Detail)
    st.subheader("4. Detail Penampang Melintang")
    pilihan = st.selectbox("Pilih Saluran:", df_res['Nama Saluran'])
    
    if pilihan:
        row_vis = df_res[df_res['Nama Saluran'] == pilihan].iloc[0]
        col1, col2 = st.columns([2, 1])
        with col1:
            st.pyplot(gambar_penampang_saluran(row_vis))
        with col2:
            st.info(f"**Posisi:** STA {row_vis['STA Awal']} s/d {row_vis['STA Akhir']}")
            st.write(f"Elevasi Hulu: `+{row_vis['Elv Dasar Awal']} m`")
            st.write(f"Elevasi Hilir: `+{row_vis['Elv Dasar Akhir']} m`")
            if row_vis['Drop/Offset'] > 0:
                st.warning(f"⬇️ Ada Terjunan setinggi {row_vis['Drop/Offset']} m di akhir saluran ini.")

    # Download
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer:
        df_res.to_excel(writer, index=False)
    st.download_button("💾 Download Hasil Lengkap (.xlsx)", output.getvalue(), "Hasil_Desain_LongSection.xlsx")
