import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# --- FUNGSI PERHITUNGAN HIDROLIS (MANNING TRAPESIUM) ---

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

# --- FUNGSI VISUALISASI PENAMPANG ---
def gambar_penampang_saluran(row):
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air, w_jagaan = row['Tinggi Total (h)'], row['Tinggi Air (y)'], row['Jagaan (w)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Koordinat Geometri
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    # Gambar Dinding
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

# --- MAIN APP ---
st.set_page_config(page_title="Desain Irigasi Pro", layout="wide")

st.title("Desain Saluran Irigasi (Input/Output Excel)")

# ---------------------------------------------------------
# SIDEBAR: MENU FILE (OPEN/SAVE)
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 Menu File")
    st.write("Kelola data desain Anda di sini.")
    
    # 1. DOWNLOAD TEMPLATE
    # Buat template kosong agar user tahu formatnya
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran Contoh'],
        'Debit (Q)': [1.0],
        'Lebar (b)': [0.8],
        'Talud (m)': [1.0],
        'Slope (S)': [0.0005],
        'Manning (n)': [0.017]
    })
    
    buffer_template = io.BytesIO()
    with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Input Data')
        
    st.download_button(
        label="📥 Download Template Excel",
        data=buffer_template.getvalue(),
        file_name="template_irigasi.xlsx",
        mime="application/vnd.ms-excel",
        help="Download file ini untuk melihat format kolom yang benar."
    )
    
    st.divider()

    # 2. UPLOAD FILE (OPEN)
    uploaded_file = st.file_uploader("Buka File Excel (.xlsx)", type=['xlsx'])
    
    # Logika Upload
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            # Validasi kolom wajib
            wajib = ['Nama Saluran', 'Debit (Q)', 'Lebar (b)', 'Talud (m)', 'Slope (S)', 'Manning (n)']
            if all(col in df_uploaded.columns for col in wajib):
                st.session_state.df_input = df_uploaded
                st.success("✅ Data berhasil dimuat!")
            else:
                st.error("❌ Format kolom salah! Gunakan template.")
        except Exception as e:
            st.error(f"Error membaca file: {e}")

# ---------------------------------------------------------
# BODY UTAMA
# ---------------------------------------------------------

# Inisialisasi Data Default (Jika belum ada upload)
if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran Sekunder 1', 'Saluran Tersier A'],
        'Debit (Q)': [1.25, 0.45],
        'Lebar (b)': [1.00, 0.60],
        'Talud (m)': [0.0, 1.0],
        'Slope (S)': [0.0005, 0.001], 
        'Manning (n)': [0.017, 0.022]
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

# EDITOR DATA
st.subheader("1. Input Parameter")
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
    key="editor" # Key penting agar sinkron
)

# Jika user mengedit tabel manual, update session state
if not edited_df.equals(st.session_state.df_input):
    st.session_state.df_input = edited_df

# PROSES HITUNG
hasil_list = []
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
        'Debit (Q)': q,
        'Lebar (b)': b,
        'Talud (m)': m,
        'Slope (S)': s,
        'Manning (n)': n,
        'Tinggi Air (y)': round(y_calc, 3),
        'Jagaan (w)': round(w_calc, 2),
        'Tinggi Total (h)': round(h_calc, 2),
        'Kecepatan (V)': round(v_calc, 2)
    })

df_hasil = pd.DataFrame(hasil_list)

# TAMPILKAN HASIL
st.subheader("2. Hasil Perhitungan")
st.dataframe(df_hasil, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# LANJUTAN SIDEBAR: TOMBOL SAVE (DOWNLOAD)
# ---------------------------------------------------------
# Kita taruh tombol download di sidebar, tapi kodenya di sini
# karena menunggu df_hasil selesai dihitung dulu.

with st.sidebar:
    st.divider()
    # 3. DOWNLOAD HASIL (SAVE)
    buffer_download = io.BytesIO()
    with pd.ExcelWriter(buffer_download, engine='xlsxwriter') as writer:
        df_hasil.to_excel(writer, index=False, sheet_name='Hasil Desain')
        
        # Opsional: Auto-adjust column width (Perlu xlsxwriter)
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

# VISUALISASI (Sama seperti sebelumnya)
st.subheader("3. Visualisasi")
pilihan = st.selectbox("Pilih Saluran:", df_hasil['Nama Saluran'])
if pilihan:
    row_vis = df_hasil[df_hasil['Nama Saluran'] == pilihan].iloc[0]
    col1, col2 = st.columns([2, 1])
    with col1:
        st.pyplot(gambar_penampang_saluran(row_vis))
    with col2:
        st.info(f"Kecepatan: {row_vis['Kecepatan (V)']} m/s")
        if row_vis['Kecepatan (V)'] < 0.3: st.warning("Rawan Endapan (<0.3)")
        elif row_vis['Kecepatan (V)'] > 2.0: st.warning("Rawan Gerusan (>2.0)")
        else: st.success("Kecepatan OK")
