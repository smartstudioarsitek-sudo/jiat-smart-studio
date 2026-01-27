import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS V.17: Real Engineering + Admin", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []
if 'data_smkk' not in st.session_state:
    st.session_state['data_smkk'] = {
        "1. Penyiapan Dokumen RKK": 0, "2. Sosialisasi & Promosi K3": 0, "3. Alat Pelindung Kerja & Diri": 0,
        "4. Asuransi & Perizinan": 0, "5. Personel K3": 0, "6. Fasilitas Kesehatan": 0,
        "7. Rambu-Rambu": 0, "8. Konsultasi Ahli K3": 0, "9. Pengendalian Risiko Lain": 0
    }

# --- 2. LIBRARY AHSP (ADMINISTRASI - V.16) ---
class AHSP_Engine:
    """
    Engine AHSP Bidang SDA - SE Dirjen Bina Konstruksi No. 182/SE/Dk/2025.
    Fitur: Koefisien Dinamis (Galian), SMKK At Cost, Format Blangko PUPR.
    """
    @staticmethod
    def get_koefisien_galian_dinamis(volume, kedalaman):
        k_pekerja, k_mandor, kategori = 0.750, 0.025, "Basis (Manual)"
        if kedalaman <= 1.0:
            if volume <= 200: pass 
            elif volume <= 2000: k_pekerja, k_mandor, kategori = 0.563, 0.0563, "Efisiensi Menengah"
            else: k_pekerja, k_mandor, kategori = 0.400, 0.0400, "Efisiensi Besar"
        elif kedalaman <= 2.0:
            if volume <= 200: k_pekerja, k_mandor, kategori = 0.900, 0.090, "Kesulitan Tinggi"
            else: k_pekerja, k_mandor, kategori = 0.675, 0.0675, "Kesulitan Menengah"
        else:
             k_pekerja, k_mandor, kategori = 1.200, 0.120, "Galian Dalam (>2m)"
        return k_pekerja, k_mandor, kategori

    @staticmethod
    def get_analisa_detail(hsp_code, prices, params=None):
        u_pekerja = prices['u_pekerja']; u_tukang = prices['u_tukang']; u_mandor = prices['u_mandor']
        
        # --- A. PEKERJAAN TANAH ---
        if hsp_code == "T.06.a.1": 
            vol_total = params.get('vol_total', 100) if params else 100
            depth = params.get('depth', 1.0) if params else 1.0
            kp, km, cat = AHSP_Engine.get_koefisien_galian_dinamis(vol_total, depth)
            return {"kode": f"T.06.a.1 ({cat})", "uraian": f"1 m3 Galian Tanah ({cat})", "items": [("Pekerja", kp, u_pekerja), ("Mandor", km, u_mandor)]}
        elif hsp_code == "T.14.a": return {"kode": "T.14.a", "uraian": "1 m3 Timbunan Kembali", "items": [("Pekerja", 0.330, u_pekerja), ("Mandor", 0.010, u_mandor)]}
        elif hsp_code == "T.15.a": return {"kode": "T.15.a", "uraian": "1 m3 Bongkaran Pasangan", "items": [("Pekerja", 2.000, u_pekerja), ("Mandor", 0.100, u_mandor)]}
        # --- B. LANGSIRAN ---
        elif hsp_code == "T.15.L": 
            jarak = params.get('jarak', 0) if params else 0
            koef_pekerja = 0.24 + (0.0036 * jarak) if jarak >= 10 else 0
            return {"kode": "T.15.L", "uraian": f"1 m3 Langsiran Manual ({jarak}m)", "items": [("Pekerja", koef_pekerja, u_pekerja), ("Mandor", koef_pekerja*0.05, u_mandor)]}
        # --- C. PASANGAN & BETON ---
        elif hsp_code == "P.01.a": return {"kode": "P.01.a", "uraian": "1 m3 Pasangan Batu 1:4", "items": [("Pekerja", 1.2, u_pekerja), ("Tukang Batu", 0.6, u_tukang), ("Mandor", 0.06, u_mandor), ("Batu Kali", 1.2, prices['p_batu']), ("Semen", 163, prices['p_semen']), ("Pasir", 0.52, prices['p_pasir'])]}
        elif hsp_code == "P.04.e": return {"kode": "P.04.e", "uraian": "1 m2 Plesteran 1:3", "items": [("Pekerja", 0.3, u_pekerja), ("Tukang Batu", 0.15, u_tukang), ("Mandor", 0.015, u_mandor), ("Semen", 7.776, prices['p_semen']), ("Pasir", 0.024, prices['p_pasir'])]}
        elif hsp_code == "P.05.a": return {"kode": "P.05.a", "uraian": "1 m2 Siaran 1:2", "items": [("Pekerja", 0.15, u_pekerja), ("Tukang Batu", 0.075, u_tukang), ("Mandor", 0.008, u_mandor), ("Semen", 6.0, prices['p_semen']), ("Pasir", 0.01, prices['p_pasir'])]}
        elif hsp_code == "B.05.a": return {"kode": "B.05.a", "uraian": "1 m3 Beton K-225", "items": [("Pekerja", 1.65, u_pekerja), ("Tukang Batu", 0.275, u_tukang), ("Mandor", 0.083, u_mandor), ("Semen", 371, prices['p_semen']), ("Pasir Beton", 0.499, prices['p_pasir']), ("Split", 0.776, prices['p_split'])]}
        elif hsp_code == "B.17.a": return {"kode": "B.17.a", "uraian": "1 kg Pembesian", "items": [("Pekerja", 0.007, u_pekerja), ("Tukang Besi", 0.007, u_tukang), ("Mandor", 0.0004, u_mandor), ("Besi Beton", 1.05, prices['p_besi']), ("Kawat Beton", 0.015, prices['p_kawat'])]}
        elif hsp_code == "B.20.a": return {"kode": "B.20.a", "uraian": "1 m2 Bekisting", "items": [("Pekerja", 0.52, u_pekerja), ("Tukang Kayu", 0.26, u_tukang), ("Mandor", 0.026, u_mandor), ("Kayu Kls III", 0.045, prices['p_kayu']), ("Paku", 0.3, prices['p_paku']), ("Minyak Bekisting", 0.1, 25000)]}
        return {"kode": "N/A", "uraian": "Item Tidak Ditemukan", "items": []}

    @staticmethod
    def hitung_harga_satuan(hsp_code, prices, overhead_pct, params=None):
        analisa = AHSP_Engine.get_analisa_detail(hsp_code, prices, params)
        total_dasar = sum([item[1] * item[2] for item in analisa['items']])
        return total_dasar * (1 + overhead_pct/100)

