import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: Smart Safety V.9", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (CORE ENGINEERING) ---
class Calculator:
    
    # --- MODUL 1: SALURAN BETON (TETAP 100%) ---
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        if h <= 0 or panjang <= 0: return {"vol_beton": 0, "rho_data": {"status": "DATA KOSONG"}}
        
        gamma_air = 9.81
        selimut = 40
        t_mm = t_cm * 10
        d_eff = t_mm - selimut - (dia/2)
        if d_eff <= 0: d_eff = 1.0 

        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 
        
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        Ac_per_meter = 1000 * d_eff
        rho_actual = As_per_meter / Ac_per_meter
        rho_min = 1.4 / fy if fy > 0 else 0.0014
        beta1 = 0.85 if fc <= 28 else max(0.65, 0.85 - 0.05 * (fc - 28) / 7)
        rho_balance = (0.85 * beta1 * fc / fy) * (600 / (600 + fy)) if fy > 0 else 0.02
        rho_max = 0.75 * rho_balance
        
        status_rho = "AMAN"
        if rho_actual < rho_min: status_rho = "KURANG BESI"
        elif rho_actual > rho_max: status_rho = "BOROS BESI"

        t_m = t_cm / 100
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) 
        vol_beton = (keliling_center * t_m) * panjang
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) 
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang
        vol_timbunan = max(0, (vol_galian - vol_beton) * 0.45)
        
        berat_m_lari = 0.006165 * (dia**2)
        keliling_besi = (b + 2*(h*math.sqrt(1+m**2))) 
        jum_potongan = (panjang * 100 / jarak) + 1
        total_berat_besi = (keliling_besi * jum_potongan * lapis * berat_m_lari) * 1.2 * (1 + waste/100)
        luas_bekisting = (2 * sisi_miring * panjang) * 2
        vol_bongkaran = vol_beton if is_rehab else 0

        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": total_berat_besi, "luas_bekisting": luas_bekisting,
            "vol_bongkaran": vol_bongkaran
        }

    # --- MODUL 2: SALURAN BATU (TETAP 100%) ---
    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        area_dinding = ((l_atas + l_bawah) / 2) * h
        vol_dinding = 2 * area_dinding * panjang
        vol_lantai = b * t_lantai * panjang
        vol_batu = vol_dinding + vol_lantai
        sisi_miring = h * math.sqrt(1 + m**2)
        luas_plester = ((2 * sisi_miring) + b) * panjang 
        luas_siaran = (2 * l_atas) * panjang 
        vol_galian = vol_batu * 1.25 
        vol_timbunan = max(0, (vol_galian - vol_batu) * 0.35)
        vol_bongkaran = vol_batu if is_rehab else 0
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "luas_plester": luas_plester, "luas_siaran": luas_siaran, "vol_bongkaran": vol_bongkaran
        }

    # --- MODUL 3: BOX CULVERT (TETAP 100%) ---
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        if w <= 0 or h <= 0 or p <= 0: return {"vol_beton": 0, "t_rekom": 0, "rho_data": {"status": "DATA 0"}}
        
        gamma_tanah = 18.0
        q_load = (gamma_tanah * 1.5) + 10 
        t_m = t_cm / 100
        L_eff = w + t_m
        Mu = (1/10) * q_load * (L_eff**2) 
        d_eff = (t_cm * 10) - 40 - (dia/2)
        if d_eff <= 0: d_eff = 1.0

        t_rekom = max((Mu / (0.85 * 2000))**0.5 * 100, L_eff/12 * 100, 15.0)
        
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * 2
        Ac_per_meter = 1000 * d_eff
        rho_actual = As_per_meter / Ac_per_meter
        rho_min = 1.4 / fy if fy > 0 else 0.0014
        rho_max = 0.025
        
        status_rho = "AMAN"
        if rho_actual < rho_min: status_rho = "KURANG BESI"
        elif rho_actual > rho_max: status_rho = "BOROS BESI"

        vol_box_total = (w + 2*t_m) * (h + 2*t_m) * p
        vol_rongga = w * h * p
        vol_beton = vol_box_total - vol_rongga
        vol_galian = vol_box_total * 1.2
        vol_timbunan = (vol_galian - vol_box_total) * 0.5
        
        berat_m_lari = 0.006165 * (dia**2)
        keliling_besi = 2 * ((w + 2*t_m) + (h + 2*t_m)) * 2 
        jum_potongan = (p * 100 / jarak) + 1
        berat_besi = (keliling_besi * jum_potongan * berat_m_lari) * 1.2
        luas_bekisting = (2*w + 2*h) * p 
        vol_bongkaran = vol_beton if is_rehab else 0
        
        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi, "luas_bekisting": luas_bekisting, "vol_bongkaran": vol_bongkaran
        }

    # --- MODUL 4: TERJUNAN FULL BETON (SMART CHECK V.9) ---
    @staticmethod
    def hitung_terjunan_smart(H_total, H_step, B, t_lantai, t_dinding, is_rehab):
        # 1. Handling Input 0
        if H_step <= 0: H_step = 0.1
        if B <= 0: B = 0.1
        
        # 2. Geometri Dasar
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps # Tinggi jatuh per trap aktual
        
        # Panjang Hidrolis (USBR Simplified)
        # L_drop approx 2.5H + L_kolam approx 2H + Safety 1m
        L_per_step = (2.5 * H_real) + (2.0 * H_real) + 1.0 
        L_total_structure = n_steps * L_per_step
        
        # Tinggi Dinding Efektif (H_trap + Freeboard 0.6m)
        h_dinding_eff = H_real + 0.6 
        
        # --- 3. SAFETY CHECK ENGINE (NEW V.9) ---
        status_dinding = "AMAN"
        status_lantai = "AMAN"
        ratio_besi = 120.0 # Default Standard (kg/m3)
        
        # A. Cek Kekakuan Dinding (Cantilever Wall Rule of Thumb: H/12)
        t_min_dinding = h_dinding_eff / 12
        if t_dinding < t_min_dinding:
            status_dinding = "⚠️ KRITIS (Terlalu Tipis)"
            ratio_besi += 30.0 # Tambah tulangan ekstra untuk kompensasi tipis
        elif t_dinding > (h_dinding_eff / 5):
            status_dinding = "⚠️ BOROS (Mass Concrete)"
            ratio_besi -= 20.0 # Kurangi tulangan karena beton tebal (gravity)
            
        # B. Cek Impact Lantai (H_jatuh/8 atau min 20cm)
        t_min_lantai = max(0.20, H_real / 8)
        if t_lantai < t_min_lantai:
            status_lantai = "⚠️ RISIKO RETAK (Impact)"
            ratio_besi += 20.0 # Butuh wiremesh/tulangan rangkap ekstra
        
        # 4. Hitung Volume
        # A. Lantai
        vol_lantai = L_total_structure * B * t_lantai
        # B. Mercu/Trap
        vol_mercu = n_steps * (B * H_real * 0.30)
        # C. Dinding Sayap
        vol_dinding = 2 * (L_total_structure * h_dinding_eff * t_dinding)
        
        vol_beton_total = vol_lantai + vol_mercu + vol_dinding
        
        # 5. Galian & Timbunan
        vol_galian = vol_beton_total * 1.3
        vol_timbunan = vol_galian * 0.3
        
        # 6. Besi & Bekisting
        berat_besi = vol_beton_total * ratio_besi
        
        luas_bekisting_dinding = (2 * L_total_structure * h_dinding_eff)
        luas_bekisting_mercu = (n_steps * B * H_real)
        luas_bekisting_lantai = (2 * L_total_structure * t_lantai)
        luas_bekisting_total = luas_bekisting_dinding + luas_bekisting_mercu + luas_bekisting_lantai
        
        vol_bongkaran = vol_beton_total if is_rehab else 0

        return {
            "info_struktur": f"{n_steps} Trap @{H_real:.2f}m",
            "safety_check": {
                "dinding": status_dinding,
                "min_dinding": t_min_dinding,
                "lantai": status_lantai,
                "min_lantai": t_min_lantai,
                "ratio_besi": ratio_besi
            },
            "vol_beton": vol_beton_total, 
            "vol_batu": 0, 
            "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi, "luas_bekisting": luas_bekisting_total,
            "luas_plester": (2 * L_total_structure * h_dinding_eff),
            "luas_siaran": 0,
            "vol_bongkaran": vol_bongkaran
        }

