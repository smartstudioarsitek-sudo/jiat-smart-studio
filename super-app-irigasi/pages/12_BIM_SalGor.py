import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: RAB Saluran & Bangunan", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste):
        # --- A. ANALISA STRUKTUR ---
        gamma_air = 9.81
        selimut = 0.04
        t_m = t_cm / 100
        
        # 1. Hitung Momen (Mu)
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        
        # 2. Cek Rekomendasi Tebal
        d_lentur = (Mu / (0.85 * 2000))**0.5 
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max(d_lentur + selimut + 0.006, sisi_miring / 12, 0.10)
        
        # --- B. VOLUME MATERIAL ---
        # Geometri Dalam
        area_in = (b + m * h) * h
        
        # Geometri Luar (Pendekatan Praktis Centerline)
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) 
        vol_beton = (keliling_center * t_m) * panjang
        
        # Galian: Volume Luar + Working Space
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) 
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang

        # Besi
        berat_m_lari = 0.00617 * (dia**2)
        keliling_besi = (b + 2*(h*math.sqrt(1+m**2))) 
        jum_potongan = (panjang * 100 / jarak) + 1
        total_berat_besi = (keliling_besi * jum_potongan * lapis * berat_m_lari) * 1.2 * (1 + waste/100)
        
        # Bekisting
        luas_bekisting = (2 * sisi_miring * panjang) * 2 

        return {
            "mu": Mu,
            "t_rekom": t_rekom * 100, 
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "berat_besi": total_berat_besi,
            "luas_bekisting": luas_bekisting
        }

    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai):
        area_dinding = ((l_atas + l_bawah) / 2) * h
        vol_dinding = 2 * area_dinding * panjang
        vol_lantai = b * t_lantai * panjang
        vol_batu = vol_dinding + vol_lantai
        
        sisi_miring = h * math.sqrt(1 + m**2)
        luas_plester = ((2 * sisi_miring) + b) * panjang 
        luas_siaran = (2 * l_atas) * panjang 
        
        vol_galian = vol_batu * 1.25 
        
        return {
            "mu": 0, "t_rekom": 0,
            "vol_batu": vol_batu,
            "vol_galian": vol_galian,
            "luas_plester": luas_plester,
            "luas_siaran": luas_siaran
        }

    @staticmethod
    def hitung_gorong_box(w, h, p):
        t = 0.20 
        vol_box_total = (w + 2*t) * (h + 2*t) * p
        vol_rongga = w * h * p
        vol_beton = vol_box_total - vol_rongga
        
        vol_galian = vol_box_total * 1.1
        berat_besi = vol_beton * 150 
        luas_bekisting = (2*w + 2*h) * p 
        
        return {
            "mu": 0, "t_rekom": 0,
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "berat_besi": berat_besi,
            "luas_bekisting": luas_bekisting
        }

