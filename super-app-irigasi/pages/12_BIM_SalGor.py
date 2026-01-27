import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: Hybrid & Multi-Step", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    
    # ... (Fungsi Saluran Beton & Batu V.6 tetap sama, saya persingkat agar muat) ...
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        # Logika sama seperti V.6 (Saluran Beton)
        gamma_air = 9.81
        selimut = 40
        t_mm = t_cm * 10
        d_eff = t_mm - selimut - (dia/2)
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 
        
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        Ac_per_meter = 1000 * d_eff
        rho_actual = As_per_meter / Ac_per_meter
        rho_min = 1.4 / fy
        beta1 = 0.85 if fc <= 28 else max(0.65, 0.85 - 0.05 * (fc - 28) / 7)
        rho_balance = (0.85 * beta1 * fc / fy) * (600 / (600 + fy))
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

    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        # Logika sama seperti V.6 (Saluran Batu)
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

    # --- MODUL BARU 1: BOX CULVERT PINTAR (STRUKTUR CHECK) ---
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        # 1. Analisa Struktur Box (Approximation)
        # Beban asumsi: Tanah (18kN/m3) + Hidrostatis + Lalu Lintas (Equivalent)
        gamma_tanah = 18.0
        q_load = (gamma_tanah * 1.5) + 10 # Kedalaman tanah 1.5m + Beban LL 10kN/m2
        
        # Momen Maksimum (Approximation Frame: M = 1/12 * q * L^2)
        # L = lebar bersih + tebal (center-to-center)
        t_m = t_cm / 100
        L_eff = w + t_m
        Mu = (1/10) * q_load * (L_eff**2) # Pakai 1/10 untuk safety factor corner
        
        # Cek Tebal (Shear & Moment)
        d_eff = (t_cm * 10) - 40 - (dia/2) # mm
        t_rekom = max((Mu / (0.85 * 2000))**0.5 * 100, L_eff/12 * 100, 15.0) # Minimal 15cm
        
        # Cek Rasio Tulangan
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * 2 # 2 Lapis (Luar Dalam)
        Ac_per_meter = 1000 * d_eff
        rho_actual = As_per_meter / Ac_per_meter
        rho_min = 1.4 / fy
        rho_max = 0.025 # Limit praktis box culvert
        
        status_rho = "AMAN"
        if rho_actual < rho_min: status_rho = "KURANG BESI"
        elif rho_actual > rho_max: status_rho = "BOROS BESI"

        # 2. Volume
        vol_box_total = (w + 2*t_m) * (h + 2*t_m) * p
        vol_rongga = w * h * p
        vol_beton = vol_box_total - vol_rongga
        
        vol_galian = vol_box_total * 1.2
        vol_timbunan = (vol_galian - vol_box_total) * 0.5
        
        # Besi (kg) - Box perlu besi lebih banyak (dinding + plat atas bawah, 2 rangkap)
        berat_m_lari = 0.006165 * (dia**2)
        keliling_besi = 2 * ((w + 2*t_m) + (h + 2*t_m)) * 2 # 2 rangkap
        jum_potongan = (p * 100 / jarak) + 1
        berat_besi = (keliling_besi * jum_potongan * berat_m_lari) * 1.2
        
        luas_bekisting = (2*w + 2*h) * p # Dalam saja (Luar galian rapi/bekisting bata)
        vol_bongkaran = vol_beton if is_rehab else 0
        
        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi, "luas_bekisting": luas_bekisting, "vol_bongkaran": vol_bongkaran
        }

    # --- MODUL BARU 2: TERJUNAN HYBRID (MULTI-STEP) ---
    @staticmethod
    def hitung_terjunan_hybrid(H_total, H_step, B, t_lantai_beton, t_dinding_batu, is_rehab):
        # 1. Geometri Multi-Step
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps # Tinggi terjun aktual per trap
        
        # Estimasi Panjang Hidrolis (Simplified dari file Kakak: L_drop + L_kolam)
        # L_drop approx 2.5 * H_real, L_kolam approx 2 * H_real (USBR simple)
        L_per_step = (2.5 * H_real) + (2.0 * H_real) + 1.0 # +1m Safety/Transisi
        L_total_structure = n_steps * L_per_step
        
        # 2. Volume Beton (Hanya Lantai & Mercu - Agar Kuat & Awet)
        # Volume Lantai = Panjang Total x Lebar x Tebal Beton
        vol_lantai = L_total_structure * B * t_lantai_beton
        # Volume Mercu/Dinding Tegak (Beton)
        vol_mercu = n_steps * (B * H_real * 0.30) # Tebal mercu 30cm
        vol_beton = vol_lantai + vol_mercu
        
        # 3. Volume Pasangan Batu (Dinding Sayap Kiri Kanan)
        # Tinggi dinding rata-rata = H_real + Freeboard (0.5m)
        h_dinding_avg = H_real + 0.5 
        vol_batu = 2 * (L_total_structure * h_dinding_avg * t_dinding_batu) # Kiri + Kanan
        
        # 4. Galian & Timbunan
        vol_total_struktur = vol_beton + vol_batu
        vol_galian = vol_total_struktur * 1.3
        vol_timbunan = vol_galian * 0.25
        
        # 5. Finishing
        luas_plester = (2 * L_total_structure * h_dinding_avg) # Dinding Batu
        luas_siaran = 0 # Biasanya plester semua untuk terjunan
        
        # 6. Besi (Untuk Lantai Beton) - Asumsi wiremesh/tulangan praktis 100kg/m3
        berat_besi = vol_beton * 100
        
        # 7. Bekisting (Mercu + Sisi Lantai)
        luas_bekisting = (n_steps * B * H_real) + (2 * L_total_structure * t_lantai_beton)
        
        vol_bongkaran = vol_total_struktur if is_rehab else 0

        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "info_struktur": f"{n_steps} Trap x {H_real:.2f}m",
            "vol_beton": vol_beton, "vol_batu": vol_batu, # HYBRID OUTPUT
            "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi, "luas_bekisting": luas_bekisting,
            "luas_plester": luas_plester, "luas_siaran": luas_siaran,
            "vol_bongkaran": vol_bongkaran
        }

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    # ... (Save/Open code sama) ...
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button("💾 Save", json_str, "rab_proyek.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open", type=["json"])
    if uploaded_file:
        try: st.session_state['data_proyek'] = json.load(uploaded_file); st.success("Loaded!")
        except: st.error("Error")
            
    st.markdown("---")
    st.header("💰 Harga Satuan Dasar")
    
    with st.expander("Upah & Material", expanded=False):
        u_pekerja = st.number_input("Pekerja", 110000.0)
        u_tukang = st.number_input("Tukang", 135000.0)
        u_k_tukang = st.number_input("K. Tukang", 150000.0)
        u_mandor = st.number_input("Mandor", 170000.0)
        overhead = st.slider("Overhead %", 0, 15, 10)
        
        p_semen = st.number_input("Semen (kg)", 1600.0)
        p_pasir = st.number_input("Pasir (m3)", 250000.0)
        p_split = st.number_input("Split (m3)", 350000.0)
        p_batu = st.number_input("Batu (m3)", 280000.0)
        p_besi = st.number_input("Besi (kg)", 14500.0)
        p_kayu = st.number_input("Kayu (m3)", 3000000.0)

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
st.title("🏗️ Pro QS: Hybrid & Multi-Step (V.7)")
st.caption("Fitur: Gorong-gorong Struktur, Terjunan Bertingkat, Konstruksi Kombinasi (Beton+Batu)")

