import streamlit as st
import pandas as pd
import math
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: RAB Saluran & Bangunan", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste):
        # --- A. ANALISA STRUKTUR (Konsisten dengan kode lama) ---
        gamma_air = 9.81
        selimut = 0.04
        t_m = t_cm / 100
        
        # 1. Hitung Momen (Mu)
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        
        # 2. Cek Rekomendasi Tebal
        d_lentur = (Mu / (0.85 * 2000))**0.5 
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max(d_lentur + selimut + 0.006, sisi_miring / 12, 0.10)
        
        # --- B. VOLUME MATERIAL (Per m' x Panjang) ---
        # Geometri Dalam
        area_in = (b + m * h) * h
        
        # Geometri Luar
        h_out = h + t_m
        # Rumus QS: Area Luar = Area Dalam + (Keliling * Tebal) + Corner Adjustment
        # Kita pakai pendekatan geometri trapesium luar exact
        # Lebar atas air = b + 2mh. Lebar atas beton = Lebar atas air + 2*(t/sin_theta) -> rumit
        # Pendekatan Praktis Volume Beton Saluran = Luas Penampang Beton * Panjang
        # Luas Penampang Beton ~ (Keliling Tengah * Tebal)
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) # Approximation
        vol_beton = (keliling_center * t_m) * panjang
        
        # Galian: Volume Luar + Working Space (20cm kiri kanan bawah)
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) # Asumsi galian miring m sama
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang

        # Besi
        berat_m_lari = 0.00617 * (dia**2)
        # Panjang besi per potongan = Keliling + Overlap/Kait
        keliling_besi = (b + 2*(h*math.sqrt(1+m**2))) 
        jum_potongan = (panjang * 100 / jarak) + 1
        # Total panjang = (Panjang per potong * jumlah * lapis) + (Besi memanjang/pembagi est. 20%)
        total_berat_besi = (keliling_besi * jum_potongan * lapis * berat_m_lari) * 1.2 * (1 + waste/100)
        
        # Bekisting (Dinding Dalam + Luar Miring jika perlu, biasanya dalam saja untuk saluran tanah)
        # Asumsi: Bekisting 2 sisi (Luar Dalam) untuk kualitas baik
        luas_bekisting = (2 * sisi_miring * panjang) * 2 

        return {
            "mu": Mu,
            "t_rekom": t_rekom * 100, # ke cm
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "berat_besi": total_berat_besi,
            "luas_bekisting": luas_bekisting
        }

    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai):
        # Sama dengan kode lama
        area_dinding = ((l_atas + l_bawah) / 2) * h
        vol_dinding = 2 * area_dinding * panjang
        vol_lantai = b * t_lantai * panjang
        vol_batu = vol_dinding + vol_lantai
        
        sisi_miring = h * math.sqrt(1 + m**2)
        luas_plester = ((2 * sisi_miring) + b) * panjang # Dalam + Lantai
        luas_siaran = (2 * l_atas) * panjang # Bibir atas
        
        vol_galian = vol_batu * 1.25 # Faktor gembur
        
        return {
            "mu": 0, "t_rekom": 0,
            "vol_batu": vol_batu,
            "vol_galian": vol_galian,
            "luas_plester": luas_plester,
            "luas_siaran": luas_siaran
        }

    @staticmethod
    def hitung_gorong_box(w, h, p):
        # Simple Box Culvert Logic
        t = 0.20 # tebal 20cm
        vol_box_total = (w + 2*t) * (h + 2*t) * p
        vol_rongga = w * h * p
        vol_beton = vol_box_total - vol_rongga
        
        vol_galian = vol_box_total * 1.1
        berat_besi = vol_beton * 150 # kg/m3 estimate
        luas_bekisting = (2*w + 2*h) * p # bekisting dalam
        
        return {
            "mu": 0, "t_rekom": 0,
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "berat_besi": berat_besi,
            "luas_bekisting": luas_bekisting
        }

