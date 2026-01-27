import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS V.12: AHSP SDA Bengkulu", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY AHSP & HARGA (DATABASE BENGKULU) ---
class AHSP_Engine:
    """
    Engine Analisa Harga Satuan Pekerjaan (AHSP) Bidang SDA.
    Referensi: SE Menteri PUPR Bidang SDA.
    Lokasi Harga: Provinsi Bengkulu (Estimasi)
    """
    
    @staticmethod
    def get_analisa_detail(hsp_code, prices):
        """Mengembalikan Rincian Analisa dalam format Dictionary"""
        u_pekerja = prices['u_pekerja']
        u_tukang = prices['u_tukang']
        u_mandor = prices['u_mandor']
        p_semen = prices['p_semen']
        p_pasir = prices['p_pasir']
        p_batu = prices['p_batu']
        p_split = prices['p_split']
        p_besi = prices['p_besi']
        p_kayu = prices['p_kayu']
        p_paku = prices['p_paku']
        p_kawat = prices['p_kawat'] # Kawat beton

        # --- A. PEKERJAAN TANAH (SDA) ---
        if hsp_code == "T.06.a.1": # Galian Tanah Biasa (Manual) - T.06.a.1
            koef = [
                ("Pekerja", 0.750, u_pekerja),
                ("Mandor", 0.025, u_mandor)
            ]
            return {"kode": "T.06.a.1", "uraian": "1 m3 Galian Tanah Biasa (Manual)", "items": koef}
            
        elif hsp_code == "T.14.a": # Timbunan Tanah Kembali (Manual)
            koef = [
                ("Pekerja", 0.330, u_pekerja),
                ("Mandor", 0.010, u_mandor)
            ]
            return {"kode": "T.14.a", "uraian": "1 m3 Timbunan Kembali Dipadatkan", "items": koef}

        # --- B. PEKERJAAN PASANGAN (SDA) ---
        elif hsp_code == "P.01.a": # Pasangan Batu Kali 1:4 (SDA)
            koef = [
                # Tenaga
                ("Pekerja", 1.200, u_pekerja),
                ("Tukang Batu", 0.600, u_tukang),
                ("Mandor", 0.060, u_mandor),
                # Bahan
                ("Batu Kali", 1.200, p_batu),
                ("Semen (PC)", 163.00, p_semen),
                ("Pasir Pasang", 0.520, p_pasir)
            ]
            return {"kode": "P.01.a (SDA)", "uraian": "1 m3 Pasangan Batu Camp. 1:4", "items": koef}
            
        elif hsp_code == "P.04.e": # Plesteran 1:3 + Acian (Tebal 15mm)
            koef = [
                ("Pekerja", 0.300, u_pekerja),
                ("Tukang Batu", 0.150, u_tukang),
                ("Mandor", 0.015, u_mandor),
                ("Semen (PC)", 7.776, p_semen), # 6.24 plester + acian
                ("Pasir Pasang", 0.024, p_pasir)
            ]
            return {"kode": "P.04.e", "uraian": "1 m2 Plesteran 1:3 + Acian", "items": koef}

        elif hsp_code == "P.05.a": # Siaran 1:2
            koef = [
                ("Pekerja", 0.150, u_pekerja),
                ("Tukang Batu", 0.075, u_tukang),
                ("Mandor", 0.008, u_mandor),
                ("Semen (PC)", 6.000, p_semen), # Estimasi Siaran
                ("Pasir Pasang", 0.010, p_pasir)
            ]
            return {"kode": "P.05.a", "uraian": "1 m2 Siaran Camp. 1:2", "items": koef}

        # --- C. PEKERJAAN BETON (SDA) ---
        elif hsp_code == "B.05.a": # Beton K-225 (Manual/Molen Kecil)
            koef = [
                ("Pekerja", 1.650, u_pekerja),
                ("Tukang Batu", 0.275, u_tukang),
                ("Mandor", 0.083, u_mandor),
                ("Semen (PC)", 371.0, p_semen),
                ("Pasir Beton", 0.499, p_pasir),
                ("Split/Kerikil", 0.776, p_split)
            ]
            return {"kode": "B.05.a", "uraian": "1 m3 Beton Mutu K-225 (f'c 19.3 MPa)", "items": koef}

        elif hsp_code == "B.17.a": # Pembesian (Polos/Ulir)
            koef = [
                ("Pekerja", 0.007, u_pekerja),
                ("Tukang Besi", 0.007, u_tukang),
                ("Mandor", 0.0004, u_mandor),
                ("Besi Beton", 1.050, p_besi), # Waste 5%
                ("Kawat Beton", 0.015, p_kawat)
            ]
            return {"kode": "B.17.a", "uraian": "1 kg Pembesian Besi Polos/Ulir", "items": koef}
            
        elif hsp_code == "B.20.a": # Bekisting Kayu (Untuk Saluran/Struktur) - 2x Pakai
            koef = [
                ("Pekerja", 0.520, u_pekerja),
                ("Tukang Kayu", 0.260, u_tukang),
                ("Mandor", 0.026, u_mandor),
                ("Kayu Kelas III", 0.045, p_kayu),
                ("Paku", 0.300, p_paku),
                ("Minyak Bekisting", 0.100, 25000) # Assumsi liter
            ]
            return {"kode": "B.20.a", "uraian": "1 m2 Pasang Bekisting (Kayu Kls III)", "items": koef}
        
        elif hsp_code == "T.15.a": # Bongkaran Pasangan
            koef = [
                ("Pekerja", 2.000, u_pekerja),
                ("Mandor", 0.100, u_mandor)
            ]
            return {"kode": "T.15.a", "uraian": "1 m3 Bongkaran Pasangan", "items": koef}

        return {"kode": "N/A", "uraian": "Item Tidak Ditemukan", "items": []}

    @staticmethod
    def hitung_harga_satuan(hsp_code, prices, overhead_pct):
        analisa = AHSP_Engine.get_analisa_detail(hsp_code, prices)
        total_dasar = sum([item[1] * item[2] for item in analisa['items']])
        total_final = total_dasar * (1 + overhead_pct/100)
        return total_final