tab1, tab2, tab3 = st.tabs(["➕ Input", "📋 List", "📊 RAB Detail"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Terjunan Km 2+100")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehab?", help="Hitung bongkaran otomatis")
        
    with col2:
        st.subheader("2. Spesifikasi")
        
        # --- SALURAN ---
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0)
            
            if tipe_kons == "Beton Bertulang":
                h = st.number_input("Tinggi H (m)", 0.8)
                b = st.number_input("Lebar B (m)", 0.6)
                m = st.number_input("Talud m", 0.0)
                fc = st.number_input("fc' (MPa)", 20.0)
                fy = st.number_input("fy (MPa)", 280.0)
                t_cm = st.number_input("Tebal (cm)", 15.0)
                dia = st.number_input("Dia Besi (mm)", 10.0)
                jarak = st.number_input("Jarak (cm)", 15.0)
                
                calc = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 5, fc, fy, is_rehab)
                st.caption(f"Status Besi: {calc['rho_data']['status']}")

            else: # Batu
                h = st.number_input("Tinggi H", 0.8)
                l_atas = st.number_input("L. Atas", 0.3)
                l_bawah = st.number_input("L. Bawah", 0.4)
                t_lantai = st.number_input("T. Lantai", 0.2)
                calc = Calculator.hitung_pasangan_batu(h, b, 0.2, panjang, l_atas, l_bawah, t_lantai, is_rehab)

        # --- BANGUNAN (GORONG & TERJUNAN) ---
        else:
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box (Cek Struktur)", "Terjunan Bertingkat (Hybrid)"])
            
            if "Gorong" in jenis_bang:
                st.info("📦 Analisa Struktur Box Culvert")
                w = st.number_input("Lebar (m)", 1.0)
                h_box = st.number_input("Tinggi (m)", 1.0)
                p_box = st.number_input("Panjang (m)", 6.0)
                
                c_s1, c_s2 = st.columns(2)
                fc = c_s1.number_input("fc' (MPa)", 25.0)
                fy = c_s2.number_input("fy (MPa)", 400.0)
                
                t_cm = st.number_input("Tebal Beton (cm)", 20.0)
                dia = st.number_input("Dia. Besi (mm)", 13.0)
                jarak = st.number_input("Jarak (cm)", 15.0)
                
                calc = Calculator.hitung_gorong_box_struktur(w, h_box, p_box, t_cm, dia, jarak, fc, fy, is_rehab)
                
                # Report Struktur Box
                st.markdown("---")
                c_r1, c_r2 = st.columns(2)
                if t_cm < calc['t_rekom']: c_r1.error(f"❌ Tebal Kurang (Min {calc['t_rekom']:.1f}cm)")
                else: c_r1.success(f"✅ Tebal Aman")
                
                if "AMAN" in calc['rho_data']['status']: c_r2.success(f"✅ {calc['rho_data']['status']}")
                else: c_r2.warning(f"⚠️ {calc['rho_data']['status']}")
                
            else: # Terjunan Hybrid
                st.info("🌊 Terjunan Multi-Step (Beton + Batu)")
                H_total = st.number_input("Total Tinggi Jatuh (m)", 3.0)
                H_step = st.number_input("Max Tinggi per Trap (m)", 1.5, help="Sistem akan membagi otomatis")
                B_terjun = st.number_input("Lebar Saluran (m)", 1.5)
                
                st.markdown("**Komposisi Material (Hybrid):**")
                c_m1, c_m2 = st.columns(2)
                t_lantai_beton = c_m1.number_input("Tebal Lantai Beton (m)", 0.3, help="Untuk tahan gerusan & uplift")
                t_dinding_batu = c_m2.number_input("Tebal Dinding Batu (m)", 0.4, help="Dinding sayap kiri kanan")
                
                calc = Calculator.hitung_terjunan_hybrid(H_total, H_step, B_terjun, t_lantai_beton, t_dinding_batu, is_rehab)
                st.success(f"ℹ️ Desain: {calc['info_struktur']}")

    if st.button("Simpan Item", type="primary"):
        if not nama_item: st.warning("Isi Nama!")
        else:
            tipe_final = jenis_bang if kategori != "Saluran (Linear)" else ("Saluran Beton" if tipe_kons == "Beton Bertulang" else "Saluran Batu")
            if is_rehab: nama_item += " (REHAB)"
            
            # Save data
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": 0, "vol": calc}
            if kategori == "Saluran (Linear)": item_data["panjang"] = panjang
            st.session_state['data_proyek'].append(item_data)
            st.success("Tersimpan!")

# === TAB 2 & 3 ===
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
            "vol_beton": ("Beton Mutu K-225 (Lantai/Box)", "m3", hsp_beton),
            "vol_batu": ("Pasangan Batu Kali (Dinding Sayap)", "m3", hsp_batu), # ITEM BARU UTK HYBRID
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
        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V7_Hybrid.xlsx")
