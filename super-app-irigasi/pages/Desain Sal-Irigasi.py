import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# ==========================================
# 1. FUNGSI PERHITUNGAN & VISUALISASI
# ==========================================

def get_freeboard_kp03(Q):
    """Standar KP-03"""
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.25
    elif Q < 5.0: return 0.30
    elif Q < 10.0: return 0.40
    elif Q < 15.0: return 0.50
    else: return 0.60

def solve_manning_y(Q, b, m, n, S):
    """Mencari y (tinggi air) dengan iterasi"""
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

def gambar_penampang_saluran(row):
    """Menggambar plot Matplotlib"""
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air, w_jagaan = row['Tinggi Total (h)'], row['Tinggi Air (y)'], row['Jagaan (w)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Geometri
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Titik Saluran
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    # Gambar Fisik Saluran
    poly_saluran = patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor='#444444', facecolor='none', linewidth=3)
    ax.add_patch(poly_saluran)
    
    # Gambar Air
    wa1 = (x_talud_total - x_talud_air, y_air)
    wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0)
    wa4 = (x_talud_total + b + x_talud_air, y_air)
    poly_air = patches.Polygon([wa1, wa2, wa3, wa4], closed=True, edgecolor='none', facecolor='#00BFFF', alpha=0.6)
    ax.add_patch(poly_air)
    
    # Garis Tanah
    ax.plot([-1, 0], [h_total, h_total], color='sienna', linestyle='--')
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], color='sienna', linestyle='--')

    # Anotasi
    ax.annotate(f'b={b}m', xy=(x_talud_total + b/2, -0.1 * h_total), ha='center', va='top', color='blue')
    ax.annotate(f'h={h_total}', xy=(-0.2, h_total/2), ha='right', rotation=90)
    ax.annotate(f'w={w_jagaan}m', xy=(p4[0], h_total - w_jagaan/2), ha='left', color='red')
    
    ax.set_title(f"Penampang: {nama} (m={m})")
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_xlim(-1, p4[0] + 1)
    ax.set_ylim(-0.5 * h_total, h_total * 1.5)
    return fig

# ==========================================
# 2. KONFIGURASI HALAMAN & SIDEBAR
# ==========================================

st.set_page_config(page_title="Desain Irigasi Pro", layout="wide")
st.title("Desain Saluran Irigasi (Run Mode)")

# --- SIDEBAR (EXCEL MENU) ---
with st.sidebar:
    st.header("📂 Menu File")
    
    # A. Download Template
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran Contoh'],
        'Debit (Q)': [1.0], 'Lebar (b)': [0.8], 'Talud (m)': [1.0], 
        'Slope (S)': [0.0005], 'Manning (n)': [0.017]
    })
    buffer_template = io.BytesIO()
    with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False)
        
    st.download_button("📥 Download Template Excel", data=buffer_template.getvalue(), file_name="template_irigasi.xlsx")
    
    st.divider()

    # B. Upload File
    uploaded_file = st.file_uploader("Buka File Excel (.xlsx)", type=['xlsx'])
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            st.session_state.df_input = df_uploaded
            st.success("✅ Data dimuat!")
        except:
            st.error("❌ Gagal baca file.")

# ==========================================
# 3. INPUT DATA (BAGIAN 1)
# ==========================================

# Inisialisasi Session State Input
if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Sekunder 1', 'Tersier A'],
        'Debit (Q)': [1.25, 0.45],
        'Lebar (b)': [1.00, 0.60],
        'Talud (m)': [0.0, 1.0],
        'Slope (S)': [0.0005, 0.001], 
        'Manning (n)': [0.017, 0.022]
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

st.subheader("1. Input Parameter Desain")
st.caption("Silakan edit data di bawah ini. Tekan tombol RUN jika sudah selesai.")

# Tampilkan Editor
edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Debit (Q)": st.column_config.NumberColumn("Debit Q", format="%.3f"),
        "Lebar (b)": st.column_config.NumberColumn("Lebar b", format="%.2f"),
        "Talud (m)": st.column_config.NumberColumn("Talud m", format="%.2f"),
        "Slope (S)": st.column_config.NumberColumn("Slope S", format="%.5f"),
    },
    hide_index=True,
    key="editor_utama" 
)