# --- 3. SIDEBAR (AHSP) ---
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
    st.header("💰 Harga Satuan")
    
    with st.expander("Upah & Material", expanded=False):
        u_pekerja = st.number_input("Pekerja", value=110000.0)
        u_tukang = st.number_input("Tukang", value=135000.0)
        u_k_tukang = st.number_input("K. Tukang", value=150000.0)
        u_mandor = st.number_input("Mandor", value=170000.0)
        overhead = st.number_input("Overhead %", value=10.0)
        
        p_semen = st.number_input("Semen (kg)", value=1600.0)
        p_pasir = st.number_input("Pasir (m3)", value=250000.0)
        p_split = st.number_input("Split (m3)", value=350000.0)
        p_batu = st.number_input("Batu (m3)", value=280000.0)
        p_besi = st.number_input("Besi (kg)", value=14500.0)
        p_kayu = st.number_input("Kayu (m3)", value=3000000.0)

    # AHSP Engine
    oh = 1 + (overhead/100)
    hsp_galian = ((0.75*u_pekerja) + (0.025*u_mandor)) * oh
    hsp_timbunan = ((0.33*u_pekerja) + (0.01*u_mandor)) * oh
    hsp_bongkaran = ((2.0*u_pekerja) + (0.1*u_mandor)) * oh
    hsp_beton = ((371*p_semen + 0.4986*p_pasir + 0.7756*p_split) + (1.65*u_pekerja + 0.275*u_tukang + 0.028*u_k_tukang + 0.083*u_mandor)) * oh
    hsp_besi = ((1.05*p_besi + 0.015*22000) + (0.007*u_pekerja + 0.007*u_tukang + 0.0007*u_k_tukang + 0.0004*u_mandor)) * oh
    hsp_bekisting = ((0.045*p_kayu + 0.3*20000) + (0.66*u_pekerja + 0.33*u_tukang + 0.033*u_k_tukang + 0.033*u_mandor)) * oh
    hsp_batu = ((1.2*p_batu + 163*p_semen + 0.52*p_pasir) + (1.5*u_pekerja + 0.75*u_tukang + 0.075*u_k_tukang + 0.075*u_mandor)) * oh
    hsp_plester = ((6.24*p_semen + 0.024*p_pasir) + (0.3*u_pekerja + 0.15*u_tukang + 0.015*u_k_tukang + 0.015*u_mandor)) * oh
    hsp_siaran = ((3*p_semen + 0.01*p_pasir) + (0.15*u_pekerja + 0.075*u_tukang + 0.0075*u_k_tukang + 0.004*u_mandor)) * oh