# --- 3. LIBRARY PERHITUNGAN VOLUME (ENGINEERING CORE - V.11) ---
class Calculator:
    
    # 3.1 SALURAN BETON
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        if h <= 0 or panjang <= 0: return {"vol_beton": 0, "rho_data": {"status": "DATA KOSONG"}}
        gamma_air, selimut = 9.81, 40
        t_mm = t_cm * 10
        d_eff = max(1.0, t_mm - selimut - (dia/2))
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        rho_actual = As_per_meter / (1000 * d_eff)
        rho_min = 1.4 / fy if fy > 0 else 0.0014
        rho_max = 0.75 * ((0.85 * (0.85 if fc<=28 else 0.65) * fc / fy) * (600/(600+fy)))
        status_rho = "AMAN" if rho_min <= rho_actual <= rho_max else ("KURANG BESI" if rho_actual < rho_min else "BOROS BESI")
        t_m = t_cm / 100
        vol_beton = (b + 2*(h*math.sqrt(1+m**2)) + 2*t_m) * t_m * panjang
        vol_galian = ((b + 2*t_m*math.sqrt(1+m**2) + 0.4 + (b + 2*t_m*math.sqrt(1+m**2) + 0.4 + 2*m*(h+t_m+0.2)))/2) * (h+t_m+0.2) * panjang
        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": max(0, (vol_galian-vol_beton)*0.45),
            "berat_besi": (b + 2*(h*math.sqrt(1+m**2))) * ((panjang*100/jarak)+1) * lapis * (0.006165*dia**2) * 1.2 * (1+waste/100),
            "luas_bekisting": (2 * sisi_miring * panjang) * 2, "vol_bongkaran": vol_beton if is_rehab else 0
        }

    # 3.2 SALURAN BATU
    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        vol_batu = ((((l_atas+l_bawah)/2)*h)*2 + (b*t_lantai)) * panjang
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu, "vol_galian": vol_batu*1.25, "vol_timbunan": max(0, (vol_batu*1.25 - vol_batu)*0.35),
            "luas_plester": ((2*h*math.sqrt(1+m**2))+b)*panjang, "luas_siaran": (2*l_atas)*panjang, "vol_bongkaran": vol_batu if is_rehab else 0
        }

    # 3.3 BOX CULVERT
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        if w<=0 or h<=0: return {"vol_beton": 0, "t_rekom": 0, "rho_data": {"status": "DATA 0"}}
        t_m = t_cm / 100
        Mu = (1/10) * ((18*1.5)+10) * ((w+t_m)**2)
        d_eff = (t_cm*10) - 40 - (dia/2)
        t_rekom = max((Mu/(0.85*2000))**0.5 * 100, (w+t_m)/12*100, 15.0)
        rho_act = ((1000/jarak)*(0.25*math.pi*dia**2)*2) / (1000*d_eff)
        status = "AMAN" if (1.4/fy) <= rho_act <= 0.025 else ("KURANG" if rho_act < 1.4/fy else "BOROS")
        vol_beton = ((w+2*t_m)*(h+2*t_m)*p) - (w*h*p)
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": rho_act, "min": 1.4/fy, "max": 0.025, "status": status},
            "vol_beton": vol_beton, "vol_galian": vol_beton/0.2, "vol_timbunan": vol_beton/0.5,
            "berat_besi": 2*((w+2*t_m)+(h+2*t_m))*2 * ((p*100/jarak)+1) * (0.006165*dia**2) * 1.2,
            "luas_bekisting": (2*w+2*h)*p, "vol_bongkaran": vol_beton if is_rehab else 0
        }

    # 3.4 TERJUNAN USBR + MODE HEMAT
    @staticmethod
    def hitung_terjunan_usbr(Q, H_total, H_step, B, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab):
        if H_step <= 0: H_step = 0.1
        if B <= 0: B = 1.0
        if Q <= 0: Q = 0.1 
        g = 9.81
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps 
        q = Q / B
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1)
        
        tipe_usbr = "Unknown"
        k_length = 0
        if Fr1 < 1.7: tipe_usbr, k_length = "Aliran Undular", 4.0
        elif Fr1 < 2.5: tipe_usbr, k_length = "USBR Tipe I", 5.0
        elif Fr1 <= 4.5: tipe_usbr, k_length = "USBR Tipe IV", 6.0 
        else:
            if V1 < 18.0: tipe_usbr, k_length = "USBR Tipe III", 2.7 
            else: tipe_usbr, k_length = "USBR Tipe II", 4.3
        
        L_kolam_standard = k_length * y2
        L_drop = 4.30 * H_real * ((q**2 / (g * H_real**3))**0.27)
        
        is_hemat_active = mode_hemat and (H_real <= 1.2)
        L_kolam_inter = 0.5 if is_hemat_active else L_kolam_standard
        tipe_desain = "Mode Hemat (Kolam Hilir Saja)" if is_hemat_active else "Standard (Full USBR)"
        L_kolam_final = L_kolam_standard 
        
        jml_inter = max(0, n_steps - 1)
        L_total_structure_linear = (jml_inter * (L_drop + L_kolam_inter)) + (1 * (L_drop + L_kolam_final))
        
        gamma_c, gamma_w = 24, 9.81
        L_final_segment = L_drop + L_kolam_final
        W_beton = L_final_segment * B * t_lantai * gamma_c
        W_air = 0.5 * (y1 + y2) * L_final_segment * B * gamma_w
        Total_Berat = W_beton + W_air
        head_hulu = y2 + (0.5 * H_real)
        Uplift_Force = 0.5 * (head_hulu + y2) * L_final_segment * B * gamma_w
        SF_uplift = Total_Berat / Uplift_Force if Uplift_Force > 0 else 99
        Tekanan_Netto = (Total_Berat - Uplift_Force) / (B * L_final_segment)
        if Tekanan_Netto < 0: Tekanan_Netto = 0
        
        status_uplift = "AMAN" if SF_uplift >= 1.5 else "⚠️ BAHAYA (Mengapung)"
        status_tanah = "AMAN" if Tekanan_Netto <= qa_tanah else "⚠️ BAHAYA (Amblas)"
        
        h_dinding = y2 + 0.6 
        vol_lantai = L_total_structure_linear * B * t_lantai
        vol_mercu = n_steps * (B * H_real * 0.4) 
        vol_dinding = 2 * (L_total_structure_linear * h_dinding * t_dinding)
        vol_beton_total = vol_lantai + vol_mercu + vol_dinding
        
        ratio_besi = 120.0
        if SF_uplift < 1.5: ratio_besi += 10 
        if "USBR Tipe III" in tipe_usbr: ratio_besi += 15
        
        return {
            "info_struktur": f"{tipe_usbr} ({n_steps} Trap) - {tipe_desain}",
            "detail_usbr": {"Fr": Fr1, "y1": y1, "y2": y2, "L_kolam_final": L_kolam_final, "L_total": L_total_structure_linear},
            "stabilitas": {"sf_uplift": SF_uplift, "status_uplift": status_uplift, "sigma_tanah": Tekanan_Netto, "status_tanah": status_tanah},
            "vol_beton": vol_beton_total, "vol_batu": 0, "vol_galian": vol_beton_total * 1.3, 
            "vol_timbunan": vol_beton_total * 0.3, "berat_besi": vol_beton_total * ratio_besi, 
            "luas_bekisting": (2 * L_total_structure_linear * h_dinding) + (n_steps*B*H_real),
            "luas_plester": (2 * L_total_structure_linear * h_dinding), "luas_siaran": 0,
            "vol_bongkaran": vol_beton_total if is_rehab else 0
        }

