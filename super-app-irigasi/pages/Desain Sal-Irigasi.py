import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- FUNGSI-FUNGSI PERHITUNGAN HIDROLIS (SESUAI SNI/KP-03) ---

def get_freeboard_kp03(Q):
    """
    Menentukan Tinggi Jagaan (w) berdasarkan Debit (Q)
    Sesuai Standar Perencanaan Irigasi KP-03.
    """
    if Q < 0.5:
        return 0.20
    elif Q < 1.5:
        return 0.25
    elif Q < 5.0:
        return 0.30
    elif Q < 10.0:
        return 0.40
    elif Q < 15.0:
        return 0.50
    else:
        return 0.60

def solve_manning_y(Q, b, n, S):
    """
    Menghitung kedalaman normal air (y) dari Q, b, n, S
    Menggunakan metode iterasi numerik karena persamaan Manning implisit untuk y.
    Rumus: Q = (1/n) * A * R^(2/3) * S^(1/2)
    """
    if Q <= 0 or b <= 0 or S <= 0:
        return 0.0
    
    # Tebakan awal y (misal 0.5 meter)
    y = 0.5
    
    # Iterasi untuk mencari y yang menyeimbangkan persamaan
    for _ in range(50): # 50 iterasi biasanya sudah sangat presisi
        A = b * y
        P = b + 2 * y
        R = A / P if P > 0 else 0
        
        # Hitung Q berdasarkan tebakan y saat ini
        Q_calc = (1/n) * A * (R**(2/3)) * (S**0.5)
        
        # Cek error
        if abs(Q_calc - Q) < 0.0001:
            break
            
        # Update y menggunakan rasio (metode konvergensi cepat hidrolika)
        # Mencegah pembagian nol
        if Q_calc == 0: 
            y += 0.1
        else:
            y = y * (Q / Q_calc) ** 0.6
            
    return y

# --- FUNGSI VISUALISASI ---

def gambar_penampang_saluran(row):
    """
    Menggambar penampang saluran kotak berdasarkan hasil desain.
    """
    # Ambil data dari baris dataframe
    b = row['Lebar (b)']
    h_total = row['Tinggi Total (h)']
    y_air = row['Tinggi Air (y)']
    w_jagaan = row['Jagaan (w)']
    nama = row['Nama Saluran']
    
    # Setup Plot
    fig, ax = plt.subplots(figsize=(6, 4))
    
    # 1. Gambar Tanah Dasar (Garis Coklat)
    ax.plot([-1, b+1], [0, 0], color='sienna', linewidth=2, linestyle='--')
    
    # 2. Gambar Kotak Saluran (Dinding & Lantai) - Warna Abu Gelap (Beton/Batu)
    # Koordinat: (0,h) -> (0,0) -> (b,0) -> (b,h)
    x_coords = [0, 0, b, b]
    y_coords = [h_total, 0, 0, h_total]
    ax.plot(x_coords, y_coords, color='#444444', linewidth=3, label='Dinding Saluran')
    
    # 3. Gambar Air (Isi Biru)
    # Rectangle(xy, width, height)
    air = patches.Rectangle((0, 0), b, y_air, linewidth=0, edgecolor=None, facecolor='#00BFFF', alpha=0.6, label='Air')
    ax.add_patch(air)
    
    # 4. Anotasi Dimensi
    # Label Lebar (b)
    ax.annotate(f'b = {b:.2f} m', xy=(b/2, -0.1), ha='center', va='top', fontsize=10, color='blue')
    
    # Label Tinggi Total (h)
    ax.annotate(f'h = {h_total:.2f} m', xy=(-0.1, h_total/2), ha='right', va='center', rotation=90, fontsize=10)
    
    # Label Tinggi Air (y)
    ax.annotate(f'y = {y_air:.2f} m', xy=(b/2, y_air/2), ha='center', va='center', color='white', fontweight='bold')
    
    # Label Jagaan (w)
    ax.annotate(f'w = {w_jagaan:.2f} m', xy=(b+0.1, y_air + w_jagaan/2), ha='left', va='center', fontsize=9, color='red')
    
    # Garis batas air
    ax.hlines(y=y_air, xmin=0, xmax=b, colors='blue', linestyles='-', linewidth=1)
    
    # Tampilan Air Mengalir (Simbol segitiga terbalik)
    ax.plot(b/2, y_air, marker='v', markersize=8, color='blue')

    ax.set_title(f"Visualisasi: {nama}", fontweight='bold')
    ax.set_aspect('equal') # Agar skala x dan y sama (proporsional)
    ax.set_xlim(-0.5, b + 0.5)
    ax.set_ylim(-0.5, h_total + 0.5)
    ax.axis('off') # Hilangkan sumbu x/y standar agar bersih
    
    return fig

# --- MAIN APP STREAMLIT ---

st.title("Aplikasi Desain Saluran Irigasi (Otomatis)")
st.markdown("""
Aplikasi ini menghitung dimensi saluran secara otomatis berdasarkan **Debit Rencana**.
* **Tinggi Air ($y$)**: Dihitung menggunakan Rumus Manning.
* **Tinggi Jagaan ($w$)**: Otomatis berdasarkan Standar KP-03.
* **Tinggi Saluran ($h$)**: Penjumlahan $y + w$.
""")