# Update session state jika editor berubah
if not edited_df.equals(st.session_state.df_input):
    st.session_state.df_input = edited_df

# ==========================================
# 4. TOMBOL EKSEKUSI (RUNNING)
# ==========================================

st.write("")
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    # Tombol Primary agar mencolok
    tombol_run = st.button("▶️ MULAI PERHITUNGAN (RUN)", type="primary", use_container_width=True)

# Logika Tombol Run
if tombol_run:
    with st.spinner('Sedang menghitung hidrolika...'):
        hasil_list = []
        # Loop perhitungan
        for index, row in edited_df.iterrows():
            q, b, m, s, n = row['Debit (Q)'], row['Lebar (b)'], row['Talud (m)'], row['Slope (S)'], row['Manning (n)']
            
            y_calc = solve_manning_y(q, b, m, n, s)
            w_calc = get_freeboard_kp03(q)
            h_calc = y_calc + w_calc
            area = (b + m * y_calc) * y_calc
            v_calc = q / area if area > 0 else 0
            tipe = "Kotak" if m == 0 else "Trapesium"
            
            hasil_list.append({
                'Nama Saluran': row['Nama Saluran'],
                'Tipe': tipe,
                'Debit (Q)': q, 'Lebar (b)': b, 'Talud (m)': m,
                'Slope (S)': s, 'Manning (n)': n,
                'Tinggi Air (y)': round(y_calc, 3),
                'Jagaan (w)': round(w_calc, 2),
                'Tinggi Total (h)': round(h_calc, 2),
                'Kecepatan (V)': round(v_calc, 2)
            })
        
        # SIMPAN HASIL KE SESSION STATE (Supaya tidak hilang saat klik lain)
        st.session_state.df_hasil = pd.DataFrame(hasil_list)
        st.success("Perhitungan Selesai! Lihat hasil di bawah.")

# ==========================================
# 5. OUTPUT DATA (BAGIAN 2 & 3)
# ==========================================

# Cek apakah sudah ada hasil hitungan di memori
if 'df_hasil' in st.session_state:
    df_hasil = st.session_state.df_hasil
    
    st.divider()
    st.subheader("2. Hasil Perhitungan")
    st.dataframe(df_hasil, use_container_width=True, hide_index=True)

    # --- FITUR DOWNLOAD HASIL ---
    buffer_download = io.BytesIO()
    with pd.ExcelWriter(buffer_download, engine='xlsxwriter') as writer:
        df_hasil.to_excel(writer, index=False, sheet_name='Hasil Desain')
        # Auto-adjust width column
        worksheet = writer.sheets['Hasil Desain']
        for i, col in enumerate(df_hasil.columns):
            width = max(df_hasil[col].astype(str).map(len).max(), len(col))
            worksheet.set_column(i, i, width + 2)
            
    st.download_button(
        label="💾 Simpan Hasil ke Excel",
        data=buffer_download.getvalue(),
        file_name="hasil_desain_irigasi.xlsx",
        mime="application/vnd.ms-excel"
    )

    st.divider()

    # --- VISUALISASI ---
    st.subheader("3. Visualisasi Penampang")
    
    # Pilih saluran dari hasil yang sudah dihitung
    pilihan_saluran = st.selectbox("Pilih Saluran:", df_hasil['Nama Saluran'])
    
    if pilihan_saluran:
        row_vis = df_hasil[df_hasil['Nama Saluran'] == pilihan_saluran].iloc[0]
        
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = gambar_penampang_saluran(row_vis)
            st.pyplot(fig)
            
        with col2:
            st.markdown(f"**Info Teknis: {pilihan_saluran}**")
            st.info(f"Dimensi: {row_vis['Lebar (b)']} x {row_vis['Tinggi Total (h)']} m")
            
            v = row_vis['Kecepatan (V)']
            st.metric("Kecepatan (V)", f"{v} m/s")
            
            if v < 0.3: st.error("⚠️ Terlalu Rendah (Endapan)")
            elif v > 2.0: st.warning("⚠️ Terlalu Tinggi (Gerusan)")
            else: st.success("✅ Kecepatan Aman")

else:
    # Jika belum klik Run
    st.info("👆 Masukkan data di tabel atas, lalu klik tombol 'MULAI PERHITUNGAN (RUN)' untuk melihat hasil.")
