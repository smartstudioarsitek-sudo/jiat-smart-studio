import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: Saluran, Terjunan & Rehab", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        # A. ANALISA STRUKTUR (SNI 2847)
        gamma_air = 9.81
        selimut = 40 # mm
        t_mm = t_cm * 10
        d_eff = t_mm - selimut - (dia/2)
        
        # 1. Momen & Tebal Rekomendasi
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        sisi_miring = h * math.sqrt(1 + m**2)
        # Tebal Min (Crack control + Shear + Practical)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 
        
        # 2. Rasio Tulangan
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

        # B. VOLUME MATERIAL
        t_m = t_cm / 100
        
        # 1. Beton
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) 
        vol_beton = (keliling_center * t_m) * panjang
        
        # 2. Galian
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) 
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang

        # 3. Timbunan
        vol_timbunan = max(0, (vol_galian - vol_beton) * 0.45)
        
        # 4. Besi
        berat_m_lari = 0.006165 * (dia**2)
        keliling_besi = (b + 2*(h*math.sqrt(1+m**2))) 
        jum_potongan = (panjang * 100 / jarak) + 1
        total_berat_besi = (keliling_besi * jum_potongan * lapis * berat_m_lari) * 1.2 * (1 + waste/100)
        
        # 5. Bekisting
        luas_bekisting = (2 * sisi_miring * panjang) * 2
        
        # 6. Bongkaran (Jika Rehab)
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
            "luas_plester": luas_plester, "luas_siaran": luas_siaran,
            "vol_bongkaran": vol_bongkaran
        }

    @staticmethod
    def hitung_gorong_box(w, h, p, is_rehab):
        t = 0.20 
        vol_box_total = (w + 2*t) * (h + 2*t) * p
        vol_rongga = w * h * p
        
        vol_beton = vol_box_total - vol_rongga
        vol_galian = vol_box_total * 1.2
        vol_timbunan = (vol_galian - vol_box_total) * 0.5
        berat_besi = vol_beton * 150 
        luas_bekisting = (2*w + 2*h) * p
        
        vol_bongkaran = vol_beton if is_rehab else 0
        
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi, "luas_bekisting": luas_bekisting,
            "vol_bongkaran": vol_bongkaran
        }

    @staticmethod
    def hitung_terjunan_batu(h_terjun, b_saluran, l_kolam, is_rehab):
        # Estimasi Volume Terjunan Pasangan Batu
        t_dinding = 0.40 # Tebal rata-rata pasangan batu 40cm
        
        # 1. Volume Mercu (Dinding Tegak Air Jatuh)
        # Vol = Lebar x Tinggi Jatuh x Tebal
        v_mercu = b_saluran * h_terjun * t_dinding
        
        # 2. Volume Lantai Kolam Olak
        # Vol = Lebar x Panjang Kolam x Tebal
        v_lantai = b_saluran * l_kolam * t_dinding
        
        # 3. Volume Dinding Sayap (Kiri + Kanan)
        # Asumsi: Tinggi dinding rata-rata = Tinggi terjun, Panjang = Panjang Kolam
        v_sayap = 2 * (l_kolam * h_terjun * t_dinding)
        
        vol_batu = v_mercu + v_lantai + v_sayap
        
        # 4. Finishing (Plesteran & Siaran)
        # Area basah = Lantai + Dinding dalam
        luas_plester = (b_saluran * l_kolam) + (2 * l_kolam * h_terjun)
        # Area atas = Bibir dinding
        luas_siaran = 2 * l_kolam
        
        # 5. Tanah
        vol_galian = vol_batu * 1.3 # Faktor gembur & working space
        vol_timbunan = vol_galian * 0.3 # Timbunan kembali
        
        # 6. Bongkaran (Jika rehab, bongkar terjunan lama)
        vol_bongkaran = vol_batu if is_rehab else 0
        
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "luas_plester": luas_plester, "luas_siaran": luas_siaran,
            "vol_bongkaran": vol_bongkaran
        }