# --- 3. LIBRARY CALCULATOR (ENGINEERING - REAL LOGIC RESTORED V.15) ---
class Calculator:
    # 3.1 SALURAN BETON (Safety Check Aktif)
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
        lebar_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.6 
        tinggi_galian = h + t_m + 0.1
        vol_galian = lebar_galian * tinggi_galian * panjang
        berat_besi = (b + 2*(h*math.sqrt(1+m**2))) * ((panjang*100/jarak)+1) * lapis * (0.006165*dia**2) * 1.2 * (1+waste/100)
        
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": max(0, (vol_galian-vol_beton)*0.45),
            "berat_besi": berat_besi, "luas_bekisting": (2 * sisi_miring * panjang) * 2, "vol_bongkaran": vol_beton if is_rehab else 0,
            "material_raw": {"semen_m3": vol_beton*371/1250, "pasir": vol_beton*0.5, "batu_split": vol_beton*0.78},
            "params_galian": {"depth": tinggi_galian, "vol_total": vol_galian}
        }

    # 3.2 SALURAN BATU
    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        vol_batu = ((((l_atas+l_bawah)/2)*h)*2 + (b*t_lantai)) * panjang
        vol_galian = vol_batu * 1.3
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu, "vol_galian": vol_galian, "vol_timbunan": max(0, (vol_galian-vol_batu)*0.35),
            "luas_plester": ((2*h*math.sqrt(1+m**2))+b)*panjang, "luas_siaran": (2*l_atas)*panjang, "vol_bongkaran": vol_batu if is_rehab else 0,
            "material_raw": {"batu_kali": vol_batu*1.2, "semen_m3": vol_batu*163/1250, "pasir": vol_batu*0.52},
            "params_galian": {"depth": h, "vol_total": vol_galian}
        }

    # 3.3 BOX CULVERT (LOGIC ASLI V.15 DIKEMBALIKAN)
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        if w<=0 or h<=0: return {"vol_beton": 0, "t_rekom": 0, "rho_data": {"status": "DATA 0"}}
        t_m = t_cm / 100
        
        # Real Engineering Check
        Mu = (1/10) * ((18*1.5)+10) * ((w+t_m)**2)
        d_eff = (t_cm*10) - 40 - (dia/2)
        t_rekom = max((Mu/(0.85*2000))**0.5 * 100, (w+t_m)/12*100, 15.0)
        rho_act = ((1000/jarak)*(0.25*math.pi*dia**2)*2) / (1000*d_eff)
        status = "AMAN" if (1.4/fy) <= rho_act <= 0.025 else ("KURANG" if rho_act < 1.4/fy else "BOROS")
        
        vol_beton = ((w+2*t_m)*(h+2*t_m)*p) - (w*h*p)
        vol_galian = vol_beton / 0.2
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": rho_act, "min": 1.4/fy, "max": 0.025, "status": status},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_beton/0.5,
            "berat_besi": 2*((w+2*t_m)+(h+2*t_m))*2 * ((p*100/jarak)+1) * (0.006165*dia**2) * 1.2,
            "luas_bekisting": (2*w+2*h)*p, "vol_bongkaran": vol_beton if is_rehab else 0,
            "material_raw": {"semen_m3": vol_beton*0.3, "pasir": vol_beton*0.5, "batu_split": vol_beton*0.78},
            "params_galian": {"depth": h+t_m, "vol_total": vol_galian}
        }

    # 3.4 TERJUNAN USBR (LOGIC ASLI V.15 DIKEMBALIKAN - NO DUMMY!)
    @staticmethod
    def hitung_terjunan_usbr(Q, H_total, H_step, B, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab):
        if H_step <= 0: H_step = 0.1
        if B <= 0: B = 1.0
        g = 9.81
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps 
        q = (Q if Q>0 else 0.1) / B
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1)
        
        tipe_usbr, k_length = ("USBR I", 5.0) if Fr1 < 2.5 else (("USBR IV", 6.0) if Fr1 <= 4.5 else ("USBR III", 2.7))
        L_drop = 4.30 * H_real * ((q**2 / (g * H_real**3))**0.27)
        L_kolam = k_length * y2
        
        is_hemat = mode_hemat and (H_real <= 1.2)
        L_total = (max(0, n_steps-1) * (L_drop + (0.5 if is_hemat else L_kolam))) + (1 * (L_drop + L_kolam))
        
        # REAL STABILITY CHECK
        gamma_c, gamma_w = 24, 9.81
        L_final = L_drop + L_kolam
        W_beton = L_final * B * t_lantai * gamma_c
        W_air = 0.5 * (y1 + y2) * L_final * B * gamma_w
        Uplift = 0.5 * (y2 + 0.5*H_real + y2) * L_final * B * gamma_w
        
        SF_uplift = (W_beton + W_air) / Uplift if Uplift > 0 else 99
        status_uplift = "AMAN" if SF_uplift >= 1.5 else "⚠️ BAHAYA (Mengapung)"
        Tekanan = (W_beton + W_air - Uplift) / (B * L_final)
        status_tanah = "AMAN" if Tekanan <= qa_tanah else "⚠️ BAHAYA (Amblas)"
        
        h_dinding = y2 + 0.6
        vol_beton = L_total * B * t_lantai + (n_steps * B * H_real * 0.4) + (2 * L_total * h_dinding * t_dinding)
        vol_galian = vol_beton * 1.3
        
        ratio_besi = 120.0 + (10 if SF_uplift < 1.5 else 0)
        
        return {
            "info_struktur": f"{tipe_usbr} ({n_steps} Trap)", "detail_usbr": {"Fr": Fr1, "L_total": L_total},
            "stabilitas": {"sf_uplift": SF_uplift, "status_uplift": status_uplift, "sigma_tanah": Tekanan, "status_tanah": status_tanah},
            "vol_beton": vol_beton, "vol_batu": 0, "vol_galian": vol_galian, "vol_timbunan": vol_beton*0.3,
            "berat_besi": vol_beton*ratio_besi, "luas_bekisting": vol_beton*4, "luas_plester": vol_beton*2, "luas_siaran": 0,
            "material_raw": {"semen_m3": vol_beton*0.3, "pasir": vol_beton*0.5, "batu_split": vol_beton*0.78},
            "vol_bongkaran": vol_beton if is_rehab else 0, "params_galian": {"depth": h_dinding, "vol_total": vol_galian}
        }

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Proyek & Regulasi")
    st.info("Mode: SE 182/2025 (SDA)")
    if st.button("Reset All"): st.session_state['data_proyek'] = []; st.rerun()
    
    st.markdown("---")
    st.header("⚖️ Kebijakan Fiskal")
    ppn_rate = st.number_input("Tarif PPN (%)", 0.0, 15.0, 12.0)
    overhead_pct = st.number_input("Overhead & Profit (%)", 0.0, 15.0, 15.0)
    jarak_langsir = st.slider("Jarak Angkut Manual (m)", 0, 500, 0, step=10)
    
    st.header("💰 Harga Dasar (Bengkulu)")
    with st.expander("Upah & Material", expanded=False):
        u_pekerja = st.number_input("Pekerja", 115000.0); u_tukang = st.number_input("Tukang", 140000.0); u_mandor = st.number_input("Mandor", 165000.0)
        p_semen = st.number_input("Semen (kg)", 1650.0); p_pasir = st.number_input("Pasir (m3)", 215000.0)
        p_batu = st.number_input("Batu Kali (m3)", 265000.0); p_split = st.number_input("Split (m3)", 325000.0)
        p_besi = st.number_input("Besi (kg)", 15500.0); p_kayu = st.number_input("Kayu (m3)", 2850000.0)
        p_kawat = 22000.0; p_paku = 20000.0
    prices = {'u_pekerja':u_pekerja, 'u_tukang':u_tukang, 'u_mandor':u_mandor, 'p_semen':p_semen, 'p_pasir':p_pasir, 'p_batu':p_batu, 'p_split':p_split, 'p_besi':p_besi, 'p_kayu':p_kayu, 'p_kawat':p_kawat, 'p_paku':p_paku}
    def get_hsp(kode, params=None): return AHSP_Engine.hitung_harga_satuan(kode, prices, overhead_pct, params)

