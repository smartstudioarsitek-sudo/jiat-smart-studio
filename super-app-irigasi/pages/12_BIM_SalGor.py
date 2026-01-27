import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: RAB Detail SDA & CK", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste):
        # A. ANALISA STRUKTUR
        gamma_air = 9.81
        selimut = 0.04
        t_m = t_cm / 100
        
        # Hitung Momen & Tebal
        Mu = 1.6 * (1/6) * gamma_air * (h**3)
        d_lentur = (Mu / (0.85 * 2000))**0.5 
        sisi_miring = h * math.sqrt(1 + m**2)
        t_rekom = max(d_lentur + selimut + 0.006, sisi_miring / 12, 0.10)
        
        # B. VOLUME MATERIAL
        # 1. Beton
        keliling_center = b + 2 * (h * math.sqrt(1+m**2)) + (2 * t_m) 
        vol_beton = (keliling_center * t_m) * panjang
        
        # 2. Galian (SDA: T.06.a) - Ada working space
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + 0.4 
        tinggi_galian = h + t_m + 0.2
        lebar_atas_galian = lebar_bawah_galian + 2 * (m * tinggi_galian) 
        area_galian = ((lebar_bawah_galian + lebar_atas_galian)/2) * tinggi_galian
        vol_galian = area_galian * panjang

        # 3. Timbunan Kembali (SDA: T.07.a)
        # Logika: Tanah Galian dikembalikan menutup sisi samping struktur
        vol_timbunan = max(0, (vol_galian - vol_beton) * 0.4) # Asumsi 40% volume sisa bisa dipadatkan kembali
        
        # 4. Besi (CK: A.4.1.1.17)
        berat_m_lari = 0.00617 * (dia**2)
        keliling_besi = (b + 2*(h*math.sqrt(1+m**2))) 
        jum_potongan = (panjang * 100 / jarak) + 1
        total_berat_besi = (keliling_besi * jum_potongan * lapis * berat_m_lari) * 1.2 * (1 + waste/100)
        
        # 5. Bekisting (CK: A.4.1.1.20)
        luas_bekisting = (2 * sisi_miring * panjang) * 2 

        return {
            "mu": Mu, "t_rekom": t_rekom * 100, 
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "vol_timbunan": vol_timbunan,
            "berat_besi": total_berat_besi,
            "luas_bekisting": luas_bekisting
        }

    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai):
        # Geometri
        area_dinding = ((l_atas + l_bawah) / 2) * h
        vol_dinding = 2 * area_dinding * panjang
        vol_lantai = b * t_lantai * panjang
        
        # 1. Pasangan Batu (SDA: P.01.a)
        vol_batu = vol_dinding + vol_lantai
        
        # 2. Plesteran & Siaran (CK: A.4.4.2)
        sisi_miring = h * math.sqrt(1 + m**2)
        luas_plester = ((2 * sisi_miring) + b) * panjang 
        luas_siaran = (2 * l_atas) * panjang 
        
        # 3. Galian
        vol_galian = vol_batu * 1.25 
        
        # 4. Timbunan
        vol_timbunan = max(0, (vol_galian - vol_batu) * 0.3)
        
        return {
            "mu": 0, "t_rekom": 0,
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
        
        # 1. Beton
        vol_beton = vol_box_total - vol_rongga
        
        # 2. Galian
        vol_galian = vol_box_total * 1.2
        
        # 3. Timbunan
        vol_timbunan = (vol_galian - vol_box_total) * 0.5
        
        # 4. Besi & Bekisting
        berat_besi = vol_beton * 150 
        luas_bekisting = (2*w + 2*h) * p 
        
        return {
            "mu": 0, "t_rekom": 0,
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "vol_timbunan": vol_timbunan,
            "berat_besi": berat_besi,
            "luas_bekisting": luas_bekisting
        }

# --- 3. SIDEBAR: MANAJEMEN FILE & HARGA (PERMEN PUPR) ---
with st.sidebar:
    st.title("📂 Manajemen Proyek")
    
    # --- FITUR SAVE/OPEN ---
    col_save, col_load = st.columns(2)
    json_str = json.dumps(st.session_state['data_proyek'], indent=2)
    col_save.download_button("💾 Save Data", json_str, "proyek_rab_data.json", "application/json")
    uploaded_file = st.file_uploader("📂 Open Data", type=["json"])
    if uploaded_file:
        try:
            st.session_state['data_proyek'] = json.load(uploaded_file)
            st.success("Loaded!")
        except: st.error("Error loading file")
            
    st.markdown("---")
    
    # --- INPUT HARGA DASAR ---
    st.header("💰 Harga Satuan Dasar")
    st.caption("Referensi: Permen PUPR No. 1 Tahun 2022 / SE 182")
    
    with st.expander("1. Upah Kerja", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", 110000.0, step=1000.0, format="%.0f")
        u_tukang = st.number_input("Tukang (OH)", 135000.0, step=1000.0, format="%.0f")
        u_mandor = st.number_input("Mandor (OH)", 160000.0, step=1000.0, format="%.0f")
        overhead = st.slider("Overhead & Profit %", 0, 15, 10) # Max 15% sesuai SE
    
    with st.expander("2. Material Alam & Pabrikasi", expanded=False):
        p_semen = st.number_input("Semen (kg)", 1600.0, step=100.0, format="%.0f")
        p_pasir = st.number_input("Pasir Beton (m3)", 250000.0, step=1000.0, format="%.0f")
        p_split = st.number_input("Kerikil/Split (m3)", 350000.0, step=1000.0, format="%.0f")
        p_batu = st.number_input("Batu Belah (m3)", 280000.0, step=1000.0, format="%.0f")
        p_besi = st.number_input("Besi Beton (kg)", 14500.0, step=50.0, format="%.0f")
        p_kayu = st.number_input("Kayu Bekisting (m3)", 3000000.0, step=10000.0, format="%.0f")

    # --- ENGINE AHSP (SDA & CK MAPPING) ---
    oh = 1 + (overhead/100)
    
    # A.2.3.1.1 / T.06.a.1 Penggalian Tanah Biasa (Manual)
    # Koef: 0.75 Pekerja, 0.025 Mandor
    hsp_galian = ((0.75*u_pekerja) + (0.025*u_mandor)) * oh
    
    # T.07.a Timbunan Tanah Kembali (Manual)
    # Koef: 0.33 Pekerja, 0.01 Mandor
    hsp_timbunan = ((0.33*u_pekerja) + (0.01*u_mandor)) * oh

    # A.4.1.1.7 Beton Mutu f'c=19.3 MPa (K-225)
    # Koef Bahan: Semen 371kg, Pasir 0.49m3, Kerikil 0.77m3
    # Koef Upah: 1.65 Pekerja, 0.275 Tukang, etc
    mat_beton = (371*p_semen + 0.4986*p_pasir + 0.7756*p_split)
    upah_beton = (1.65*u_pekerja + 0.275*u_tukang + 0.083*u_mandor)
    hsp_beton = (mat_beton + upah_beton) * oh
    
    # A.4.1.1.17 Pembesian dengan Besi Polos/Ulir
    # Koef: 1.05 Besi, 0.015 Kawat, 0.007 Pekerja/Tukang
    hsp_besi = ((0.007*u_pekerja + 0.007*u_tukang + 0.0004*u_mandor) + 
                (1.05*p_besi + 0.015*22000)) * oh 
    
    # A.4.1.1.20 Bekisting (2x Pakai)
    hsp_bekisting = ((0.66*u_pekerja + 0.33*u_tukang + 0.033*u_mandor) + 
                     (0.045*p_kayu + 0.3*20000)) * oh 

    # A.3.2.1.2 Pasangan Batu
    hsp_batu = ((1.5*u_pekerja + 0.75*u_tukang + 0.075*u_mandor) + 
                (1.2*p_batu + 163*p_semen + 0.52*p_pasir)) * oh
    
    # A.4.4.2.4 Plesteran 1:3
    hsp_plester = ((0.3*u_pekerja + 0.15*u_tukang + 0.015*u_mandor) + 
                   (6.24*p_semen + 0.024*p_pasir)) * oh
    
    hsp_siaran = ((0.15*u_pekerja + 0.075*u_tukang) + (3*p_semen + 0.01*p_pasir)) * oh

# --- 4. MAIN UI ---
st.title("🏗️ Integrated QS Estimator V.3 (SDA & CK)")
st.markdown("Referensi: **Permen PUPR Bidang SDA & Cipta Karya** | Fitur: **Detail Breakdown per Item**")

tab1, tab2, tab3 = st.tabs(["➕ Input Data", "📋 Daftar Item", "📊 RAB Detail & Rekap"])

# === TAB 1 & 2 (Logic Input tetap sama agar aman) ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas Item")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Contoh: Saluran Sekunder Ruas 1 (S1)")
        
    with col2:
        st.subheader("2. Spesifikasi")
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", value=50.0, step=0.1, format="%.2f", min_value=0.0)
            
            if tipe_kons == "Beton Bertulang":
                c_a, c_b, c_c = st.columns(3)
                h = c_a.number_input("Tinggi H (m)", value=0.8, step=0.01, format="%.3f")
                b = c_b.number_input("Lebar B (m)", value=0.6, step=0.01, format="%.3f")
                m = c_c.number_input("Talud m", value=0.0, step=0.01, format="%.2f")
                
                st.markdown("**Detail Penulangan:**")
                cc1, cc2, cc3 = st.columns(3)
                t_cm = cc1.number_input("Tebal (cm)", value=15.0, step=0.1)
                dia = cc2.number_input("Dia. Besi (mm)", value=10.0, step=1.0)
                jarak = cc3.number_input("Jarak (cm)", value=15.0, step=0.5)
                
                calc_temp = Calculator.hitung_beton_struktur(h, b, m, 1, t_cm, dia, jarak, 2, 5)
                if calc_temp['mu'] > 0:
                     if t_cm < calc_temp['t_rekom']:
                        st.error(f"⚠️ Tebal {t_cm} cm < Min {calc_temp['t_rekom']:.1f} cm (SNI 2847)")
                
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

    if st.button("Simpan Item ke Daftar", type="primary"):
        if not nama_item:
            st.warning("Nama item wajib diisi!")
        else:
            vol_result = {}
            tipe_final = ""
            if kategori == "Saluran (Linear)":
                if tipe_kons == "Beton Bertulang":
                    vol_result = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 7)
                    tipe_final = "Saluran Beton"
                else:
                    vol_result = Calculator.hitung_pasangan_batu(h, b, 0.2, panjang, l_atas, l_bawah, t_lantai)
                    tipe_final = "Saluran Batu"
            else:
                vol_result = Calculator.hitung_gorong_box(w, h_b, p_b)
                tipe_final = "Gorong-Gorong"
            
            item_data = {
                "nama": nama_item,
                "tipe": tipe_final,
                "panjang": panjang if kategori == "Saluran (Linear)" else p_b,
                "vol": vol_result
            }
            st.session_state['data_proyek'].append(item_data)
            st.success("✅ Tersimpan!")

with tab2:
    if st.session_state['data_proyek']:
        st.dataframe(pd.DataFrame(st.session_state['data_proyek'])[["nama", "tipe", "panjang"]])
        if st.button("Hapus Semua"):
            st.session_state['data_proyek'] = []
            st.rerun()

# === TAB 3: RAB DETAIL (UPGRADE UTAMA) ===
with tab3:
    st.header("📊 Detail Engineering Estimate (EE)")
    
    if not st.session_state['data_proyek']:
        st.info("Belum ada data input.")
    else:
        # List untuk menampung semua baris excel nanti
        excel_rows = []
        grand_total = 0
        
        # Mapping nama variabel volume ke Nama Pekerjaan & Harga Satuan
        map_pekerjaan = {
            "vol_galian": ("Galian Tanah Biasa (SDA T.06.a)", "m3", hsp_galian),
            "vol_timbunan": ("Timbunan Kembali Dipadatkan (SDA T.07.a)", "m3", hsp_timbunan),
            "vol_beton": ("Beton Mutu K-225 (SDA F.03.c / CK A.4.1.1.7)", "m3", hsp_beton),
            "berat_besi": ("Pembesian Ulir/Polos (CK A.4.1.1.17)", "kg", hsp_besi),
            "luas_bekisting": ("Pasang Bekisting (CK A.4.1.1.20)", "m2", hsp_bekisting),
            "vol_batu": ("Pasangan Batu Kali 1:4 (SDA P.01.a)", "m3", hsp_batu),
            "luas_plester": ("Plesteran 1:3 + Acian (CK A.4.4.2.4)", "m2", hsp_plester),
            "luas_siaran": ("Siaran 1:2 (CK A.4.4.2.27)", "m2", hsp_siaran),
        }

        # ITERASI PER ITEM PROYEK (LOOPING S1, S2, dst)
        for i, item in enumerate(st.session_state['data_proyek']):
            nama = item['nama']
            tipe = item['tipe']
            vol_data = item['vol']
            
            with st.expander(f"📍 {i+1}. {nama} ({tipe})", expanded=True):
                item_rows = []
                # Loop setiap komponen volume dalam item tersebut
                for key, val in vol_data.items():
                    if key in map_pekerjaan and val > 0.001:
                        uraian, sat, harga = map_pekerjaan[key]
                        jumlah = val * harga
                        
                        # Data untuk Tabel UI
                        item_rows.append({
                            "Uraian Pekerjaan": uraian,
                            "Volume": val,
                            "Satuan": sat,
                            "Harga Satuan (Rp)": harga,
                            "Jumlah Harga (Rp)": jumlah
                        })
                        
                        # Data untuk Excel (Flat)
                        excel_rows.append({
                            "No Item": i+1,
                            "Nama Item": nama,
                            "Uraian Pekerjaan": uraian,
                            "Volume": val,
                            "Satuan": sat,
                            "Harga Satuan": harga,
                            "Total Harga": jumlah
                        })
                
                # Tampilkan Tabel per Item
                df_item = pd.DataFrame(item_rows)
                subtotal = df_item["Jumlah Harga (Rp)"].sum()
                grand_total += subtotal
                
                st.dataframe(df_item.style.format({
                    "Volume": "{:.3f}", 
                    "Harga Satuan (Rp)": "{:,.0f}", 
                    "Jumlah Harga (Rp)": "{:,.0f}"
                }), use_container_width=True)
                
                st.markdown(f"**Subtotal {nama}: Rp {subtotal:,.0f}**")

        # TOTAL KESELURUHAN
        st.divider()
        ppn = grand_total * 0.11
        st.markdown(f"### 💰 Rekapitulasi Total Proyek")
        st.markdown(f"**Total Fisik: Rp {grand_total:,.0f}**")
        st.markdown(f"**PPN 11%: Rp {ppn:,.0f}**")
        st.success(f"# Grand Total: Rp {grand_total + ppn:,.0f}")

        # --- EXPORT EXCEL ADVANCED (BoQ Format) ---
        def generate_boq_excel(rows):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Format Uang
                money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'})
                border_fmt = workbook.add_format({'border': 1})
                
                # Sheet 1: Bill of Quantities
                ws = workbook.add_worksheet("RAB Detail")
                headers = ["No", "Nama Item", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan", "Total Harga"]
                
                # Write Header
                for col, h in enumerate(headers):
                    ws.write(0, col, h, header_fmt)
                
                # Write Data
                df_ex = pd.DataFrame(rows)
                current_row = 1
                for _, row in df_ex.iterrows():
                    ws.write(current_row, 0, row['No Item'], border_fmt)
                    ws.write(current_row, 1, row['Nama Item'], border_fmt)
                    ws.write(current_row, 2, row['Uraian Pekerjaan'], border_fmt)
                    ws.write(current_row, 3, row['Volume'], border_fmt)
                    ws.write(current_row, 4, row['Satuan'], border_fmt)
                    ws.write(current_row, 5, row['Harga Satuan'], money_fmt)
                    ws.write(current_row, 6, row['Total Harga'], money_fmt)
                    current_row += 1
                
                # Write Footer
                ws.write(current_row, 5, "GRAND TOTAL", header_fmt)
                ws.write(current_row, 6, grand_total, money_fmt)
                
                # Adjust Width
                ws.set_column(1, 1, 25) # Nama Item
                ws.set_column(2, 2, 40) # Uraian
                ws.set_column(5, 6, 15) # Harga
                
            return output.getvalue()

        st.download_button("📥 Download RAB Detail (BoQ)", generate_boq_excel(excel_rows), "RAB_Detail_Proyek.xlsx")