# --- 4. SIDEBAR (AHSP & INPUT HARGA) ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button("💾 Save", json_str, "rab_proyek.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open", type=["json"])
    if uploaded_file:
        try: st.session_state['data_proyek'] = json.load(uploaded_file); st.success("Loaded!")
        except: st.error("Error")
            
    st.markdown("---")
    st.header("💰 Harga Satuan (Bengkulu)")
    st.caption("Referensi: Harga Pasar Prov. Bengkulu (Estimasi 2024/2025)")
    
    with st.expander("1. Upah Tenaga Kerja", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", value=115000.0)
        u_tukang = st.number_input("Tukang (OH)", value=140000.0) # Tukang Batu/Kayu
        u_mandor = st.number_input("Mandor (OH)", value=165000.0)
        overhead = st.number_input("Overhead & Profit (%)", value=15.0) # SDA biasanya 10-15%
        
    with st.expander("2. Bahan Bangunan", expanded=False):
        p_semen = st.number_input("Semen PC (kg)", value=1650.0) # ~82.500 per sak
        p_pasir = st.number_input("Pasir Pasang/Beton (m3)", value=215000.0)
        p_batu = st.number_input("Batu Kali (m3)", value=265000.0)
        p_split = st.number_input("Kerikil/Split (m3)", value=325000.0)
        p_besi = st.number_input("Besi Beton (kg)", value=15500.0)
        p_kawat = st.number_input("Kawat Beton (kg)", value=22000.0)
        p_kayu = st.number_input("Kayu Kls III (m3)", value=2850000.0)
        p_paku = st.number_input("Paku (kg)", value=20000.0)

    # Dictionary Harga untuk AHSP Engine
    prices_bengkulu = {
        'u_pekerja': u_pekerja, 'u_tukang': u_tukang, 'u_mandor': u_mandor,
        'p_semen': p_semen, 'p_pasir': p_pasir, 'p_batu': p_batu,
        'p_split': p_split, 'p_besi': p_besi, 'p_kayu': p_kayu,
        'p_paku': p_paku, 'p_kawat': p_kawat
    }

    # Hitung Harga Satuan Pekerjaan (HSP) Final menggunakan AHSP Engine
    hsp_galian = AHSP_Engine.hitung_harga_satuan("T.06.a.1", prices_bengkulu, overhead)
    hsp_timbunan = AHSP_Engine.hitung_harga_satuan("T.14.a", prices_bengkulu, overhead)
    hsp_bongkaran = AHSP_Engine.hitung_harga_satuan("T.15.a", prices_bengkulu, overhead)
    hsp_beton = AHSP_Engine.hitung_harga_satuan("B.05.a", prices_bengkulu, overhead)
    hsp_besi = AHSP_Engine.hitung_harga_satuan("B.17.a", prices_bengkulu, overhead)
    hsp_bekisting = AHSP_Engine.hitung_harga_satuan("B.20.a", prices_bengkulu, overhead)
    hsp_batu = AHSP_Engine.hitung_harga_satuan("P.01.a", prices_bengkulu, overhead)
    hsp_plester = AHSP_Engine.hitung_harga_satuan("P.04.e", prices_bengkulu, overhead)
    hsp_siaran = AHSP_Engine.hitung_harga_satuan("P.05.a", prices_bengkulu, overhead)

# --- 5. MAIN UI ---
st.title("🏗️ Pro QS V.12: AHSP SDA Bengkulu")
st.caption("Standar: SE Menteri PUPR Bidang SDA | Harga: Provinsi Bengkulu")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Input", "📋 List", "📊 RAB Detail", "📑 Analisa Harga (Formulir)"])

# === TAB 1: INPUT (TETAP SAMA 100%) ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Terjunan Km 2+100")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehab?", help="Hitung bongkaran otomatis")
        
    with col2:
        st.subheader("2. Spesifikasi")
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0)
            if tipe_kons == "Beton Bertulang":
                h = st.number_input("Tinggi H (m)", value=0.8)
                b = st.number_input("Lebar B (m)", value=0.6)
                m = st.number_input("Talud m", value=0.0)
                t_cm = st.number_input("Tebal (cm)", value=15.0)
                dia = st.number_input("Dia Besi (mm)", value=10.0)
                jarak = st.number_input("Jarak (cm)", value=15.0)
                calc = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 5, 20, 280, is_rehab)
            else:
                h = st.number_input("Tinggi H", value=0.8)
                l_atas = st.number_input("L. Atas", value=0.3)
                l_bawah = st.number_input("L. Bawah", value=0.4)
                t_lantai = st.number_input("T. Lantai", value=0.2)
                calc = Calculator.hitung_pasangan_batu(h, 0.5, 0.2, panjang, l_atas, l_bawah, t_lantai, is_rehab)

        else:
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box", "Terjunan USBR (Integrated)"])
            if "Gorong" in jenis_bang:
                w = st.number_input("Lebar (m)", value=1.0)
                h_box = st.number_input("Tinggi (m)", value=1.0)
                p_box = st.number_input("Panjang (m)", value=6.0)
                t_cm = st.number_input("Tebal Beton (cm)", value=20.0)
                dia = st.number_input("Dia. Besi (mm)", value=13.0)
                jarak = st.number_input("Jarak (cm)", value=15.0)
                calc = Calculator.hitung_gorong_box_struktur(w, h_box, p_box, t_cm, dia, jarak, 25, 400, is_rehab)
            else: 
                mode_hemat = st.checkbox("✅ Aktifkan Mode Hemat?", value=True)
                c_h1, c_h2, c_h3 = st.columns(3)
                Q_debit = c_h1.number_input("Debit Q (m3/s)", value=1.5)
                H_total = c_h2.number_input("Total Tinggi (m)", value=3.0)
                H_step = c_h3.number_input("Max Tinggi/Trap (m)", value=1.5)
                c_d1, c_d2 = st.columns(2)
                B_terjun = c_d1.number_input("Lebar Saluran B (m)", value=1.5)
                qa_tanah = c_d2.number_input("Daya Dukung Tanah (kN/m2)", value=150.0)
                t_lantai = st.number_input("Tebal Lantai (m)", value=0.25)
                t_dinding = st.number_input("Tebal Dinding (m)", value=0.25)
                calc = Calculator.hitung_terjunan_usbr(Q_debit, H_total, H_step, B_terjun, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab)
                st.divider()
                st.write(f"**Analisa: {calc['info_struktur']}**")

    if st.button("Simpan Item", type="primary"):
        if not nama_item: st.warning("Isi Nama!")
        else:
            tipe_final = jenis_bang if kategori != "Saluran (Linear)" else ("Saluran Beton" if tipe_kons == "Beton Bertulang" else "Saluran Batu")
            if is_rehab: nama_item += " (REHAB)"
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": 0, "vol": calc}
            if kategori == "Saluran (Linear)": item_data["panjang"] = panjang
            st.session_state['data_proyek'].append(item_data)
            st.success("Tersimpan!")

