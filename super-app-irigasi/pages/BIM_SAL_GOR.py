import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# ==========================================
# 1. KONFIGURASI & ENGINE HARGA (AHSP)
# ==========================================
st.set_page_config(page_title="Pro QS: Ultimate Flexible V.10", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

def hitung_hsp_dinamis(upah, material, overhead):
    """
    Menghitung Harga Satuan Pekerjaan (HSP) Realtime
    """
    oh = 1 + (overhead/100)
    u = upah
    m = material
    
    # 1. Galian & Timbunan (SDA)
    hsp_galian = ((0.75 * u['pekerja']) + (0.025 * u['mandor'])) * oh
    hsp_timbunan = ((0.33 * u['pekerja']) + (0.01 * u['mandor'])) * oh
    hsp_bongkaran = ((2.0 * u['pekerja']) + (0.1 * u['mandor'])) * oh
    
    # 2. Beton K-225 (Manual A.4.1.1.7)
    mat_beton = (371*m['semen'] + 0.4986*m['pasir'] + 0.7756*m['split'])
    upah_beton = (1.65*u['pekerja'] + 0.275*u['tukang'] + 0.028*u['k_tukang'] + 0.083*u['mandor'])
    hsp_beton = (mat_beton + upah_beton) * oh
    
    # 3. Pembesian (1 kg)
    upah_besi = (0.007*u['pekerja'] + 0.007*u['tukang'] + 0.0007*u['k_tukang'] + 0.0004*u['mandor'])
    hsp_besi = (upah_besi + (1.05*m['besi'] + 0.015*22000)) * oh 
    
    # 4. Bekisting (1 m2)
    upah_bekisting = (0.66*u['pekerja'] + 0.33*u['tukang'] + 0.033*u['k_tukang'] + 0.033*u['mandor'])
    hsp_bekisting = (upah_bekisting + (0.045*m['kayu'] + 0.3*20000)) * oh 

    # 5. Pasangan Batu (1 m3)
    upah_batu = (1.5*u['pekerja'] + 0.75*u['tukang'] + 0.075*u['k_tukang'] + 0.075*u['mandor'])
    hsp_batu = (upah_batu + (1.2*m['batu'] + 163*m['semen'] + 0.52*m['pasir'])) * oh
    
    # 6. Plesteran (1 m2)
    upah_plester = (0.3*u['pekerja'] + 0.15*u['tukang'] + 0.015*u['k_tukang'] + 0.015*u['mandor'])
    hsp_plester = (upah_plester + (6.24*m['semen'] + 0.024*m['pasir'])) * oh
    
    # 7. Siaran (1 m2)
    upah_siar = (0.15*u['pekerja'] + 0.075*u['tukang'] + 0.0075*u['k_tukang'] + 0.004*u['mandor'])
    hsp_siaran = (upah_siar + (3*m['semen'] + 0.01*m['pasir'])) * oh
    
    return {
        "hsp_galian": hsp_galian, "hsp_timbunan": hsp_timbunan, "hsp_bongkaran": hsp_bongkaran,
        "hsp_beton": hsp_beton, "hsp_besi": hsp_besi, "hsp_bekisting": hsp_bekisting,
        "hsp_batu": hsp_batu, "hsp_plester": hsp_plester, "hsp_siaran": hsp_siaran
    }

# ==========================================
# 2. CALCULATOR ENGINEERING (LOGIKA LENGKAP)
# ==========================================
class Calculator:
    
    # --- MODUL 1: SALURAN BETON (Cek Struktur) ---
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        # A. STRUKTUR
        gamma_air = 9.81
        t_mm = t_cm * 10
        d_eff = t_mm - 40 - (dia/2) # Selimut 40mm
        
        # Momen Mu
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        
        # Cek Tebal Min (Geser & Lentur)
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, sisi_miring / 12, 0.10) * 100 
        
        # Cek Rasio Besi
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        Ac_per_meter = 1000 * d_eff
        rho_actual = As_per_meter / Ac_per_meter
        rho_min = 1.4 / fy
        
        # Batas Max (Simplified SNI)
        beta1 = 0.85 if fc <= 28 else max(0.65, 0.85 - 0.05 * (fc - 28) / 7)
        rho_max = 0.75 * (0.85 * beta1 * fc / fy) * (600 / (600 + fy))
        
        status_rho = "AMAN"
        if rho_actual < rho_min: status_rho = "KURANG BESI (BAHAYA)"
        elif rho_actual > rho_max: status_rho = "BOROS BESI"

        # B. VOLUME
        t_m = t_cm / 100
        # Volume Beton (Metode Centerline)
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) 
        vol_beton = (keliling_center * t_m) * panjang
        
        # Galian (Ada working space)
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) 
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang
        
        vol_timbunan = max(0, (vol_galian - vol_beton) * 0.45)
        
        # Besi
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

    # --- MODUL 2: SALURAN BATU (Gravitasi) ---
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

    # --- MODUL 3: BOX CULVERT (Struktur Frame) ---
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        # Analisa Struktur Box
        gamma_tanah = 18.0
        q_load = (gamma_tanah * 1.5) + 10 # Beban Tanah + LL
        t_m = t_cm / 100
        L_eff = w + t_m
        
        # Momen Pendekatan
        Mu = (1/10) * q_load * (L_eff**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5 * 100, L_eff/12 * 100, 15.0)
        
        # Cek Rho
        d_eff = (t_cm * 10) - 40 - (dia/2)
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * 2 # 2 Lapis
        Ac_per_meter = 1000 * d_eff
        rho = As_per_meter / Ac_per_meter
        rho_min = 1.4/fy
        status_rho = "AMAN" if rho > rho_min else "KURANG BESI"

        # Volume
        vol_box_total = (w + 2*t_m) * (h + 2*t_m) * p
        vol_rongga = w * h * p
        vol_beton = vol_box_total - vol_rongga
        
        vol_galian = vol_box_total * 1.2
        vol_timbunan = (vol_galian - vol_box_total) * 0.5
        
        # Besi
        berat_m_lari = 0.006165 * (dia**2)
        keliling_besi = 2 * ((w + 2*t_m) + (h + 2*t_m)) * 2 
        jum_potongan = (p * 100 / jarak) + 1
        berat_besi = (keliling_besi * jum_potongan * berat_m_lari) * 1.25 # Overlap & Kait
        
        luas_bekisting = (2*w + 2*h) * p
        vol_bongkaran = vol_beton if is_rehab else 0
        
        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho, "min": rho_min, "max": 0.025, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi, "luas_bekisting": luas_bekisting,
            "vol_bongkaran": vol_bongkaran
        }

    # --- MODUL 4: TERJUNAN FLEXIBLE (PILIHAN MATERIAL BEBAS) ---
    @staticmethod
    def hitung_terjunan_flexible(Q, H_total, H_step_max, B, mat_lantai, t_lantai_cm, mat_dinding, t_dinding_cm, h_dinding_input, is_rehab):
        g = 9.81
        
        # 1. Geometri Trap
        n_steps = math.ceil(H_total / H_step_max)
        H_real = H_total / n_steps
        
        # 2. Analisa Hidrolis (Smart Hydraulic)
        q = Q / B
        drop_number = (q**2) / (g * H_real**3)
        L_drop = 4.30 * H_real * (drop_number ** 0.27)
        
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1)
        L_kolam = 4.0 * y2
        
        L_per_step = L_drop + L_kolam + 0.5
        L_total = n_steps * L_per_step
        
        # 3. Safety Check
        warnings = []
        h_min_req = H_real + y2 + 0.4 
        if h_dinding_input < h_min_req:
            warnings.append(f"❌ Tinggi Dinding Kurang! (Input: {h_dinding_input}m < Min: {h_min_req:.2f}m)")
        
        t_min_lantai = 20.0 if mat_lantai == "Beton" else 30.0
        if t_lantai_cm < t_min_lantai:
             warnings.append(f"❌ Tebal Lantai Riskan! (Input: {t_lantai_cm}cm < Saran: {t_min_lantai}cm)")

        # 4. Volume Calculation (LOGIKA HYBRID)
        vol_beton = 0
        vol_batu = 0
        t_lantai_m = t_lantai_cm / 100
        t_dinding_m = t_dinding_cm / 100
        
        # -- LANTAI --
        v_lantai = L_total * B * t_lantai_m
        if mat_lantai == "Beton": vol_beton += v_lantai
        else: vol_batu += v_lantai
        
        # -- MERCU (Selalu Beton agar awet) --
        v_mercu = n_steps * (B * H_real * 0.30)
        vol_beton += v_mercu 
        
        # -- DINDING --
        v_dinding = 2 * (L_total * h_dinding_input * t_dinding_m)
        if mat_dinding == "Beton": vol_beton += v_dinding
        else: vol_batu += v_dinding
        
        # Output Lain
        vol_galian = (vol_beton + vol_batu) * 1.3
        vol_timbunan = vol_galian * 0.2
        
        # Besi (Hanya jika ada volume beton)
        berat_besi = vol_beton * 100 if vol_beton > 0 else 0
        
        # Bekisting (Hanya sisi beton)
        luas_bekisting = 0
        if mat_lantai == "Beton": luas_bekisting += (2 * L_total * t_lantai_m)
        if mat_dinding == "Beton": luas_bekisting += (2 * L_total * h_dinding_input)
        luas_bekisting += (n_steps * B * H_real) # Mercu
        
        # Plesteran (Hanya sisi batu)
        luas_plester = 0
        if mat_dinding == "Batu": luas_plester += (2 * L_total * h_dinding_input)
        
        vol_bongkaran = (vol_beton + vol_batu) if is_rehab else 0
        
        return {
            "hidrolis": {"n_trap": n_steps, "L_kolam": L_kolam, "y2": y2, "h_min": h_min_req},
            "warnings": warnings,
            "vol": {
                "vol_beton": vol_beton, "vol_batu": vol_batu,
                "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
                "berat_besi": berat_besi, "luas_bekisting": luas_bekisting,
                "luas_plester": luas_plester, "luas_siaran": 0,
                "vol_bongkaran": vol_bongkaran
            }
        }

