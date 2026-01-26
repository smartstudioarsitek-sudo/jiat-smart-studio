import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="QS Ultimate - SE 182/2025", layout="wide")

# --- 2. FUNGSI LOGIKA (STRUKTUR + VOLUME) ---
def hitung_struktur_dan_volume(h, b, m, fc, t_user_cm, dia, jarak, lapis, waste):
    # A. ANALISA STRUKTUR (DIKEMBALIKAN)
    gamma_air = 9.81
    selimut = 0.04
    
    # Hitung Momen Desain (Mu)
    Mu = 1.6 * (1/6) * gamma_air * (h**3)
    
    # Hitung Tebal Perlu (Lentur)
    # Asumsi lebar tinjauan 1000mm, d = tebal - selimut - 1/2 diameter
    # Mn = Mu/0.8, lalu pendekatan d_perlu
    d_lentur = (Mu / (0.85 * 2000))**0.5 # Rumus pendekatan cepat
    
    sisi_miring = h * math.sqrt(1 + m**2)
    
    # Tebal Rekomendasi (Max dari Lentur, Empiris, atau Min 10cm)
    t_rekom_m = max(d_lentur + selimut + 0.006, sisi_miring / 12, 0.10)
    
    # B. HITUNG VOLUME (AUTOCAD SYNC)
    t_m = t_user_cm / 100
    
    # Luas Dalam (Air)
    area_in = (b + m * h) * h
    
    # Luas Luar (Beton+Tanah) - Presisi Geometri
    h_out = h + t_m
    w_bot_out = b + 2 * t_m * (math.sqrt(1 + m**2) - m)
    w_top_out = b + 2 * m * h + 2 * t_m * math.sqrt(1 + m**2)
    area_out = (w_bot_out + w_top_out) / 2 * h_out
    
    vol_beton = area_out - area_in
    vol_galian = area_out
    
    # C. BESI & BEKISTING
    berat_m = 0.00617 * (dia**2)
    t_mid = t_m / 2
    # Keliling As Tulangan
    keliling_besi = (b + t_mid * (math.sqrt(1+m**2)-m)) + 2*(h+t_mid)*math.sqrt(1+m**2)
    # Berat Besi Total (kg/m')
    total_besi = keliling_besi * ((2 * (100/jarak + 1)) * berat_m * lapis) * (1 + waste/100)
    
    # Luas Bekisting
    bekisting = (2 * sisi_miring) + (2 * (h+t_m) * math.sqrt(1+m**2))
    
    return {
        "Mu": Mu,
        "t_rekom": round(t_rekom_m * 100, 1),
        "vol_beton": vol_beton,
        "vol_galian": vol_galian,
        "berat_besi": total_besi,
        "luas_bek": bekisting
    }

# --- 3. SIDEBAR: DATA & SAVE/LOAD ---
with st.sidebar:
    st.header("📋 Identitas & File")
    # Fitur Save/Load ditaruh paling atas agar mudah
    uploaded_file = st.file_uploader("📂 Buka Data Lama (JSON)", type="json")
    
    # Default Values
    def_vals = {
        "nama": "Saluran Sekunder 1", "pjg": 100.0, 
        "h": 0.8, "b": 0.6, "m": 1.0, "fc": 20,
        "dia": 10, "jarak": 20, "lapis": 1, "waste": 7
    }
    
    if uploaded_file is not None:
        try:
            d = json.load(uploaded_file)
            def_vals.update(d)
            st.success("✅ Data Terload!")
        except:
            st.error("File rusak")

    nama_saluran = st.text_input("Nama Saluran", value=def_vals["nama"])
    panjang_total = st.number_input("Panjang (m')", value=def_vals["pjg"])
    
    st.divider()
    st.header("📐 Dimensi & Struktur")
    h_in = st.number_input("Tinggi (H)", value=def_vals["h"])
    b_in = st.number_input("Lebar (B)", value=def_vals["b"])
    m_in = st.number_input("Talud (m)", value=def_vals["m"])
    fc_in = st.selectbox("Mutu Beton", [20, 25, 30], index=0)
    
    st.header("⛓️ Penulangan")
    dia_in = st.number_input("Diameter (mm)", value=def_vals["dia"])
    jarak_in = st.number_input("Jarak (cm)", value=def_vals["jarak"])
    lapis_in = st.radio("Lapis", [1, 2], index=1 if def_vals["lapis"]==2 else 0)
    waste_in = st.slider("Waste %", 0, 15, def_vals["waste"])
    
    # Tombol Download JSON
    curr_data = {
        "nama": nama_saluran, "pjg": panjang_total,
        "h": h_in, "b": b_in, "m": m_in, "fc": fc_in,
        "dia": dia_in, "jarak": jarak_in, "lapis": lapis_in, "waste": waste_in
    }
    st.download_button("💾 Simpan Data (JSON)", json.dumps(curr_data), f"{nama_saluran}.json", "application/json")

