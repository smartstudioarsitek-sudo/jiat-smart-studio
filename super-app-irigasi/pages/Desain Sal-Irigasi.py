import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Desain Saluran Irigasi", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 15px; background-color: #2c3e50; color: white;
        border-radius: 8px; text-align: center; margin-bottom: 15px;
    }
    div[data-testid="stMetricValue"] { font-size: 18px; }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNGSI LOGIKA (CALCULATION) ---
def hitung_hidrolika_fixed(df):
    """
    Menghitung parameter hidrolika sesuai format input user.
    """
    # 1. Pastikan kolom angka terbaca sebagai numerik (handle error input text)
    cols_num = ['STA Awal', 'STA Akhir', 'Z Awal', 'Z Akhir', 'Lebar b', 'Talud m', 'Tinggi H', 'Debit Q', 'Kekasaran n']
    for c in cols_num:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
    # 2. Hitung Geometri Panjang
    df['Panjang L'] = df['STA Akhir'] - df['STA Awal']
    df['Beda Tinggi'] = df['Z Awal'] - df['Z Akhir']
    
    # 3. Hitung Slope (S)
    # Jika Panjang > 0, S = Delta Z / L. Jika tidak, anggap 0.
    df['Slope S'] = df.apply(lambda x: x['Beda Tinggi'] / x['Panjang L'] if x['Panjang L'] > 0 else 0, axis=1)

    # 4. Loop Perhitungan Manning
    hasil_list = []
    for idx, row in df.iterrows():
        b = row['Lebar b']
        h = row['Tinggi H']
        m = row['Talud m']
        n = row.get('Kekasaran n', 0.025) # Default jika kosong
        S = row['Slope S']
        
        # Luas Basah (A) & Keliling Basah (P)
        A = (b + m * h) * h
        P = b + 2 * h * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        
        # Kecepatan (V) & Debit Kapasitas (Q Cap)
        V = 0
        Q_cap = 0
        if S > 0 and n > 0:
            V = (1/n) * (R**(2/3)) * (S**(0.5))
            Q_cap = A * V
            
        # Froude Number (Cek Aliran)
        T = b + 2 * m * h # Lebar atas
        D_hyd = A / T if T > 0 else 0
        Fr = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0
        
        # Status
        Q_req = row.get('Debit Q', 0)
        status = "✅ AMAN" if Q_cap >= Q_req else "❌ MELUAP"
        
        hasil_list.append({
            'Luas A': round(A, 3),
            'Kecepatan V': round(V, 3),
            'Q Kapasitas': round(Q_cap, 3),
            'Froude Fr': round(Fr, 3),
            'Status': status
        })
        
    # Gabungkan hasil ke dataframe asli
    df_hasil = pd.concat([df, pd.DataFrame(hasil_list)], axis=1)
    return df_hasil

# --- 3. AUTOCAD SCRIPT GENERATOR ---
def generate_script_fixed(df):
    """
    Membuat Script AutoCAD (.scr) untuk Long Section & Cross Section
    Sesuai format kolom user.
    """
    scr = []
    scr.append("OSMODE 0")
    scr.append("LIMITS OFF")
    scr.append("ZOOM E")
    
    # --- A. LONG SECTION (Z Awal ke Z Akhir) ---
    scr.append("; --- LONG SECTION START ---")
    scr.append("_PLINE") # Mulai garis
    
    first = True
    for idx, row in df.iterrows():
        x1, z1 = row['STA Awal'], row['Z Awal']
        x2, z2 = row['STA Akhir'], row['Z Akhir']
        
        if first:
            scr.append(f"{x1},{z1}")
            first = False
        scr.append(f"{x2},{z2}")
    scr.append("") # Enter (Selesai Pline)
    
    # Text STA di Long Section
    for idx, row in df.iterrows():
        scr.append(f"_TEXT {row['STA Awal']},{row['Z Awal']-1} 0.2 90 {row['STA Awal']}")
    
    # --- B. CROSS SECTION ---
    scr.append("; --- CROSS SECTION START ---")
    start_x_cross = df['STA Akhir'].max() + 20 # Geser ke kanan gambar
    gap = 15 # Jarak antar gambar
    
    current_x = start_x_cross
    for idx, row in df.iterrows():
        b = row['Lebar b']
        h = row['Tinggi H']
        m = row['Talud m']
        
        # Koordinat lokal trapesium
        # 1. Kiri Atas -> 2. Kiri Bawah -> 3. Kanan Bawah -> 4. Kanan Atas
        dx = m * h
        x1, y1 = current_x - dx, h
        x2, y2 = current_x, 0
        x3, y3 = current_x + b, 0
        x4, y4 = current_x + b + dx, h
        
        scr.append("_PLINE")
        scr.append(f"{x1},{y1}")
        scr.append(f"{x2},{y2}")
        scr.append(f"{x3},{y3}")
        scr.append(f"{x4},{y4}")
        scr.append("")
        
        # Nama Saluran
        scr.append(f"_TEXT {current_x + b/2},{y2 - 1} 0.3 0 {row['Nama']}")
        
        current_x += (b + 2*dx + gap)
        
    scr.append("ZOOM E")
    return "\n".join(scr)

