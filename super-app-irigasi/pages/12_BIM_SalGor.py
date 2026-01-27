import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: AHSP Master 2025", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY AHSP & KOEFISIEN (The Brain of Pricing) ---
class AHSPLibrary:
    """
    Menyimpan Database Koefisien sesuai SNI/Permen PUPR.
    Struktur: {Kode_Item: {Komponen: [{Nama, Satuan, Koefisien, Kategori}]}}
    """
    DATA = {
        "Galian": {
            "nama": "A.2.3.1.1. Galian Tanah Biasa sedalam s.d 1 m",
            "satuan": "m3",
            "komponen": [
                {"tipe": "Upah", "item": "Pekerja", "koef": 0.750},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.025}
            ]
        },
        "Timbunan": {
            "nama": "A.2.3.1.9. Timbunan Tanah Kembali",
            "satuan": "m3",
            "komponen": [
                {"tipe": "Upah", "item": "Pekerja", "koef": 0.330},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.010} # Asumsi pengawasan
            ]
        },
        "Beton K225": {
            "nama": "A.4.1.1.7. Membuat 1 m3 Beton Mutu f'c=19.3 MPa (K-225)",
            "satuan": "m3",
            "komponen": [
                {"tipe": "Bahan", "item": "Semen PC", "koef": 371.0}, # kg
                {"tipe": "Bahan", "item": "Pasir Beton", "koef": 0.4986}, # Konversi m3
                {"tipe": "Bahan", "item": "Kerikil/Split", "koef": 0.7756}, # Konversi m3
                {"tipe": "Upah", "item": "Pekerja", "koef": 1.650},
                {"tipe": "Upah", "item": "Tukang Batu", "koef": 0.275},
                {"tipe": "Upah", "item": "Kepala Tukang", "koef": 0.028},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.083}
            ]
        },
        "Pasangan Batu": {
            "nama": "A.3.2.1.2. Pasangan Batu Belah Camp. 1 SP : 4 PP",
            "satuan": "m3",
            "komponen": [
                {"tipe": "Bahan", "item": "Batu Belah", "koef": 1.200},
                {"tipe": "Bahan", "item": "Semen PC", "koef": 163.0},
                {"tipe": "Bahan", "item": "Pasir Pasang", "koef": 0.520},
                {"tipe": "Upah", "item": "Pekerja", "koef": 1.500},
                {"tipe": "Upah", "item": "Tukang Batu", "koef": 0.750},
                {"tipe": "Upah", "item": "Kepala Tukang", "koef": 0.075},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.075}
            ]
        },
        "Besi": {
            "nama": "A.4.1.1.17. Pembesian 10 kg dengan Besi Polos/Ulir",
            "satuan": "kg", # Base calculation per kg in output, but AHSP usually per 10kg or 1kg. Here we normalize to 1 kg logic
            "komponen": [
                {"tipe": "Bahan", "item": "Besi Beton", "koef": 1.050}, # Waste 5%
                {"tipe": "Bahan", "item": "Kawat Beton", "koef": 0.015},
                {"tipe": "Upah", "item": "Pekerja", "koef": 0.007},
                {"tipe": "Upah", "item": "Tukang Besi", "koef": 0.007},
                {"tipe": "Upah", "item": "Kepala Tukang", "koef": 0.0007},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.0004}
            ]
        },
        "Bekisting": {
            "nama": "A.4.1.1.20. Pasang Bekisting untuk Saluran/Struktur",
            "satuan": "m2",
            "komponen": [
                {"tipe": "Bahan", "item": "Kayu Kelas III", "koef": 0.045},
                {"tipe": "Bahan", "item": "Paku", "koef": 0.300},
                {"tipe": "Bahan", "item": "Minyak Bekisting", "koef": 0.100},
                {"tipe": "Upah", "item": "Pekerja", "koef": 0.520},
                {"tipe": "Upah", "item": "Tukang Kayu", "koef": 0.260},
                {"tipe": "Upah", "item": "Kepala Tukang", "koef": 0.026},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.026}
            ]
        },
        "Plesteran": {
            "nama": "A.4.4.2.4. Plesteran 1 SP : 3 PP Tebal 15 mm",
            "satuan": "m2",
            "komponen": [
                {"tipe": "Bahan", "item": "Semen PC", "koef": 6.240},
                {"tipe": "Bahan", "item": "Pasir Pasang", "koef": 0.024},
                {"tipe": "Upah", "item": "Pekerja", "koef": 0.300},
                {"tipe": "Upah", "item": "Tukang Batu", "koef": 0.150},
                {"tipe": "Upah", "item": "Kepala Tukang", "koef": 0.015},
                {"tipe": "Upah", "item": "Mandor", "koef": 0.015}
            ]
        },
        "Bongkaran": {
             "nama": "A.2.2.1.9. Pembongkaran Pasangan Dinding Tembok",
             "satuan": "m3",
             "komponen": [
                 {"tipe": "Upah", "item": "Pekerja", "koef": 2.0},
                 {"tipe": "Upah", "item": "Mandor", "koef": 0.1}
             ]
        }
    }

    @staticmethod
    def hitung_harga_satuan(kode_ahsp, harga_dasar, overhead_persen):
        """
        Menghitung HSP berdasarkan harga dasar input user.
        Return: (Total Harga, DataFrame Detail)
        """
        if kode_ahsp not in AHSPLibrary.DATA:
            return 0, None
        
        data_ahsp = AHSPLibrary.DATA[kode_ahsp]
        rows = []
        total_upah = 0
        total_bahan = 0
        
        for komp in data_ahsp['komponen']:
            nama_item = komp['item']
            koef = komp['koef']
            tipe = komp['tipe']
            
            # Mapping nama item AHSP ke variable harga_dasar user
            # Ini mapping sederhana, di sistem real menggunakan ID database
            harga_sat = 0
            if "Pekerja" in nama_item: harga_sat = harga_dasar['u_pekerja']
            elif "Tukang" in nama_item: harga_sat = harga_dasar['u_tukang'] # Generalisir tukang
            elif "Kepala" in nama_item: harga_sat = harga_dasar['u_k_tukang']
            elif "Mandor" in nama_item: harga_sat = harga_dasar['u_mandor']
            elif "Semen" in nama_item: harga_sat = harga_dasar['p_semen']
            elif "Pasir Beton" in nama_item or "Split" in nama_item: 
                 # Pasir beton & split di input user biasanya m3, di AHSP bisa kg atau m3. 
                 # Disini kita asumsi input user sesuai AHSP (m3)
                 harga_sat = harga_dasar['p_split'] if "Split" in nama_item else harga_dasar['p_pasir']
            elif "Pasir Pasang" in nama_item: harga_sat = harga_dasar['p_pasir']
            elif "Batu" in nama_item and tipe == "Bahan": harga_sat = harga_dasar['p_batu']
            elif "Besi" in nama_item: harga_sat = harga_dasar['p_besi']
            elif "Kawat" in nama_item: harga_sat = 22000 # Default/Hardcoded for minor items
            elif "Kayu" in nama_item: harga_sat = harga_dasar['p_kayu']
            elif "Paku" in nama_item: harga_sat = 20000 
            elif "Minyak" in nama_item: harga_sat = 15000
            
            jumlah = koef * harga_sat
            rows.append({
                "Kategori": tipe,
                "Uraian": nama_item,
                "Koefisien": koef,
                "Satuan": "bh/ls/org", # Simplified
                "Harga Satuan": harga_sat,
                "Jumlah Harga": jumlah
            })
            
            if tipe == "Upah": total_upah += jumlah
            else: total_bahan += jumlah
            
        df = pd.DataFrame(rows)
        
        # Hitung Overhead
        total_real = total_upah + total_bahan
        biaya_overhead = total_real * (overhead_persen / 100)
        hsp_final = total_real + biaya_overhead
        
        return hsp_final, df, biaya_overhead

