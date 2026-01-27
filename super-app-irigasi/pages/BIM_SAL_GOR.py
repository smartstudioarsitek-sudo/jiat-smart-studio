import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS V.14: Ultimate (Full Feature)", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY AHSP & HARGA (DATABASE BENGKULU + LANGSIRAN) ---
class AHSP_Engine:
    
    @staticmethod
    def get_analisa_detail(hsp_code, prices, params=None):
        u_pekerja = prices['u_pekerja']
        u_tukang = prices['u_tukang']
        u_mandor = prices['u_mandor']
        
        # --- A. PEKERJAAN TANAH ---
        if hsp_code == "T.06.a.1": 
            return {"kode": "T.06.a.1", "uraian": "1 m3 Galian Tanah Biasa", "items": [("Pekerja", 0.750, u_pekerja), ("Mandor", 0.025, u_mandor)]}
        elif hsp_code == "T.14.a": 
            return {"kode": "T.14.a", "uraian": "1 m3 Timbunan Kembali", "items": [("Pekerja", 0.330, u_pekerja), ("Mandor", 0.010, u_mandor)]}
        elif hsp_code == "T.15.a": # Bongkaran
             return {"kode": "T.15.a", "uraian": "1 m3 Bongkaran Pasangan", "items": [("Pekerja", 2.000, u_pekerja), ("Mandor", 0.100, u_mandor)]}

        # --- B. LANGSIRAN (FITUR V.13) ---
        elif hsp_code == "T.15.L": 
            jarak = params.get('jarak', 0) if params else 0
            # Rumus Interpolasi AHSP SDA: Base 0.24 + (0.0036 * Jarak)
            koef_pekerja = 0.24 + (0.0036 * jarak)
            if jarak < 10: koef_pekerja = 0 
            return {
                "kode": f"T.15.L ({jarak}m)", 
                "uraian": f"1 m3 Langsiran Material sejauh {jarak}m", 
                "items": [("Pekerja", koef_pekerja, u_pekerja), ("Mandor", koef_pekerja*0.05, u_mandor)]
            }

        # --- C. PEKERJAAN PASANGAN ---
        elif hsp_code == "P.01.a": 
            return {"kode": "P.01.a", "uraian": "1 m3 Pasangan Batu 1:4", "items": [
                ("Pekerja", 1.2, u_pekerja), ("Tukang", 0.6, u_tukang), ("Mandor", 0.06, u_mandor),
                ("Batu Kali", 1.2, prices['p_batu']), ("Semen", 163, prices['p_semen']), ("Pasir", 0.52, prices['p_pasir'])
            ]}
        elif hsp_code == "P.04.e": 
            return {"kode": "P.04.e", "uraian": "1 m2 Plesteran 1:3", "items": [
                ("Pekerja", 0.3, u_pekerja), ("Tukang", 0.15, u_tukang), ("Mandor", 0.015, u_mandor),
                ("Semen", 7.776, prices['p_semen']), ("Pasir", 0.024, prices['p_pasir'])
            ]}
        elif hsp_code == "P.05.a": 
            return {"kode": "P.05.a", "uraian": "1 m2 Siaran 1:2", "items": [
                ("Pekerja", 0.15, u_pekerja), ("Tukang", 0.075, u_tukang), ("Mandor", 0.008, u_mandor),
                ("Semen", 6.0, prices['p_semen']), ("Pasir", 0.01, prices['p_pasir'])
            ]}

        # --- D. PEKERJAAN BETON ---
        elif hsp_code == "B.05.a": 
            return {"kode": "B.05.a", "uraian": "1 m3 Beton K-225", "items": [
                ("Pekerja", 1.65, u_pekerja), ("Tukang", 0.275, u_tukang), ("Mandor", 0.083, u_mandor),
                ("Semen", 371, prices['p_semen']), ("Pasir", 0.499, prices['p_pasir']), ("Split", 0.776, prices['p_split'])
            ]}
        elif hsp_code == "B.17.a": 
            return {"kode": "B.17.a", "uraian": "1 kg Pembesian", "items": [
                ("Pekerja", 0.007, u_pekerja), ("Tukang", 0.007, u_tukang), ("Mandor", 0.0004, u_mandor),
                ("Besi", 1.05, prices['p_besi']), ("Kawat", 0.015, prices['p_kawat'])
            ]}
        elif hsp_code == "B.20.a": 
            return {"kode": "B.20.a", "uraian": "1 m2 Bekisting", "items": [
                ("Pekerja", 0.52, u_pekerja), ("Tukang", 0.26, u_tukang), ("Mandor", 0.026, u_mandor),
                ("Kayu", 0.045, prices['p_kayu']), ("Paku", 0.3, prices['p_paku']), ("Minyak", 0.1, 25000)
            ]}

        return {"kode": "N/A", "uraian": "Item Tidak Ditemukan", "items": []}

    @staticmethod
    def hitung_harga_satuan(hsp_code, prices, overhead_pct, params=None):
        analisa = AHSP_Engine.get_analisa_detail(hsp_code, prices, params)
        total_dasar = sum([item[1] * item[2] for item in analisa['items']])
        total_final = total_dasar * (1 + overhead_pct/100)
        return total_final

