import streamlit as st
import pandas as pd
import math

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Kalkulator DED Irigasi (Hidrolis & Struktur)",
    page_icon="🌊",
    layout="wide" # Pakai wide layout biar lega
)

# --- FUNGSI 1: HITUNG TINGGI MUKA AIR (HIDROLIS) ---
def hitung_h_air(Q, b, s=0.0003, n=0.015):
    """
    Menghitung tinggi muka air (y) menggunakan rumus Manning sederhana (Rectangular).
    Iterasi Newton-Raphson untuk akurasi.
    Q: Debit (m3/s)
    b: Lebar (m)
    s: Kemiringan (default 0.0003)
    n: Kekasaran Manning (default 0.015 beton halus)
    """
    if Q <= 0 or b <= 0: return 0.0
    
    # Tebakan awal y
    y = 1.0 
    for _ in range(10): # 10 iterasi cukup
        A = b * y
        P = b + 2 * y
        R = A / P
        # Q = (1/n) * A * R^(2/3) * S^(1/2)
        Q_calc = (1/n) * A * (R**(2/3)) * (s**0.5)
        
        # Turunan f(y) agak ribet, kita pakai pendekatan sederhana error check
        diff = Q - Q_calc
        if abs(diff) < 0.001: break
        
        # Adjustment kasar
        y = y * (Q / Q_calc) ** 0.6
        
    return y

# --- FUNGSI 2: HITUNG STRUKTUR ---
def hitung_struktur(h_dinding, h_air_aktual, fc):
    # Parameter
    gamma_air   = 9.81
    gamma_tanah = 18.0
    ka          = 0.33
    selimut     = 0.04
    fc_kpa      = fc * 1000

    # LOAD CASE 1: Air Penuh (Pakai H dinding penuh untuk jaga-jaga banjir/freeboard penuh)
    # Secara konservatif struktur dihitung saat air penuh setinggi dinding (banjir)
    Mu_air = 1.6 * (1/6) * gamma_air * (h_dinding**3)
    Vu_air = 1.6 * 0.5 * gamma_air * (h_dinding**2)
    
    # LOAD CASE 2: Tanah Luar (Saluran Kosong)
    Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_dinding**3)
    Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_dinding**2)
    
    # Governing
    Mu_desain = max(Mu_air, Mu_tanah)
    Vu_desain = max(Vu_air, Vu_tanah)
    kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"
    
    # Kebutuhan Tebal
    d_lentur = (Mu_desain / (0.85 * 2000))**0.5 # Rn asumsi 2000
    
    denom_geser = 0.75 * 0.17 * math.sqrt(fc_kpa)
    d_geser = Vu_desain / denom_geser
    
    d_pakai = max(d_lentur, d_geser)
    t_calc = d_pakai + selimut + 0.006
    
    # Syarat Empiris H/12
    t_empiris = h_dinding / 12
    
    t_final = max(t_calc, t_empiris, 0.10) # Min 10 cm
    
    return t_final, kondisi, h_air_aktual

# --- UI STREAMLIT ---
st.title("🌊 DED Irigasi: Cek Hidrolis & Struktur")
st.markdown("---")

col_input, col_result = st.columns([1, 2])

with col_input:
    st.subheader("1. Data Saluran")
    Q_input = st.number_input("Debit Rencana Q (m³/det)", value=1.54)
    b_input = st.number_input("Lebar Saluran B (m)", value=4.2)
    h_dinding_input = st.number_input("Tinggi Dinding H (m)", value=1.4, help="Tinggi total beton dari dasar")
    
    st.subheader("2. Parameter Teknis")
    slope = st.number_input("Kemiringan Dasar (S)", value=0.0003, format="%.4f")
    fc_input = st.selectbox("Mutu Beton (fc')", [20, 25, 30])

# --- PROSES PERHITUNGAN ---

# 1. Hitung Tinggi Air (Hidrolis)
h_air_calc = hitung_h_air(Q_input, b_input, slope)
freeboard = h_dinding_input - h_air_calc

# 2. Hitung Tebal (Struktur)
t_rekomendasi, kondisi_kritis, _ = hitung_struktur(h_dinding_input, h_air_calc, fc_input)
t_cm = round(t_rekomendasi * 100, 1)

with col_result:
    st.subheader("📊 Hasil Analisa")
    
    # Scorecard
    c1, c2, c3 = st.columns(3)
    c1.metric("Tinggi Air (y)", f"{h_air_calc:.2f} m")
    c2.metric("Freeboard (Jagaan)", f"{freeboard:.2f} m", delta_color="normal" if freeboard >= 0.3 else "inverse")
    c3.metric("REKOMENDASI TEBAL", f"{t_cm} cm", delta="Aman Struktur")
    
    # Warning Freeboard
    if freeboard < 0.3:
        st.error(f"⚠️ Hati-hati! Tinggi jagaan (Freeboard) hanya {freeboard:.2f} m. Standar KP-03 minimal 0.30 m - 0.40 m.")
    else:
        st.success("✅ Tinggi jagaan aman.")

    st.markdown("---")
    st.write(f"**Detail Logika:**")
    st.info(f"""
    * **Kondisi Desain Penentu:** {kondisi_kritis}
    * Meskipun air hanya setinggi **{h_air_calc:.2f} m**, struktur dinding tetap dihitung mampu menahan air setinggi penuh **{h_dinding_input} m** (antisipasi banjir) atau tekanan tanah saat saluran kering.
    """)
