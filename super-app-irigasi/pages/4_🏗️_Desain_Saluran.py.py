import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="SmartStudio - Desain Saluran", layout="wide", page_icon="💧")

# --- 2. HEADER RAKSASA (IDENTITAS SMARTSTUDIO) ---
st.markdown("""
<style>
    .hero-box-small {
        background: linear-gradient(120deg, #0d47a1 0%, #1976d2 50%, #42a5f5 100%);
        padding: 30px; border-radius: 15px; color: white; text-align: center; margin-bottom: 25px;
    }
    /* Memperbesar font input data */
    div[data-testid="stDataFrame"] { font-size: 18px !important; font-weight: 600; }
</style>
<div class="hero-box-small">
    <h1 style="font-size: 50px; margin:0;">💧 SmartStudio</h1>
    <p style="font-size: 18px; opacity: 0.9;">Modul Desain Hidrolika Saluran Terbuka</p>
</div>
""", unsafe_allow_html=True)

# --- 3. TEMPLATE DATA ---
def get_default_data():
    return pd.DataFrame({
        'Nama Saluran': ['SDT 1KiKa', 'SDT 2KiKa', 'SDT 3KaKi', 'Saluran Sekunder A'],
        'Luas Area': [50.4, 103.95, 148.6, 0.0],
        'Modulus': [1.5, 1.5, 1.5, 0.0],
        'Q Manual': [0.0, 0.0, 0.0, 2.5],
        'Lebar (b)': [1.5, 2.0, 2.0, 1.5],
        'Tinggi (h)': [0.55, 0.8, 1.2, 1.2],
        'Kemiringan (m)': [1.0, 1.0, 1.5, 1.0],
        'Slope (S)': [0.0154, 0.0146, 0.0101, 0.0005],
        'Manning (n)': [0.025, 0.025, 0.025, 0.015]
    })

if 'df_saluran' not in st.session_state:
    st.session_state['df_saluran'] = get_default_data()

# Tombol Reset
if st.button("🔄 Reset Data Tabel"):
    st.session_state['df_saluran'] = get_default_data()
    st.rerun()

# --- 4. TABEL INPUT (FIX ERROR KOSONG) ---
st.subheader("📝 Input Parameter Saluran")
column_config = {
    "Luas Area": st.column_config.NumberColumn("Area (ha)", format="%.2f"),
    "Modulus": st.column_config.NumberColumn("Mod (l/s/ha)", format="%.2f"),
    "Q Manual": st.column_config.NumberColumn("Q Man (m3/s)", format="%.3f"),
    "Lebar (b)": st.column_config.NumberColumn("b (m)", format="%.2f"),
    "Tinggi (h)": st.column_config.NumberColumn("h (m)", format="%.2f"),
    "Slope (S)": st.column_config.NumberColumn("S", format="%.4f")
}

# Menggunakan parameter 'width' yang benar untuk menghindari error
edited_df = st.data_editor(
    st.session_state['df_saluran'],
    column_config=column_config,
    num_rows="dynamic",
    use_container_width=True, # Tetap gunakan ini, tapi pastikan library up to date
    key="editor_v2"
)
st.session_state['df_saluran'] = edited_df

# --- 5. ENGINE HITUNGAN ---
def hitung_hidrolika(df):
    results = []
    for _, row in df.iterrows():
        try:
            q_target = (row['Luas Area'] * row['Modulus'] / 1000) if row['Luas Area'] > 0 else row['Q Manual']
            b, h, m, S, n = row['Lebar (b)'], row['Tinggi (h)'], row['Kemiringan (m)'], row['Slope (S)'], row['Manning (n)']
            
            A = (b + m * h) * h
            P = b + 2 * h * np.sqrt(1 + m**2)
            R = A / P if P > 0 else 0
            V = (1/n) * (R**(2/3)) * (S**0.5) if n > 0 else 0
            Q_cap = A * V
            status = "✅ AMAN" if Q_cap >= q_target else "⛔ KURANG"
            
            results.append({'Q Desain': q_target, 'Q Kapasitas': Q_cap, 'V (m/s)': V, 'Status': status})
        except:
            results.append({'Q Desain': 0, 'Q Kapasitas': 0, 'V (m/s)': 0, 'Status': 'Error'})
    return pd.concat([df, pd.DataFrame(results)], axis=1)

df_final = hitung_hidrolika(edited_df)

# --- 6. HASIL ANALISA (FIX STYLE ERROR) ---
st.divider()
st.subheader("📊 Hasil Analisa Kapasitas")

def color_status(val):
    color = '#d1e7dd' if 'AMAN' in str(val) else '#f8d7da'
    return f'background-color: {color}'

# Menggunakan .map() sebagai pengganti .applymap() yang error di log
st.dataframe(
    df_final[['Nama Saluran', 'Q Desain', 'Q Kapasitas', 'V (m/s)', 'Status']].style.map(color_status, subset=['Status']),
    use_container_width=True
)