import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: Estimator SNI & PUPR", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy):
        # A. ANALISA STRUKTUR & TULANGAN (SNI 2847)
        gamma_air = 9.81
        selimut = 40 # mm (4cm)
        t_mm = t_cm * 10
        d_eff = t_mm - selimut - (dia/2) # Tinggi efektif (mm)
        
        # 1. Hitung Momen (Mu) - Beban Air Penuh
        Mu = 1.6 * (1/6) * gamma_air * (h**3) # kNm
        
        # 2. Cek Tebal (Crack Control & Shear estimate)
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 # cm
        
        # 3. Cek Rasio Tulangan (Rho)
        # Luas Besi Per Meter (mm2)
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        # Luas Penampang Beton Per Meter (mm2) -> b=1000mm, d=d_eff
        Ac_per_meter = 1000 * d_eff
        
        rho_actual = As_per_meter / Ac_per_meter
        
        # Batas Min & Max (Simplified SNI 2847 untuk Lentur)
        rho_min = 1.4 / fy
        # Rho Balance (pendekatan) -> Rho Max = 0.75 * Rho Balance
        beta1 = 0.85 if fc <= 28 else max(0.65, 0.85 - 0.05 * (fc - 28) / 7)
        rho_balance = (0.85 * beta1 * fc / fy) * (600 / (600 + fy))
        rho_max = 0.75 * rho_balance
        
        status_rho = "AMAN (Ekonomis)"
        if rho_actual < rho_min:
            status_rho = "BAHAYA (Kurang Besi)"
        elif rho_actual > rho_max:
            status_rho = "BOROS (Besi Berlebih)"

        # B. VOLUME MATERIAL
        t_m = t_cm / 100
        
        # 1. Beton
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) 
        vol_beton = (keliling_center * t_m) * panjang
        
        # 2. Galian (SDA T.06.a)
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) 
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang

        # 3. Timbunan Kembali (SDA T.07.a)
        vol_timbunan = max(0, (vol_galian - vol_beton) * 0.45) # Faktor pemadatan
        
        # 4. Besi (kg)
        berat_m_lari = 0.006165 * (dia**2)
        keliling_besi = (b + 2*(h*math.sqrt(1+m**2))) 
        jum_potongan = (panjang * 100 / jarak) + 1
        total_berat_besi = (keliling_besi * jum_potongan * lapis * berat_m_lari) * 1.2 * (1 + waste/100)
        
        # 5. Bekisting
        luas_bekisting = (2 * sisi_miring * panjang) * 2 

        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "vol_timbunan": vol_timbunan,
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
        vol_timbunan = max(0, (vol_galian - vol_batu) * 0.35)
        
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu,
            "vol_galian": vol_galian,
            "vol_timbunan": vol_timbunan,
            "luas_plester": luas_plester,
            "luas_siaran": luas_siaran
        }

    @staticmethod
    def hitung_gorong_box(w, h, p):
        t = 0.20 
        vol_box_total = (w + 2*t) * (h + 2*t) * p
        vol_rongga = w * h * p
        
        vol_beton = vol_box_total - vol_rongga
        vol_galian = vol_box_total * 1.2
        vol_timbunan = (vol_galian - vol_box_total) * 0.5
        
        berat_besi = vol_beton * 150 
        luas_bekisting = (2*w + 2*h) * p 
        
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi,
            "luas_bekisting": luas_bekisting
        }

