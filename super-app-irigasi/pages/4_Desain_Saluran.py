import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Hydraulic Batch Pro", layout="wide", page_icon="🏗️")

# --- 1. CSS CUSTOM (MAKEOVER TABEL & INPUT) ---
st.markdown("""
<style>
    /* Mengubah Header Tabel jadi Biru Muda & Teks Biru Tua */
    div[data-testid="stDataFrame"] div[class*="stDataFrame"] {
        background-color: #f8f9fa; /* Warna latar tabel */
    }
    
    /* Bikin teks di dalam tabel lebih tebal (Bold) */
    div[data-testid="stDataFrame"] {
        font-weight: 600;
        color: #2c3e50;
    }

    /* Warna Tombol Reset */
    div.stButton > button:first-child {
        background-color: #ffcdd2;
        color: #b71c1c;
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #ef9a9a;
        color: #fff;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. TEMPLATE DATA AWAL
# ==========================================
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

# ==========================================
# 3. HEADER & TOMBOL RESET
# ==========================================
col_header, col_btn = st.columns([4, 1])
with col_header:
    st.title("🏗️ Desain Hidrolika Saluran")
    st.caption("Batch Calculation System (Manning Formula)")
with col_btn:
    st.write("") # Spasi
    if st.button("🔄 Reset Data", help="Kembalikan tabel ke data awal"):
        st.session_state['df_saluran'] = get_default_data()
        st.rerun()

st.info("💡 **Tips:** Klik dua kali pada sel untuk mengedit. Tekan **Ctrl+Z** jika salah ketik.")

# ==========================================
# 4. TABEL INPUT (DENGAN FORMATTING CANGGIH)
# ==========================================
# Di sini kita atur formatting biar ada satuannya (ha, m, dll)
column_config = {
    "Nama Saluran": st.column_config.TextColumn("Nama Saluran", width="medium", required=True),
    "Luas Area": st.column_config.NumberColumn("Luas (A)", format="%.2f ha", min_value=0),
    "Modulus": st.column_config.NumberColumn("Modulus", format="%.2f l/s/ha"),
    "Q Manual": st.column_config.NumberColumn("Q Manual", format="%.3f m³/s"),
    "Lebar (b)": st.column_config.NumberColumn("Lebar (b)", format="%.2f m"),
    "Tinggi (h)": st.column_config.NumberColumn("Tinggi (h)", format="%.2f m"),
    "Kemiringan (m)": st.column_config.NumberColumn("Talud (m)", format="1 : %.1f"),
    "Slope (S)": st.column_config.NumberColumn("Slope (S)", format="%.4f", step=0.0001),
    "Manning (n)": st.column_config.NumberColumn("Kekasaran (n)", format="%.3f")
}

edited_df = st.data_editor(
    st.session_state['df_saluran'],
    column_config=column_config, # <--- Ini kuncinya!
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
        # Mapping Nama Kolom (Sesuai Dataframe di atas)
        luas = row['Luas Area']
        modulus = row['Modulus']
        q_manual = row['Q Manual']
        
        # Logika Q Target
        if luas > 0:
            q_target = (luas * modulus) / 1000 
        else:
            q_target = q_manual
            
        b = row['Lebar (b)']
        h = row['Tinggi (h)']
        m = row['Kemiringan (m)']
        S = row['Slope (S)']
        n = row['Manning (n)']
        
        if h <= 0 or b < 0 or n <= 0:
            hasil_list.append({'Q Desain': 0, 'Q Kapasitas': 0, 'V': 0, 'Fr': 0, 'Status': 'Error'})
            continue

        A = (b + m * h) * h
        P = b + 2 * h * np.sqrt(1 + m**2)
        R = A / P
        V = (1/n) * (R**(2/3)) * (S**0.5)
        Q_cap = A * V
        
        T = b + 2 * m * h 
        D = A / T         
        Fr = V / np.sqrt(9.81 * D)
        
        status = "✅ AMAN" if Q_cap >= q_target else "⛔ BANJIR"
        
        hasil_list.append({
            'Q Desain': round(q_target, 3),
            'Q Kapasitas': round(Q_cap, 3),
            'V (m/s)': round(V, 2),
            'Fr': round(Fr, 2),
            'Status': status
        })
        
    df_hasil = pd.DataFrame(hasil_list)
    return pd.concat([df.reset_index(drop=True), df_hasil], axis=1)

df_final = hitung_batch(edited_df)

# ==========================================
# 6. HASIL & VISUALISASI
# ==========================================
st.divider()
st.subheader("📊 Hasil Analisa")

def highlight_status(val):
    color = '#d1e7dd' if 'AMAN' in str(val) else '#f8d7da' if 'BANJIR' in str(val) else ''
    return f'background-color: {color}; color: black; font-weight: bold;'

# Tampilkan Hasil dengan Format Angka yang Rapi
st.dataframe(
    df_final[['Nama Saluran', 'Q Desain', 'Q Kapasitas', 'V (m/s)', 'Fr', 'Status']].style.applymap(highlight_status, subset=['Status']).format("{:.3f}", subset=['Q Desain', 'Q Kapasitas', 'V (m/s)', 'Fr']),
    use_container_width=True
)

# Detail Penampang
st.subheader("🖼️ Detail Penampang & Cross Section")
col_sel, col_fig = st.columns([1, 2])

with col_sel:
    pilihan = st.selectbox("Pilih Saluran:", df_final['Nama Saluran'].unique())
    row_select = df_final[df_final['Nama Saluran'] == pilihan].iloc[0]
    
    st.markdown(f"""
    <div style="background-color:#e3f2fd; padding:15px; border-radius:10px; border-left:5px solid #2196f3;">
        <h4 style="margin:0; color:#1565c0;">{row_select['Nama Saluran']}</h4>
        <hr style="margin:10px 0;">
        <b>Debit Desain:</b> {row_select['Q Desain']} m³/s<br>
        <b>Kapasitas:</b> {row_select['Q Kapasitas']} m³/s<br>
        <b>Kecepatan:</b> {row_select['V (m/s)']} m/s<br>
        <b>Froude:</b> {row_select['Fr']}
    </div>
    """, unsafe_allow_html=True)
    
    if row_select['Q Kapasitas'] < row_select['Q Desain']:
        st.error("⚠️ Kapasitas KURANG! Perbesar dimensi.")
    else:
        st.success("✅ Dimensi OK.")

with col_fig:
    b, h, m = row_select['Lebar (b)'], row_select['Tinggi (h)'], row_select['Kemiringan (m)']
    w = 0.5 
    fig, ax = plt.subplots(figsize=(8, 3.5))
    H_total = h + w
    x_tanah = [-(b/2 + m*H_total + 1), -(b/2 + m*H_total), -b/2, b/2, b/2 + m*H_total, b/2 + m*H_total + 1]
    y_tanah = [H_total, H_total, 0, 0, H_total, H_total]
    x_air = [-(b/2 + m*h), -b/2, b/2, b/2 + m*h]
    y_air = [h, 0, 0, h]
    
    ax.plot(x_tanah, y_tanah, 'k-', linewidth=2, label='Tanah')
    ax.fill(x_air, y_air, '#03a9f4', alpha=0.6, label='Air')
    ax.plot([x_air[0], x_air[-1]], [h, h], 'b--', linewidth=1)
    
    ax.text(0, h/2, f"{h} m", ha='center', color='white', fontweight='bold')
    ax.text(0, -0.2, f"b = {b} m", ha='center', fontweight='bold')
    
    ax.set_title(f"Penampang: {pilihan}")
    ax.set_aspect('equal')
    ax.axis('off')
    st.pyplot(fig)