# --- 3. SIDEBAR: INPUT HARGA DASAR (KEMBALI KE ASAL) ---
with st.sidebar:
    st.header("💰 Harga Satuan Dasar")
    st.info("Fitur Analisa Harga Satuan (AHSP) dikembalikan.")
    
    with st.expander("1. Upah Kerja", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", 110000)
        u_tukang = st.number_input("Tukang (OH)", 135000)
        u_mandor = st.number_input("Mandor (OH)", 160000)
        overhead = st.slider("Overhead & Profit %", 0, 20, 10)
    
    with st.expander("2. Material Konstruksi", expanded=False):
        p_semen = st.number_input("Semen (kg)", 1600) # per kg (sak 50kg = 80rb -> 1600)
        p_pasir = st.number_input("Pasir Beton (m3)", 250000)
        p_split = st.number_input("Kerikil/Split (m3)", 350000)
        p_batu = st.number_input("Batu Belah (m3)", 280000)
        p_besi = st.number_input("Besi Beton (kg)", 14500)
        p_kayu = st.number_input("Kayu Bekisting (m3)", 3000000)

    # --- ENGINE AHSP (LOGIKA KODE LAMA) ---
    oh_factor = 1 + (overhead/100)
    
    # 1. Galian
    hsp_galian = ((0.75*u_pekerja) + (0.025*u_mandor)) * oh_factor
    
    # 2. Beton K-225 (Manual A.4.1.1.8)
    hsp_beton = ((1.65*u_pekerja + 0.275*u_tukang + 0.083*u_mandor) + 
                 (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)) * oh_factor
                 
    # 3. Pembesian (A.4.1.1.17)
    hsp_besi = ((0.007*u_pekerja + 0.007*u_tukang + 0.0004*u_mandor) + 
                (1.05*p_besi + 0.015*20000)) * oh_factor # kawat
                
    # 4. Bekisting (A.4.1.1.21)
    hsp_bekisting = ((0.66*u_pekerja + 0.33*u_tukang + 0.033*u_mandor) + 
                     (0.045*p_kayu + 0.3*20000)) * oh_factor # paku/minyak
                     
    # 5. Pasangan Batu 1:4 (A.3.2.1.2)
    hsp_batu = ((1.5*u_pekerja + 0.75*u_tukang + 0.075*u_mandor) + 
                (1.2*p_batu + 163*p_semen + 0.52*p_pasir)) * oh_factor
                
    # 6. Plesteran (A.4.4.2.4)
    hsp_plester = ((0.3*u_pekerja + 0.15*u_tukang + 0.015*u_mandor) + 
                   (6.24*p_semen + 0.024*p_pasir)) * oh_factor
    
    # 7. Siaran (A.4.4.2.27)
    hsp_siaran = ((0.15*u_pekerja + 0.075*u_tukang) + 
                  (3*p_semen + 0.01*p_pasir)) * oh_factor

    # Tampilkan Preview HSP
    st.markdown("### 🏷️ Preview Harga Jadi")
    st.caption(f"Beton K-225: Rp {hsp_beton:,.0f}/m3")
    st.caption(f"Pas. Batu: Rp {hsp_batu:,.0f}/m3")
    st.caption(f"Besi: Rp {hsp_besi:,.0f}/kg")

# --- 4. MAIN UI ---
st.title("🏗️ Integrated QS Estimator")
st.markdown("Fitur: **Multi-Segmen** + **Analisa Struktur** + **AHSP Dinamis**")

tab1, tab2, tab3 = st.tabs(["➕ Input Data (Saluran/Bangunan)", "📋 Daftar Item", "📊 Output RAB"])

# === TAB 1: INPUT CENTER ===
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Identitas Item")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Saluran Sekunder 1 atau Gorong-gorong")
        
    with col2:
        st.subheader("2. Spesifikasi")
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", 50.0)
            
            if tipe_kons == "Beton Bertulang":
                c_a, c_b, c_c = st.columns(3)
                h = c_a.number_input("Tinggi H (m)", 0.8)
                b = c_b.number_input("Lebar B (m)", 0.6)
                m = c_c.number_input("Talud m", 0.0)
                
                st.markdown("**Detail Penulangan:**")
                cc1, cc2, cc3 = st.columns(3)
                t_cm = cc1.number_input("Tebal Dinding (cm)", 15.0)
                dia = cc2.number_input("Diameter Besi (mm)", 10)
                jarak = cc3.number_input("Jarak (cm)", 15)
                
                # PREVIEW STRUKTUR (Fitur Lama Dikembalikan)
                calc_temp = Calculator.hitung_beton_struktur(h, b, m, 1, t_cm, dia, jarak, 2, 5)
                if calc_temp['mu'] > 0:
                    st.info(f"📐 **Cek Struktur:** Momen Mu = {calc_temp['mu']:.2f} kNm | Tebal Min. = {calc_temp['t_rekom']:.1f} cm")
                    if t_cm < calc_temp['t_rekom']:
                        st.error(f"⚠️ Tebal dinding {t_cm} cm < Rekomendasi {calc_temp['t_rekom']:.1f} cm!")
                
            else: # Batu
                h = st.number_input("Tinggi H (m)", 0.8)
                l_atas = st.number_input("Lebar Atas (m)", 0.3)
                l_bawah = st.number_input("Lebar Bawah (m)", 0.4)
                t_lantai = st.number_input("Tebal Lantai (m)", 0.2)
                
        else: # Bangunan
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box"])
            w = st.number_input("Lebar (m)", 1.0)
            h_b = st.number_input("Tinggi (m)", 1.0)
            p_b = st.number_input("Panjang (m)", 5.0)

    # TOMBOL EKSEKUSI
    if st.button("Simpan Item ke Daftar", type="primary"):
        if not nama_item:
            st.warning("Isi nama item dulu!")
        else:
            vol_result = {}
            tipe_final = ""
            
            if kategori == "Saluran (Linear)":
                if tipe_kons == "Beton Bertulang":
                    vol_result = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 7) # Waste 7% default
                    tipe_final = "Saluran Beton"
                else:
                    vol_result = Calculator.hitung_pasangan_batu(h, b, 0.2, panjang, l_atas, l_bawah, t_lantai) # m asumsi 0.2
                    tipe_final = "Saluran Batu"
            else:
                vol_result = Calculator.hitung_gorong_box(w, h_b, p_b)
                tipe_final = "Gorong-Gorong"
            
            # Simpan ke Session State
            item_data = {
                "nama": nama_item,
                "tipe": tipe_final,
                "panjang": panjang if kategori == "Saluran (Linear)" else p_b,
                "vol": vol_result
            }
            st.session_state['data_proyek'].append(item_data)
            st.success("✅ Data tersimpan!")

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
    df_rab = df_rab[df_rab["Vol"] > 0] # Sembunyikan yang 0
    
    st.dataframe(df_rab.style.format({
        "Vol": "{:.2f}", 
        "Harga": "{:,.0f}", 
        "Jumlah (Rp)": "{:,.0f}"
    }), use_container_width=True)
    
    grand_total = df_rab["Jumlah (Rp)"].sum()
    st.success(f"### 💰 Total Proyek: Rp {grand_total:,.0f}")
    
    # Export
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='RAB')
        return output.getvalue()

    st.download_button("📥 Download Excel", to_excel(df_rab), "RAB_Final.xlsx")