# --- 3. SIDEBAR: MANAJEMEN & HARGA (PERMEN PUPR UPDATE) ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    
    # Save/Open Logic
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button("💾 Save Data", json_str, "rab_proyek.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open Data", type=["json"])
    if uploaded_file:
        try:
            st.session_state['data_proyek'] = json.load(uploaded_file)
            st.success("Loaded!")
        except: st.error("Error loading file")
            
    st.markdown("---")
    
    # --- INPUT HARGA DASAR (Update Kepala Tukang) ---
    st.header("💰 Harga Satuan Dasar")
    
    with st.expander("1. Upah Tenaga Kerja", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", 110000.0, step=1000.0, format="%.0f")
        u_tukang = st.number_input("Tukang (OH)", 135000.0, step=1000.0, format="%.0f")
        # FITUR BARU: Kepala Tukang
        u_k_tukang = st.number_input("Kepala Tukang (OH)", 150000.0, step=1000.0, format="%.0f") 
        u_mandor = st.number_input("Mandor (OH)", 170000.0, step=1000.0, format="%.0f")
        overhead = st.slider("Overhead & Profit %", 0, 15, 10)
    
    with st.expander("2. Material Konstruksi", expanded=False):
        p_semen = st.number_input("Semen (kg)", 1600.0, step=100.0, format="%.0f")
        p_pasir = st.number_input("Pasir Beton (m3)", 250000.0, step=1000.0, format="%.0f")
        p_split = st.number_input("Kerikil/Split (m3)", 350000.0, step=1000.0, format="%.0f")
        p_batu = st.number_input("Batu Belah (m3)", 280000.0, step=1000.0, format="%.0f")
        p_besi = st.number_input("Besi Beton (kg)", 14500.0, step=50.0, format="%.0f")
        p_kayu = st.number_input("Kayu Bekisting (m3)", 3000000.0, step=10000.0, format="%.0f")

    # --- ENGINE AHSP (Update Koefisien Kepala Tukang) ---
    oh = 1 + (overhead/100)
    
    # Galian (SDA T.06.a): 0.75 Pekerja, 0.025 Mandor
    hsp_galian = ((0.75*u_pekerja) + (0.025*u_mandor)) * oh
    
    # Timbunan (SDA T.07.a): 0.33 Pekerja, 0.01 Mandor
    hsp_timbunan = ((0.33*u_pekerja) + (0.01*u_mandor)) * oh

    # Beton K-225 (Manual A.4.1.1.7)
    # Koef Upah: 1.65 P, 0.275 Tk, 0.028 K.Tk, 0.083 M
    mat_beton = (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)
    upah_beton = (1.65*u_pekerja + 0.275*u_tukang + 0.028*u_k_tukang + 0.083*u_mandor)
    hsp_beton = (mat_beton + upah_beton) * oh
    
    # Pembesian (A.4.1.1.17)
    # Koef: 0.007 P, 0.007 Tk, 0.0007 K.Tk, 0.0004 M
    upah_besi = (0.007*u_pekerja + 0.007*u_tukang + 0.0007*u_k_tukang + 0.0004*u_mandor)
    hsp_besi = (upah_besi + (1.05*p_besi + 0.015*22000)) * oh 
    
    # Bekisting (A.4.1.1.20)
    # Koef: 0.66 P, 0.33 Tk, 0.033 K.Tk, 0.033 M
    upah_bekisting = (0.66*u_pekerja + 0.33*u_tukang + 0.033*u_k_tukang + 0.033*u_mandor)
    hsp_bekisting = (upah_bekisting + (0.045*p_kayu + 0.3*20000)) * oh 

    # Pasangan Batu (A.3.2.1.2)
    # Koef: 1.5 P, 0.75 Tk, 0.075 K.Tk, 0.075 M
    upah_batu = (1.5*u_pekerja + 0.75*u_tukang + 0.075*u_k_tukang + 0.075*u_mandor)
    hsp_batu = (upah_batu + (1.2*p_batu + 163*p_semen + 0.52*p_pasir)) * oh
    
    # Plesteran (A.4.4.2.4)
    upah_plester = (0.3*u_pekerja + 0.15*u_tukang + 0.015*u_k_tukang + 0.015*u_mandor)
    hsp_plester = (upah_plester + (6.24*p_semen + 0.024*p_pasir)) * oh
    
    # Siaran
    upah_siar = (0.15*u_pekerja + 0.075*u_tukang + 0.0075*u_k_tukang + 0.004*u_mandor)
    hsp_siaran = (upah_siar + (3*p_semen + 0.01*p_pasir)) * oh

# --- 4. MAIN UI ---
st.title("🏗️ QS Pro: Analisa Struktur & Biaya (V.4)")
st.caption("Compliance: SNI 2847 (Beton) & Permen PUPR SE 182 (Biaya)")

tab1, tab2, tab3 = st.tabs(["➕ Input Engineering", "📋 Daftar Item", "📊 RAB Detail"])

# === TAB 1 ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas Item")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Saluran Primer Km 0+500")
        
    with col2:
        st.subheader("2. Spesifikasi Teknis")
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0, step=0.1, format="%.2f")
            
            if tipe_kons == "Beton Bertulang":
                c_a, c_b, c_c = st.columns(3)
                h = c_a.number_input("Tinggi H (m)", value=0.8, step=0.01)
                b = c_b.number_input("Lebar B (m)", value=0.6, step=0.01)
                m = c_c.number_input("Talud m", value=0.0, step=0.01)
                
                st.markdown("**Detail Struktur (SNI 2847):**")
                # INPUT BARU: MUTU MATERIAL
                cm1, cm2 = st.columns(2)
                fc = cm1.number_input("Mutu Beton fc' (MPa)", value=20.0, help="Standar K-225 ~ 19.3 MPa")
                fy = cm2.number_input("Mutu Baja fy (MPa)", value=280.0, help="U-24=240, U-40=400")

                cc1, cc2, cc3 = st.columns(3)
                t_cm = cc1.number_input("Tebal (cm)", value=15.0, step=0.1)
                dia = cc2.number_input("Dia. Besi (mm)", value=10.0, step=1.0)
                jarak = cc3.number_input("Jarak (cm)", value=15.0, step=0.5)
                
                # LIVE CALCULATION
                calc = Calculator.hitung_beton_struktur(h, b, m, 1, t_cm, dia, jarak, 2, 5, fc, fy)
                
                # DISPLAY WARNINGS
                st.info(f"📊 **Analisa Ratio Tulangan (Rho):** {calc['rho_data']['act']:.5f}")
                
                col_w1, col_w2 = st.columns(2)
                # Cek Tebal
                if t_cm < calc['t_rekom']:
                    col_w1.error(f"❌ Tebal < Min ({calc['t_rekom']:.1f} cm)")
                else:
                    col_w1.success(f"✅ Tebal Aman")
                
                # Cek Ratio Besi
                status_besi = calc['rho_data']['status']
                if "AMAN" in status_besi:
                    col_w2.success(f"✅ {status_besi}")
                elif "BAHAYA" in status_besi:
                    col_w2.error(f"⚠️ {status_besi} (Min: {calc['rho_data']['min']:.5f})")
                else:
                    col_w2.warning(f"⚠️ {status_besi} (Max: {calc['rho_data']['max']:.5f})")
                
            else: # Batu
                h = st.number_input("Tinggi H (m)", value=0.8, step=0.01)
                l_atas = st.number_input("L. Atas (m)", value=0.3, step=0.01)
                l_bawah = st.number_input("L. Bawah (m)", value=0.4, step=0.01)
                t_lantai = st.number_input("T. Lantai (m)", value=0.2, step=0.01)
                
        else: # Bangunan
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box"])
            w = st.number_input("Lebar (m)", value=1.0, step=0.01)
            h_b = st.number_input("Tinggi (m)", value=1.0, step=0.01)
            p_b = st.number_input("Panjang (m)", value=5.0, step=0.01)

    if st.button("Simpan Item", type="primary"):
        if not nama_item:
            st.warning("Nama wajib diisi!")
        else:
            vol_result = {}
            tipe_final = ""
            if kategori == "Saluran (Linear)":
                if tipe_kons == "Beton Bertulang":
                    vol_result = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 7, fc, fy)
                    tipe_final = "Saluran Beton"
                else:
                    vol_result = Calculator.hitung_pasangan_batu(h, b, 0.2, panjang, l_atas, l_bawah, t_lantai)
                    tipe_final = "Saluran Batu"
            else:
                vol_result = Calculator.hitung_gorong_box(w, h_b, p_b)
                tipe_final = "Gorong-Gorong"
            
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": panjang if kategori=="Saluran (Linear)" else p_b, "vol": vol_result}
            st.session_state['data_proyek'].append(item_data)
            st.success("Tersimpan!")

# === TAB 2: List ===
with tab2:
    if st.session_state['data_proyek']:
        st.dataframe(pd.DataFrame(st.session_state['data_proyek'])[["nama", "tipe", "panjang"]])
        if st.button("Hapus Semua Data"):
            st.session_state['data_proyek'] = []
            st.rerun()

# === TAB 3: RAB DETAIL ===
with tab3:
    st.header("📊 Detail Engineering Estimate (EE)")
    
    if st.session_state['data_proyek']:
        excel_rows = []
        grand_total = 0
        
        map_pekerjaan = {
            "vol_galian": ("Galian Tanah Biasa (SDA T.06.a)", "m3", hsp_galian),
            "vol_timbunan": ("Timbunan Kembali Dipadatkan (SDA T.07.a)", "m3", hsp_timbunan), # NEW ITEM
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
        
        # EXPORT FUNCTION
        def generate_excel():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_ex = pd.DataFrame(excel_rows)
                df_ex.to_excel(writer, index=False, sheet_name='RAB Detail')
            return output.getvalue()

        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V4.xlsx")
    else:
        st.info("Input data dulu di Tab 1")