# --- 3. LIBRARY CALCULATOR (RESTORED FULL ENGINEERING V.12 + MATERIAL V.13) ---
class Calculator:
    
    # 3.1 SALURAN BETON (FULL LOGIC RESTORED)
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        if h <= 0 or panjang <= 0: return {"vol_beton": 0, "rho_data": {"status": "DATA KOSONG"}}
        
        gamma_air, selimut = 9.81, 40
        t_mm = t_cm * 10
        d_eff = max(1.0, t_mm - selimut - (dia/2))
        
        # Engineering Checks
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 
        
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        rho_actual = As_per_meter / (1000 * d_eff)
        rho_min = 1.4 / fy if fy > 0 else 0.0014
        rho_max = 0.75 * ((0.85 * (0.85 if fc<=28 else 0.65) * fc / fy) * (600/(600+fy)))
        
        status_rho = "AMAN" if rho_min <= rho_actual <= rho_max else ("KURANG BESI" if rho_actual < rho_min else "BOROS BESI")
        
        # Volume Calculation
        t_m = t_cm / 100
        vol_beton = (b + 2*(h*math.sqrt(1+m**2)) + 2*t_m) * t_m * panjang
        vol_galian = ((b + 2*t_m*math.sqrt(1+m**2) + 0.4 + (b + 2*t_m*math.sqrt(1+m**2) + 0.4 + 2*m*(h+t_m+0.2)))/2) * (h+t_m+0.2) * panjang
        berat_besi = (b + 2*(h*math.sqrt(1+m**2))) * ((panjang*100/jarak)+1) * lapis * (0.006165*dia**2) * 1.2 * (1+waste/100)
        
        # Material Breakdown (V.13 Feature)
        mat_semen = vol_beton * 371 / 1250 
        mat_pasir = vol_beton * 0.5
        mat_split = vol_beton * 0.78
        
        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": max(0, (vol_galian-vol_beton)*0.45),
            "berat_besi": berat_besi,
            "luas_bekisting": (2 * sisi_miring * panjang) * 2, "vol_bongkaran": vol_beton if is_rehab else 0,
            "material_raw": {"semen_m3": mat_semen, "pasir": mat_pasir, "batu_split": mat_split}
        }

    # 3.2 SALURAN BATU
    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        vol_batu = ((((l_atas+l_bawah)/2)*h)*2 + (b*t_lantai)) * panjang
        mat_batu = vol_batu * 1.2
        mat_semen = vol_batu * 163 / 1250
        mat_pasir = vol_batu * 0.52
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu, "vol_galian": vol_batu*1.25, "vol_timbunan": max(0, (vol_batu*1.25 - vol_batu)*0.35),
            "luas_plester": ((2*h*math.sqrt(1+m**2))+b)*panjang, "luas_siaran": (2*l_atas)*panjang, "vol_bongkaran": vol_batu if is_rehab else 0,
            "material_raw": {"batu_kali": mat_batu, "semen_m3": mat_semen, "pasir": mat_pasir}
        }

    # 3.3 BOX CULVERT (FULL CHECK RESTORED)
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        if w<=0 or h<=0: return {"vol_beton": 0, "t_rekom": 0, "rho_data": {"status": "DATA 0"}}
        t_m = t_cm / 100
        
        # Engineering Checks
        Mu = (1/10) * ((18*1.5)+10) * ((w+t_m)**2)
        d_eff = (t_cm*10) - 40 - (dia/2)
        t_rekom = max((Mu/(0.85*2000))**0.5 * 100, (w+t_m)/12*100, 15.0)
        rho_act = ((1000/jarak)*(0.25*math.pi*dia**2)*2) / (1000*d_eff)
        status = "AMAN" if (1.4/fy) <= rho_act <= 0.025 else ("KURANG" if rho_act < 1.4/fy else "BOROS")
        
        # Volume
        vol_beton = ((w+2*t_m)*(h+2*t_m)*p) - (w*h*p)
        berat_besi = 2*((w+2*t_m)+(h+2*t_m))*2 * ((p*100/jarak)+1) * (0.006165*dia**2) * 1.2
        
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": rho_act, "min": 1.4/fy, "max": 0.025, "status": status},
            "vol_beton": vol_beton, "vol_galian": vol_beton/0.2, "vol_timbunan": vol_beton/0.5,
            "berat_besi": berat_besi,
            "luas_bekisting": (2*w+2*h)*p, "vol_bongkaran": vol_beton if is_rehab else 0,
            "material_raw": {"semen_m3": vol_beton*0.3, "pasir": vol_beton*0.5, "batu_split": vol_beton*0.78}
        }

    # 3.4 TERJUNAN USBR + MODE HEMAT + SAFETY CHECK (ALL RESTORED)
    @staticmethod
    def hitung_terjunan_usbr(Q, H_total, H_step, B, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab):
        if H_step <= 0: H_step = 0.1
        if B <= 0: B = 1.0
        if Q <= 0: Q = 0.1 
        g = 9.81
        
        # Geometri & Hidrolis
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps 
        q = Q / B
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1)
        
        # Tipe USBR
        tipe_usbr, k_length = "Unknown", 0
        if Fr1 < 1.7: tipe_usbr, k_length = "Aliran Undular", 4.0
        elif Fr1 < 2.5: tipe_usbr, k_length = "USBR Tipe I", 5.0
        elif Fr1 <= 4.5: tipe_usbr, k_length = "USBR Tipe IV", 6.0 
        else:
            if V1 < 18.0: tipe_usbr, k_length = "USBR Tipe III", 2.7 
            else: tipe_usbr, k_length = "USBR Tipe II", 4.3
        
        L_kolam_standard = k_length * y2
        L_drop = 4.30 * H_real * ((q**2 / (g * H_real**3))**0.27)
        
        # Mode Hemat Logic
        is_hemat_active = mode_hemat and (H_real <= 1.2)
        L_kolam_inter = 0.5 if is_hemat_active else L_kolam_standard
        tipe_desain = "Mode Hemat (Kolam Hilir Saja)" if is_hemat_active else "Standard (Full USBR)"
        L_kolam_final = L_kolam_standard 
        
        # Length & Vol Calc
        jml_inter = max(0, n_steps - 1)
        L_total_structure_linear = (jml_inter * (L_drop + L_kolam_inter)) + (1 * (L_drop + L_kolam_final))
        
        # SAFETY CHECK (Uplift)
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
        
        # Final Vol
        h_dinding = y2 + 0.6 
        vol_lantai = L_total_structure_linear * B * t_lantai
        vol_mercu = n_steps * (B * H_real * 0.4) 
        vol_dinding = 2 * (L_total_structure_linear * h_dinding * t_dinding)
        vol_beton_total = vol_lantai + vol_mercu + vol_dinding
        
        ratio_besi = 120.0
        if SF_uplift < 1.5: ratio_besi += 10 
        if "USBR Tipe III" in tipe_usbr: ratio_besi += 15
        
        mat_semen = vol_beton_total * 371 / 1250
        mat_pasir = vol_beton_total * 0.5
        mat_split = vol_beton_total * 0.78
        
        return {
            "info_struktur": f"{tipe_usbr} ({n_steps} Trap) - {tipe_desain}",
            "detail_usbr": {"Fr": Fr1, "y1": y1, "y2": y2, "L_kolam_final": L_kolam_final, "L_total": L_total_structure_linear},
            "stabilitas": {"sf_uplift": SF_uplift, "status_uplift": status_uplift, "sigma_tanah": Tekanan_Netto, "status_tanah": status_tanah},
            "vol_beton": vol_beton_total, "vol_batu": 0, "vol_galian": vol_beton_total * 1.3, 
            "vol_timbunan": vol_beton_total * 0.3, "berat_besi": vol_beton_total * ratio_besi, 
            "luas_bekisting": (2 * L_total_structure_linear * h_dinding) + (n_steps*B*H_real),
            "luas_plester": (2 * L_total_structure_linear * h_dinding), "luas_siaran": 0,
            "material_raw": {"semen_m3": mat_semen, "pasir": mat_pasir, "batu_split": mat_split},
            "vol_bongkaran": vol_beton_total if is_rehab else 0
        }