# --- 3. LIBRARY PERHITUNGAN (ENGINEERING CORE - TETAP) ---
class Calculator:
    # (Metode hitung volume tetap sama seperti V.7 Anda, saya hide untuk ringkas)
    # Anda bisa copy-paste method hitung_beton_struktur, hitung_pasangan_batu, dll dari kode lama kesini.
    # Agar kode ini bisa dijalankan langsung, saya buat dummy wrapper singkat.
    
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        # ... (Logika V.7) ...
        # Placeholder logic:
        t_m = t_cm/100
        vol_beton = (b + 2*h)*t_m * panjang
        return {"vol_beton": vol_beton, "berat_besi": vol_beton*100, "luas_bekisting": vol_beton*10, "vol_galian": vol_beton*1.2, "vol_timbunan":0, "vol_bongkaran": vol_beton if is_rehab else 0, "rho_data": {"status": "AMAN"}}

    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        vol_batu = ((l_atas+l_bawah)/2 * h * panjang) + (b*t_lantai*panjang)
        return {"vol_batu": vol_batu, "luas_plester": vol_batu*2, "vol_galian": vol_batu*1.2, "vol_timbunan": 0, "luas_siaran": 0, "vol_bongkaran": vol_batu if is_rehab else 0}
        
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        vol_beton = ((w+0.4)*(h+0.4) - (w*h)) * p
        return {"vol_beton": vol_beton, "berat_besi": vol_beton*110, "luas_bekisting": 2*(w+h)*p, "vol_galian": vol_beton*1.2, "vol_timbunan":0, "vol_bongkaran": vol_beton if is_rehab else 0, "t_rekom": 15, "rho_data": {"status": "AMAN"}}

    @staticmethod
    def hitung_terjunan_hybrid(H_total, H_step, B, t_lantai_beton, t_dinding_batu, is_rehab):
        vol_beton = H_total * B * t_lantai_beton
        vol_batu = H_total * B * t_dinding_batu * 2
        return {"info_struktur": "Hybrid Drop", "vol_beton": vol_beton, "vol_batu": vol_batu, "berat_besi": vol_beton*100, "luas_bekisting": vol_beton*5, "vol_galian": (vol_beton+vol_batu)*1.2, "vol_timbunan":0, "luas_plester": vol_batu, "luas_siaran":0, "vol_bongkaran": (vol_beton+vol_batu) if is_rehab else 0}

