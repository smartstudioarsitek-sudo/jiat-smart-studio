import streamlit as st
import pandas as pd
import json

# --- CONFIG ---
st.set_page_config(page_title="JIAT Smart Studio", page_icon="💧", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .main-header {font-size: 40px; font-weight: bold; color: #0d47a1; text-align: center; margin-bottom: 10px;}
    .sub-header {font-size: 18px; color: #555; text-align: center; margin-bottom: 30px;}
    .project-card {padding: 20px; background-color: #e3f2fd; border-radius: 10px; border: 1px solid #bbdefb; margin-bottom: 20px;}
    .stButton button {width: 100%; border-radius: 5px; font-weight: bold;}
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
# TAMPILAN DASHBOARD
# ==========================================

st.markdown('<div class="main-header">💧 JIAT Smart Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Super App Perencanaan Jaringan Irigasi Air Tanah (KP-01)</div>', unsafe_allow_html=True)

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
cols = st.columns(4)
modules = [('df_iklim_24', 'Klimatologi'), ('data_nfr_manual', 'Pola Tanam'), ('df_pipa', 'Irigasi Pipa')]

for i, (key, label) in enumerate(modules):
    with cols[i]:
        if key in st.session_state: st.success(f"✅ {label}: Ada")
        else: st.warning(f"⬜ {label}: Kosong")