# --- 3. SIDEBAR: MANAJEMEN FILE & HARGA ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    
    # --- FITUR SAVE/OPEN (BARU) ---
    col_save, col_load = st.columns(2)
    
    # 1. Download (Save)
    # Konversi data session ke JSON string
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button(
        label="💾 Save Data",
        data=json_str,
        file_name="proyek_rab_data.json",
        mime="application/json",
        help="Download data proyek saat ini ke file JSON"
    )
    
    # 2. Upload (Open)
    uploaded_file = st.file_uploader("📂 Open Data (.json)", type=["json"])
    if uploaded_file is not None:
        try:
            # Baca file dan load ke session state
            data_loaded = json.load(uploaded_file)
            st.session_state['data_proyek'] = data_loaded
            st.success("Data berhasil dimuat!")
        except Exception as e:
            st.error(f"Gagal memuat file: {e}")
            
    st.markdown("---")
    
    # --- HARGA SATUAN (EXISTING) ---
    st.header("💰 Harga Satuan Dasar")
    
    with st.expander("1. Upah Kerja", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", value=110000.0, step=1000.0, format="%.0f")
        u_tukang = st.number_input("Tukang (OH)", value=135000.0, step=1000.0, format="%.0f")
        u_mandor = st.number_input("Mandor (OH)", value=160000.0, step=1000.0, format="%.0f")
        overhead = st.slider("Overhead & Profit %", 0, 20, 10)
    
    with st.expander("2. Material Konstruksi", expanded=False):
        # Gunakan step=100.0 agar bisa input harga detail
        p_semen = st.number_input("Semen (kg)", value=1600.0, step=100.0, format="%.0f")
        p_pasir = st.number_input("Pasir Beton (m3)", value=250000.0, step=1000.0, format="%.0f")
        p_split = st.number_input("Kerikil/Split (m3)", value=350000.0, step=1000.0, format="%.0f")
        p_batu = st.number_input("Batu Belah (m3)", value=280000.0, step=1000.0, format="%.0f")
        p_besi = st.number_input("Besi Beton (kg)", value=14500.0, step=50.0, format="%.0f")
        p_kayu = st.number_input("Kayu Bekisting (m3)", value=3000000.0, step=10000.0, format="%.0f")

    # --- ENGINE AHSP ---
    oh_factor = 1 + (overhead/100)
    hsp_galian = ((0.75*u_pekerja) + (0.025*u_mandor)) * oh_factor
    hsp_beton = ((1.65*u_pekerja + 0.275*u_tukang + 0.083*u_mandor) + 
                 (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * oh_factor
    hsp_besi = ((0.007*u_pekerja + 0.007*u_tukang + 0.0004*u_mandor) + 
                (1.05*p_besi + 0.015*20000)) * oh_factor 
    hsp_bekisting = ((0.66*u_pekerja + 0.33*u_tukang + 0.033*u_mandor) + 
                     (0.045*p_kayu + 0.3*20000)) * oh_factor 
    hsp_batu = ((1.5*u_pekerja + 0.75*u_tukang + 0.075*u_mandor) + 
                (1.2*p_batu + 163*p_semen + 0.52*p_pasir)) * oh_factor
    hsp_plester = ((0.3*u_pekerja + 0.15*u_tukang + 0.015*u_mandor) + 
                   (6.24*p_semen + 0.024*p_pasir)) * oh_factor
    hsp_siaran = ((0.15*u_pekerja + 0.075*u_tukang) + 
                  (3*p_semen + 0.01*p_pasir)) * oh_factor

    st.markdown("### 🏷️ Preview Harga Jadi")
    st.caption(f"Beton K-225: Rp {hsp_beton:,.0f}/m3")

# --- 4. MAIN UI ---
st.title("🏗️ Integrated QS Estimator V.2")
st.markdown("**Fitur Baru:** Save/Open Data & Input Presisi Tinggi")

tab1, tab2, tab3 = st.tabs(["➕ Input Data (Saluran/Bangunan)", "📋 Daftar Item", "📊 Output RAB"])

# === TAB 1: INPUT CENTER ===
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Identitas Item")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Saluran Sekunder 1")
        
    with col2:
        st.subheader("2. Spesifikasi")
        # NOTE: Parameter step=0.01 dan format="%.3f" memungkinkan input desimal presisi
        # min_value=0.0 mencegah angka negatif
        
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0, step=0.1, format="%.2f", min_value=0.0)
            
            if tipe_kons == "Beton Bertulang":
                c_a, c_b, c_c = st.columns(3)
                h = c_a.number_input("Tinggi H (m)", value=0.8, step=0.01, format="%.3f", min_value=0.0)
                b = c_b.number_input("Lebar B (m)", value=0.6, step=0.01, format="%.3f", min_value=0.0)
                m = c_c.number_input("Talud m", value=0.0, step=0.01, format="%.2f", min_value=0.0)
                
                st.markdown("**Detail Penulangan:**")
                cc1, cc2, cc3 = st.columns(3)
                t_cm = cc1.number_input("Tebal Dinding (cm)", value=15.0, step=0.1, format="%.1f", min_value=0.0)
                dia = cc2.number_input("Diameter Besi (mm)", value=10.0, step=1.0, format="%.1f", min_value=0.0)
                jarak = cc3.number_input("Jarak (cm)", value=15.0, step=0.5, format="%.1f", min_value=0.0)
                
                # PREVIEW STRUKTUR
                calc_temp = Calculator.hitung_beton_struktur(h, b, m, 1, t_cm, dia, jarak, 2, 5)
                if calc_temp['mu'] > 0:
                    st.info(f"📐 **Cek Struktur:** Momen Mu = {calc_temp['mu']:.2f} kNm | Tebal Min. = {calc_temp['t_rekom']:.1f} cm")
                    if t_cm < calc_temp['t_rekom']:
                        st.error(f"⚠️ Tebal dinding {t_cm} cm < Rekomendasi {calc_temp['t_rekom']:.1f} cm!")
                
            else: # Batu
                h = st.number_input("Tinggi H (m)", value=0.8, step=0.01, format="%.3f", min_value=0.0)
                l_atas = st.number_input("Lebar Atas (m)", value=0.3, step=0.01, format="%.3f", min_value=0.0)
                l_bawah = st.number_input("Lebar Bawah (m)", value=0.4, step=0.01, format="%.3f", min_value=0.0)
                t_lantai = st.number_input("Tebal Lantai (m)", value=0.2, step=0.01, format="%.3f", min_value=0.0)
                
        else: # Bangunan
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box"])
            w = st.number_input("Lebar (m)", value=1.0, step=0.01, format="%.3f", min_value=0.0)
            h_b = st.number_input("Tinggi (m)", value=1.0, step=0.01, format="%.3f", min_value=0.0)
            p_b = st.number_input("Panjang (m)", value=5.0, step=0.01, format="%.3f", min_value=0.0)

    # TOMBOL EKSEKUSI
    if st.button("Simpan Item ke Daftar", type="primary"):
        if not nama_item:
            st.warning("Isi nama item dulu!")
        else:
            vol_result = {}
            tipe_final = ""
            
            if kategori == "Saluran (Linear)":
                if tipe_kons == "Beton Bertulang":
                    vol_result = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 7)
                    tipe_final = "Saluran Beton"
                else:
                    vol_result = Calculator.hitung_pasangan_batu(h, b, 0.2, panjang, l_atas, l_bawah, t_lantai)
                    tipe_final = "Saluran Batu"
            else:
                vol_result = Calculator.hitung_gorong_box(w, h_b, p_b)
                tipe_final = "Gorong-Gorong"
            
            item_data = {
                "nama": nama_item,
                "tipe": tipe_final,
                "panjang": panjang if kategori == "Saluran (Linear)" else p_b,
                "vol": vol_result
            }
            st.session_state['data_proyek'].append(item_data)
            st.success("✅ Data tersimpan! Jangan lupa Save Data (JSON) jika ingin menutup aplikasi.")

