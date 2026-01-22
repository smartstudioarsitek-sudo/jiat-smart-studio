# --- FUNGSI 2: HITUNG STRUKTUR (REVISI UNIT) ---
def hitung_struktur(h_dinding, h_air_aktual, fc):
    # Parameter
    gamma_air   = 9.81   # kN/m3
    gamma_tanah = 18.0   # kN/m3
    ka          = 0.33   # Koefisien tanah aktif
    selimut     = 0.04   # 4 cm (0.04 m)
    
    # --- LOAD CASE ---
    # 1. Air Penuh (Internal Pressure)
    Mu_air = 1.6 * (1/6) * gamma_air * (h_dinding**3)
    Vu_air = 1.6 * 0.5 * gamma_air * (h_dinding**2)
    
    # 2. Tanah Luar (External Pressure)
    Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_dinding**3)
    Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_dinding**2)
    
    # Ambil beban terbesar
    Mu_desain = max(Mu_air, Mu_tanah)
    Vu_desain = max(Vu_air, Vu_tanah)
    kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"
    
    # --- PERHITUNGAN TEBAL ---
    
    # A. CEK LENTUR (FLEXURE)
    # Rn asumsi ekonomis ~ 1500-2000 kN/m2 untuk K-250
    # d_perlu = sqrt(Mu / (phi * Rn * b)) -> b diambil 1 meter lari
    d_lentur = (Mu_desain / (0.85 * 2000))**0.5 
    
    # B. CEK GESER (SHEAR) - INI YANG KEMARIN SALAH
    # Rumus Vc = 0.17 * sqrt(fc') * b * d
    # fc' harus dalam MPa, hasil Vc dalam MN, baru dikonversi ke kN.
    # Cara simpel: Kuat geser beton (Tau) = 0.17 * sqrt(fc')
    # Jika fc=20, sqrt(20)=4.47. Tau = 0.17 * 4.47 = 0.76 MPa = 760 kN/m2
    
    kuat_geser_beton_kpa = 0.17 * math.sqrt(fc) * 1000  # Hasil dalam kPa (kN/m2)
    phi_geser = 0.75
    
    # d_perlu = Vu / (phi * kuat_geser * b) -> b = 1.0 m
    d_geser = Vu_desain / (phi_geser * kuat_geser_beton_kpa * 1.0)
    
    # --- KEPUTUSAN FINAL ---
    # Ambil d terbesar
    d_pakai = max(d_lentur, d_geser)
    
    # Tebal total = d + selimut + 1/2 diameter tulangan (asumsi D12 = 0.006m)
    t_calc = d_pakai + selimut + 0.006
    
    # Syarat Empiris (Kekakuan Dinding) H/12
    # Agar dinding tidak 'langsing' dan mudah retak
    t_empiris = h_dinding / 12
    
    # Ambil nilai MAX, tapi kasih batas bawah 10 cm
    t_final = max(t_calc, t_empiris, 0.10) 
    
    return t_final, kondisi, h_air_aktual