# === TAB 2 & 3 (LIST & RAB DETAIL) ===
with tab2:
    if st.session_state['data_proyek']:
        st.dataframe(pd.DataFrame(st.session_state['data_proyek'])[["nama", "tipe"]])
        if st.button("Hapus Semua"): st.session_state['data_proyek'] = []; st.rerun()

with tab3:
    st.header("📊 Detail Engineering Estimate (EE)")
    if st.session_state['data_proyek']:
        excel_rows = []
        grand_total = 0
        
        map_pekerjaan = {
            "vol_bongkaran": ("Bongkaran Pasangan Eksisting", "m3", "T.15.a", hsp_bongkaran),
            "vol_galian": ("Galian Tanah Biasa", "m3", "T.06.a.1", hsp_galian),
            "vol_timbunan": ("Timbunan Kembali Dipadatkan", "m3", "T.14.a", hsp_timbunan),
            "vol_beton": ("Beton K-225 (Struktur)", "m3", "B.05.a", hsp_beton),
            "vol_batu": ("Pasangan Batu Kali 1:4", "m3", "P.01.a", hsp_batu),
            "berat_besi": ("Pembesian Ulir/Polos", "kg", "B.17.a", hsp_besi),
            "luas_bekisting": ("Pasang Bekisting", "m2", "B.20.a", hsp_bekisting),
            "luas_plester": ("Plesteran 1:3 + Acian", "m2", "P.04.e", hsp_plester),
            "luas_siaran": ("Siaran 1:2", "m2", "P.05.a", hsp_siaran),
        }

        for i, item in enumerate(st.session_state['data_proyek']):
            nama = item['nama']
            vol_data = item['vol']
            
            with st.expander(f"📍 {i+1}. {nama} ({item['tipe']})", expanded=True):
                item_rows = []
                for key, val in vol_data.items():
                    if key in map_pekerjaan and val > 0.001:
                        uraian, sat, kode_ahsp, harga = map_pekerjaan[key]
                        jumlah = val * harga
                        item_rows.append({"Kode": kode_ahsp, "Uraian": uraian, "Vol": val, "Sat": sat, "H.Sat": harga, "Total": jumlah})
                        excel_rows.append({"No": i+1, "Item": nama, "Kode": kode_ahsp, "Uraian": uraian, "Vol": val, "Sat": sat, "H.Sat": harga, "Total": jumlah})
                
                df_item = pd.DataFrame(item_rows)
                if not df_item.empty:
                    subtotal = df_item["Total"].sum()
                    grand_total += subtotal
                    st.dataframe(df_item.style.format({"Vol": "{:.3f}", "H.Sat": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
                    st.markdown(f"**Subtotal: Rp {subtotal:,.0f}**")

        st.divider()
        ppn = grand_total * 0.11 # Tarif PPN 11%
        st.success(f"### Total Akhir: Rp {grand_total + ppn:,.0f} (Termasuk PPN 11%)")
        
        def generate_excel():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(excel_rows).to_excel(writer, index=False, sheet_name='RAB Detail')
            return output.getvalue()
        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V12_Bengkulu.xlsx")

# === TAB 4: FORMULIR ANALISA HARGA (FITUR BARU) ===
with tab4:
    st.header("📑 Rincian Analisa Harga Satuan (AHSP)")
    st.caption("Format Standar Formulir Analisa Harga Satuan - Bidang SDA")
    
    # List Kode AHSP yang digunakan
    list_kode = [
        "T.06.a.1", "T.14.a", "T.15.a", "P.01.a", 
        "P.04.e", "P.05.a", "B.05.a", "B.17.a", "B.20.a"
    ]
    
    selected_ahsp = st.selectbox("Pilih Analisa:", list_kode)
    
    # Get Detail
    detail_ahsp = AHSP_Engine.get_analisa_detail(selected_ahsp, prices_bengkulu)
    
    st.subheader(f"Analisa: {detail_ahsp['uraian']}")
    st.text(f"Kode: {detail_ahsp['kode']}")
    
    # Buat Tampilan Formulir Standar
    data_form = []
    total_upah = 0
    total_bahan = 0
    
    # Proses Data
    for uraian, koef, harga in detail_ahsp['items']:
        jumlah = koef * harga
        kategori_item = "Upah" if "Pekerja" in uraian or "Tukang" in uraian or "Mandor" in uraian else "Bahan"
        
        if kategori_item == "Upah": total_upah += jumlah
        else: total_bahan += jumlah
            
        data_form.append({
            "Uraian": uraian,
            "Koefisien": koef,
            "Satuan": "OH" if kategori_item == "Upah" else ("kg" if "Semen" in uraian or "Besi" in uraian else "m3"),
            "Harga Satuan (Rp)": harga,
            "Jumlah Harga (Rp)": jumlah,
            "Kategori": kategori_item
        })
    
    df_form = pd.DataFrame(data_form)
    
    # Tampilkan Tabel
    st.table(df_form.style.format({
        "Koefisien": "{:.4f}", 
        "Harga Satuan (Rp)": "{:,.2f}", 
        "Jumlah Harga (Rp)": "{:,.2f}"
    }))
    
    # Rekap Bawah
    jum_dasar = total_upah + total_bahan
    ovr_val = jum_dasar * (overhead/100)
    jum_final = jum_dasar + ovr_val
    
    c_f1, c_f2 = st.columns([3, 1])
    with c_f2:
        st.markdown(f"""
        | Komponen | Nilai (Rp) |
        | :--- | :--- |
        | **A. Tenaga** | **{total_upah:,.2f}** |
        | **B. Bahan** | **{total_bahan:,.2f}** |
        | **C. Jumlah (A+B)** | **{jum_dasar:,.2f}** |
        | **D. Overhead ({overhead}%)** | **{ovr_val:,.2f}** |
        | **E. Harga Satuan** | **{jum_final:,.2f}** |
        """)