# === TAB 2: DAFTAR ===
with tab2:
    if st.session_state['data_proyek']:
        df_list = pd.DataFrame(st.session_state['data_proyek'])
        st.dataframe(df_list[["nama", "tipe", "panjang"]])
        if st.button("Hapus Semua Data"):
            st.session_state['data_proyek'] = []
            st.rerun()
    else:
        st.info("Belum ada data.")

# === TAB 3: RAB ===
with tab3:
    st.header("📊 Rekapitulasi Anggaran Biaya")
    
    if st.session_state['data_proyek']:
        # Agregasi Volume
        total_galian = sum([x['vol'].get('vol_galian', 0) for x in st.session_state['data_proyek']])
        total_beton = sum([x['vol'].get('vol_beton', 0) for x in st.session_state['data_proyek']])
        total_besi = sum([x['vol'].get('berat_besi', 0) for x in st.session_state['data_proyek']])
        total_bekisting = sum([x['vol'].get('luas_bekisting', 0) for x in st.session_state['data_proyek']])
        total_batu = sum([x['vol'].get('vol_batu', 0) for x in st.session_state['data_proyek']])
        total_plester = sum([x['vol'].get('luas_plester', 0) for x in st.session_state['data_proyek']])
        total_siaran = sum([x['vol'].get('luas_siaran', 0) for x in st.session_state['data_proyek']])
        
        # Tabel RAB
        data_rab = [
            {"Uraian": "Galian Tanah", "Vol": total_galian, "Sat": "m3", "Harga": hsp_galian},
            {"Uraian": "Beton K-225", "Vol": total_beton, "Sat": "m3", "Harga": hsp_beton},
            {"Uraian": "Pembesian", "Vol": total_besi, "Sat": "kg", "Harga": hsp_besi},
            {"Uraian": "Bekisting", "Vol": total_bekisting, "Sat": "m2", "Harga": hsp_bekisting},
            {"Uraian": "Pasangan Batu", "Vol": total_batu, "Sat": "m3", "Harga": hsp_batu},
            {"Uraian": "Plesteran", "Vol": total_plester, "Sat": "m2", "Harga": hsp_plester},
            {"Uraian": "Siaran", "Vol": total_siaran, "Sat": "m2", "Harga": hsp_siaran},
        ]
        
        df_rab = pd.DataFrame(data_rab)
        df_rab["Jumlah (Rp)"] = df_rab["Vol"] * df_rab["Harga"]
        df_rab = df_rab[df_rab["Vol"] > 0]
        
        st.dataframe(df_rab.style.format({
            "Vol": "{:.3f}", 
            "Harga": "{:,.0f}", 
            "Jumlah (Rp)": "{:,.0f}"
        }), use_container_width=True)
        
        grand_total = df_rab["Jumlah (Rp)"].sum()
        st.success(f"### 💰 Total Proyek: Rp {grand_total:,.0f}")
        
        # Export Excel
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='RAB')
                # Tambah sheet detail
                pd.DataFrame(st.session_state['data_proyek']).drop(columns=['vol']).to_excel(writer, index=False, sheet_name='Data Mentah')
            return output.getvalue()

        st.download_button("📥 Download Excel RAB", to_excel(df_rab), "RAB_Final.xlsx")
    else:
        st.warning("Belum ada data proyek untuk dihitung.")