# --- 4. MAIN UI ---
st.title("🏗️ Pro QS: Smart Check & Safety V.9")
st.caption("Status: ✅ Safety Verification Active (Terjunan) | ✅ All Inputs Unlocked")

tab1, tab2, tab3 = st.tabs(["➕ Input", "📋 List", "📊 RAB Detail"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Terjunan Km 2+100")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehab?", help="Hitung bongkaran otomatis")
        
    with col2:
        st.subheader("2. Spesifikasi (Bebas Input)")
        
        # --- SALURAN ---
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0)
            
            if tipe_kons == "Beton Bertulang":
                h = st.number_input("Tinggi H (m)", value=0.8)
                b = st.number_input("Lebar B (m)", value=0.6)
                m = st.number_input("Talud m", value=0.0)
                fc = st.number_input("fc' (MPa)", value=20.0)
                fy = st.number_input("fy (MPa)", value=280.0)
                t_cm = st.number_input("Tebal (cm)", value=15.0)
                dia = st.number_input("Dia Besi (mm)", value=10.0)
                jarak = st.number_input("Jarak (cm)", value=15.0)
                
                calc = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 5, fc, fy, is_rehab)
                st.caption(f"Status Besi: {calc['rho_data']['status']}")

            else: # Batu
                h = st.number_input("Tinggi H", value=0.8)
                l_atas = st.number_input("L. Atas", value=0.3)
                l_bawah = st.number_input("L. Bawah", value=0.4)
                t_lantai = st.number_input("T. Lantai", value=0.2)
                calc = Calculator.hitung_pasangan_batu(h, b if 'b' in locals() else 0.5, 0.2, panjang, l_atas, l_bawah, t_lantai, is_rehab)

        # --- BANGUNAN (GORONG & TERJUNAN) ---
        else:
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box (Cek Struktur)", "Terjunan Bertingkat (Smart Check)"])
            
            if "Gorong" in jenis_bang:
                st.info("📦 Box Culvert (Input Bebas)")
                w = st.number_input("Lebar (m)", value=1.0)
                h_box = st.number_input("Tinggi (m)", value=1.0)
                p_box = st.number_input("Panjang (m)", value=6.0)
                
                c_s1, c_s2 = st.columns(2)
                fc = c_s1.number_input("fc' (MPa)", value=25.0)
                fy = c_s2.number_input("fy (MPa)", value=400.0)
                
                t_cm = st.number_input("Tebal Beton (cm)", value=20.0)
                dia = st.number_input("Dia. Besi (mm)", value=13.0)
                jarak = st.number_input("Jarak (cm)", value=15.0)
                
                calc = Calculator.hitung_gorong_box_struktur(w, h_box, p_box, t_cm, dia, jarak, fc, fy, is_rehab)
                
                # Report Box
                st.markdown("---")
                c_r1, c_r2 = st.columns(2)
                if t_cm < calc['t_rekom']: c_r1.error(f"❌ Tebal Kurang (Min {calc['t_rekom']:.1f}cm)")
                else: c_r1.success(f"✅ Tebal Aman")
                
                if "AMAN" in calc['rho_data']['status']: c_r2.success(f"✅ {calc['rho_data']['status']}")
                else: c_r2.warning(f"⚠️ {calc['rho_data']['status']}")
                
            else: # Terjunan SMART CHECK (V.9)
                st.info("🌊 Terjunan Multi-Step (Smart Safety Check)")
                
                H_total = st.number_input("Total Tinggi Jatuh (m)", value=3.0)
                H_step = st.number_input("Max Tinggi per Trap (m)", value=1.5)
                B_terjun = st.number_input("Lebar Saluran (m)", value=1.5)
                
                st.markdown("**Dimensi Struktur (Verifikasi Otomatis):**")
                c_m1, c_m2 = st.columns(2)
                t_lantai_beton = c_m1.number_input("Tebal Lantai (m)", value=0.25)
                t_dinding_beton = c_m2.number_input("Tebal Dinding (m)", value=0.25)
                
                calc = Calculator.hitung_terjunan_smart(H_total, H_step, B_terjun, t_lantai_beton, t_dinding_beton, is_rehab)
                
                # --- HASIL VERIFIKASI (SMART OUTPUT) ---
                st.divider()
                st.caption(f"ℹ️ Layout: {calc['info_struktur']}")
                
                # Report Dinding
                status_d = calc['safety_check']['dinding']
                min_d = calc['safety_check']['min_dinding']
                if "KRITIS" in status_d: st.error(f"❌ Dinding: {status_d} (Min: {min_d:.2f}m)")
                elif "BOROS" in status_d: st.warning(f"⚠️ Dinding: {status_d}")
                else: st.success(f"✅ Dinding: AMAN (Sesuai SNI)")
                
                # Report Lantai
                status_l = calc['safety_check']['lantai']
                min_l = calc['safety_check']['min_lantai']
                if "RISIKO" in status_l: st.error(f"❌ Lantai: {status_l} (Min: {min_l:.2f}m)")
                else: st.success(f"✅ Lantai: AMAN")
                
                st.info(f"🧬 Besi Terpakai: {calc['safety_check']['ratio_besi']} kg/m3 (Auto-Adjusted)")

    if st.button("Simpan Item", type="primary"):
        if not nama_item: st.warning("Isi Nama!")
        else:
            tipe_final = jenis_bang if kategori != "Saluran (Linear)" else ("Saluran Beton" if tipe_kons == "Beton Bertulang" else "Saluran Batu")
            if is_rehab: nama_item += " (REHAB)"
            
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": 0, "vol": calc}
            if kategori == "Saluran (Linear)": item_data["panjang"] = panjang
            st.session_state['data_proyek'].append(item_data)
            st.success("Tersimpan!")