# --- 4. ENGINE PERHITUNGAN (MAIN PAGE) ---
st.title("🏗️ QS Ultimate: Struktur & RAB Terpadu")

# Step 1: Hitung Rekomendasi dulu
# Panggil fungsi dengan dummy tebal untuk dapatkan rekomendasi
rec = hitung_struktur_dan_volume(h_in, b_in, m_in, fc_in, 15, dia_in, jarak_in, lapis_in, waste_in)

# Tampilkan Info Struktur
col_info1, col_info2 = st.columns([2, 1])
with col_info1:
    st.info(f"💡 **Analisa Struktur:** Momen Beban (Mu) = **{rec['Mu']:.2f} kNm**")
with col_info2:
    st.warning(f"Rekomendasi Tebal: **{rec['t_rekom']} cm**")

# Step 2: Input Tebal Final & Hitung Volume
st.divider()
col_t1, col_t2 = st.columns([1, 3])
with col_t1:
    t_final = st.number_input("Tebal Beton Pakai (cm)", value=float(math.ceil(rec['t_rekom'])), step=1.0)
    vol_timbun = st.number_input("Vol. Timbunan (m3/m')", value=0.25)

# Hitung Ulang dengan Tebal Final
res = hitung_struktur_dan_volume(h_in, b_in, m_in, fc_in, t_final, dia_in, jarak_in, lapis_in, waste_in)

# --- 5. FORMULIR HARGA (AHSP) ---
st.header("💰 Data Harga Satuan (HSD)")
with st.expander("📝 Input Upah & Bahan (Klik Disini)", expanded=True):
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

# LOGIKA HARGA
oh = 1 + (overhead/100)
# HSP Galian
hsp_galian = ((0.75 * u_pekerja) + (0.025 * u_mandor)) * oh
# HSP Beton K-225 (A.4.1.1.8)
hsp_beton = ((1.65*u_pekerja + 0.275*135000 + 0.083*u_mandor) + (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * oh
# HSP Besi (A.4.1.1.17)
hsp_besi = ((0.007*u_pekerja + 0.007*135000 + 0.0004*u_mandor) + (1.05*p_besi + 0.015*24000)) * oh
# HSP Bekisting
hsp_bek = ((0.66*u_pekerja + 0.33*135000 + 0.033*u_mandor) + (0.045*p_kayu + 0.3*22000 + 0.1*18000)) * oh
# HSP Timbunan
hsp_timbun = ((0.5*u_pekerja + 0.05*u_mandor) + (0.05*s_stamper)) * oh

# --- 6. OUTPUT TABEL RAB ---
st.subheader(f"📊 Rekapitulasi RAB: {nama_saluran}")

data_rab = {
    "Uraian Pekerjaan": ["Galian Tanah", "Beton K-225", "Baja Tulangan", "Bekisting", "Timbunan Kembali"],
    "Satuan": ["m3", "m3", "kg", "m2", "m3"],
    "Vol/m'": [res['vol_galian'], res['vol_beton'], res['berat_besi'], res['luas_bek'], vol_timbun],
    "Vol Total": [
        res['vol_galian']*panjang_total, 
        res['vol_beton']*panjang_total, 
        res['berat_besi']*panjang_total, 
        res['luas_bek']*panjang_total, 
        vol_timbun*panjang_total
    ],
    "Harga Satuan": [hsp_galian, hsp_beton, hsp_besi, hsp_bek, hsp_timbun]
}
df = pd.DataFrame(data_rab)
df["Jumlah Harga (Rp)"] = df["Vol Total"] * df["Harga Satuan"]

st.dataframe(df.style.format({
    "Vol/m'": "{:.3f}", "Vol Total": "{:.2f}", 
    "Harga Satuan": "{:,.0f}", "Jumlah Harga (Rp)": "{:,.0f}"
}), use_container_width=True)

total_rab = df["Jumlah Harga (Rp)"].sum()
st.success(f"## TOTAL RAB PROYEK: Rp {total_rab:,.0f}")

# --- 7. EXPORT EXCEL ---
def to_excel(df, nama):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: RAB
        df.to_excel(writer, index=False, sheet_name='RAB')
        workbook = writer.book
        worksheet = writer.sheets['RAB']
        money_fmt = workbook.add_format({'num_format': '#,##0'})
        worksheet.set_column('E:F', 15, money_fmt)
        
        # Sheet 2: Data Teknis
        df_tech = pd.DataFrame({
            "Parameter": ["Momen Mu", "Tebal Rekomendasi", "Tebal Pakai", "Panjang Saluran"],
            "Nilai": [f"{rec['Mu']:.2f} kNm", f"{rec['t_rekom']} cm", f"{t_final} cm", f"{panjang_total} m"]
        })
        df_tech.to_excel(writer, index=False, sheet_name='Data Teknis')
        
    return output.getvalue()

excel_data = to_excel(df, nama_saluran)
st.download_button("📥 Download Excel (.xlsx)", excel_data, f"RAB_{nama_saluran}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
