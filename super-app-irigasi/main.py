import streamlit as st
import pandas as pd
import json

# --- CONFIG ---
st.set_page_config(page_title="Hydro Planner", page_icon="💧", layout="wide")

# --- CSS CANTIK (DENGAN GOOGLE FONTS) ---
st.markdown("""
<style>
    /* Import Font Keren */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&family=Pacifico&display=swap');

    .branding-tag {
        font-family: 'Pacifico', cursive; /* Font tulisan tangan manis */
        font-size: 18px;
        color: #ff7675; /* Warna agak pink/salmon biar manis kontras sama biru */
        text-align: center;
        margin-bottom: -10px;
    }
    
    .main-title {
        font-family: 'Poppins', sans-serif;
        font-size: 55px;
        font-weight: 800;
        /* Efek Gradasi Air */
        background: -webkit-linear-gradient(45deg, #0984e3, #00cec9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        line-height: 1.2;
        margin-top: 0px;
    }

    .sub-title {
        font-family: 'Poppins', sans-serif;
        font-size: 18px;
        color: #636e72;
        text-align: center;
        font-weight: 400;
        letter-spacing: 1px;
        margin-bottom: 30px;
    }

    .project-card {
        padding: 25px; 
        background-color: #ffffff; 
        border-radius: 15px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); /* Bayangan halus */
        border: 1px solid #dfe6e9; 
        margin-bottom: 20px;
    }
    
    .stButton button {
        width: 100%; 
        border-radius: 8px; 
        font-weight: bold; 
        height: 50px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI SAVE/LOAD ---
def serialize_session():
    """Mengubah memori aplikasi jadi JSON"""
    export = {}
    for k, v in st.session_state.items():
        if k.startswith(("Form", "editor", "uploaded")): continue
        if isinstance(v, pd.DataFrame):
            export[k] = {'__type__': 'df', 'data': v.to_dict(orient='records')}
        else:
            try:
                json.dumps(v)
                export[k] = v
            except: pass
    return json.dumps(export, indent=2)

def load_session(json_file):
    """Mengembalikan JSON ke memori aplikasi"""
    try:
        data = json.load(json_file)
        count = 0
        for k, v in data.items():
            if isinstance(v, dict) and v.get('__type__') == 'df':
                st.session_state[k] = pd.DataFrame(v['data'])
            else:
                st.session_state[k] = v
            count += 1
        return True, count
    except Exception as e: return False, str(e)

# --- INIT STATE ---
if 'nama_proyek' not in st.session_state: st.session_state['nama_proyek'] = "Proyek Baru"
if 'lokasi' not in st.session_state: st.session_state['lokasi'] = "-"
if 'tahun' not in st.session_state: st.session_state['tahun'] = 2026

# ==========================================
# TAMPILAN HEADER BARU
# ==========================================

# 1. Branding Kecil nan Manis
st.markdown('<div class="branding-tag">by Smart Studio</div>', unsafe_allow_html=True)

# 2. Judul Besar Gradasi (Bisa Kakak ganti teksnya disini)
st.markdown('<div class="main-title">HYDRO PLANNER</div>', unsafe_allow_html=True)

# 3. Sub-Judul Deskriptif
st.markdown('<div class="sub-title">Integrated Irrigation & Drainage Engineering Suite</div>', unsafe_allow_html=True)

# --- BAGIAN 1: IDENTITAS PROYEK ---
st.markdown("### 1️⃣ Identitas Proyek")
with st.container():
    st.markdown('<div class="project-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: st.session_state['nama_proyek'] = st.text_input("Nama Pekerjaan", value=st.session_state['nama_proyek'])
    with c2: st.session_state['lokasi'] = st.text_input("Lokasi / Desa", value=st.session_state['lokasi'])
    with c3: st.session_state['tahun'] = st.number_input("Tahun Anggaran", value=st.session_state['tahun'])
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# --- BAGIAN 2: MANAJEMEN DATA ---
c_left, c_right = st.columns(2)

# LOAD
with c_left:
    st.markdown("### 📂 Buka File Lama")
    uploaded = st.file_uploader("Upload file .json", type=['json'])
    if uploaded:
        if st.button("📂 Load Project"):
            ok, msg = load_session(uploaded)
            if ok: 
                st.success(f"✅ Berhasil memuat {msg} data! Cek halaman lain.")
                st.rerun()
            else: st.error(f"Gagal: {msg}")

# SAVE
with c_right:
    st.markdown("### 💾 Simpan Proyek (Save All)")
    st.info("Tombol ini akan menyimpan SELURUH DATA dari semua halaman.")
    
    file_label = f"{st.session_state['nama_proyek'].replace(' ', '_')}.json"
    json_str = serialize_session()
    
    st.download_button(
        label=f"💾 Download: {file_label}",
        data=json_str,
        file_name=file_label,
        mime="application/json",
        type="primary"
    )

# STATUS DATA
st.divider()
st.caption("Status Data di Memori (RAM):")
cols = st.columns(5)
modules = [
    ('df_iklim_24', 'Klimatologi'), 
    ('data_nfr_manual', 'Pola Tanam'), 
    ('df_mock_input', 'Ketersediaan Air'),
    ('hujan_rancangan', 'Analisa Banjir'),
    ('df_pipa', 'Desain Pipa')
]

for i, (key, label) in enumerate(modules):
    with cols[i]:
        if key in st.session_state: st.success(f"✅ {label}")
        else: st.markdown(f"⬜ {label}")
