import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# ==========================================
# 1. FUNGSI PERHITUNGAN HIDROLIS (STANDAR KP-03)
# ==========================================

def get_freeboard_kp03(Q):
    """
    Menghitung Tinggi Jagaan (Freeboard) sesuai Tabel KP-03.
    Q dalam m3/dt, Output W dalam meter.
    """
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.20  # Revisi sesuai Laporan (0.5 - 1.5 tetap 0.20)
    elif Q < 5.0: return 0.25
    elif Q < 10.0: return 0.30
    elif Q < 15.0: return 0.40
    else: return 0.50

def solve_strickler_y(Q, b, m, k, S):
    """
    Menghitung tinggi muka air (y) dengan Rumus STRICKLER (KP-03).
    V = k * R^(2/3) * I^(1/2)
    """
    if Q <= 0 or b <= 0 or S <= 0: return 0.0
    
    y = 0.5 # Tebakan awal
    # Iterasi Newton-Raphson untuk konvergensi cepat
    for _ in range(50):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        
        # Rumus Debit Strickler: Q = A * V
        Q_calc = A * k * (R**(2/3)) * (S**0.5)
        
        if abs(Q_calc - Q) < 0.0001: break
        
        # Adjustment step
        if Q_calc == 0: y += 0.1
        else: y = y * (Q / Q_calc) ** 0.6
        
    return y

def cek_keamanan_desain(Q, b, m, y, k, S):
    """
    Audit keamanan desain berdasarkan kecepatan dan Bilangan Froude.
    """
    A = (b + m * y) * y
    V = Q / A if A > 0 else 0
    
    # 1. Hitung Froude Number (Fr)
    # Lebar muka air atas (T)
    T = b + 2 * m * y
    D = A / T if T > 0 else 0 # Hydraulic Depth
    g = 9.81
    Fr = V / np.sqrt(g * D) if D > 0 else 0
    
    warnings = []
    status = "AMAN"
    
    # Cek 1: Froude (Stabilitas Aliran)
    if Fr >= 1.0:
        warnings.append(f"BAHAYA: Superkritis (Fr={Fr:.2f}). Loncatan air!")
        status = "KRITIS"
    elif Fr > 0.5:
        warnings.append(f"Info: Mendekati Kritis (Fr={Fr:.2f}).")

    # Cek 2: Kecepatan (Erosi & Sedimen)
    # Batas kecepatan berdasarkan material (Asumsi k=60 adalah Batu, k=35-45 Tanah)
    v_max = 2.0 if k >= 60 else 0.7
    v_min = 0.6
    
    if V > v_max:
        warnings.append(f"EROSI: V ({V:.2f}) > Izin ({v_max}).")
        if status != "KRITIS": status = "TIDAK AMAN"
    elif V < v_min:
        warnings.append(f"ENDAPAN: V ({V:.2f}) < Min ({v_min}).")
        if status == "AMAN": status = "PERHATIAN"
        
    return V, Fr, status, "; ".join(warnings)

# ==========================================
# 2. FUNGSI VISUALISASI
# ==========================================

def gambar_penampang_saluran(row):
    """Visualisasi Potongan Melintang"""
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air = row['Tinggi Total (h)'], row['Tinggi Air (y)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Geometri
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Koordinat Dinding
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    # Gambar Dinding
    color_wall = 'red' if row['Status'] == 'KRITIS' else '#333'
    ax.add_patch(patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor=color_wall, facecolor='none', linewidth=3))
    
    # Gambar Air
    wa1 = (x_talud_total - x_talud_air, y_air)
    wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0)
    wa4 = (x_talud_total + b + x_talud_air, y_air)
    ax.add_patch(patches.Polygon([wa1, wa2, wa3, wa4], closed=True, color='#00BFFF', alpha=0.6))
    
    # Label
    ax.text(x_talud_total + b/2, y_air/2, f"V={row['Kecepatan (V)']} m/s\nFr={row['Froude (Fr)']}", ha='center', color='white', fontweight='bold', fontsize=9)
    ax.set_title(f"Penampang: {nama} ({row['Status']})")
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_ylim(-0.2, h_total * 1.3); ax.set_xlim(-1, p4[0]+1)
    return fig

