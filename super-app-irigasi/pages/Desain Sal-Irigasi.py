import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- FUNGSI PERHITUNGAN HIDROLIS (MANNING TRAPESIUM) ---

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

def solve_manning_y(Q, b, m, n, S):
    """
    Menghitung kedalaman normal air (y) untuk penampang TRAPESIUM/KOTAK.
    Param:
    Q = Debit (m3/s)
    b = Lebar dasar (m)
    m = Kemiringan talud (1:m). Jika m=0 berarti persegi.
    n = Kekasaran Manning
    S = Kemiringan saluran
    """
    if Q <= 0 or b <= 0 or S <= 0:
        return 0.0
    
    # Tebakan awal y
    y = 0.5
    
    # Iterasi Newton/Secant sederhana
    for _ in range(50):
        # Rumus Geometri Trapesium
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        
        # Hitung Q berdasarkan tebakan y
        Q_calc = (1/n) * A * (R**(2/3)) * (S**0.5)
        
        # Cek konvergensi
        if abs(Q_calc - Q) < 0.0001:
            break
            
        # Update y (Metode rasio hidrolis untuk konvergensi stabil)
        if Q_calc == 0:
            y += 0.1
        else:
            # Pangkat 0.6 adalah pendekatan eksponen untuk Manning
            y = y * (Q / Q_calc) ** 0.6
            
    return y

# --- FUNGSI VISUALISASI PENAMPANG (TRAPESIUM) ---

def gambar_penampang_saluran(row):
    b = row['Lebar (b)']
    m = row['Talud (m)']  # Ambil nilai m
    h_total = row['Tinggi Total (h)']
    y_air = row['Tinggi Air (y)']
    w_jagaan = row['Jagaan (w)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # --- KOORDINAT GEOMETRI ---
    # Kita buat titik acuan x=0 di tebing kiri paling atas
    # Lebar atas total = b + 2 * (m * h)
    
    # Jarak horizontal talud (horizontal projection)
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Titik Sudut Saluran (Dinding Luar)
    # Urutan: Kiri-Atas -> Kiri-Bawah -> Kanan-Bawah -> Kanan-Atas
    p1 = (0, h_total)                       # Kiri Atas
    p2 = (x_talud_total, 0)                 # Kiri Bawah (Dasar)
    p3 = (x_talud_total + b, 0)             # Kanan Bawah (Dasar)
    p4 = (x_talud_total + b + x_talud_total, h_total) # Kanan Atas
    
    coords_saluran = [p1, p2, p3, p4]
    
    # Polygon Saluran (Tanah/Beton)
    poly_saluran = patches.Polygon(coords_saluran, closed=False, 
                                   edgecolor='#444444', facecolor='none', 
                                   linewidth=3, label='Dinding Saluran')
    ax.add_patch(poly_saluran)
    
    # Polygon Air
    # Titik air:
    wa1 = (x_talud_total - x_talud_air, y_air) # Kiri Atas Air
    wa2 = (x_talud_total, 0)                   # Kiri Bawah Air
    wa3 = (x_talud_total + b, 0)               # Kanan Bawah Air
    wa4 = (x_talud_total + b + x_talud_air, y_air) # Kanan Atas Air
    
    coords_air = [wa1, wa2, wa3, wa4]
    poly_air = patches.Polygon(coords_air, closed=True, 
                               edgecolor='none', facecolor='#00BFFF', 
                               alpha=0.6, label='Air')
    ax.add_patch(poly_air)
    
    # Garis Tanah Dasar (Kiri & Kanan luar saluran)
    ax.plot([-1, 0], [h_total, h_total], color='sienna', linewidth=2, linestyle='--')
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], color='sienna', linewidth=2, linestyle='--')

    # --- ANOTASI ---
    # Lebar Dasar (b)
    ax.annotate(f'b = {b:.2f} m', xy=(x_talud_total + b/2, -0.1 * h_total), 
                ha='center', va='top', color='blue')
    
    # Tinggi (h)
    ax.annotate(f'h = {h_total:.2f}', xy=(-0.2, h_total/2), 
                ha='right', va='center', rotation=90)
    
    # Kemiringan Talud (m)
    if m > 0:
        ax.annotate(f'm = {m}', xy=(x_talud_total/2, h_total/2), 
                    ha='center', va='center', rotation=45, fontsize=9, color='brown')
    else:
        ax.annotate('Tegak (m=0)', xy=(-0.5, h_total/2), rotation=90, fontsize=8, color='gray')

    # Jagaan (w)
    ax.annotate(f'w = {w_jagaan:.2f} m', xy=(p4[0], h_total - w_jagaan/2), 
                ha='left', va='center', color='red', fontsize=9)
    
    # Garis Muka Air
    ax.hlines(y=y_air, xmin=wa1[0], xmax=wa4[0], colors='blue', linewidth=1)
    ax.plot((wa1[0]+wa4[0])/2, y_air, marker='v', markersize=8, color='blue')

    # Setting Grafik
    ax.set_title(f"Penampang: {nama} (m={m})", fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Auto Scale limit
    max_width = p4[0]
    ax.set_xlim(-1, max_width + 1)
    ax.set_ylim(-0.5 * h_total, h_total * 1.5)
    
    return fig

# --- MAIN APP STREAMLIT ---

st.title("Desain Saluran Irigasi (Trapesium & Kotak)")
st.markdown("""
Hitung dimensi saluran hidrolis secara otomatis sesuai **Standar KP-03**.
* Masukkan **Talud (m)**: 
    * `0` untuk saluran **Kotak/Persegi** (Pasangan Batu/Beton).
    * `1` atau `1.5` untuk saluran **Trapesium** (Saluran Tanah).
""")

# 1. INISIALISASI DATA
if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran Sekunder 1', 'Saluran Tersier A'],
        'Debit (Q)': [1.25, 0.45],       # m3/s
        'Lebar (b)': [1.00, 0.60],       # m
        'Talud (m)': [0.0, 1.0],         # 0 = Kotak, 1 = Miring 1:1
        'Slope (S)': [0.0005, 0.001], 
        'Manning (n)': [0.017, 0.022]    # 0.017 (Batu), 0.022 (Tanah)
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

# 2. INPUT DATA EDITOR
st.subheader("1. Input Parameter Desain")
st.caption("Ubah nilai di bawah. Tekan Enter untuk update hasil.")

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Debit (Q)": st.column_config.NumberColumn("Debit Q (m³/s)", min_value=0.001, format="%.3f"),
        "Lebar (b)": st.column_config.NumberColumn("Lebar Dasar b (m)", min_value=0.1, format="%.2f"),
        "Talud (m)": st.column_config.NumberColumn("Talud m (1:m)", min_value=0.0, step=0.25, format="%.2f", help="0=Tegak, 1=Miring 45 derajat"),
        "Slope (S)": st.column_config.NumberColumn("Kemiringan S", format="%.5f"),
        "Manning (n)": st.column_config.NumberColumn("Kekasaran n", format="%.3f"),
    },
    hide_index=True
)