# --- 4. UI & LOGIC ---
with st.sidebar:
    st.title("📂 Proyek & Harga")
    col_s, col_l = st.columns(2)
    if st.button("Reset"): st.session_state['data_proyek'] = []; st.rerun()
    st.download_button("Download JSON", json.dumps(st.session_state['data_proyek']), "data.json")
    
    st.markdown("---")
    st.header("🚚 Opsi Langsiran")
    jarak_langsir = st.slider("Jarak Angkut Manual (m)", 0, 500, 0, step=10, help="Jika > 0, biaya angkut material akan dihitung otomatis.")
    
    st.header("💰 Harga Satuan (Bengkulu)")
    with st.expander("Upah & Material", expanded=False):
        u_pekerja = st.number_input("Pekerja", 115000.0)
        u_tukang = st.number_input("Tukang", 140000.0)
        u_mandor = st.number_input("Mandor", 165000.0)
        overhead = st.number_input("Overhead %", 15.0)
        p_semen = st.number_input("Semen (kg)", 1650.0)
        p_pasir = st.number_input("Pasir (m3)", 215000.0)
        p_batu = st.number_input("Batu Kali (m3)", 265000.0)
        p_split = st.number_input("Split (m3)", 325000.0)
        p_besi = st.number_input("Besi (kg)", 15500.0)
        p_kayu = st.number_input("Kayu (m3)", 2850000.0)
        p_kawat = 22000.0; p_paku = 20000.0

    prices = {'u_pekerja':u_pekerja, 'u_tukang':u_tukang, 'u_mandor':u_mandor, 'p_semen':p_semen, 
              'p_pasir':p_pasir, 'p_batu':p_batu, 'p_split':p_split, 'p_besi':p_besi, 'p_kayu':p_kayu, 'p_kawat':p_kawat, 'p_paku':p_paku}
    def get_hsp(kode, params=None): return AHSP_Engine.hitung_harga_satuan(kode, prices, overhead, params)