def gambar_profil_memanjang(df_hasil):
    """Visualisasi Long Section"""
    fig, ax = plt.subplots(figsize=(10, 4))
    
    stas = []
    elvs_dasar = []
    elvs_air = []
    elvs_tanggul = []
    
    for i, row in df_hasil.iterrows():
        stas.extend([row['STA Awal'], row['STA Akhir']])
        elvs_dasar.extend([row['Elv Dasar Awal'], row['Elv Dasar Akhir']])
        elvs_air.extend([row['Elv Dasar Awal'] + row['Tinggi Air (y)'], row['Elv Dasar Akhir'] + row['Tinggi Air (y)']])
        elvs_tanggul.extend([row['Elv Dasar Awal'] + row['Tinggi Total (h)'], row['Elv Dasar Akhir'] + row['Tinggi Total (h)']])

    ax.plot(stas, elvs_tanggul, 'k--', label='Tanggul Jagaan', alpha=0.5)
    ax.plot(stas, elvs_dasar, color='brown', linewidth=2, label='Dasar Saluran')
    ax.plot(stas, elvs_air, color='blue', linewidth=1, label='Muka Air')
    ax.fill_between(stas, elvs_dasar, elvs_air, color='cyan', alpha=0.3)
    
    ax.set_xlabel("Stationing (m)")
    ax.set_ylabel("Elevasi (+m)")
    ax.set_title("Profil Memanjang (Long Section)", fontweight='bold')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)
    return fig

# ==========================================
# 3. SETUP HALAMAN
# ==========================================

st.set_page_config(page_title="Desain Irigasi KP-03", layout="wide")
st.title("🛠️ Desain Irigasi: Standar KP-03 & KP-07")
st.markdown("---")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Konfigurasi Trase")
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Awal (+m)", value=100.00)
    
    st.header("2. Referensi Nilai k")
    st.info("""
    **Koefisien Strickler (k):**
    * Pasangan Batu: **60**
    * Beton: **70**
    * Tanah Bersih: **40**
    * Tanah Kasar: **35**
    """)
    
    st.divider()
    # Template Download
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran 1'], 'Panjang (m)': [50.0], 'Offset (m)': [-0.10],
        'Debit (Q)': [1.5], 'Lebar (b)': [1.0], 'Talud (m)': [1.0], 
        'Slope (S)': [0.001], 'Strickler (k)': [60]
    })
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer: df_template.to_excel(writer, index=False)
    st.download_button("📥 Download Template Excel", buffer.getvalue(), "template_irigasi_kp03.xlsx")

# ==========================================
# 4. DATA EDITOR
# ==========================================

if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran A', 'Saluran B'],
        'Panjang (m)': [50.0, 50.0],
        'Offset (m)': [-0.50, -0.50],
        'Debit (Q)': [2.00, 2.00],
        'Lebar (b)': [1.00, 1.20],
        'Talud (m)': [1.0, 1.0],
        'Slope (S)': [0.001, 0.0015], 
        'Strickler (k)': [60, 60] # Default Batu Kali
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

st.subheader("1. Input Data Desain")
st.caption("Pastikan nilai **k** sesuai material. Gunakan **Offset negatif** untuk terjunan.")

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Panjang (m)": st.column_config.NumberColumn(format="%.1f"),
        "Offset (m)": st.column_config.NumberColumn(format="%.2f", help="Beda tinggi lantai ke segmen berikutnya"),
        "Debit (Q)": st.column_config.NumberColumn(format="%.3f"),
        "Slope (S)": st.column_config.NumberColumn(format="%.5f"),
        "Strickler (k)": st.column_config.NumberColumn(min_value=20, max_value=100, step=1, help="Nilai kekasaran Strickler (KP-03)"),
    },
    hide_index=True
)