# --- 4. UI SIDEBAR & INPUT ---
with st.sidebar:
    st.title("📂 Project Dashboard")
    
    # Save/Load Logic (Simplified)
    col_save, col_load = st.columns(2)
    col_save.download_button("💾 Save", json.dumps(st.session_state['data_proyek']), "data.json")
    
    st.markdown("---")
    st.header("💰 Survey Harga Dasar")
    
    with st.expander("1. Upah Tenaga (Harian)", expanded=True):
        u_pekerja = st.number_input("Pekerja", value=110000.0, step=5000.0)
        u_tukang = st.number_input("Tukang (Batu/Kayu/Besi)", value=135000.0, step=5000.0)
        u_k_tukang = st.number_input("Kepala Tukang", value=150000.0, step=5000.0)
        u_mandor = st.number_input("Mandor", value=170000.0, step=5000.0)
    
    with st.expander("2. Harga Bahan (Loco)", expanded=False):
        p_semen = st.number_input("Semen (per kg)", value=1600.0)
        p_pasir = st.number_input("Pasir Beton/Pasang (m3)", value=250000.0)
        p_split = st.number_input("Batu Pecah/Split (m3)", value=350000.0)
        p_batu = st.number_input("Batu Belah/Kali (m3)", value=280000.0)
        p_besi = st.number_input("Besi Beton (kg)", value=14500.0)
        p_kayu = st.number_input("Kayu Bekisting (m3)", value=3000000.0)
        
    overhead = st.slider("Overhead & Profit (%)", 0, 15, 10)

    # Dictionary Harga Dasar untuk dikirim ke AHSP Engine
    harga_dasar_dict = {
        'u_pekerja': u_pekerja, 'u_tukang': u_tukang, 
        'u_k_tukang': u_k_tukang, 'u_mandor': u_mandor,
        'p_semen': p_semen, 'p_pasir': p_pasir, 'p_split': p_split,
        'p_batu': p_batu, 'p_besi': p_besi, 'p_kayu': p_kayu
    }
    
    # CALCULATE ALL AHSP PRICES ONCE HERE
    dict_hsp_final = {}
    for key in AHSPLibrary.DATA.keys():
        val, _, _ = AHSPLibrary.hitung_harga_satuan(key, harga_dasar_dict, overhead)
        dict_hsp_final[key] = val

# --- 5. MAIN CONTENT ---
st.title("🏗️ Pro QS V.8: Enterprise Civil System")
st.caption(f"📍 Location: Bandar Lampung | Time: {pd.Timestamp.now().strftime('%d-%m-%Y %H:%M')}")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Input Data", "📋 Item List", "📊 RAB Detail", "📚 Analisa AHSP (Ref. SE)"])

# === TAB 1: INPUT (Sama seperti V.7, hanya memanggil Calculator) ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Pelengkap (Unit)"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Cth: Saluran Tersier Ruas A")
        is_rehab = st.checkbox("🚧 Pekerjaan Rehab?", help="Hitung bongkaran otomatis")
        
    with col2:
        st.subheader("2. Geometri")
        # --- Logic Input UI disederhanakan untuk fokus ke fitur baru ---
        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Konstruksi", ["Beton Bertulang", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m')", 50.0)
            if tipe_kons == "Beton Bertulang":
                calc = Calculator.hitung_beton_struktur(0.8, 0.6, 0, panjang, 15, 10, 15, 2, 5, 20, 280, is_rehab)
            else:
                calc = Calculator.hitung_pasangan_batu(0.8, 0.6, 0.2, panjang, 0.3, 0.4, 0.2, is_rehab)
        else:
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box", "Terjunan Hybrid"])
            if "Gorong" in jenis_bang:
                calc = Calculator.hitung_gorong_box_struktur(1, 1, 6, 20, 13, 15, 25, 400, is_rehab)
            else:
                calc = Calculator.hitung_terjunan_hybrid(3, 1.5, 1.5, 0.3, 0.4, is_rehab)

    if st.button("Simpan Data", type="primary"):
        tipe_final = "Saluran" if kategori == "Saluran (Linear)" else jenis_bang
        st.session_state['data_proyek'].append({"nama": nama_item, "tipe": tipe_final, "vol": calc})
        st.success("Item tersimpan ke Database!")

