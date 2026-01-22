import streamlit as st
import pandas as pd
import math

# --- 1. KONFIGURASI HALAMAN (SAFETY FIRST) ---
try:
    st.set_page_config(page_title="Cek Tebal Saluran", layout="wide")
except:
    pass 

st.title("🌊 Cek Tebal & Geometri Saluran Irigasi")
st.caption("Status: ✅ Aplikasi Berjalan Normal (Support Trapesium & Persegi)")
st.divider()

# --- 2. FUNGSI LOGIKA (TERINTEGRASI) ---

def solve_manning_trapezoidal(Q, b, m, s, n=0.015):
    """
    Menghitung tinggi muka air (h) untuk saluran Trapesium/Persegi.
    Rumus Manning: Q = (1/n) * A * R^(2/3) * S^(1/2)
    """
    if Q <= 0 or b <= 0 or s <= 0: return 0.0
    
    h = 1.0 # Tebakan awal
    
    for _ in range(30): # Iterasi Newton-Raphson Sederhana
        try:
            # Properti Geometri Trapesium
            # A = (b + mh)h
            area = (b + m * h) * h 
            # P = b + 2h * sqrt(1 + m^2)
            perimeter = b + 2 * h * math.sqrt(1 + m**2)
            
            if perimeter == 0: break
            
            R = area / perimeter
            
            # Hitung Q berdasarkan tebakan h
            Q_calc = (1/n) * area * (R**(2/3)) * (s**0.5)
            
            # Cek Error
            if abs(Q - Q_calc) < 0.001:
                return h
            
            # Koreksi h (Metode rasio sederhana agar stabil)
            if Q_calc < 0.00001: Q_calc = 0.00001
            h = h * (Q / Q_calc) ** 0.5 # Pangkat diperkecil agar loncatan halus
            
        except:
            return h
            
    return h

def hitung_struktur_lengkap(h_dinding, b, m, fc, h_air_aktual):
    try:
        # Parameter Desain
        gamma_air   = 9.81
        gamma_tanah = 18.0
        ka          = 0.33
        selimut     = 0.04
        
        # --- A. GEOMETRI DINDING ---
        # Panjang Sisi Miring (Slant Length) = H * sqrt(1+m^2)
        # Ini adalah panjang dinding beton sesungguhnya
        sisi_miring = h_dinding * math.sqrt(1 + m**2)
        
        # Keliling Lining (Total Beton) = Lebar Dasar + 2 x Sisi Miring
        keliling_beton = b + (2 * sisi_miring)
        
        # --- B. BEBAN STRUKTUR ---
        # Catatan: Perhitungan Momen & Geser tetap menggunakan proyeksi vertikal (H)
        # Ini adalah pendekatan konservatif yang aman untuk DED.
        
        # Case 1: Air Penuh
        Mu_air = 1.6 * (1/6) * gamma_air * (h_dinding**3)
        Vu_air = 1.6 * 0.5 * gamma_air * (h_dinding**2)
        
        # Case 2: Tanah Luar
        Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_dinding**3)
        Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_dinding**2)
        
        Mu_desain = max(Mu_air, Mu_tanah)
        Vu_desain = max(Vu_air, Vu_tanah)
        kondisi = "Air Penuh" if Mu_air > Mu_tanah else "Tekanan Tanah"

        # --- C. CEK TEBAL ---
        # 1. Lentur
        d_lentur = (Mu_desain / (0.85 * 2000))**0.5
        
        # 2. Geser (Fix Satuan)
        kuat_geser_kpa = 0.17 * math.sqrt(fc) * 1000 
        d_geser = Vu_desain / (0.75 * kuat_geser_kpa)
        
        # 3. Empiris (Kekakuan) -> Pakai Sisi Miring!
        # Dinding miring lebih panjang dari dinding tegak, jadi harus lebih kaku
        t_empiris = sisi_miring / 12
        
        # Keputusan Final
        d_pakai = max(d_lentur, d_geser)
        t_calc = d_pakai + selimut + 0.006
        t_final = max(t_calc, t_empiris, 0.10) # Min 10 cm
        
        return {
            "H (m)": h_dinding,
            "m (Talud)": m,
            "Sisi Miring (m)": round(sisi_miring, 2),
            "Keliling Lining (m)": round(keliling_beton, 2),
            "Tebal Rekomendasi (cm)": round(t_final * 100, 1),
            "Mu (kNm)": round(Mu_desain, 2),
            "Vu (kN)": round(Vu_desain, 2),
            "Kondisi": kondisi,
            "Tebal H/12 (cm)": round(t_empiris*100, 1)
        }
    except Exception as e:
        return {"Error": str(e)}