if not edited_df.equals(st.session_state.df_input):
    st.session_state.df_input = edited_df

# ==========================================
# 5. EKSEKUSI PERHITUNGAN
# ==========================================

btn_run = st.button("▶️ HITUNG & VERIFIKASI (RUN)", type="primary", use_container_width=True)

if btn_run:
    hasil_list = []
    curr_sta = start_sta
    curr_elv = start_elv
    
    for idx, row in edited_df.iterrows():
        # Input
        L, Q, b, m = row['Panjang (m)'], row['Debit (Q)'], row['Lebar (b)'], row['Talud (m)']
        S, k, offset = row['Slope (S)'], row['Strickler (k)'], row['Offset (m)']
        
        # 1. Hitung Hidrolis (Strickler)
        y_calc = solve_strickler_y(Q, b, m, k, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        
        # 2. Cek Keamanan (Verifikasi KP-03)
        V_calc, Fr_calc, status, pesan = cek_keamanan_desain(Q, b, m, y_calc, k, S)
        
        # 3. Hitung Elevasi
        elv_awal = curr_elv
        elv_akhir = elv_awal - (L * S)
        
        hasil_list.append({
            'Nama Saluran': row['Nama Saluran'],
            'Status': status,
            'Peringatan': pesan,
            'STA Awal': round(curr_sta, 1),
            'STA Akhir': round(curr_sta + L, 1),
            'Elv Dasar Awal': round(elv_awal, 3),
            'Elv Dasar Akhir': round(elv_akhir, 3),
            'Tinggi Air (y)': round(y_calc, 3),
            'Tinggi Total (h)': round(h_calc, 2),
            'Kecepatan (V)': round(V_calc, 2),
            'Froude (Fr)': round(Fr_calc, 2),
            'Strickler (k)': k, 'Lebar (b)': b, 'Talud (m)': m
        })
        
        # Update Loop
        curr_sta += L
        curr_elv = elv_akhir + offset

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    
    # Cek Global Status
    if any(x in ['KRITIS', 'TIDAK AMAN'] for x in st.session_state.df_hasil['Status']):
        st.error("⚠️ Ditemukan desain yang TIDAK MEMENUHI kriteria KP-03. Periksa tabel di bawah.")
    else:
        st.success("✅ Semua saluran memenuhi kriteria hidrolis KP-03.")

# ==========================================
# 6. OUTPUT & LAPORAN
# ==========================================

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    
    st.divider()
    st.subheader("2. Hasil Analisis Hidrolis")
    
    # Styling Tabel: Highlight baris berbahaya
    def highlight_status(val):
        color = 'red' if val == 'KRITIS' else 'orange' if val == 'TIDAK AMAN' else 'green'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df_res.style.map(highlight_status, subset=['Status']),
        column_config={
            "Peringatan": st.column_config.TextColumn(width="large"),
            "Froude (Fr)": st.column_config.NumberColumn(help="Harus < 1.0 (Subkritis)"),
        },
        use_container_width=True, hide_index=True
    )
    
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("3. Profil Memanjang")
        st.pyplot(gambar_profil_memanjang(df_res))
        
    with col_g2:
        st.subheader("4. Detail Penampang")
        pilih_sal = st.selectbox("Pilih Saluran:", df_res['Nama Saluran'])
        row_vis = df_res[df_res['Nama Saluran'] == pilih_sal].iloc[0]
        st.pyplot(gambar_penampang_saluran(row_vis))
        
        # Kartu Info Teknis
        st.info(f"""
        **Analisis {pilih_sal}:**
        - Kecepatan: {row_vis['Kecepatan (V)']} m/s
        - Froude: {row_vis['Froude (Fr)']}
        - **Status: {row_vis['Status']}**
        """)

    # Download Report
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer: df_res.to_excel(writer, index=False)
    st.download_button("💾 Download Hasil Verifikasi (.xlsx)", output.getvalue(), "Hasil_Desain_KP03.xlsx")