# --- MAIN UI ---
st.title("🏗️ Pro QS V.14: Full Feature")
st.caption(f"Status: Mode Langsiran {'AKTIF' if jarak_langsir > 0 else 'OFF'} | Safety Check AKTIF")

tab1, tab2, tab3 = st.tabs(["➕ Input", "📋 List", "📊 RAB Detail"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        kategori = st.radio("Kategori", ["Saluran", "Bangunan"], horizontal=True)
        nama_item = st.text_input("Nama Item", "Item 1")
        is_rehab = st.checkbox("Rehab?")
    
    with col2:
        if kategori == "Saluran":
            tipe = st.selectbox("Tipe", ["Batu", "Beton"])
            pjg = st.number_input("Panjang (m)", 50.0)
            if tipe == "Batu":
                calc = Calculator.hitung_pasangan_batu(0.8, 0.6, 0.2, pjg, 0.3, 0.4, 0.2, is_rehab)
            else:
                # Input Beton Lengkap
                h = st.number_input("Tinggi H", 0.8)
                b = st.number_input("Lebar B", 0.6)
                fc = st.number_input("fc (MPa)", 20.0)
                fy = st.number_input("fy (MPa)", 280.0)
                t_cm = st.number_input("Tebal (cm)", 15.0)
                dia = st.number_input("Dia Besi", 10.0)
                jarak = st.number_input("Jarak", 15.0)
                calc = Calculator.hitung_beton_struktur(h, b, 0, pjg, t_cm, dia, jarak, 2, 5, fc, fy, is_rehab)
                st.caption(f"Status: {calc.get('rho_data', {}).get('status', '-')}")
        else:
            tipe = st.selectbox("Tipe", ["Terjunan USBR", "Box Culvert"])
            if tipe == "Terjunan USBR":
                Q_debit = st.number_input("Debit Q", 1.5)
                H_total = st.number_input("Total Tinggi", 3.0)
                H_step = st.number_input("Tinggi/Trap", 1.5)
                B_terjun = st.number_input("Lebar", 1.5)
                qa = st.number_input("Daya Dukung", 150.0)
                mode_hemat = st.checkbox("Mode Hemat", True)
                calc = Calculator.hitung_terjunan_usbr(Q_debit, H_total, H_step, B_terjun, 0.25, 0.25, qa, mode_hemat, is_rehab)
                st.write(f"Info: {calc['info_struktur']}")
                st.write(f"Safety: {calc['stabilitas']['status_uplift']}")
            else:
                calc = Calculator.hitung_gorong_box_struktur(1,1,6,20,13,15,25,400,is_rehab)

    if st.button("Simpan Item", type="primary"):
        st.session_state['data_proyek'].append({"nama": nama_item, "tipe": "Item", "vol": calc})
        st.success("Disimpan!")

with tab3:
    if st.session_state['data_proyek']:
        excel_rows = []
        grand_total = 0
        map_job = {
            "vol_galian": ("Galian Tanah", "m3", "T.06.a.1"), "vol_beton": ("Beton K-225", "m3", "B.05.a"),
            "vol_batu": ("Pasangan Batu", "m3", "P.01.a"), "berat_besi": ("Pembesian", "kg", "B.17.a"),
            "luas_bekisting": ("Bekisting", "m2", "B.20.a"), "vol_bongkaran": ("Bongkaran", "m3", "T.15.a")
        }

        st.subheader("I. Pekerjaan Utama")
        for item in st.session_state['data_proyek']:
            vol_data = item['vol']
            with st.expander(f"{item['nama']}"):
                for key, val in vol_data.items():
                    if key in map_job and val > 0.001:
                        desc, sat, kode = map_job[key]
                        h_sat = get_hsp(kode)
                        tot = val * h_sat
                        st.write(f"- {desc}: {val:.2f} {sat} x Rp {h_sat:,.0f} = Rp {tot:,.0f}")
                        grand_total += tot
                        excel_rows.append({"Uraian": desc, "Vol": val, "H.Sat": h_sat, "Total": tot})

        if jarak_langsir > 0:
            st.subheader(f"II. Biaya Langsiran (Jarak {jarak_langsir}m)")
            total_mat_vol = sum([
                i['vol'].get('material_raw', {}).get('batu_kali', 0) + 
                i['vol'].get('material_raw', {}).get('pasir', 0) + 
                i['vol'].get('material_raw', {}).get('batu_split', 0) + 
                i['vol'].get('material_raw', {}).get('semen_m3', 0) 
                for i in st.session_state['data_proyek']
            ])
            
            if total_mat_vol > 0:
                hsp_langsir = get_hsp("T.15.L", params={'jarak': jarak_langsir})
                biaya_langsir = total_mat_vol * hsp_langsir
                st.info(f"Total Vol Material: **{total_mat_vol:.2f} m3**")
                st.table(pd.DataFrame([{"Uraian": f"Langsiran ({jarak_langsir}m)", "Volume": total_mat_vol, "H.Sat": hsp_langsir, "Total": biaya_langsir}]))
                grand_total += biaya_langsir
                excel_rows.append({"Uraian": "Langsiran", "Vol": total_mat_vol, "H.Sat": hsp_langsir, "Total": biaya_langsir})

        st.success(f"### Total Akhir: Rp {grand_total*1.11:,.0f}")
        
        def generate_excel():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: pd.DataFrame(excel_rows).to_excel(writer, index=False)
            return output.getvalue()
        st.download_button("📥 Download Excel", generate_excel(), "RAB_V14_Final.xlsx")