# --- 4. UI LAYOUT ---
st.markdown('<div class="header-box"><h2>🌊 Aplikasi Desain Irigasi (Format User)</h2></div>', unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.header("📂 File Operations")
    
    # A. DOWNLOAD TEMPLATE (Sesuai format user)
    # Kolom: Nama,STA Awal,STA Akhir,Z Awal,Z Akhir,Lebar b,Talud m,Tinggi H,Debit Q,Kekasaran n
    df_temp = pd.DataFrame(columns=[
        'Nama', 'STA Awal', 'STA Akhir', 'Z Awal', 'Z Akhir', 
        'Lebar b', 'Talud m', 'Tinggi H', 'Debit Q', 'Kekasaran n'
    ])
    # Contoh data dummy 1 baris
    df_temp.loc[0] = ['S1', 0, 50, 100.5, 100.2, 1.0, 1.0, 1.2, 0.5, 0.025]
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_temp.to_excel(writer, index=False)
        
    st.download_button("⬇️ Download Template Excel", buffer.getvalue(), "template_irigasi_user.xlsx", "application/vnd.ms-excel")
    
    st.divider()
    
    # B. UPLOAD
    uploaded = st.file_uploader("Upload Data (.xlsx)", type=['xlsx'])
    if uploaded:
        try:
            df_input = pd.read_excel(uploaded)
            st.session_state['df_main'] = df_input
            st.success("Data loaded!")
        except:
            st.error("Gagal baca file.")

    if 'df_main' not in st.session_state:
        st.session_state['df_main'] = df_temp.copy()

# TABS
t_input, t_hasil, t_long, t_cad = st.tabs(["📝 Input Data", "📊 Hasil Hitungan", "📈 Long Section", "💻 AutoCAD Script"])

with t_input:
    st.write("Edit data di bawah ini (Format sesuai Excel Kakak):")
    df_edited = st.data_editor(st.session_state['df_main'], num_rows="dynamic", use_container_width=True, key='editor_user')
    st.session_state['df_main'] = df_edited

# Hitung data jika ada
if not df_edited.empty:
    df_calc = hitung_hidrolika_fixed(df_edited)
else:
    df_calc = pd.DataFrame()

with t_hasil:
    st.write("Hasil Analisa Hidrolika (Manning):")
    if not df_calc.empty:
        # Tampilkan kolom-kolom penting saja agar rapi
        cols_show = ['Nama', 'STA Awal', 'Q Kapasitas', 'Kecepatan V', 'Froude Fr', 'Status']
        st.dataframe(
            df_calc.style.format({
                'Q Kapasitas': '{:.3f}', 
                'Kecepatan V': '{:.2f}',
                'Froude Fr': '{:.2f}'
            }).map(lambda x: 'color: red' if x == '❌ MELUAP' else 'color: green', subset=['Status']),
            use_container_width=True
        )
        
        # Save Button
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_calc.to_excel(writer, index=False)
        st.download_button("💾 Simpan Hasil ke Excel", output.getvalue(), "hasil_perhitungan.xlsx")

with t_long:
    if not df_calc.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        # Plot garis Z (Dasar Saluran)
        x_p = []
        y_p = []
        for i, r in df_calc.iterrows():
            x_p.extend([r['STA Awal'], r['STA Akhir']])
            y_p.extend([r['Z Awal'], r['Z Akhir']])
        
        ax.plot(x_p, y_p, marker='.', linestyle='-', color='brown', label='Dasar Saluran')
        ax.set_title("Long Section (Profil Memanjang)")
        ax.set_xlabel("Station (m)")
        ax.set_ylabel("Elevasi (m)")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

with t_cad:
    st.write("Download script di bawah, lalu ketik command `SCRIPT` di AutoCAD.")
    if not df_calc.empty:
        sc = generate_script_fixed(df_calc)
        st.download_button("📐 Download Script (.scr)", sc, "gambar_irigasi.scr")