# ==========================================
# 3. USER INTERFACE (STREAMLIT)
# ==========================================
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    
    # Save/Open
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button("💾 Save", json_str, "rab_proyek.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open", type=["json"])
    if uploaded_file:
        try: st.session_state['data_proyek'] = json.load(uploaded_file); st.success("Loaded!")
        except: st.error("Error")
            
    st.markdown("---")
    st.header("💰 Harga Satuan Dasar")
    
    with st.expander("Update Harga", expanded=True):
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

    # Hitung HSP
    hsp = hitung_hsp_dinamis(
        {'pekerja': u_pekerja, 'tukang': u_tukang, 'k_tukang': u_k_tukang, 'mandor': u_mandor},
        {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'batu': p_batu, 'besi': p_besi, 'kayu': p_kayu},
        overhead
    )

st.title("🏗️ Pro QS: Ultimate Edition (V.10)")
st.caption("Fitur Lengkap: Saluran, Box Culvert, Terjunan Flexible (Pilih Material), Rehab")

tab1, tab2, tab3 = st.tabs(["➕ Input Data", "📋 List", "📊 RAB Detail"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Unit"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Saluran S1 / Terjunan T1")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehab?", help="Hitung bongkaran otomatis")
        
    with col2:
        st.subheader("2. Spesifikasi")
        vol_final = {}
        
        # --- A. SALURAN ---
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0)
            
            if tipe_kons == "Beton Bertulang":
                c1, c2 = st.columns(2)
                h = c1.number_input("Tinggi H", 0.8); b = c2.number_input("Lebar B", 0.6)
                m_talud = st.number_input("Talud m", 0.0)
                
                st.markdown("**Struktur:**")
                fc = st.number_input("fc' (MPa)", 20.0)
                t_cm = st.number_input("Tebal (cm)", 15.0)
                dia = st.number_input("Dia Besi (mm)", 10.0)
                jarak = st.number_input("Jarak (cm)", 15.0)
                
                calc = Calculator.hitung_beton_struktur(h, b, m_talud, panjang, t_cm, dia, jarak, 2, 5, fc, 280, is_rehab)
                
                # Feedback UI
                if t_cm < calc['t_rekom']: st.error(f"❌ Tebal Kurang (Min {calc['t_rekom']:.1f}cm)")
                else: st.success("✅ Tebal Aman")
                st.info(f"Rasio Besi: {calc['rho_data']['status']}")
                vol_final = calc
                
            else: # Batu
                h = st.number_input("Tinggi H", 0.8)
                l_atas = st.number_input("L. Atas", 0.3)
                l_bawah = st.number_input("L. Bawah", 0.4)
                vol_final = Calculator.hitung_pasangan_batu(h, 0.6, 0.2, panjang, l_atas, l_bawah, 0.2, is_rehab)

        # --- B. BANGUNAN ---
        else:
            jenis_bang = st.selectbox("Jenis", ["Box Culvert (Struktur)", "Terjunan Flexible (Pilih Material)"])
            
            if "Box" in jenis_bang:
                w = st.number_input("Lebar", 1.0); h = st.number_input("Tinggi", 1.0); p = st.number_input("Panjang", 6.0)
                t_cm = st.number_input("Tebal Beton (cm)", 20.0)
                
                # Parameter Struktur Box
                fc_box = st.number_input("Mutu Beton fc'", 25.0)
                calc = Calculator.hitung_gorong_box_struktur(w, h, p, t_cm, 13, 15, fc_box, 400, is_rehab)
                
                if t_cm < calc['t_rekom']: st.error(f"❌ Tebal Kurang (Min {calc['t_rekom']:.1f}cm)")
                else: st.success("✅ Tebal Aman")
                vol_final = calc
                
            else: # TERJUNAN FLEXIBLE
                st.info("🌊 Desain Terjunan: User Control (V.10)")
                
                # 1. Hidrolis
                c_h1, c_h2 = st.columns(2)
                Q = c_h1.number_input("Debit Q (m3/dt)", 1.5)
                H_tot = c_h2.number_input("Tinggi Jatuh Total (m)", 3.0)
                B = st.number_input("Lebar Mercu (m)", 1.5)
                
                st.markdown("---")
                # 2. Material & Dimensi Manual
                st.write("**🔧 Spesifikasi Material & Dimensi**")
                
                # KOLOM 1: LANTAI
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Bagian Dasar / Lantai")
                    mat_lantai = st.selectbox("Material Lantai", ["Beton", "Batu"])
                    t_lantai = st.number_input(f"Tebal Lantai {mat_lantai} (cm)", value=30.0, step=5.0)
                
                # KOLOM 2: DINDING
                with c2:
                    st.caption("Bagian Dinding Sayap")
                    mat_dinding = st.selectbox("Material Dinding", ["Batu", "Beton"], index=0)
                    t_dinding = st.number_input(f"Tebal Dinding {mat_dinding} (cm)", value=40.0, step=5.0)
                
                h_dinding_manual = st.number_input("Tinggi Dinding (m)", value=2.0, step=0.1)
                
                # Calculate
                res = Calculator.hitung_terjunan_flexible(Q, H_tot, 1.5, B, mat_lantai, t_lantai, mat_dinding, t_dinding, h_dinding_manual, is_rehab)
                
                # Warning System
                if res['warnings']:
                    for w in res['warnings']: st.error(w)
                else:
                    st.success("✅ Desain Aman!")
                
                st.caption(f"ℹ️ Min. Tinggi Dinding Hidrolis = {res['hidrolis']['h_min']:.2f} m")
                vol_final = res['vol']

    if st.button("Simpan Item", type="primary"):
        if not nama_item: st.warning("Nama wajib diisi")
        else:
            tipe_final = jenis_bang if kategori != "Saluran (Linear)" else (tipe_kons)
            if is_rehab: nama_item += " (REHAB)"
            
            item_data = {"nama": nama_item, "tipe": tipe_final, "vol": vol_final}
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
        rows = []
        map_job = {
            "vol_beton": ("Beton K-225", hsp['hsp_beton']),
            "vol_batu": ("Pasangan Batu", hsp['hsp_batu']),
            "vol_galian": ("Galian Tanah", hsp['hsp_galian']),
            "vol_timbunan": ("Timbunan Kembali", hsp['hsp_timbunan']),
            "berat_besi": ("Pembesian", hsp['hsp_besi']),
            "luas_bekisting": ("Bekisting", hsp['hsp_bekisting']),
            "luas_plester": ("Plesteran", hsp['hsp_plester']),
            "luas_siaran": ("Siaran", hsp['hsp_siaran']),
            "vol_bongkaran": ("Bongkaran", hsp['hsp_bongkaran'])
        }
        
        for item in st.session_state['data_proyek']:
            for k, v in item['vol'].items():
                if k in map_job and v > 0.001:
                    rows.append({"Item": item['nama'], "Uraian": map_job[k][0], "Vol": v, "H.Sat": map_job[k][1], "Total": v*map_job[k][1]})
        
        df_rab = pd.DataFrame(rows)
        if not df_rab.empty:
            st.dataframe(df_rab.style.format({"Vol": "{:.3f}", "H.Sat": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
            st.metric("Total Biaya", f"Rp {df_rab['Total'].sum():,.0f}")
            
            def generate_excel():
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_rab.to_excel(writer, index=False, sheet_name='RAB Detail')
                return output.getvalue()
            st.download_button("📥 Download Excel", generate_excel(), "RAB_V10_Flexible.xlsx")
        else:
            st.info("Belum ada volume pekerjaan.")