# --- MAIN UI ---
st.title("🏗️ Pro QS V.17: Full Compliance (Real Engineering)")
st.caption(f"Legalitas: SE 182/2025 | PPN: {ppn_rate}% | Fitur: Kode Analisa + Hitungan Struktur Asli")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Input Pekerjaan", "🦺 Biaya SMKK", "📊 RAB Detail", "📑 Analisa (Blangko)"])

# === TAB 1: INPUT ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        kategori = st.radio("Kategori", ["Saluran", "Bangunan"], horizontal=True)
        nama_item = st.text_input("Nama Item", "Item Baru")
        is_rehab = st.checkbox("Rehab?")
    with col2:
        if kategori == "Saluran":
            tipe = st.selectbox("Tipe", ["Batu", "Beton"])
            pjg = st.number_input("Panjang (m)", 50.0)
            if tipe == "Batu": calc = Calculator.hitung_pasangan_batu(0.8, 0.6, 0.2, pjg, 0.3, 0.4, 0.2, is_rehab)
            else:
                h = st.number_input("Tinggi H", 0.8); b = st.number_input("Lebar B", 0.6)
                t_cm = st.number_input("Tebal (cm)", 15.0); dia = st.number_input("Dia Besi", 10.0); jarak = st.number_input("Jarak", 15.0)
                fc = st.number_input("fc (MPa)", 20.0); fy = st.number_input("fy (MPa)", 280.0)
                calc = Calculator.hitung_beton_struktur(h, b, 0, pjg, t_cm, dia, jarak, 2, 5, fc, fy, is_rehab)
                st.caption(f"Status Struktur: {calc.get('rho_data', {}).get('status', '-')}")
                if calc.get('t_rekom', 0) > t_cm: st.error(f"Tebal kurang! Rekomendasi: {calc['t_rekom']:.1f} cm")
        else:
            tipe = st.selectbox("Tipe", ["Terjunan USBR", "Box Culvert"])
            if tipe == "Terjunan USBR":
                Q_debit = st.number_input("Debit Q", 1.5); H_total = st.number_input("Total H", 3.0); H_step = st.number_input("H/Trap", 1.5)
                B_terjun = st.number_input("Lebar", 1.5); qa = st.number_input("Daya Dukung", 150.0)
                mode_hemat = st.checkbox("Mode Hemat", True)
                calc = Calculator.hitung_terjunan_usbr(Q_debit, H_total, H_step, B_terjun, 0.25, 0.25, qa, mode_hemat, is_rehab)
                st.write(f"**Info Hidrolis:** {calc['info_struktur']}")
                st.write(f"**Cek Stabilitas:** Uplift SF={calc['stabilitas']['sf_uplift']:.2f} ({calc['stabilitas']['status_uplift']})")
            else:
                calc = Calculator.hitung_gorong_box_struktur(1,1,6,20,13,15,25,400,is_rehab)
                st.caption(f"Status Besi: {calc['rho_data']['status']}")

    if st.button("Simpan Item", type="primary"):
        st.session_state['data_proyek'].append({"nama": nama_item, "tipe": "Item", "vol": calc})
        st.success("Disimpan!")

