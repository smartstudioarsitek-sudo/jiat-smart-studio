import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Desain Saluran Irigasi Pro", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 15px; background-color: #2c3e50; color: white;
        border-radius: 8px; text-align: center; margin-bottom: 15px;
    }
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 5px; }
    .warning-box { padding: 10px; background-color: #fff3cd; color: #856404; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNGSI LOGIKA (CALCULATION) ---
def hitung_hidrolika_advanced(df):
    """
    Menghitung parameter hidrolika berdasarkan data input.
    Menggunakan Rumus Manning: V = 1/n * R^(2/3) * S^(1/2)
    """
    # Pastikan tipe data numerik
    numeric_cols = ['STA Awal', 'STA Akhir', 'Z Awal', 'Z Akhir', 'Lebar b', 'Talud m', 'Tinggi H', 'Kekasaran n', 'Debit Q']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Hitung Panjang (L) dan Slope (S) jika Z ada
    df['Panjang L'] = df['STA Akhir'] - df['STA Awal']
    
    # Logic Slope: Jika Z Awal/Akhir ada, hitung S. Jika tidak, pakai kolom 'Slope S' manual jika ada
    # Disini kita prioritaskan hitungan dari elevasi (Z) agar akurat sesuai Long Section
    df['Delta Z'] = df['Z Awal'] - df['Z Akhir']
    
    # Hindari pembagian nol
    df['Slope S'] = df.apply(lambda x: x['Delta Z'] / x['Panjang L'] if x['Panjang L'] > 0 else 0, axis=1)
    
    # Calculation Loop
    results = []
    for idx, row in df.iterrows():
        b = row['Lebar b']
        h = row['Tinggi H'] # Tinggi air rencana
        m = row['Talud m']
        n = row.get('Kekasaran n', 0.025) # Default beton kasar/pasangan batu
        S = row['Slope S']
        
        # Geometri Basah
        A = (b + m * h) * h
        P = b + 2 * h * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        
        # Manning
        V = 0
        Q_cap = 0
        if S > 0 and n > 0:
            V = (1/n) * (R**(2/3)) * (S**(0.5))
            Q_cap = A * V # m3/s
        
        # Froude
        T = b + 2 * m * h # Lebar atas
        D_hyd = A / T if T > 0 else 0
        Fr = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0
        
        results.append({
            'Luas Basah A': round(A, 3),
            'Keliling P': round(P, 3),
            'Jari-jari R': round(R, 3),
            'Kecepatan V': round(V, 3),
            'Q Kapasitas': round(Q_cap, 3),
            'Froude Fr': round(Fr, 3),
            'Status Aliran': 'Superkritis' if Fr > 1 else 'Subkritis'
        })
        
    df_res = pd.concat([df, pd.DataFrame(results)], axis=1)
    return df_res

# --- 3. FUNGSI AUTOCAD SCRIPT (KP-07 STYLE) ---
def generate_autocad_script(df):
    """
    Membuat file teks (.scr) untuk menggambar Long Section dan Cross Section di AutoCAD.
    """
    scr = []
    scr.append("OSMODE 0") # Matikan object snap agar akurat
    scr.append("LIMITS OFF")
    scr.append("ZOOM E")

    # --- A. GAMBAR LONG SECTION (Profile) ---
    # Kita gambar garis tanah dasar (Z Awal ke Z Akhir)
    scr.append(f"; --- LONG SECTION ---")
    start_x_long = 0
    start_y_long = 0 # Offset Y untuk Long Section
    
    # Gambar Garis Dasar Saluran
    scr.append("_PLINE")
    for idx, row in df.iterrows():
        # Koordinat X berdasarkan STA, Y berdasarkan Elevasi Z
        x1 = row['STA Awal']
        y1 = row['Z Awal']
        x2 = row['STA Akhir']
        y2 = row['Z Akhir']
        
        if idx == 0:
            scr.append(f"{x1},{y1}") # Titik pertama
        scr.append(f"{x2},{y2}") # Titik selanjutnya
    scr.append("") # Enter untuk selesai command PLINE
    
    # Label STA di Long Section
    for idx, row in df.iterrows():
        scr.append(f"_TEXT {row['STA Awal']},{row['Z Awal'] - 2} 0.5 90 STA {row['STA Awal']}")
    # Label STA Akhir terakhir
    last_row = df.iloc[-1]
    scr.append(f"_TEXT {last_row['STA Akhir']},{last_row['Z Akhir'] - 2} 0.5 90 STA {last_row['STA Akhir']}")

    # --- B. GAMBAR CROSS SECTION (Per Segmen) ---
    scr.append(f"; --- CROSS SECTIONS ---")
    # Digambar terpisah di sebelah kanan grafik Long Section
    offset_x_cross = df['STA Akhir'].max() + 50 
    gap_antar_cross = 30 # Jarak antar gambar cross section
    
    current_x = offset_x_cross
    
    for idx, row in df.iterrows():
        b = row['Lebar b']
        h = row['Tinggi H']
        m = row['Talud m']
        z_base = 0 # Kita gambar relatif terhadap 0 lokal
        
        # Titik Koordinat Trapesium (Lokal)
        # Kiri Atas -> Kiri Bawah -> Kanan Bawah -> Kanan Atas
        # Lebar atas total = b + 2mh
        dx_top = m * h
        
        x_bl = current_x # Bottom Left
        y_bl = z_base
        
        x_br = current_x + b # Bottom Right
        y_br = z_base
        
        x_tl = current_x - dx_top # Top Left
        y_tl = z_base + h
        
        x_tr = current_x + b + dx_top # Top Right
        y_tr = z_base + h
        
        # Gambar Penampang
        scr.append("_PLINE")
        scr.append(f"{x_tl},{y_tl}")
        scr.append(f"{x_bl},{y_bl}")
        scr.append(f"{x_br},{y_br}")
        scr.append(f"{x_tr},{y_tr}")
        scr.append("") # Enter
        
        # Label Nama Segmen
        scr.append(f"_TEXT {current_x + b/2},{y_bl - 2} 0.5 0 {row['Nama']}")
        
        # Geser X untuk gambar berikutnya
        current_x += (b + 2*dx_top + gap_antar_cross)

    scr.append("ZOOM E")
    return "\n".join(scr)

# --- 4. LAYOUT APLIKASI ---

st.markdown('<div class="header-box"><h2>🌊 Aplikasi Desain Irigasi Terpadu (XLSX & AutoCAD)</h2></div>', unsafe_allow_html=True)

# SIDEBAR: DATA HANDLING
with st.sidebar:
    st.header("📂 Menu File")
    
    # 1. Download Template
    st.subheader("1. Template Data")
    # Membuat DataFrame dummy untuk template
    df_template = pd.DataFrame(columns=[
        'Nama', 'STA Awal', 'STA Akhir', 'Z Awal', 'Z Akhir', 
        'Lebar b', 'Talud m', 'Tinggi H', 'Kekasaran n', 'Debit Q'
    ])
    # Isi satu baris contoh
    df_template.loc[0] = ['Saluran 1', 0, 50, 100.5, 100.0, 1.0, 1.0, 1.2, 0.025, 0.5]
    
    buffer_template = io.BytesIO()
    with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='DataSaluran')
    
    st.download_button(
        label="⬇️ Download Template Excel",
        data=buffer_template.getvalue(),
        file_name="template_irigasi.xlsx",
        mime="application/vnd.ms-excel"
    )
    
    st.divider()
    
    # 2. Upload Data
    st.subheader("2. Upload & Open")
    uploaded_file = st.file_uploader("Upload File Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df_input = pd.read_excel(uploaded_file)
            st.session_state['data_irigasi'] = df_input
            st.success("✅ Data berhasil dimuat!")
        except Exception as e:
            st.error(f"Error membaca file: {e}")
            
    # Inisialisasi Data Default jika kosong
    if 'data_irigasi' not in st.session_state:
        st.session_state['data_irigasi'] = df_template.copy()

# MAIN CONTENT TABS
tab_input, tab_calc, tab_long, tab_cross, tab_export = st.tabs([
    "📝 Input Data", "🧮 Perhitungan", "📈 Long Section", "📐 Cross Section", "🖨️ Export CAD"
])

# --- TAB 1: INPUT DATA ---
with tab_input:
    st.subheader("Input Data Geometri & Elevasi")
    st.markdown("Silakan edit data di bawah ini atau upload Excel di sidebar.")
    
    df_edited = st.data_editor(
        st.session_state['data_irigasi'],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_utama"
    )
    # Simpan perubahan
    st.session_state['data_irigasi'] = df_edited

# --- TAB 2: PERHITUNGAN ---
with tab_calc:
    st.subheader("Analisa Hidrolika (Manning)")
    if not df_edited.empty:
        df_hasil = hitung_hidrolika_advanced(df_edited)
        
        # Highlight kolom penting
        tampilan_cols = ['Nama', 'STA Awal', 'STA Akhir', 'Slope S', 'Q Kapasitas', 'Kecepatan V', 'Froude Fr', 'Status Aliran']
        st.dataframe(
            df_hasil[tampilan_cols].style.format({
                'Slope S': '{:.5f}',
                'Q Kapasitas': '{:.3f}',
                'Kecepatan V': '{:.2f}',
                'Froude Fr': '{:.2f}'
            }).background_gradient(subset=['Kecepatan V'], cmap="Blues"),
            use_container_width=True
        )
        st.info("Catatan: Slope (S) dihitung otomatis berdasarkan (Z Awal - Z Akhir) / Panjang.")
    else:
        st.warning("Data kosong.")

# --- TAB 3: LONG SECTION ---
with tab_long:
    st.subheader("Visualisasi Profil Memanjang (Long Section)")
    if not df_edited.empty:
        fig_long, ax_long = plt.subplots(figsize=(10, 4))
        
        # Extract data plotting
        x_plot = []
        z_plot = []
        
        for idx, row in df_edited.iterrows():
            # Agar garis nyambung, kita plot titik awal dan akhir setiap segmen
            x_plot.extend([row['STA Awal'], row['STA Akhir']])
            z_plot.extend([row['Z Awal'], row['Z Akhir']])
            
        ax_long.plot(x_plot, z_plot, marker='o', linestyle='-', color='brown', label='Dasar Saluran (Z)')
        
        # Formatting
        ax_long.set_xlabel('Station (m)')
        ax_long.set_ylabel('Elevasi (m)')
        ax_long.set_title('Profil Memanjang Saluran')
        ax_long.grid(True, linestyle='--', alpha=0.6)
        ax_long.legend()
        
        st.pyplot(fig_long)
    else:
        st.warning("Data belum tersedia.")

# --- TAB 4: CROSS SECTION ---
with tab_cross:
    st.subheader("Visualisasi Potongan Melintang (Cross Section)")
    
    if not df_edited.empty:
        col_sel, col_fig = st.columns([1, 3])
        
        with col_sel:
            pilih_segmen = st.selectbox("Pilih Segmen / Nama Saluran:", df_edited['Nama'].unique())
            row_cs = df_edited[df_edited['Nama'] == pilih_segmen].iloc[0]
            
            st.markdown(f"""
            **Detail:**
            - Lebar (b): {row_cs['Lebar b']} m
            - Tinggi (h): {row_cs['Tinggi H']} m
            - Talud (m): {row_cs['Talud m']}
            """)
            
        with col_fig:
            b = row_cs['Lebar b']
            h = row_cs['Tinggi H']
            m = row_cs['Talud m']
            
            # Plot
            fig_cs, ax_cs = plt.subplots(figsize=(6, 4))
            
            # Koordinat Trapesium (Tanah)
            x_poly = [-m*h, 0, b, b+m*h]
            y_poly = [h, 0, 0, h]
            
            ax_cs.plot(x_poly, y_poly, 'k-', linewidth=2, color='brown', label='Saluran')
            
            # Air (Visualisasi Penuh)
            ax_cs.fill_between(x_poly, y_poly, h, color='cyan', alpha=0.3, label='Air (Full)')
            
            ax_cs.set_aspect('equal')
            ax_cs.set_title(f"Cross Section: {pilih_segmen}")
            st.pyplot(fig_cs)

# --- TAB 5: EXPORT & AUTOCAD ---
with tab_export:
    st.subheader("Export Data & Drawing")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 1. Simpan Excel")
        # Fungsi Save to Excel
        buffer_save = io.BytesIO()
        with pd.ExcelWriter(buffer_save, engine='xlsxwriter') as writer:
            df_edited.to_excel(writer, index=False, sheet_name='DataFinal')
        
        st.download_button(
            label="💾 Simpan Data ke Excel (.xlsx)",
            data=buffer_save.getvalue(),
            file_name="Data_Saluran_Terupdate.xlsx",
            mime="application/vnd.ms-excel"
        )
        
    with c2:
        st.markdown("### 2. Export ke AutoCAD (.scr)")
        st.markdown("""
        Fitur ini akan menghasilkan file **Script (.scr)**.
        **Cara Pakai di AutoCAD:**
        1. Download file .scr
        2. Buka AutoCAD -> Ketik command `SCRIPT` -> Enter
        3. Pilih file .scr yang didownload.
        4. Gambar Long Section & Cross Section akan otomatis tergambar.
        """)
        
        if not df_edited.empty:
            script_content = generate_autocad_script(df_edited)
            st.download_button(
                label="📐 Download AutoCAD Script (.scr)",
                data=script_content,
                file_name="gambar_saluran.scr",
                mime="text/plain"
            )

st.divider()
st.caption("Dikembangkan dengan Python Streamlit untuk Teknik Sipil & Pengairan.")