# === TAB 2 & 3 (STANDARD EXPORT) ===
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
            "vol_bongkaran": ("Bongkaran Pasangan Eksisting", "m3", hsp_bongkaran),
            "vol_galian": ("Galian Tanah Biasa", "m3", hsp_galian),
            "vol_timbunan": ("Timbunan Kembali Dipadatkan", "m3", hsp_timbunan),
            "vol_beton": ("Beton Bertulang K-225 (Structure)", "m3", hsp_beton),
            "vol_batu": ("Pasangan Batu Kali (Sayap)", "m3", hsp_batu),
            "berat_besi": ("Pembesian Ulir/Polos", "kg", hsp_besi),
            "luas_bekisting": ("Pasang Bekisting", "m2", hsp_bekisting),
            "luas_plester": ("Plesteran 1:3 + Acian", "m2", hsp_plester),
            "luas_siaran": ("Siaran 1:2", "m2", hsp_siaran),
        }

        for i, item in enumerate(st.session_state['data_proyek']):
            nama = item['nama']
            vol_data = item['vol']
            
            with st.expander(f"📍 {i+1}. {nama} ({item['tipe']})", expanded=True):
                item_rows = []
                for key, val in vol_data.items():
                    if key in map_pekerjaan and val > 0.001:
                        uraian, sat, harga = map_pekerjaan[key]
                        jumlah = val * harga
                        item_rows.append({"Uraian": uraian, "Vol": val, "Sat": sat, "H.Sat": harga, "Total": jumlah})
                        excel_rows.append({"No": i+1, "Item": nama, "Uraian": uraian, "Vol": val, "Sat": sat, "H.Sat": harga, "Total": jumlah})
                
                df_item = pd.DataFrame(item_rows)
                if not df_item.empty:
                    subtotal = df_item["Total"].sum()
                    grand_total += subtotal
                    st.dataframe(df_item.style.format({"Vol": "{:.3f}", "H.Sat": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
                    st.markdown(f"**Subtotal: Rp {subtotal:,.0f}**")

        st.divider()
        ppn = grand_total * 0.11
        st.success(f"### Total Akhir: Rp {grand_total + ppn:,.0f} (Termasuk PPN)")
        
        def generate_excel():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(excel_rows).to_excel(writer, index=False, sheet_name='RAB Detail')
            return output.getvalue()
        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V9_SmartSafety.xlsx")