# === TAB 2: LIST ===
with tab2:
    if st.session_state['data_proyek']:
        st.dataframe(pd.DataFrame(st.session_state['data_proyek'])[["nama", "tipe"]])
        if st.button("Clear Data"): st.session_state['data_proyek'] = []; st.rerun()

# === TAB 3: RAB DETAIL (Menggunakan Harga dari AHSP Engine) ===
with tab3:
    st.header("Engineering Estimate (EE)")
    if st.session_state['data_proyek']:
        excel_rows = []
        grand_total = 0
        
        # Mapping Key Volume -> Key AHSP Library
        map_pekerjaan = {
            "vol_bongkaran": "Bongkaran",
            "vol_galian": "Galian",
            "vol_timbunan": "Timbunan",
            "vol_beton": "Beton K225",
            "vol_batu": "Pasangan Batu",
            "berat_besi": "Besi",
            "luas_bekisting": "Bekisting",
            "luas_plester": "Plesteran",
        }

        for i, item in enumerate(st.session_state['data_proyek']):
            nama = item['nama']
            vol_data = item['vol']
            
            with st.expander(f"📍 {i+1}. {nama}", expanded=True):
                item_rows = []
                for key, val in vol_data.items():
                    if key in map_pekerjaan and val > 0.001:
                        kode_ahsp = map_pekerjaan[key]
                        nama_pekerjaan = AHSPLibrary.DATA[kode_ahsp]['nama']
                        satuan = AHSPLibrary.DATA[kode_ahsp]['satuan']
                        
                        # Ambil Harga dari Dictionary yang sudah dihitung via Class
                        harga_satuan = dict_hsp_final[kode_ahsp]
                        
                        jumlah = val * harga_satuan
                        item_rows.append({
                            "Uraian Pekerjaan": nama_pekerjaan, 
                            "Volume": val, 
                            "Sat": satuan, 
                            "H.Satuan (Rp)": harga_satuan, 
                            "Total (Rp)": jumlah
                        })
                        excel_rows.append({"Item": nama, "Uraian": nama_pekerjaan, "Vol": val, "Sat": satuan, "Harga": harga_satuan, "Total": jumlah})
                
                df_item = pd.DataFrame(item_rows)
                if not df_item.empty:
                    subtotal = df_item["Total (Rp)"].sum()
                    grand_total += subtotal
                    st.dataframe(df_item.style.format({"Volume": "{:.3f}", "H.Satuan (Rp)": "{:,.2f}", "Total (Rp)": "{:,.2f}"}), use_container_width=True)

        st.info(f"Grand Total (Sebelum PPN): Rp {grand_total:,.2f}")

# === TAB 4: ANALISA AHSP (FITUR BARU) ===
with tab4:
    st.header("📚 Analisa Harga Satuan Pekerjaan (AHSP)")
    st.markdown("""
    *Format sesuai spesifikasi Teknis Bina Marga / Cipta Karya.*
    Data di bawah ini **dinamis** mengikuti input harga dasar di Sidebar.
    """)
    
    pilihan_ahsp = st.selectbox("Pilih Item Analisa:", list(AHSPLibrary.DATA.keys()))
    
    if pilihan_ahsp:
        # Panggil Engine Hitung Detail
        hsp_total, df_detail, val_overhead = AHSPLibrary.hitung_harga_satuan(pilihan_ahsp, harga_dasar_dict, overhead)
        
        info_ahsp = AHSPLibrary.DATA[pilihan_ahsp]
        st.subheader(f"{info_ahsp['nama']}")
        st.caption(f"Satuan Pembayaran: {info_ahsp['satuan']}")
        
        # Tampilkan Tabel Breakdown
        # Formatting agar mirip Excel Dinas
        st.dataframe(
            df_detail.style.format({
                "Koefisien": "{:.4f}",
                "Harga Satuan": "Rp {:,.2f}",
                "Jumlah Harga": "Rp {:,.2f}"
            }),
            use_container_width=True,
            height=300
        )
        
        # Rekapitulasi Footer Analisa
        c1, c2, c3 = st.columns([2, 1, 1])
        with c3:
            st.markdown(f"""
            | Komponen | Nilai |
            | :--- | ---: |
            | **Jumlah (A+B)** | **{hsp_total - val_overhead:,.2f}** |
            | Overhead ({overhead}%) | {val_overhead:,.2f} |
            | **H. Satuan Final** | **{hsp_total:,.2f}** |
            """)
            
    st.markdown("---")
    st.download_button("📥 Download Database AHSP (JSON)", json.dumps(AHSPLibrary.DATA, indent=2), "db_ahsp_2025.json")
