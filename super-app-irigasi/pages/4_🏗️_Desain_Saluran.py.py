import streamlit as st
import pandas as pd
import numpy as np

# --- 1. SETTING HALAMAN ---
st.set_page_config(page_title="SmartStudio - Saluran", layout="wide", page_icon="💧")

# --- 2. HEADER SMARTSTUDIO (FONT BESAR + LOGO AIR) ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 40px; border-radius: 15px; color: white; text-align: center; margin-bottom: 30px;
    }
    /* Memperbesar Font Tabel agar Mudah Dibaca */
    div[data-testid="stDataFrame"] { font-size: 18px !important; font-weight: 600; }
</style>
<div class="hero-box">
    <h1 style="font-size: 60px; margin:0;">💧 SmartStudio</h1>
    <p style="font-size: 20px; opacity: 0.9;">Modul Desain Hidrolika Saluran Terbuka</p>
</div>
""", unsafe_allow_html=True)

# --- 3. MANAJEMEN DATA ---
def init_data():
    return pd.DataFrame({
        'Nama Saluran': ['SDT 1KiKa', 'SDT 2KiKa', 'SDT 3KaKi', 'Sekunder A'],
        'Luas Area (ha)': [50.4, 103.95, 148.6, 0.0],
        'Modulus (l/s/ha)': [1.5, 1.5, 1.5, 0.0],
        'Q Manual (m3/s)': [0.0, 0.0, 0.0, 2.5],
        'Lebar b (m)': [1.5, 2.0, 2.0, 1.5],
        'Tinggi h (m)': [0.55, 0.8, 1.2, 1.2],
        'Talud m': [1.0, 1.0, 1.5, 1.0],
        'Slope S': [0.0154, 0.0146, 0.0101, 0.0005],
        'Manning n': [0.025, 0.025, 0.025, 0.015]
    })

if 'data_saluran' not in st.session_state:
    st.session_state['data_saluran'] = init_data()

# Tombol Reset
if st.button("🔄 Reset Data"):
    st.session_state['data_saluran'] = init_data()
    st.rerun()

# --- 4. TABEL INPUT (VERSI PALING STABIL) ---
st.subheader("📝 Input Parameter")
# Menggunakan data_editor tanpa konfigurasi rumit dulu agar PASTI MUNCUL
df_input = st.data_editor(
    st.session_state['data_saluran'],
    num_rows="dynamic",
    use_container_width=True,
    key="editor_fix_v3"
)
st.session_state['data_saluran'] = df_input

# --- 5. HITUNGAN OTOMATIS ---
def hitung(df):
    results = []
    for _, row in df.iterrows():
        try:
            # Hitung Q Rencana
            q_rencana = (row['Luas Area (ha)'] * row['Modulus (l/s/ha)'] / 1000) if row['Luas Area (ha)'] > 0 else row['Q Manual (m3/s)']
            
            # Manning Formula
            b, h, m, S, n = row['Lebar b (m)'], row['Tinggi h (m)'], row['Talud m'], row['Slope S'], row['Manning n']
            A = (b + m * h) * h
            P = b + 2 * h * np.sqrt(1 + m**2)
            R = A / P if P > 0 else 0
            V = (1/n) * (R**(2/3)) * (S**0.5) if n > 0 else 0
            Q_cap = A * V
            
            res = "✅ AMAN" if Q_cap >= q_rencana else "⚠️ KURANG"
            results.append([round(q_rencana, 3), round(Q_cap, 3), round(V, 2), res])
        except:
            results.append([0, 0, 0, "Error"])
    
    return pd.DataFrame(results, columns=['Q Desain', 'Q Kapasitas', 'V (m/s)', 'Status'])

# --- 6. TAMPILKAN HASIL ---
st.divider()
st.subheader("📊 Hasil Analisa")

hasil_df = hitung(df_input)
final_display = pd.concat([df_input[['Nama Saluran']], hasil_df], axis=1)

# FIX ERROR: Menggunakan .map() bukan .applymap()
def warna_status(val):
    color = '#d1e7dd' if val == "✅ AMAN" else '#f8d7da'
    return f'background-color: {color}'

# Tampilkan tabel hasil
st.dataframe(
    final_display.style.map(warna_status, subset=['Status']),
    use_container_width=True
)