# === TAB 2: SMKK ===
with tab2:
    cols = st.columns(3)
    idx = 0
    for k, v in st.session_state['data_smkk'].items():
        with cols[idx % 3]:
            new_val = st.number_input(f"{k}", value=float(v), step=100000.0)
            st.session_state['data_smkk'][k] = new_val
        idx += 1
    total_smkk = sum(st.session_state['data_smkk'].values())
    st.metric("Total Biaya SMKK", f"Rp {total_smkk:,.0f}")

# === TAB 3: RAB DETAIL ===
with tab3:
    if st.session_state['data_proyek']:
        excel_rows = []
        grand_total_fisik = 0
        map_job = {
            "vol_galian": ("Galian Tanah", "m3", "T.06.a.1"), "vol_beton": ("Beton K-225", "m3", "B.05.a"),
            "vol_batu": ("Pasangan Batu", "m3", "P.01.a"), "berat_besi": ("Pembesian", "kg", "B.17.a"),
            "luas_bekisting": ("Bekisting", "m2", "B.20.a"), "vol_bongkaran": ("Bongkaran", "m3", "T.15.a"),
            "luas_plester": ("Plesteran 1:3", "m2", "P.04.e"), "luas_siaran": ("Siaran 1:2", "m2", "P.05.a")
        }
        used_ahsp_codes = set()

        st.subheader("I. Daftar Kuantitas dan Harga (BoQ)")
        for i, item in enumerate(st.session_state['data_proyek']):
            vol_data = item['vol']
            params_galian = vol_data.get('params_galian', {})
            with st.expander(f"{i+1}. {item['nama']}"):
                item_rows = []
                for key, val in vol_data.items():
                    if key in map_job and val > 0.001:
                        desc, sat, kode_base = map_job[key]
                        detail = AHSP_Engine.get_analisa_detail(kode_base, prices, params=params_galian if kode_base=="T.06.a.1" else None)
                        used_ahsp_codes.add((kode_base, json.dumps(params_galian if kode_base=="T.06.a.1" else {}))) 
                        h_sat = AHSP_Engine.hitung_harga_satuan(kode_base, prices, overhead_pct, params=params_galian if kode_base=="T.06.a.1" else None)
                        tot = val * h_sat
                        grand_total_fisik += tot
                        row = {"Kode": detail['kode'], "Uraian": desc, "Volume": val, "Satuan": sat, "H.Satuan": h_sat, "Jumlah Harga": tot}
                        item_rows.append(row); excel_rows.append(row)
                if item_rows: st.dataframe(pd.DataFrame(item_rows).style.format({"Volume": "{:.3f}", "H.Satuan": "{:,.0f}", "Jumlah Harga": "{:,.0f}"}), use_container_width=True)

        if jarak_langsir > 0:
            total_mat_vol = sum([i['vol'].get('material_raw', {}).get('batu_kali', 0) + i['vol'].get('material_raw', {}).get('pasir', 0) + i['vol'].get('material_raw', {}).get('batu_split', 0) + i['vol'].get('material_raw', {}).get('semen_m3', 0) for i in st.session_state['data_proyek']])
            if total_mat_vol > 0:
                hsp_L = get_hsp("T.15.L", params={'jarak': jarak_langsir})
                tot_L = total_mat_vol * hsp_L
                grand_total_fisik += tot_L
                st.info(f"Biaya Langsiran ({jarak_langsir}m): Rp {tot_L:,.0f}")
                excel_rows.append({"Kode": "T.15.L", "Uraian": f"Langsiran {jarak_langsir}m", "Volume": total_mat_vol, "Satuan": "m3", "H.Satuan": hsp_L, "Jumlah Harga": tot_L})
                used_ahsp_codes.add(("T.15.L", json.dumps({'jarak': jarak_langsir})))

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c2:
            st.markdown(f"**Total Fisik: Rp {grand_total_fisik:,.0f}**")
            st.markdown(f"**Total SMKK: Rp {total_smkk:,.0f}**")
            tot_proyek = (grand_total_fisik + total_smkk) * (1 + ppn_rate/100)
            st.success(f"### GRAND TOTAL: Rp {tot_proyek:,.0f}")

        def generate_excel():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: pd.DataFrame(excel_rows).to_excel(writer, index=False)
            return output.getvalue()
        st.download_button("📥 Download Excel RAB", generate_excel(), "RAB_V17.xlsx")