# 1. INISIALISASI DATA AWAL
if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran Sekunder 1', 'Saluran Tersier A'],
        'Debit (Q)': [1.25, 0.45],       # m3/s
        'Lebar (b)': [1.00, 0.60],       # m
        'Slope (S)': [0.0005, 0.001],    # Kemiringan dasar (misal 1/2000 dan 1/1000)
        'Manning (n)': [0.017, 0.017]    # 0.017 = Pasangan Batu, 0.015 = Beton
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

# 2. INPUT DATA (USER HANYA EDIT INPUT UTAMA)
st.subheader("1. Input Parameter Desain")
st.info("Silakan ubah Debit (Q) atau Lebar (b). Tinggi (h) akan dihitung otomatis.")

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Debit (Q)": st.column_config.NumberColumn("Debit Q (m³/s)", min_value=0.01, step=0.05, format="%.3f"),
        "Lebar (b)": st.column_config.NumberColumn("Lebar b (m)", min_value=0.1, step=0.1, format="%.2f"),
        "Slope (S)": st.column_config.NumberColumn("Kemiringan S", min_value=0.0001, step=0.0001, format="%.5f"),
        "Manning (n)": st.column_config.NumberColumn("Kekasaran n", min_value=0.010, step=0.001, format="%.3f"),
    },
    hide_index=True
)

# 3. PROSES PERHITUNGAN OTOMATIS (BACKEND)
# Kita buat list kosong untuk menampung hasil hitungan
hasil_y = []
hasil_w = []
hasil_h = []
hasil_v = [] # Kecepatan aliran

for index, row in edited_df.iterrows():
    q = row['Debit (Q)']
    b = row['Lebar (b)']
    s = row['Slope (S)']
    n = row['Manning (n)']
    
    # Hitung Tinggi Muka Air (y)
    y_calc = solve_manning_y(q, b, n, s)
    
    # Hitung Jagaan (w) sesuai KP-03
    w_calc = get_freeboard_kp03(q)
    
    # Hitung Tinggi Total (h)
    h_calc = y_calc + w_calc
    
    # Hitung Kecepatan (V = Q/A) untuk info tambahan
    area = b * y_calc
    v_calc = q / area if area > 0 else 0
    
    hasil_y.append(round(y_calc, 3))
    hasil_w.append(round(w_calc, 2))
    hasil_h.append(round(h_calc, 2)) # Pembulatan desain (misal 2 desimal)
    hasil_v.append(round(v_calc, 2))

# Masukkan hasil hitungan ke DataFrame baru untuk ditampilkan
df_hasil = edited_df.copy()
df_hasil['Tinggi Air (y)'] = hasil_y
df_hasil['Jagaan (w)'] = hasil_w
df_hasil['Tinggi Total (h)'] = hasil_h
df_hasil['Kecepatan (V)'] = hasil_v

# 4. TAMPILKAN HASIL DESAIN
st.subheader("2. Hasil Desain (Sesuai KP-03)")
st.dataframe(
    df_hasil[['Nama Saluran', 'Debit (Q)', 'Lebar (b)', 'Tinggi Air (y)', 'Jagaan (w)', 'Tinggi Total (h)', 'Kecepatan (V)']],
    use_container_width=True,
    hide_index=True
)

st.write("---")

# 5. VISUALISASI PENAMPANG
st.subheader("3. Visualisasi Penampang")

# Pilih saluran mana yang mau divisualisasikan
pilihan_saluran = st.selectbox("Pilih Saluran untuk Dilihat:", df_hasil['Nama Saluran'])

# Ambil data baris yang dipilih
row_visual = df_hasil[df_hasil['Nama Saluran'] == pilihan_saluran].iloc[0]

# Render Gambar
col1, col2 = st.columns([2, 1])

with col1:
    fig = gambar_penampang_saluran(row_visual)
    st.pyplot(fig)

with col2:
    st.write(f"**Detail {pilihan_saluran}:**")
    st.write(f"- Debit: `{row_visual['Debit (Q)']} m³/s`")
    st.write(f"- Dimensi: `{row_visual['Lebar (b)']} m` x `{row_visual['Tinggi Total (h)']} m`")
    st.write(f"- Tinggi Air: `{row_visual['Tinggi Air (y)']} m`")
    st.write(f"- Freeboard: `{row_visual['Jagaan (w)']} m`")
    
    # Cek Logika Kecepatan (Ijin)
    # Kecepatan ijin biasanya 0.3 - 2.0 m/s untuk pasangan batu
    v = row_visual['Kecepatan (V)']
    if v < 0.3:
        st.warning(f"⚠️ Kecepatan {v} m/s terlalu rendah (Potensi sedimentasi/endapan lumpur).")
    elif v > 2.0:
        st.warning(f"⚠️ Kecepatan {v} m/s terlalu tinggi (Potensi gerusan).")
    else:
        st.success(f"✅ Kecepatan {v} m/s aman (0.3 - 2.0 m/s).")

