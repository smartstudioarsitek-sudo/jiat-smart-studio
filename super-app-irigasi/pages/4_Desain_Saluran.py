import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Desain Saluran", layout="wide", page_icon="🏗️")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #546e7a 0%, #78909c 50%, #90a4ae 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px; padding: 10px 20px; font-weight: bold;
    }
    .stTabs [aria-selected="true"] { background-color: #e3f2fd; color: #1565c0; border: 2px solid #1565c0; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🏗️ Desain Hidrolika Saluran</h1>
    <p style="opacity: 0.9;">Analisa Dimensi Berdasarkan Hirarki Saluran (Induk, Sekunder, Tersier)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. LOGIKA MODULUS & EFISIENSI ---
# Ambil NFR Global dari Modul 2 sebagai referensi
if 'nfr_global' in st.session_state:
    nfr_ref = st.session_state['nfr_global']
    status_link = "✅ Terhubung: Modul Pola Tanam"
else:
    nfr_ref = 1.25
    status_link = "⚠️ Default (Modul Pola Tanam belum dijalankan)"

# Fungsi Template Data
def get_template_df(tipe):
    if tipe == "Induk":
        eff = 0.90 # KP-01 Saluran Induk
        b, h, m, s, n = 2.0, 1.2, 1.5, 0.04, 0.025 # Default Induk
        nama = ["Induk Kanan", "Induk Kiri"]
        luas = [500.0, 400.0]
    elif tipe == "Sekunder":
        eff = 0.85 # KP-01 Saluran Sekunder
        b, h, m, s, n = 1.0, 0.8, 1.0, 0.06, 0.025 # Default Sekunder
        nama = ["Sekunder A", "Sekunder B"]
        luas = [150.0, 100.0]
    else: # Tersier
        eff = 0.80 # KP-01 Saluran Tersier
        b, h, m, s, n = 0.5, 0.4, 1.0, 0.10, 0.030 # Default Tersier (Tanah)
        nama = ["Tersier 1-Kn", "Tersier 1-Kr"]
        luas = [50.0, 40.0]
        
    return pd.DataFrame({
        'Nama Saluran': nama,
        'Luas (ha)': luas,
        'Modulus (l/s/ha)': [nfr_ref] * 2,
        'Efisiensi': [eff] * 2, # Kolom Baru
        'Lebar (b)': [b] * 2,
        'Tinggi (h)': [h] * 2,
        'Talud (m)': [m] * 2,
        'Slope S (%)': [s] * 2,
        'Kekasaran n': [n] * 2
    })

# Inisialisasi 3 Dataframe Terpisah
if 'df_induk' not in st.session_state: st.session_state.df_induk = get_template_df("Induk")
if 'df_sekunder' not in st.session_state: st.session_state.df_sekunder = get_template_df("Sekunder")
if 'df_tersier' not in st.session_state: st.session_state.df_tersier = get_template_df("Tersier")

# --- 4. TABS INPUT ---
st.subheader("1. Input Dimensi Saluran")
st.info(f"ℹ️ **Info:** {status_link} | Base NFR: **{nfr_ref} l/s/ha**")

# Membuat 3 Tab
tab1, tab2, tab3 = st.tabs(["🟦 Saluran INDUK", "🟨 Saluran SEKUNDER", "🟩 Saluran TERSIER"])

# -- EDITOR TAB 1: INDUK --
with tab1:
    st.caption("Saluran Utama (Efisiensi Tinggi ~90%)")
    st.session_state.df_induk = st.data_editor(
        st.session_state.df_induk, use_container_width=True, num_rows="dynamic", key="ed_induk",
        column_config={
            "Efisiensi": st.column_config.NumberColumn(min_value=0.1, max_value=1.0, step=0.01, format="%.2f", help="Faktor efisiensi saluran (0-1.0)"),
            "Modulus (l/s/ha)": st.column_config.NumberColumn(format="%.3f"),
            "Slope S (%)": st.column_config.NumberColumn(format="%.3f")
        }
    )

# -- EDITOR TAB 2: SEKUNDER --
with tab2:
    st.caption("Saluran Cabang (Efisiensi Sedang ~85%)")
    st.session_state.df_sekunder = st.data_editor(
        st.session_state.df_sekunder, use_container_width=True, num_rows="dynamic", key="ed_sekunder",
        column_config={
            "Efisiensi": st.column_config.NumberColumn(min_value=0.1, max_value=1.0, step=0.01, format="%.2f"),
            "Modulus (l/s/ha)": st.column_config.NumberColumn(format="%.3f"),
            "Slope S (%)": st.column_config.NumberColumn(format="%.3f")
        }
    )

# -- EDITOR TAB 3: TERSIER --
with tab3:
    st.caption("Saluran Petak (Efisiensi Rendah ~80%)")
    st.session_state.df_tersier = st.data_editor(
        st.session_state.df_tersier, use_container_width=True, num_rows="dynamic", key="ed_tersier",
        column_config={
            "Efisiensi": st.column_config.NumberColumn(min_value=0.1, max_value=1.0, step=0.01, format="%.2f"),
            "Modulus (l/s/ha)": st.column_config.NumberColumn(format="%.3f"),
            "Slope S (%)": st.column_config.NumberColumn(format="%.3f")
        }
    )

# --- 5. ENGINE PERHITUNGAN (Global Function) ---
def hitung_hidrolika(df):
    results = []
    for idx, row in df.iterrows():
        # Input Data
        A_ha = row['Luas (ha)']
        mod = row['Modulus (l/s/ha)']
        eff = row['Efisiensi']
        b = row['Lebar (b)']
        h = row['Tinggi (h)']
        m = row['Talud (m)']
        S_dec = row['Slope S (%)'] / 100
        n = row['Kekasaran n']
        
        # 1. Debit Rencana (Q Desain)
        # Rumus: Q = (Luas * Modulus) / Efisiensi
        if eff <= 0: eff = 1.0 # Safety division
        q_desain = (A_ha * mod / 1000) / eff 
        
        # 2. Geometri & Manning
        A_wet = (b + m * h) * h
        P_wet = b + 2 * h * np.sqrt(1 + m**2)
        R = A_wet / P_wet if P_wet > 0 else 0
        V = (1/n) * (R**(2/3)) * (S_dec**0.5)
        q_kapasitas = A_wet * V
        
        # 3. Status
        if q_kapasitas >= q_desain:
            status = "✅ AMAN"
            delta = f"Sisa +{round(q_kapasitas - q_desain, 3)}"
        else:
            status = "❌ BANJIR"
            delta = f"Kurang {round(q_desain - q_kapasitas, 3)}"
            
        # Froude
        T = b + 2 * m * h
        D = A_wet / T if T > 0 else 0
        Fr = V / np.sqrt(9.81 * D) if D > 0 else 0
        
        results.append({
            'Nama Saluran': row['Nama Saluran'],
            'Q Desain (m³/s)': round(q_desain, 3),
            'Q Kapasitas': round(q_kapasitas, 3),
            'V (m/s)': round(V, 2),
            'Fr': round(Fr, 2),
            'Status': status,
            'Keterangan': delta
        })
    return pd.DataFrame(results)

# Hitung Semua
res_induk = hitung_hidrolika(st.session_state.df_induk)
res_sekunder = hitung_hidrolika(st.session_state.df_sekunder)
res_tersier = hitung_hidrolika(st.session_state.df_tersier)

# --- 6. HASIL ANALISA (TAB JUGA) ---
st.divider()
st.subheader("2. Hasil Analisa Kapasitas")

def style_df(df):
    return df.style.map(lambda x: 'color: green; font-weight: bold' if 'AMAN' in str(x) else 'color: red; font-weight: bold' if 'BANJIR' in str(x) else '', subset=['Status'])

t1, t2, t3 = st.tabs(["Hasil INDUK", "Hasil SEKUNDER", "Hasil TERSIER"])

with t1: st.dataframe(style_df(res_induk), use_container_width=True)
with t2: st.dataframe(style_df(res_sekunder), use_container_width=True)
with t3: st.dataframe(style_df(res_tersier), use_container_width=True)

# --- 7. VISUALISASI PENAMPANG ---
st.divider()
col_v1, col_v2 = st.columns([1, 2])

with col_v1:
    st.markdown("### 🔍 Cek Visual")
    # Gabungkan nama saluran untuk dropdown
    all_names = []
    all_dfs = []
    
    if not st.session_state.df_induk.empty:
        all_names += [f"[Induk] {x}" for x in st.session_state.df_induk['Nama Saluran']]
        all_dfs.append(st.session_state.df_induk)
    if not st.session_state.df_sekunder.empty:
        all_names += [f"[Sekunder] {x}" for x in st.session_state.df_sekunder['Nama Saluran']]
        all_dfs.append(st.session_state.df_sekunder)
    if not st.session_state.df_tersier.empty:
        all_names += [f"[Tersier] {x}" for x in st.session_state.df_tersier['Nama Saluran']]
        all_dfs.append(st.session_state.df_tersier)

    sel_full = st.selectbox("Pilih Saluran:", all_names)
    
    # Logic cari data berdasarkan pilihan
    sel_type = sel_full.split("] ")[0].replace("[", "")
    sel_name = sel_full.split("] ")[1]
    
    if sel_type == "Induk": df_target = st.session_state.df_induk
    elif sel_type == "Sekunder": df_target = st.session_state.df_sekunder
    else: df_target = st.session_state.df_tersier
    
    row_vis = df_target[df_target['Nama Saluran'] == sel_name].iloc[0]
    
    # Hitung ulang Q untuk display metric
    eff_v = row_vis['Efisiensi']
    q_des_v = (row_vis['Luas (ha)'] * row_vis['Modulus (l/s/ha)'] / 1000) / eff_v
    st.metric("Q Desain (Kebutuhan)", f"{round(q_des_v, 3)} m³/s", f"Efisiensi {eff_v*100}%")

with col_v2:
    # Plotting
    b, h, m = row_vis['Lebar (b)'], row_vis['Tinggi (h)'], row_vis['Talud (m)']
    
    fig, ax = plt.subplots(figsize=(6, 2.5))
    x = [0, m*h, m*h + b, m*h + b + m*h]
    y = [h, 0, 0, h]
    
    ax.plot(x, y, 'k-', linewidth=2)
    ax.fill(x, y, '#795548', alpha=0.3, label='Tanah')
    
    # Air (Full Capacity)
    ax.fill(x, y, '#2196f3', alpha=0.6, label='Air (Full)')
    
    ax.set_title(f"Penampang: {sel_name}")
    ax.set_aspect('equal')
    ax.grid(True, linestyle=':', alpha=0.5)
    st.pyplot(fig)