# 3. PERHITUNGAN OTOMATIS
hasil_y = []
hasil_w = []
hasil_h = []
hasil_v = []
hasil_type = []

for index, row in edited_df.iterrows():
    q = row['Debit (Q)']
    b = row['Lebar (b)']
    m = row['Talud (m)'] # Ambil m
    s = row['Slope (S)']
    n = row['Manning (n)']
    
    # Hitung Y (Manning Trapesium/Kotak)
    y_calc = solve_manning_y(q, b, m, n, s)
    
    # Hitung W (Freeboard KP-03)
    w_calc = get_freeboard_kp03(q)
    
    # Hitung H total
    h_calc = y_calc + w_calc
    
    # Hitung Kecepatan V = Q / A
    area = (b + m * y_calc) * y_calc
    v_calc = q / area if area > 0 else 0
    
    # Tentukan Tipe untuk info
    tipe_sal = "Kotak" if m == 0 else "Trapesium"
    
    hasil_y.append(round(y_calc, 3))
    hasil_w.append(round(w_calc, 2))
    hasil_h.append(round(h_calc, 2))
    hasil_v.append(round(v_calc, 2))
    hasil_type.append(tipe_sal)

# Gabungkan Hasil
df_hasil = edited_df.copy()
df_hasil['Tipe'] = hasil_type
df_hasil['Tinggi Air (y)'] = hasil_y
df_hasil['Jagaan (w)'] = hasil_w
df_hasil['Tinggi Total (h)'] = hasil_h
df_hasil['Kecepatan (V)'] = hasil_v

# 4. TABEL HASIL
st.subheader("2. Hasil Perhitungan")
st.dataframe(
    df_hasil[['Nama Saluran', 'Tipe', 'Debit (Q)', 'Lebar (b)', 'Talud (m)', 'Tinggi Air (y)', 'Tinggi Total (h)', 'Kecepatan (V)']],
    use_container_width=True,
    hide_index=True
)

# 5. VISUALISASI GAMBAR
st.subheader("3. Visualisasi Penampang")
pilihan_saluran = st.selectbox("Pilih Saluran:", df_hasil['Nama Saluran'])

if pilihan_saluran:
    row_visual = df_hasil[df_hasil['Nama Saluran'] == pilihan_saluran].iloc[0]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = gambar_penampang_saluran(row_visual)
        st.pyplot(fig)
        
    with col2:
        st.markdown(f"**Data Teknis: {pilihan_saluran}**")
        st.write(f"Tipe: **{row_visual['Tipe']}**")
        st.write(f"Talud ($m$): `{row_visual['Talud (m)']}`")
        st.write(f"Lebar Dasar ($b$): `{row_visual['Lebar (b)']} m`")
        st.write(f"Tinggi Jagaan ($w$): `{row_visual['Jagaan (w)']} m`")
        
        # Luas Basah
        b_vis = row_visual['Lebar (b)']
        m_vis = row_visual['Talud (m)']
        y_vis = row_visual['Tinggi Air (y)']
        A_wet = (b_vis + m_vis * y_vis) * y_vis
        st.write(f"Luas Basah ($A$): `{A_wet:.2f} m²`")
        
        # Cek Kecepatan
        v = row_visual['Kecepatan (V)']
        st.metric("Kecepatan Aliran", f"{v} m/s")
        if v < 0.3:
            st.error("Terlalu Rendah (< 0.3 m/s). Sedimentasi!")
        elif v > 2.0: # Asumsi pasangan batu/tanah keras
            st.warning("Hati-hati, kecepatan tinggi (> 2 m/s).")
        else:
            st.success("Kecepatan Aman.")