# === TAB 4: ANALISA ===
with tab4:
    st.header("📑 Formulir Standar Analisa Harga Satuan")
    if 'used_ahsp_codes' in locals() and used_ahsp_codes:
        list_pilihan = []
        map_pilihan = {}
        for k_base, s_params in used_ahsp_codes:
            params = json.loads(s_params)
            det = AHSP_Engine.get_analisa_detail(k_base, prices, params)
            label = f"{det['kode']} - {det['uraian']}"
            list_pilihan.append(label)
            map_pilihan[label] = (k_base, params)
        
        selected_label = st.selectbox("Pilih Analisa:", sorted(list_pilihan))
        if selected_label:
            kode_base, params = map_pilihan[selected_label]
            detail = AHSP_Engine.get_analisa_detail(kode_base, prices, params)
            
            st.markdown(f"### Analisa: {detail['uraian']}")
            data_form = []
            tot_upah = 0; tot_bahan = 0
            for uraian, koef, harga in detail['items']:
                jum = koef * harga
                kat = "Upah" if any(x in uraian for x in ["Pekerja", "Tukang", "Mandor"]) else "Bahan"
                if kat == "Upah": tot_upah += jum
                else: tot_bahan += jum
                data_form.append({"Uraian": uraian, "Koefisien": koef, "Satuan": "OH" if kat=="Upah" else "Bh/Kg/m3", "Harga Satuan (Rp)": harga, "Jumlah Harga (Rp)": jum, "Kategori": kat})
            
            st.table(pd.DataFrame(data_form).style.format({"Koefisien": "{:.4f}", "Harga Satuan (Rp)": "{:,.2f}", "Jumlah Harga (Rp)": "{:,.2f}"}))
            jum_d = tot_upah + tot_bahan
            ovr = jum_d * (overhead_pct/100)
            st.markdown(f"**Total Harga Satuan: Rp {jum_d + ovr:,.2f}** (Termasuk Overhead {overhead_pct}%)")
    else:
        st.info("Input item di Tab 1 dulu.")
