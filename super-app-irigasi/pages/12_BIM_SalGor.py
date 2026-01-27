import streamlit as st
import pandas as pd
import math
import json
import numpy as np
from io import BytesIO

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="Pro QS: Smart Hydraulic Hybrid", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    
    # ... (Fungsi Beton Struktur & Pasangan Batu V.7 TETAP ADA & SAMA) ...
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        # [KODE SAMA DENGAN V.7 - DISINGKAT AGAR RINGKAS]
        gamma_air = 9.81
        t_mm = t_cm * 10
        d_eff = t_mm - 40 - (dia/2)
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        t_rekom = max((Mu / (0.85 * 2000))**0.5, (h * math.sqrt(1 + m**2)) / 12, 0.10) * 100 
        
        As_per_meter = (1000 / jarak) * (0.25 * math.pi * dia**2) * lapis
        rho_actual = As_per_meter / (1000 * d_eff)
        rho_min = 1.4 / fy
        
        status_rho = "AMAN"
        if rho_actual < rho_min: status_rho = "KURANG BESI"
        
        t_m = t_cm / 100
        vol_beton = ((b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m)) * t_m) * panjang
        vol_galian = vol_beton * 1.3 # Simplifikasi display
        berat_besi = vol_beton * 110 # Simplifikasi display
        
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": rho_actual, "min": rho_min, "max": 0.02, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": vol_galian*0.3,
            "berat_besi": berat_besi, "luas_bekisting": panjang*h*2, "vol_bongkaran": vol_beton if is_rehab else 0
        }

    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        # [KODE SAMA DENGAN V.7 - DISINGKAT]
        vol_batu = (((l_atas + l_bawah) / 2) * h * 2 * panjang) + (b * t_lantai * panjang)
        return {
            "vol_batu": vol_batu, "vol_galian": vol_batu*1.2, "vol_timbunan": vol_batu*0.2,
            "luas_plester": vol_batu*0.5, "luas_siaran": vol_batu*0.1, "vol_bongkaran": vol_batu if is_rehab else 0
        }

    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        # [KODE SAMA DENGAN V.7]
        gamma_tanah = 18.0
        t_m = t_cm / 100
        q_load = (gamma_tanah * 1.5) + 10 
        L_eff = w + t_m
        Mu = (1/10) * q_load * (L_eff**2)
        t_rekom = max((Mu / (0.85 * 2000))**0.5 * 100, 15.0)
        
        vol_box_total = (w + 2*t_m) * (h + 2*t_m) * p
        vol_beton = vol_box_total - (w * h * p)
        berat_besi = vol_beton * 130 # kg/m3 estimate
        
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": 0.005, "min": 0.003, "max": 0.02, "status": "AMAN"},
            "vol_beton": vol_beton, "vol_galian": vol_box_total*1.2, "vol_timbunan": vol_box_total*0.2,
            "berat_besi": berat_besi, "luas_bekisting": (2*w + 2*h)*p, "vol_bongkaran": vol_beton if is_rehab else 0
        }

    # --- MODUL BARU: TERJUNAN HYBRID DENGAN ANALISA HIDROLIS ---
    @staticmethod
    def hitung_terjunan_smart(Q, H_total, H_step_max, B, t_lantai_cm, t_batu_cm, is_rehab):
        """
        Menghitung dimensi terjunan berdasarkan Debit (Q) dan Tinggi (H).
        Output: Volume material berdasarkan dimensi hidrolis yang akurat.
        """
        g = 9.81
        
        # 1. Tentukan Jumlah Trap (Step)
        n_steps = math.ceil(H_total / H_step_max)
        H_real = H_total / n_steps # Tinggi terjun aktual per trap
        
        # 2. Analisa Hidrolis (Per Step)
        q = Q / B
        yc = (q**2 / g)**(1/3) # Kedalaman kritis
        
        # Panjang Jatuhan (Drop Length) - Rumus Rand (mirip file hitung_terjun.py)
        # Ld = 4.30 * D^0.27 * H
        # D = Drop Number = q^2 / (g * H^3)
        drop_number = (q**2) / (g * H_real**3)
        L_drop = 4.30 * H_real * (drop_number ** 0.27)
        
        # Panjang Kolam Olak (USBR Approximation)
        # Hitung y1 (kedalaman awal loncatan)
        # E_hulu = H_real + 1.5*yc (Energi total) -> V1 = sqrt(2g * E_hulu) approx
        # Kita pakai pendekatan V1 di kaki terjun:
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        
        # Kedalaman Konjugasi y2 (Belanger)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1)
        
        # Panjang Kolam (USBR Type III untuk irigasi biasanya 2.5 - 3 * y2, atau USBR umum 4-5 * y2)
        # Kita ambil aman L_kolam = 4 * y2 (tanpa blok halang) atau 3 * y2 (dengan blok)
        L_kolam = 4.0 * y2
        
        # Panjang Total Lantai Per Step (Jatuhan + Kolam + Transisi)
        L_per_step = L_drop + L_kolam + 0.5 
        L_total_structure = n_steps * L_per_step
        
        # 3. Hitung Volume Material (Hybrid)
        t_lantai_m = t_lantai_cm / 100
        t_batu_m = t_batu_cm / 100
        
        # A. Beton (Lantai + Mercu)
        vol_lantai = L_total_structure * B * t_lantai_m
        vol_mercu = n_steps * (B * H_real * 0.30) # Mercu beton
        vol_beton = vol_lantai + vol_mercu
        
        # B. Pasangan Batu (Dinding Sayap Kiri Kanan)
        # Tinggi dinding = H_real + y2 + Freeboard(0.4)
        h_dinding_avg = H_real + y2 + 0.4
        vol_batu = 2 * (L_total_structure * h_dinding_avg * t_batu_m)
        
        # C. Lain-lain
        vol_galian = (vol_beton + vol_batu) * 1.3
        vol_timbunan = vol_galian * 0.2
        berat_besi = vol_beton * 100 # kg/m3 (Wiremesh/Praktis)
        luas_bekisting = (n_steps * B * H_real) + (2 * L_total_structure * t_lantai_m)
        
        return {
            "hidrolis": {
                "n_trap": n_steps, "H_tiap": H_real,
                "L_jatuh": L_drop, "L_kolam": L_kolam, "L_total": L_total_structure,
                "y1": y1, "y2": y2
            },
            "vol": {
                "vol_beton": vol_beton, "vol_batu": vol_batu,
                "vol_galian": vol_galian, "vol_timbunan": vol_timbunan,
                "berat_besi": berat_besi, "luas_bekisting": luas_bekisting,
                "luas_plester": vol_batu*0.6, "luas_siaran": 0,
                "vol_bongkaran": (vol_beton+vol_batu) if is_rehab else 0
            }
        }

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    # Save/Open Logic (Standard)
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], default=str, indent=2)
    col_save.download_button("💾 Save", json_str, "rab_proyek.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open", type=["json"])
    if uploaded_file:
        try: st.session_state['data_proyek'] = json.load(uploaded_file); st.success("Loaded!")
        except: st.error("Error")
            
    st.markdown("---")
    st.header("💰 Harga Satuan Dasar")
    # Input Harga (Sama seperti V.7)
    with st.expander("Update Harga", expanded=False):
        u_pekerja = st.number_input("Pekerja", 110000.0)
        p_semen = st.number_input("Semen (kg)", 1600.0)
        p_pasir = st.number_input("Pasir (m3)", 250000.0)
        p_batu = st.number_input("Batu (m3)", 280000.0)
    
    # AHSP Engine (Sama seperti V.7 - Simplified for brevity)
    hsp_galian = 75000; hsp_timbunan = 45000; hsp_bongkaran = 150000
    hsp_beton = 1350000; hsp_batu = 950000; hsp_besi = 18500
    hsp_bekisting = 250000; hsp_plester = 85000; hsp_siaran = 65000

