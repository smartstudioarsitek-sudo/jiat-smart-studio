import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Hydraulic Batch Pro", layout="wide", page_icon="🏗️")

# --- 1. CSS CUSTOM (WARNA INPUT & TOMBOL) ---
st.markdown("""
<style>
    /* Mengubah Warna Label Input menjadi Biru Tebal */
    .stNumberInput label p, .stTextInput label p, .stSelectbox label p {
        color: #1565c0 !important; /* Biru Engineering */
        font-weight: bold !important;
        font-size: 16px !important;
    }
    
    /* Mengubah Warna Angka di dalam Kotak Input */
    input[type="number"] {
        color: #c62828 !important; /* Merah Bata biar kontras */
        font-weight: 600 !important;
    }
    
    /* Border Tabel Input biar lebih jelas */
    [data-testid="stDataFrame"] {
        border: 2px solid #1565c0;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. TEMPLATE DATA AWAL (DEFAULT)
# ==========================================
def get_default_data():
    return pd.DataFrame({
        'Nama Saluran': ['SDT 1KiKa', 'SDT 2KiKa', 'SDT 3KaKi', 'Saluran Sekunder A'],
        'Luas Area (ha)': [50.4, 103.95, 148.6, 0.0],
        'Modulus (l/d/ha)': [1.5, 1.5, 1.5, 0.0],
        'Q Manual (m3/s)': [0.0, 0.0, 0.0, 2.5],
        'Lebar (b) m': [1.5, 2.0, 2.0, 1.5],
        'Tinggi (h) m': [0.55, 0.8, 1.2, 1.2],
        'Kemiringan (m)': [1.0, 1.0, 1.5, 1.0],
        'Slope (S)': [0.0154, 0.0146, 0.0101, 0.0005],
        'Manning (n)': [0.025, 0.025, 0.025, 0.015]
    })

# Inisialisasi Data
if 'df_saluran' not in st.session_state:
    st.session_state['df_saluran'] = get_default_data()

# ==========================================
# 3. FITUR RESET (PENGGANTI UNDO)
# ==========================================
# Tombol ini fungsinya mengembalikan data ke kondisi awal
col_header, col_btn = st.columns([4, 1])
with col_header:
    st.title("🏗️ Desain Hidrolika Saluran (Batch System)")
with col_btn:
    if st.button("🔄 Reset Default", type="primary", help="Kembalikan tabel ke data awal"):
        st.session_state['df_saluran'] = get_default_data()
        st.rerun() # Refresh halaman

st.markdown("Edit tabel di bawah ini. Gunakan **Ctrl+Z** pada tabel untuk Undo ketikan.")

# ==========================================
# 4. TABEL INPUT (DATA EDITOR)
# ==========================================
edited_df = st.data_editor(
    st.session_state['df_saluran'],
    num_rows="dynamic",
    use_container_width=True,
    height=300,
    key="editor_saluran"
)
st.session_state['df_saluran'] = edited_df

# ==========================================
# 5. ENGINE HITUNGAN
# ==========================================
def hitung_batch(df):
    hasil_list = []
    for idx, row in df.iterrows():
        # Input Data
        luas = row['Luas Area (ha)']
        modulus = row['Modulus (l/d/ha)']
        q_manual = row['Q Manual (m3/s)']
        
        # Logika Q Target
        if luas > 0:
            q_target = (luas * modulus) / 1000 
        else:
            q_target = q_manual
            
        # Parameter Fisik
        b = row['Lebar (b) m']
        h = row['Tinggi (h) m']
        m = row['Kemiringan (m)']
        S = row['Slope (S)']
        n = row['Manning (n)']
        
        # Safety Check
        if h <= 0 or b < 0 or n <= 0:
            hasil_list.append({'Q Target': q_target, 'Q Kapasitas': 0, 'V': 0, 'Fr': 0, 'Status': 'Error'})
            continue

        # Rumus Manning
        A = (b + m * h) * h
        P = b + 2 * h * np.sqrt(1 + m**2)
        R = A / P
        V = (1/n) * (R**(2/3)) * (S**0.5)
        Q_cap = A * V
        
        # Froude Number
        T = b + 2 * m * h 
        D = A / T         
        Fr = V / np.sqrt(9.81 * D)
        
        # Status
        status = "✅ AMAN" if Q_cap >= q_target else "⛔ BANJIR"
        
        hasil_list.append({
            'Q Target': round(q_target, 3),
            'Q Kapasitas': round(Q_cap, 3),
            'V (m/s)': round(V, 2),
            'Fr': round(Fr, 2),
            'Status': status
        })
        
    df_hasil = pd.DataFrame(hasil_list)
    return pd.concat([df.reset_index(drop=True), df_hasil], axis=1)

# Hitung
df_final = hitung_batch(edited_df)

# ==========================================
# 6. HASIL & VISUALISASI
# ==========================================
st.subheader("📊 Hasil Analisa")

def highlight_status(val):
    color = '#d4edda' if 'AMAN' in str(val) else '#f8d7da' if 'BANJIR' in str(val) else ''
    return f'background-color: {color}'

st.dataframe(
    df_final[['Nama Saluran', 'Q Target', 'Q Kapasitas', 'V (m/s)', 'Fr', 'Status']].style.applymap(highlight_status, subset=['Status']),
    use_container_width=True
)

st.markdown("---")
st.subheader("🖼️ Detail Penampang")

pilihan = st.selectbox("Pilih Saluran:", df_final['Nama Saluran'].unique())
row_select = df_final[df_final['Nama Saluran'] == pilihan].iloc[0]

c1, c2 = st.columns([1, 2])
with c1:
    st.info(f"**{row_select['Nama Saluran']}**")
    st.metric("Debit Desain", f"{row_select['Q Target']} m³/s")
    st.metric("Kapasitas", f"{row_select['Q Kapasitas']} m³/s", delta=round(row_select['Q Kapasitas']-row_select['Q Target'], 3))
    
    # Warna text input di metric tidak bisa diubah mudah, tapi labelnya bisa
    
with c2:
    b, h, m = row_select['Lebar (b) m'], row_select['Tinggi (h) m'], row_select['Kemiringan (m)']
    w = 0.5 
    fig, ax = plt.subplots(figsize=(8, 3.5))
    H_total = h + w
    x_tanah = [-(b/2 + m*H_total + 1), -(b/2 + m*H_total), -b/2, b/2, b/2 + m*H_total, b/2 + m*H_total + 1]
    y_tanah = [H_total, H_total, 0, 0, H_total, H_total]
    x_air = [-(b/2 + m*h), -b/2, b/2, b/2 + m*h]
    y_air = [h, 0, 0, h]
    
    ax.plot(x_tanah, y_tanah, 'k-', linewidth=2)
    ax.fill(x_air, y_air, '#29B6F6', alpha=0.6)
    ax.plot([x_air[0], x_air[-1]], [h, h], 'b--', linewidth=1)
    ax.text(0, h/2, f"h = {h}m", ha='center', color='white', fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')
    st.pyplot(fig)