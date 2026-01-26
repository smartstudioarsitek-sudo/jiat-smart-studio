import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Pro - Estimator Saluran 2025", layout="wide")

# --- 2. FUNGSI LOGIKA TEKNIS ---
def hitung_analisa_terpadu(h, b, m, t_cm, dia, jarak, lapis, waste):
    t_m = t_cm / 100
    area_in = (b + m * h) * h
    h_out = h + t_m
    w_bot_out = b + 2 * t_m * (math.sqrt(1 + m**2) - m)
    w_top_out = b + 2 * m * h + 2 * t_m * math.sqrt(1 + m**2)
    area_out = (w_bot_out + w_top_out) / 2 * h_out
    
    vol_beton = area_out - area_in
    vol_galian = area_out
    
    berat_m = 0.00617 * (dia**2)
    t_mid = t_m / 2
    keliling_besi = (b + t_mid * (math.sqrt(1+m**2)-m)) + 2*(h+t_mid)*math.sqrt(1+m**2)
    total_besi = keliling_besi * ((2 * (100/jarak + 1)) * berat_m * lapis) * (1 + waste/100)
    bekisting = (2 * h * math.sqrt(1+m**2)) + (2 * (h+t_m) * math.sqrt(1+m**2))
    
    return vol_beton, vol_galian, total_besi, bekisting

# --- 3. SIDEBAR: IDENTITAS & DATA TEKNIS ---
with st.sidebar:
    st.header("📋 Identitas Proyek")
    nama_saluran = st.text_input("Nama Saluran", value="Saluran Primer D.I. Bengkulu")
    panjang_total = st.number_input("Panjang Saluran Total (m')", value=100.0, step=10.0)
    
    st.divider()
    st.header("📐 Data Teknis")
    h_in = st.number_input("Tinggi (H)", value=0.8)
    b_in = st.number_input("Lebar (B)", value=0.6)
    m_in = st.number_input("Talud (m)", value=1.0)
    t_in = st.number_input("Tebal Beton (cm)", value=15.0)
    
    st.header("⛓️ Pembesian")
    dia_in = st.number_input("Diameter (mm)", value=10)
    jarak_in = st.number_input("Jarak (cm)", value=20)
    lapis_in = st.radio("Lapis", [1, 2], index=1)
    waste_in = st.slider("Waste %", 0, 15, 7)

# --- 4. MANAJEMEN DATA (SAVE/OPEN JSON) ---
st.title("🏗️ QS Pro: Estimator & Data Management")
col_s1, col_s2 = st.columns(2)

with col_s1:
    # Fungsi Save
    data_to_save = {
        "nama": nama_saluran, "panjang": panjang_total, "h": h_in, "b": b_in, "m": m_in,
        "t": t_in, "dia": dia_in, "jarak": jarak_in, "lapis": lapis_in, "waste": waste_in
    }
    json_string = json.dumps(data_to_save)
    st.download_button(label="💾 Simpan Data (JSON)", data=json_string, file_name=f"data_{nama_saluran}.json", mime="application/json")

with col_s2:
    # Fungsi Open
    uploaded_file = st.file_uploader("📂 Buka Data (JSON)", type="json")
    if uploaded_file is not None:
        data_loaded = json.load(uploaded_file)
        st.info(f"Data '{data_loaded['nama']}' berhasil diunggah. Silakan sesuaikan angka di sidebar jika belum berubah.")

# --- 5. MODUL HARGA & PERHITUNGAN ---
st.divider()
with st.expander("💰 Formulir AHSP (Update Harga Satuan)", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        u_pekerja = st.number_input("Upah Pekerja", value=110000)
        u_mandor = st.number_input("Upah Mandor", value=150000)
        overhead = st.slider("Overhead %", 10, 15, 10)
    with c2:
        p_besi = st.number_input("Besi (kg)", value=14500)
        p_semen = st.number_input("Semen (kg)", value=1600)
        p_pasir = st.number_input("Pasir (m3)", value=250000)
    with c3:
        p_split = st.number_input("Split (m3)", value=350000)
        p_kayu = st.number_input("Papan (m3)", value=2800000)
        s_stamper = st.number_input("Sewa Stamper", value=150000)

# LOGIKA HITUNG
oh = 1 + (overhead/100)
v_beton, v_galian, w_besi, a_bek = hitung_analisa_terpadu(h_in, b_in, m_in, t_in, dia_in, jarak_in, lapis_in, waste_in)

# HSP Standar SE 182/2025
hsp_galian = ((0.75 * u_pekerja) + (0.025 * u_mandor)) * oh
hsp_beton = ((1.65*u_pekerja + 0.275*135000 + 0.083*u_mandor) + (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * oh
hsp_besi = ((0.007*u_pekerja + 0.007*135000 + 0.0004*u_mandor) + (1.05*p_besi + 0.015*24000)) * oh
hsp_bek = ((0.66*u_pekerja + 0.33*135000 + 0.033*u_mandor) + (0.045*p_kayu + 0.3*22000 + 0.1*18000)) * oh
hsp_timbun = ((0.5*u_pekerja + 0.05*u_mandor) + (0.05*s_stamper)) * oh

# --- 6. TABEL RAB ---
st.subheader(f"📊 Rekapitulasi RAB: {nama_saluran}")
data_rab = {
    "Uraian Pekerjaan": ["Galian Tanah", "Beton K-225", "Baja Tulangan", "Bekisting", "Timbunan Kembali"],
    "Satuan": ["m3", "m3", "kg", "m2", "m3"],
    "Volume/m'": [v_galian, v_beton, w_besi, a_bek, 0.25],
    "Volume Total": [v_galian*panjang_total, v_beton*panjang_total, w_besi*panjang_total, a_bek*panjang_total, 0.25*panjang_total],
    "Harga Satuan": [hsp_galian, hsp_beton, hsp_besi, hsp_bek, hsp_timbun]
}
df = pd.DataFrame(data_rab)
df["Jumlah Harga (Rp)"] = df["Volume Total"] * df["Harga Satuan"]

st.dataframe(df.style.format({"Volume/m'": "{:.3f}", "Volume Total": "{:.2f}", "Harga Satuan": "{:,.0f}", "Jumlah Harga (Rp)": "{:,.0f}"}), use_container_width=True)

total_rab = df["Jumlah Harga (Rp)"].sum()
st.success(f"## TOTAL ANGGARAN: Rp {total_rab:,.0f}")

# --- 7. EXPORT EXCEL ---
def to_excel(df, nama):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RAB')
        writer.book.add_format({'num_format': '#,##0'})
    return output.getvalue()

excel_data = to_excel(df, nama_saluran)
st.download_button(label="📥 Download RAB ke Excel (.xlsx)", data=excel_data, file_name=f"RAB_{nama_saluran}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
