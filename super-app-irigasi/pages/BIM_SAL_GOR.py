import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI & STATE MANAGEMENT ---
st.set_page_config(page_title="Pro QS: USBR Integrated", layout="wide", page_icon="🌊")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. LIBRARY PERHITUNGAN (ENGINEERING CORE) ---
class Calculator:
    
    # 2.1 SALURAN BETON (TETAP 100%)
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
        vol_galian = ((b + 2*t_m*math.sqrt(1+m**2) + 0.4 + (b + 2*t_m*math.sqrt(1+m**2) + 0.4 + 2*m*(h+t_m+0.2)))/2) * (h+t_m+0.2) * panjang
        return {
            "mu": Mu, "t_rekom": t_rekom,
            "rho_data": {"act": rho_actual, "min": rho_min, "max": rho_max, "status": status_rho},
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": max(0, (vol_galian-vol_beton)*0.45),
            "berat_besi": (b + 2*(h*math.sqrt(1+m**2))) * ((panjang*100/jarak)+1) * lapis * (0.006165*dia**2) * 1.2 * (1+waste/100),
            "luas_bekisting": (2 * sisi_miring * panjang) * 2, "vol_bongkaran": vol_beton if is_rehab else 0
        }

    # 2.2 SALURAN BATU (TETAP 100%)
    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, l_atas, l_bawah, t_lantai, is_rehab):
        vol_batu = ((((l_atas+l_bawah)/2)*h)*2 + (b*t_lantai)) * panjang
        return {
            "mu": 0, "t_rekom": 0, "rho_data": None,
            "vol_batu": vol_batu, "vol_galian": vol_batu*1.25, "vol_timbunan": max(0, (vol_batu*1.25 - vol_batu)*0.35),
            "luas_plester": ((2*h*math.sqrt(1+m**2))+b)*panjang, "luas_siaran": (2*l_atas)*panjang, "vol_bongkaran": vol_batu if is_rehab else 0
        }

    # 2.3 BOX CULVERT (TETAP 100%)
    @staticmethod
    def hitung_gorong_box_struktur(w, h, p, t_cm, dia, jarak, fc, fy, is_rehab):
        if w<=0 or h<=0: return {"vol_beton": 0, "t_rekom": 0, "rho_data": {"status": "DATA 0"}}
        t_m = t_cm / 100
        Mu = (1/10) * ((18*1.5)+10) * ((w+t_m)**2)
        d_eff = (t_cm*10) - 40 - (dia/2)
        t_rekom = max((Mu/(0.85*2000))**0.5 * 100, (w+t_m)/12*100, 15.0)
        rho_act = ((1000/jarak)*(0.25*math.pi*dia**2)*2) / (1000*d_eff)
        status = "AMAN" if (1.4/fy) <= rho_act <= 0.025 else ("KURANG" if rho_act < 1.4/fy else "BOROS")
        vol_beton = ((w+2*t_m)*(h+2*t_m)*p) - (w*h*p)
        return {
            "mu": Mu, "t_rekom": t_rekom, "rho_data": {"act": rho_act, "min": 1.4/fy, "max": 0.025, "status": status},
            "vol_beton": vol_beton, "vol_galian": vol_beton/0.2, "vol_timbunan": vol_beton/0.5,
            "berat_besi": 2*((w+2*t_m)+(h+2*t_m))*2 * ((p*100/jarak)+1) * (0.006165*dia**2) * 1.2,
            "luas_bekisting": (2*w+2*h)*p, "vol_bongkaran": vol_beton if is_rehab else 0
        }

    # 2.4 TERJUNAN USBR + MODE HEMAT (INTEGRASI PENUH)
    @staticmethod
    def hitung_terjunan_usbr(Q, H_total, H_step, B, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab):
        """
        UPGRADE: Mengintegrasikan Mode Hemat dari file 'hitung_terjun.py'
        """
        # Handling zero logic
        if H_step <= 0: H_step = 0.1
        if B <= 0: B = 1.0
        if Q <= 0: Q = 0.1 
        
        g = 9.81
        
        # 1. GEOMETRI STEP
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps 
        
        # 2. ANALISA HIDROLIS (USBR LOGIC)
        q = Q / B
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1)
        
        # Penentuan Tipe USBR
        tipe_usbr = "Unknown"
        k_length = 0
        
        if Fr1 < 1.7:
            tipe_usbr = "Aliran Undular"
            k_length = 4.0
        elif Fr1 < 2.5:
            tipe_usbr = "USBR Tipe I"
            k_length = 5.0
        elif Fr1 <= 4.5:
            tipe_usbr = "USBR Tipe IV"
            k_length = 6.0 
        else:
            if V1 < 18.0:
                tipe_usbr = "USBR Tipe III"
                k_length = 2.7 
            else:
                tipe_usbr = "USBR Tipe II"
                k_length = 4.3
        
        L_kolam_standard = k_length * y2
        L_drop = 4.30 * H_real * ((q**2 / (g * H_real**3))**0.27)
        
        # --- LOGIKA MODE HEMAT (DARI FILE KAKAK) ---
        is_hemat_active = mode_hemat and (H_real <= 1.2)
        
        if is_hemat_active:
            L_kolam_inter = 0.5 # Pendek (cuma transisi)
            tipe_desain = "Mode Hemat (Kolam Hilir Saja)"
        else:
            L_kolam_inter = L_kolam_standard # Full USBR di setiap trap
            tipe_desain = "Standard (Full USBR per Trap)"
            
        L_kolam_final = L_kolam_standard # Lantai paling bawah selalu Full USBR
        
        # Hitung Panjang Total Struktur (Untuk Volume)
        # Jika ada 3 trap: 2 trap intermediate + 1 trap final
        jml_inter = max(0, n_steps - 1)
        
        panjang_lantai_inter = jml_inter * (L_drop + L_kolam_inter)
        panjang_lantai_final = 1 * (L_drop + L_kolam_final)
        
        L_total_structure_linear = panjang_lantai_inter + panjang_lantai_final
        
        # 3. CEK STABILITAS (UPLIFT PADA KOLAM FINAL)
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
        
        # 4. HITUNG VOLUME (QS ENGINE)
        h_dinding = y2 + 0.6 
        
        vol_lantai = L_total_structure_linear * B * t_lantai
        vol_mercu = n_steps * (B * H_real * 0.4) 
        vol_dinding = 2 * (L_total_structure_linear * h_dinding * t_dinding)
        
        vol_beton_total = vol_lantai + vol_mercu + vol_dinding
        
        ratio_besi = 120.0
        if SF_uplift < 1.5: ratio_besi += 10 
        if "USBR Tipe III" in tipe_usbr: ratio_besi += 15
        
        berat_besi = vol_beton_total * ratio_besi
        
        return {
            "info_struktur": f"{tipe_usbr} ({n_steps} Trap) - {tipe_desain}",
            "detail_usbr": {
                "Fr": Fr1, "y1": y1, "y2": y2, 
                "L_kolam_final": L_kolam_final, "L_total": L_total_structure_linear
            },
            "stabilitas": {
                "sf_uplift": SF_uplift, "status_uplift": status_uplift,
                "sigma_tanah": Tekanan_Netto, "status_tanah": status_tanah
            },
            "vol_beton": vol_beton_total, 
            "vol_batu": 0, 
            "vol_galian": vol_beton_total * 1.3, 
            "vol_timbunan": vol_beton_total * 0.3,
            "berat_besi": berat_besi, 
            "luas_bekisting": (2 * L_total_structure_linear * h_dinding) + (n_steps*B*H_real),
            "luas_plester": (2 * L_total_structure_linear * h_dinding),
            "luas_siaran": 0,
            "vol_bongkaran": vol_beton_total if is_rehab else 0
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
st.title("🏗️ Pro QS V.11: Ultimate Integration")
st.caption("Status: ✅ USBR + Mode Hemat (Upgraded) | ✅ Saluran & Box (Aman 100%)")

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
                h = st.number_input("Tinggi H (m)", value=0.8)
                b = st.number_input("Lebar B (m)", value=0.6)
                m = st.number_input("Talud m", value=0.0)
                t_cm = st.number_input("Tebal (cm)", value=15.0)
                dia = st.number_input("Dia Besi (mm)", value=10.0)
                jarak = st.number_input("Jarak (cm)", value=15.0)
                calc = Calculator.hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, 2, 5, 20, 280, is_rehab)
            else:
                h = st.number_input("Tinggi H", value=0.8)
                l_atas = st.number_input("L. Atas", value=0.3)
                l_bawah = st.number_input("L. Bawah", value=0.4)
                t_lantai = st.number_input("T. Lantai", value=0.2)
                calc = Calculator.hitung_pasangan_batu(h, 0.5, 0.2, panjang, l_atas, l_bawah, t_lantai, is_rehab)

        # --- BANGUNAN ---
        else:
            jenis_bang = st.selectbox("Jenis", ["Gorong-Gorong Box", "Terjunan USBR (Integrated)"])
            
            if "Gorong" in jenis_bang:
                st.info("📦 Box Culvert")
                w = st.number_input("Lebar (m)", value=1.0)
                h_box = st.number_input("Tinggi (m)", value=1.0)
                p_box = st.number_input("Panjang (m)", value=6.0)
                t_cm = st.number_input("Tebal Beton (cm)", value=20.0)
                dia = st.number_input("Dia. Besi (mm)", value=13.0)
                jarak = st.number_input("Jarak (cm)", value=15.0)
                calc = Calculator.hitung_gorong_box_struktur(w, h_box, p_box, t_cm, dia, jarak, 25, 400, is_rehab)
                
            else: # TERJUNAN USBR V.11 (MODE HEMAT)
                st.info("🌊 Terjunan Hidrolis (USBR & Stability Check)")
                
                # OPTION BARU: MODE HEMAT
                mode_hemat = st.checkbox("✅ Aktifkan Mode Hemat?", value=True, 
                                        help="Jika Tinggi Trap < 1.2m, lantai tengah dipendekkan (Cascaded Drop)")
                
                c_h1, c_h2, c_h3 = st.columns(3)
                Q_debit = c_h1.number_input("Debit Q (m3/s)", value=1.5, min_value=0.01)
                H_total = c_h2.number_input("Total Tinggi (m)", value=3.0)
                H_step = c_h3.number_input("Max Tinggi/Trap (m)", value=1.5)
                
                c_d1, c_d2 = st.columns(2)
                B_terjun = c_d1.number_input("Lebar Saluran B (m)", value=1.5)
                qa_tanah = c_d2.number_input("Daya Dukung Tanah (kN/m2)", value=150.0)
                
                st.markdown("**Dimensi Struktur:**")
                c_m1, c_m2 = st.columns(2)
                t_lantai = c_m1.number_input("Tebal Lantai (m)", value=0.25)
                t_dinding = c_m2.number_input("Tebal Dinding (m)", value=0.25)
                
                # HITUNG
                calc = Calculator.hitung_terjunan_usbr(Q_debit, H_total, H_step, B_terjun, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab)
                
                st.divider()
                st.write(f"**Analisa: {calc['info_struktur']}**")
                
                # Info Hidrolis
                c_res1, c_res2, c_res3 = st.columns(3)
                c_res1.metric("Froude", f"{calc['detail_usbr']['Fr']:.2f}")
                c_res2.metric("Panjang Final", f"{calc['detail_usbr']['L_kolam_final']:.2f} m")
                c_res3.metric("Total Panjang", f"{calc['detail_usbr']['L_total']:.2f} m")
                
                # Info Stabilitas
                st.markdown("---")
                s_1, s_2 = st.columns(2)
                sf = calc['stabilitas']['sf_uplift']
                if sf >= 1.5: s_1.success(f"✅ SF Uplift: {sf:.2f}")
                else: s_1.error(f"❌ SF Uplift: {sf:.2f}")
                
                sig = calc['stabilitas']['sigma_tanah']
                if sig <= qa_tanah: s_2.success(f"✅ Daya Dukung: {sig:.2f} kN/m2")
                else: s_2.error(f"❌ Daya Dukung: {sig:.2f} kN/m2")

    if st.button("Simpan Item", type="primary"):
        if not nama_item: st.warning("Isi Nama!")
        else:
            tipe_final = jenis_bang if kategori != "Saluran (Linear)" else ("Saluran Beton" if tipe_kons == "Beton Bertulang" else "Saluran Batu")
            if is_rehab: nama_item += " (REHAB)"
            item_data = {"nama": nama_item, "tipe": tipe_final, "panjang": 0, "vol": calc}
            if kategori == "Saluran (Linear)": item_data["panjang"] = panjang
            st.session_state['data_proyek'].append(item_data)
            st.success("Tersimpan!")

# === TAB 2 & 3 (STANDARD) ===
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
        st.download_button("📥 Download RAB Excel", generate_excel(), "RAB_V11_Final.xlsx")
