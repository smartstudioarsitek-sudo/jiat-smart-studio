import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="JIAT Smart Studio", page_icon="💧", layout="wide")

# --- FUNGSI SAVE/LOAD GLOBAL ---
def serialize_session():
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
    try:
        data = json.load(json_file)
        for k, v in data.items():
            if isinstance(v, dict) and v.get('__type__') == 'df':
                st.session_state[k] = pd.DataFrame(v['data'])
            else:
                st.session_state[k] = v
        return True
    except Exception as e: return False

# --- UI IDENTITAS PROYEK ---
st.title("💧 JIAT Smart Studio")
st.subheader("Manajemen Proyek Terpusat")

with st.container():
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: st.session_state['nama_proyek'] = st.text_input("Nama Pekerjaan", value=st.session_state.get('nama_proyek', "Proyek Baru"))
    with c2: st.session_state['lokasi'] = st.text_input("Lokasi / Desa", value=st.session_state.get('lokasi', "-"))
    with c3: st.session_state['tahun'] = st.number_input("Tahun", value=st.session_state.get('tahun', 2026))

st.divider()

# --- SAVE & LOAD ---
col_l, col_r = st.columns(2)
with col_l:
    uploaded = st.file_uploader("📂 Buka File Proyek (.jiat / .json)", type=['json', 'jiat'])
    if uploaded and st.button("Load Project"):
        if load_session(uploaded): st.success("✅ Data Berhasil Dimuat!"); st.rerun()

with col_r:
    file_label = f"{st.session_state['nama_proyek'].replace(' ', '_')}.json"
    st.download_button(label=f"💾 Simpan Full Project: {file_label}", data=serialize_session(), file_name=file_label, mime="application/json")

# Indikator Status Data
st.divider()
st.caption("Status Data Saat Ini:")
cols = st.columns(3)
with cols[0]: st.write("Klimatologi:", "✅" if 'df_iklim_24' in st.session_state else "⬜")
with cols[1]: st.write("Pola Tanam:", "✅" if 'data_nfr_manual' in st.session_state else "⬜")
with cols[2]: st.write("Irigasi Pipa:", "✅" if 'df_pipa' in st.session_state else "⬜")
