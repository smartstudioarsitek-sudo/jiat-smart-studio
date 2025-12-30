import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Hydraulic Batch Pro", layout="wide", page_icon="🏗️")

# --- CSS TABEL ---
st.markdown("""
<style>
    [data-testid="stDataFrame"] {border: 1px solid #ddd; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. TEMPLATE DATA AWAL
# ==========================================
if 'df_saluran' not in st.session_state:
    # Kita buat struktur mirip Excel Kakak
    data = {
        'Nama Saluran': ['SDT 1KiKa', 'SDT 2KiKa', 'SDT 3KaKi', 'Saluran Sekunder A'],
        'Luas Area (ha)': [50.4, 103.95, 148.6, 0.0],  # Jika 0, berarti input Q manual
        'Modulus (l/d/ha)': [1.5, 1.5, 1.5, 0.0],      # Modulus drainase
        'Q Manual (m3/s)': [0.0, 0.0, 0.0, 2.5],       # Debit input manual (opsional)
        'Lebar (b) m': [1.5, 2.0, 2.0, 1.5],
        'Tinggi (h) m': [0.55, 0.8, 1.2, 1.2],
        'Kemiringan (m)': [1.0, 1.0, 1.5, 1.0],        # Talud 1:m
        'Slope (S)': [0.0154, 0.0146, 0.0101, 0.0005], # Kemiringan dasar
        'Manning (n)': [0.025, 0.025, 0.025, 0.015]    # Kekasaran
    }
    st.session_state['df_saluran'] = pd.DataFrame(data)

# ==========================================
# 2. ENGINE MANNING (Batch Processing)
# ==========================================
def hitung_batch(df):
    hasil_list = []
    
    for idx, row in df.iterrows():
        # 1. Tentukan Q Desain (Target)
        luas = row['Luas Area (ha)']
        modulus = row['Modulus (l/d/ha)']
        q_manual = row['Q Manual (m3/s)']
        
        # Logika Excel: Q = Luas * Modulus (konversi l/det ke m3/det)
        if luas > 0:
            q_target = (luas * modulus) / 1000 
        else:
            q_target = q_manual # Pakai input manual kalau Luas 0
            
        # 2. Parameter Fisik
        b = row['Lebar (b) m']
        h = row['Tinggi (h) m']
        m = row['Kemiringan (m)']
        S = row['Slope (S)']
        n = row['Manning (n)']
        
        # Safety check division by zero
        if h <= 0 or b < 0 or n <= 0:
            hasil_list.append({'Q Target': q_target, 'Q Kapasitas': 0, 'V': 0, 'Fr': 0, 'Status': 'Error'})
            continue

        # 3. Rumus Manning
        A = (b + m * h) * h
        P = b + 2 * h * np.sqrt(1 + m**2)
        R = A / P
        V = (1/n) * (R**(2/3)) * (S**0.5)
        Q_cap = A * V
        
        # Froude Number
        T = b + 2 * m * h # Lebar atas
        D = A / T         # Hydraulic Depth
        Fr = V / np.sqrt(9.81 * D)
        
        # 4. Cek Status
        status = "✅ AMAN" if Q_cap >= q_target else "⛔ BANJIR"
        
        hasil_list.append({
            'Q Target': round(q_target, 3),
            'Q Kapasitas': round(Q_cap, 3),
            'V (m/s)': round(V, 2),
            'Fr': round(Fr, 2),
            'Status': status
        })
        
    # Gabungkan hasil ke DataFrame asli
    df_hasil = pd.DataFrame(hasil_list)
    return pd.concat([df.reset_index(drop=True), df_hasil], axis=1)

# ==========================================
# 3. HALAMAN UTAMA
# ==========================================
st.title("🏗️ Desain Hidrolika Saluran (Batch System)")
st.markdown("Edit tabel di bawah ini (Bisa Copy-Paste dari Excel). Otomatis menghitung Q Kapasitas.")

# --- BAGIAN 1: TABEL INPUT ---
edited_df = st.data_editor(
    st.session_state['df_saluran'],
    num_rows="dynamic", # Bisa tambah baris
    use_container_width=True,
    height=300,
    key="editor_saluran"
)
st.session_state['df_saluran'] = edited_df

# --- PROSES HITUNG ---
df_final = hitung_batch(edited_df)

# --- BAGIAN 2: HASIL REKAP ---
st.subheader("📊 Hasil Analisa")

# Tampilkan tabel hasil dengan highlight warna
def highlight_status(val):
    color = '#d4edda' if 'AMAN' in str(val) else '#f8d7da' if 'BANJIR' in str(val) else ''
    return f'background-color: {color}'

st.dataframe(
    df_final[['Nama Saluran', 'Q Target', 'Q Kapasitas', 'V (m/s)', 'Fr', 'Status']].style.applymap(highlight_status, subset=['Status']),
    use_container_width=True
)

# ==========================================
# 4. DETAIL VISUALISASI (Pilih Baris)
# ==========================================
st.markdown("---")
st.subheader("🖼️ Detail Penampang & Cross Section")

# Pilih Saluran untuk digambar
pilihan = st.selectbox("Pilih Saluran untuk dilihat gambarnya:", df_final['Nama Saluran'].unique())

# Ambil data baris yang dipilih
row_select = df_final[df_final['Nama Saluran'] == pilihan].iloc[0]

c1, c2 = st.columns([1, 2])

with c1:
    st.info(f"**{row_select['Nama Saluran']}**")
    st.metric("Debit Desain (Target)", f"{row_select['Q Target']} m³/s")
    st.metric("Kapasitas Saluran", f"{row_select['Q Kapasitas']} m³/s", delta=round(row_select['Q Kapasitas']-row_select['Q Target'], 3))
    st.metric("Kecepatan Aliran (V)", f"{row_select['V (m/s)']} m/s")
    
    if row_select['Q Kapasitas'] < row_select['Q Target']:
        st.error("⚠️ PERINGATAN: Dimensi kurang besar!")
    else:
        st.success("✅ OKE: Dimensi memenuhi syarat.")

with c2:
    # Fungsi Gambar (Sama seperti sebelumnya tapi pakai data tabel)
    b, h, m = row_select['Lebar (b) m'], row_select['Tinggi (h) m'], row_select['Kemiringan (m)']
    w = 0.5 # Asumsi jagaan standar
    
    fig, ax = plt.subplots(figsize=(8, 3.5))
    H_total = h + w
    x_tanah = [-(b/2 + m*H_total + 1), -(b/2 + m*H_total), -b/2, b/2, b/2 + m*H_total, b/2 + m*H_total + 1]
    y_tanah = [H_total, H_total, 0, 0, H_total, H_total]
    x_air = [-(b/2 + m*h), -b/2, b/2, b/2 + m*h]
    y_air = [h, 0, 0, h]
    
    ax.plot(x_tanah, y_tanah, 'k-', linewidth=2, label='Saluran')
    ax.fill(x_air, y_air, '#29B6F6', alpha=0.6, label='Air')
    ax.plot([x_air[0], x_air[-1]], [h, h], 'b--', linewidth=1)
    
    ax.text(0, h/2, f"h = {h}m", ha='center', color='white', fontweight='bold')
    ax.set_title(f"Penampang: {pilihan}")
    ax.set_aspect('equal')
    ax.axis('off')
    st.pyplot(fig)