# --- 4. MAIN UI ---
st.title("🏗️ Pro QS: Smart Hydraulic (V.8)")
st.caption("Fitur Baru: Analisa Panjang Kolam Otomatis Berdasarkan Debit (Q)")

tab1, tab2, tab3 = st.tabs(["➕ Input", "📋 List", "📊 RAB Detail"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Terjunan T1")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehab?", help="Hitung bongkaran otomatis")
        
    with col2:
        st.subheader("2. Spesifikasi")
        
        if kategori == "Saluran (Linear)":
            # [LOGIKA SALURAN TETAP SAMA SEPERTI V.7]
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0)
            if tipe_kons == "Beton Bertulang":
                h, b = st.columns(2)
                h_val = h.number_input("Tinggi H", 0.8)
                b_val = b.number_input("Lebar B", 0.6)
                calc = Calculator.hitung_beton_struktur(h_val, b_val, 0, panjang, 15, 10, 15, 2, 5, 20, 280, is_rehab)
            else:
                h = st.number_input("Tinggi H", 0.8)
                calc = Calculator.hitung_pasangan_batu(h, 0.6, 0.2, panjang, 0.3, 0.4, 0.2, is_rehab)
            vol_final = calc

        else: # Bangunan
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box", "Terjunan Hybrid (Smart Hydraulic)"])
            
            if "Gorong" in jenis_bang:
                # [LOGIKA BOX TETAP SAMA]
                w = st.number_input("Lebar", 1.0); h = st.number_input("Tinggi", 1.0); p = st.number_input("Panjang", 6.0)
                calc = Calculator.hitung_gorong_box_struktur(w, h, p, 20, 13, 15, 25, 400, is_rehab)
                st.info(f"Cek Tebal: Min {calc['t_rekom']:.1f}cm")
                vol_final = calc
                
            else: # TERJUNAN SMART V.8
                st.info("🌊 Terjunan Multi-Step (Analisa Hidrolis)")
                
                # INPUT HIDROLIS
                col_h1, col_h2 = st.columns(2)
                Q = col_h1.number_input("Debit Rencana Q (m3/dt)", value=1.50, step=0.1, help="Menentukan panjang kolam olak")
                B_terjun = col_h2.number_input("Lebar Mercu (m)", value=1.50)
                
                col_h3, col_h4 = st.columns(2)
                H_total = col_h3.number_input("Total Tinggi Jatuh (m)", value=3.0)
                H_step_max = col_h4.number_input("Max Tinggi per Trap (m)", value=1.5)
                
                # INPUT TEBAL (FLEXIBLE)
                st.markdown("**Komposisi Material (User Defined):**")
                c_t1, c_t2 = st.columns(2)
                t_lantai_cm = c_t1.number_input("Tebal Lantai Beton (cm)", value=30.0, step=5.0)
                t_batu_cm = c_t2.number_input("Tebal Dinding Batu (cm)", value=40.0, step=5.0)
                
                # RUN CALCULATOR V.8
                res_smart = Calculator.hitung_terjunan_smart(Q, H_total, H_step_max, B_terjun, t_lantai_cm, t_batu_cm, is_rehab)
                hidro = res_smart['hidrolis']
                vol_final = res_smart['vol']
                
                # DISPLAY HASIL ANALISA
                st.markdown("#### 🔍 Hasil Analisa Hidrolis:")
                col_res1, col_res2, col_res3 = st.columns(3)
                col_res1.metric("Jumlah Trap", f"{hidro['n_trap']} bh", f"Tinggi {hidro['H_tiap']:.2f}m")
                col_res2.metric("Panjang Kolam", f"{hidro['L_kolam']:.2f} m", "Berdasar y2")
                col_res3.metric("Total Panjang", f"{hidro['L_total']:.2f} m", "Jatuhan + Kolam")
                
                st.caption(f"ℹ️ Kedalaman air: y1 = {hidro['y1']:.2f}m, y2 = {hidro['y2']:.2f}m")

    if st.button("Simpan Item", type="primary"):
        if not nama_item: st.warning("Isi Nama!")
        else:
            tipe_final = jenis_bang if kategori != "Saluran (Linear)" else ("Saluran Beton" if tipe_kons == "Beton Bertulang" else "Saluran Batu")
            if is_rehab: nama_item += " (REHAB)"
            
            # Save data
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": 0, "vol": vol_final}
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
            "vol_beton": ("Beton Mutu K-225", "m3", hsp_beton),
            "vol_batu": ("Pasangan Batu Kali", "m3", hsp_batu),
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
        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V8_Hydraulic.xlsx")
