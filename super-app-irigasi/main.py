import streamlit as st
import pandas as pd
import json
import io

# --- CONFIG ---
st.set_page_config(
    page_title="JIAT Smart Studio",
    page_icon="💧",
    layout="wide"
)

# --- CSS KEREN ---
st.markdown("""
<style>
    .main-header {font-size: 42px; font-weight: bold; color: #2196f3; text-align: center; margin-bottom: 10px;}
    .sub-header {font-size: 18px; color: #555; text-align: center; margin-bottom: 30px;}
    .card {
        padding: 20px; background-color: white; border: 1px solid #ddd; 
        border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;
    }
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# FUNGSI PINTAR: SAVE & LOAD GLOBAL
# ==========================================

def serialize_session():
    """Mengubah semua data di Session State menjadi JSON yang bisa disimpan"""
    export_data = {}
    
    for key, value in st.session_state.items():
        # Filter: Jangan simpan tombol/form internal streamlit
        if key.startswith("FormSubmitter") or key.startswith("editor_"):
            continue
            
        # 1. Jika DataFrame -> Ubah jadi List of Dict (JSON friendly)
        if isinstance(value, pd.DataFrame):
            export_data[key] = {
                '__type__': 'dataframe',
                'data': value.to_dict(orient='records')
            }
        # 2. Jika Angka/Teks/List biasa -> Simpan langsung
        else:
            try:
                json.dumps(value) # Cek apakah bisa di-JSON-kan
                export_data[key] = value
            except:
                continue # Skip jika tipe data aneh
                
    return json.dumps(export_data, indent=2)

def load_session(json_file):
    """Mengembalikan data JSON ke Session State"""
    try:
        data = json.load(json_file)
        count = 0
        for key, value in data.items():
            # 1. Deteksi apakah ini DataFrame?
            if isinstance(value, dict) and value.get('__type__') == 'dataframe':
                st.session_state[key] = pd.DataFrame(value['data'])
            # 2. Data Biasa
            else:
                st.session_state[key] = value
            count += 1
        return True, count
    except Exception as e:
        return False, str(e)

# ==========================================
# TAMPILAN UTAMA (HOME)
# ==========================================

st.markdown('<div class="main-header">💧 JIAT Smart Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Super App Perencanaan Jaringan Irigasi Air Tanah (KP-01)</div>', unsafe_allow_html=True)

st.divider()

col1, col2 = st.columns([1, 1])

# --- BAGIAN KIRI: BUKA PROYEK ---
with col1:
    st.markdown("### 📂 Buka Proyek Lama")
    st.info("Upload file `.jiat` atau `.json` yang berisi seluruh data proyek.")
    
    uploaded_file = st.file_uploader("Upload File Proyek", type=['json', 'jiat'])
    
    if uploaded_file is not None:
        if st.button("📂 Load Data Proyek", type="primary"):
            success, msg = load_session(uploaded_file)
            if success:
                st.success(f"✅ Berhasil memuat {msg} variabel data!")
                st.markdown("**Sekarang silakan buka menu di sidebar (Klimatologi, dll). Data sudah terisi.**")
            else:
                st.error(f"Gagal memuat file: {msg}")

# --- BAGIAN KANAN: SIMPAN PROYEK ---
with col2:
    st.markdown("### 💾 Simpan Proyek Saat Ini")
    st.warning("Pastikan Anda sudah melakukan input/perhitungan di modul lain sebelum menyimpan.")
    
    # Input Nama File
    nama_proyek = st.session_state.get('nama_proyek', 'Proyek_JIAT_Baru')
    nama_file = st.text_input("Nama File Output", value=nama_proyek)
    
    # Tombol Download
    json_str = serialize_session()
    
    st.download_button(
        label="💾 Download Full Project (.jiat)",
        data=json_str,
        file_name=f"{nama_file}.json",
        mime="application/json",
        help="Simpan seluruh data (Klimatologi, Pola Tanam, Pipa) dalam satu file."
    )

st.divider()

# --- DASHBOARD RINGKASAN DATA ---
st.subheader("📊 Status Data Saat Ini")
c1, c2, c3, c4 = st.columns(4)

with c1:
    if 'df_iklim_24' in st.session_state:
        st.success("✅ Klimatologi: Ada")
    else:
        st.markdown("⬜ Klimatologi: Kosong")

with c2:
    if 'nfr_global' in st.session_state or 'data_nfr_manual' in st.session_state:
        st.success("✅ Pola Tanam: Ada")
    else:
        st.markdown("⬜ Pola Tanam: Kosong")

with c3:
    if 'df_pipa' in st.session_state:
        st.success("✅ Irigasi Pipa: Ada")
    else:
        st.markdown("⬜ Irigasi Pipa: Kosong")
        
with c4:
    if 'nama_proyek' in st.session_state:
        st.info(f"🏷️ {st.session_state['nama_proyek']}")