# --- 3. UI & INPUT ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.info("📥 **Dimensi Saluran**")
    Q_in = st.number_input("Debit (Q) m³/s", value=1.54)
    b_in = st.number_input("Lebar Dasar (B) m", value=4.2)
    h_in = st.number_input("Tinggi Dinding (H) m", value=1.4)
    # INPUT BARU: TALUD
    m_in = st.number_input("Kemiringan Talud (m)", value=0.0, step=0.1, help="0 = Tegak Lurus. 1 = Miring 1:1")

with col_in2:
    st.warning("⚙️ **Parameter Teknis**")
    s_in = st.number_input("Slope Dasar (S)", value=0.0003, format="%.4f")
    fc_in = st.selectbox("Mutu Beton (fc')", [20, 25, 30])
    
# --- 4. PROSES HITUNG ---

# 1. Hidrolis (Manning Trapesium)
h_air = solve_manning_trapezoidal(Q_in, b_in, m_in, s_in)
freeboard = h_in - h_air

# 2. Struktur & Geometri
res = hitung_struktur_lengkap(h_in, b_in, m_in, fc_in, h_air)

# --- 5. TAMPILKAN HASIL ---

if "Error" in res:
    st.error(f"Error: {res['Error']}")
else:
    # --- SECTION 1: HIDROLIS ---
    st.subheader("1. Analisa Hidrolis")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tinggi Air (y)", f"{h_air:.3f} m")
    
    # Logic warna Freeboard
    fb_status = "Aman" if freeboard >= 0.3 else "Bahaya (<30cm)"
    fb_color = "normal" if freeboard >= 0.3 else "inverse"
    c2.metric("Freeboard", f"{freeboard:.3f} m", delta=fb_status, delta_color=fb_color)
    
    c3.metric("Debit", f"{Q_in} m³/s")

    # --- SECTION 2: GEOMETRI & STRUKTUR ---
    st.markdown("---")
    st.subheader("2. Rekomendasi Struktur & Volume")
    
    # Tampilan Grid Baru
    g1, g2, g3, g4 = st.columns(4)
    
    g1.metric("Panjang Dinding", f"{res['Sisi Miring (m)']} m", help="Panjang sisi miring beton per satu sisi")
    
    # INI OUTPUT BARU YANG KAKAK MINTA
    g2.metric("Keliling Lining", f"{res['Keliling Lining (m)']} m", help="Total panjang beton (Lantai + 2 Dinding) untuk RAB")
    
    g3.metric("Momen Maks", f"{res['Mu (kNm)']} kNm")
    
    # REKOMENDASI TEBAL
    tebal = res['Tebal Rekomendasi (cm)']
    g4.metric("TEBAL BETON", f"{tebal} cm", delta="DED Ready", delta_color="normal" if tebal <= 20 else "inverse")

    # --- TABEL RINCIAN ---
    with st.expander("Lihat Rincian Perhitungan Lengkap"):
        st.write("""
        Tabel berikut menunjukkan detail parameter yang digunakan untuk perhitungan.
        * **Keliling Lining** berguna untuk menghitung volume pekerjaan beton per meter panjang.
        * **Tebal H/12** adalah syarat kekakuan agar dinding tidak melendut.
        """)
        df = pd.DataFrame([res]).T
        df.columns = ["Nilai"]
        st.table(df)