# --- 3. SIDEBAR: MANAJEMEN & HARGA ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    
    # Save/Open
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button("💾 Save", json_str, "rab_proyek.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open", type=["json"])
    if uploaded_file:
        try:
            st.session_state['data_proyek'] = json.load(uploaded_file)
            st.success("Loaded!")
        except: st.error("Error")
            
    st.markdown("---")
    
    # --- HARGA SATUAN ---
    st.header("💰 Harga Satuan Dasar")
    
    with st.expander("1. Upah Tenaga Kerja", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", 110000.0, step=1000.0, format="%.0f")
        u_tukang = st.number_input("Tukang (OH)", 135000.0, step=1000.0, format="%.0f")
        u_k_tukang = st.number_input("Kepala Tukang (OH)", 150000.0, step=1000.0, format="%.0f") 
        u_mandor = st.number_input("Mandor (OH)", 170000.0, step=1000.0, format="%.0f")
        overhead = st.slider("Overhead %", 0, 15, 10)
    
    with st.expander("2. Material", expanded=False):
        p_semen = st.number_input("Semen (kg)", 1600.0, step=100.0, format="%.0f")
        p_pasir = st.number_input("Pasir (m3)", 250000.0, step=1000.0, format="%.0f")
        p_split = st.number_input("Split (m3)", 350000.0, step=1000.0, format="%.0f")
        p_batu = st.number_input("Batu Kali (m3)", 280000.0, step=1000.0, format="%.0f")
        p_besi = st.number_input("Besi (kg)", 14500.0, step=50.0, format="%.0f")
        p_kayu = st.number_input("Kayu Bekisting (m3)", 3000000.0, step=10000.0, format="%.0f")

    # --- ENGINE AHSP ---
    oh = 1 + (overhead/100)
    hsp_galian = ((0.75*u_pekerja) + (0.025*u_mandor)) * oh
    hsp_timbunan = ((0.33*u_pekerja) + (0.01*u_mandor)) * oh
    hsp_bongkaran = ((2.0*u_pekerja) + (0.1*u_mandor)) * oh

    mat_beton = (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)
    upah_beton = (1.65*u_pekerja + 0.275*u_tukang + 0.028*u_k_tukang + 0.083*u_mandor)
    hsp_beton = (mat_beton + upah_beton) * oh
    
    upah_besi = (0.007*u_pekerja + 0.007*u_tukang + 0.0007*u_k_tukang + 0.0004*u_mandor)
    hsp_besi = (upah_besi + (1.05*p_besi + 0.015*22000)) * oh 
    
    upah_bekisting = (0.66*u_pekerja + 0.33*u_tukang + 0.033*u_k_tukang + 0.033*u_mandor)
    hsp_bekisting = (upah_bekisting + (0.045*p_kayu + 0.3*20000)) * oh 

    upah_batu = (1.5*u_pekerja + 0.75*u_tukang + 0.075*u_k_tukang + 0.075*u_mandor)
    hsp_batu = (upah_batu + (1.2*p_batu + 163*p_semen + 0.52*p_pasir)) * oh
    
    upah_plester = (0.3*u_pekerja + 0.15*u_tukang + 0.015*u_k_tukang + 0.015*u_mandor)
    hsp_plester = (upah_plester + (6.24*p_semen + 0.024*p_pasir)) * oh
    
    upah_siar = (0.15*u_pekerja + 0.075*u_tukang + 0.0075*u_k_tukang + 0.004*u_mandor)
    hsp_siaran = (upah_siar + (3*p_semen + 0.01*p_pasir)) * oh

# --- 4. MAIN UI ---
st.title("🏗️ Pro QS: Saluran, Terjunan & Rehab (V.6)")
st.caption("Fitur: Bangunan Terjun, Rehab, Safety Check, Detail RAB")

tab1, tab2, tab3 = st.tabs(["➕ Input", "📋 List", "📊 RAB Detail"])

# === TAB 1 ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas & Tipe")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Terjunan Tegak T1")
        
        st.markdown("---")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehabilitasi / Renovasi?", help="Centang jika ada bongkaran lama")
        if is_rehab:
            st.info("💡 Item 'Bongkaran' akan ditambahkan otomatis")
        
    with col2:
        st.subheader("2. Spesifikasi Teknis")
        
        # --- INPUT DINAMIS ---
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0, step=0.1, format="%.2f")
            
            if tipe_kons == "Beton Bertulang":
                c_a, c_b, c_c = st.columns(3)
                h = c_a.number_input("Tinggi H (m)", value=0.8, step=0.01)
                b = c_b.number_input("Lebar B (m)", value=0.6, step=0.01)
                m = c_c.number_input("Talud m", value=0.0, step=0.01)
                
                cm1, cm2 = st.columns(2)
                fc = cm1.number_input("Mutu Beton fc' (MPa)", value=20.0)
                fy = cm2.number_input("Mutu Baja fy (MPa)", value=280.0)

                st.markdown("**Penulangan:**")
                cc1, cc2, cc3 = st.columns(3)
                t_cm = cc1.number_input("Tebal Dinding (cm)", value=15.0, step=0.1)
                dia = cc2.number_input("Dia. Besi (mm)", value=10.0, step=1.0)
                jarak = cc3.number_input("Jarak (cm)", value=15.0, step=0.5)
                
                calc = Calculator.hitung_beton_struktur(h, b, m, 1, t_cm, dia, jarak, 2, 5, fc, fy, is_rehab)
                
                st.markdown("#### 🔍 Hasil Cek Struktur:")
                col_w1, col_w2 = st.columns(2)
                if t_cm < calc['t_rekom']:
                    col_w1.error(f"❌ TEBAL KURANG\nMin: {calc['t_rekom']:.2f} cm")
                else:
                    col_w1.success(f"✅ TEBAL AMAN\nMin: {calc['t_rekom']:.2f} cm")
                
                status_besi = calc['rho_data']['status']
                col_w2.info(f"ℹ️ Status Besi: {status_besi}")
                
            else: # Batu
                h = st.number_input("Tinggi H (m)", value=0.8, step=0.01)
                l_atas = st.number_input("L. Atas (m)", value=0.3, step=0.01)
                l_bawah = st.number_input("L. Bawah (m)", value=0.4, step=0.01)
                t_lantai = st.number_input("T. Lantai (m)", value=0.2, step=0.01)
                
        else: # Bangunan
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box", "Bangunan Terjun (Pas. Batu)"])
            
            if jenis_bang == "Gorong-Gorong Box":
                w = st.number_input("Lebar (m)", value=1.0, step=0.01)
                h_b = st.number_input("Tinggi (m)", value=1.0, step=0.01)
                p_b = st.number_input("Panjang (m)", value=5.0, step=0.01)
            elif jenis_bang == "Bangunan Terjun (Pas. Batu)":
                st.info("Input Dimensi Terjunan")
                h_terjun = st.number_input("Tinggi Terjun (m)", value=1.5, step=0.1)
                b_saluran = st.number_input("Lebar Saluran/Mercu (m)", value=1.0, step=0.1)
                l_kolam = st.number_input("Panjang Kolam Olak (m)", value=3.0, step=0.1, help="Biasanya 1.5 - 3 kali tinggi terjun")

    if st.button("Simpan Item", type="primary"):
        if not nama_item:
            st.warning("Nama wajib diisi!")
        else:
            vol_result = {}
            tipe_final = ""
            
            # LOGIC PENENTUAN TIPE & HITUNGAN
            if kategori == "Saluran (Linear)":
                if tipe_kons == "Beton Bertulang":
                    vol_result = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 7, fc, fy, is_rehab)
                    tipe_final = "Saluran Beton"
                else:
                    vol_result = Calculator.hitung_pasangan_batu(h, b, 0.2, panjang, l_atas, l_bawah, t_lantai, is_rehab)
                    tipe_final = "Saluran Batu"
            else:
                if jenis_bang == "Gorong-Gorong Box":
                    vol_result = Calculator.hitung_gorong_box(w, h_b, p_b, is_rehab)
                    tipe_final = "Gorong-Gorong"
                elif jenis_bang == "Bangunan Terjun (Pas. Batu)":
                    vol_result = Calculator.hitung_terjunan_batu(h_terjun, b_saluran, l_kolam, is_rehab)
                    tipe_final = "Bangunan Terjun"
            
            if is_rehab:
                nama_item += " (REHAB)"
                
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": 0, "vol": vol_result}
            # Note: Panjang di-set 0 atau 1 untuk bangunan unit
            if kategori == "Saluran (Linear)": item_data["panjang"] = panjang
            
            st.session_state['data_proyek'].append(item_data)
            st.success("Tersimpan!")

# === TAB 2 & 3 ===
with tab2:
    if st.session_state['data_proyek']:
        st.dataframe(pd.DataFrame(st.session_state['data_proyek'])[["nama", "tipe"]])
        if st.button("Hapus Semua"):
            st.session_state['data_proyek'] = []
            st.rerun()

with tab3:
    st.header("📊 Detail Engineering Estimate (EE)")
    if st.session_state['data_proyek']:
        excel_rows = []
        grand_total = 0
        
        map_pekerjaan = {
            "vol_bongkaran": ("Bongkaran Pasangan Eksisting (PUPR T.16.a)", "m3", hsp_bongkaran),
            "vol_galian": ("Galian Tanah Biasa (SDA T.06.a)", "m3", hsp_galian),
            "vol_timbunan": ("Timbunan Kembali Dipadatkan (SDA T.07.a)", "m3", hsp_timbunan),
            "vol_beton": ("Beton Mutu K-225 (SDA F.03.c)", "m3", hsp_beton),
            "berat_besi": ("Pembesian Ulir/Polos (CK A.4.1.1.17)", "kg", hsp_besi),
            "luas_bekisting": ("Pasang Bekisting (CK A.4.1.1.20)", "m2", hsp_bekisting),
            "vol_batu": ("Pasangan Batu Kali 1:4 (SDA P.01.a)", "m3", hsp_batu),
            "luas_plester": ("Plesteran 1:3 + Acian (CK A.4.4.2.4)", "m2", hsp_plester),
            "luas_siaran": ("Siaran 1:2 (CK A.4.4.2.27)", "m2", hsp_siaran),
        }

        for i, item in enumerate(st.session_state['data_proyek']):
            nama = item['nama']
            vol_data = item['vol']
            
            with st.expander(f"📍 {i+1}. {nama}", expanded=True):
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
                df_ex = pd.DataFrame(excel_rows)
                df_ex.to_excel(writer, index=False, sheet_name='RAB Detail')
            return output.getvalue()
        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V6_Terjunan.xlsx")
