def hitung_detail_ded_irigasi(h_saluran, b_saluran, fc, fy):
    # 1. PARAMETER DESAIN
    gamma_air   = 9.81
    gamma_tanah = 18.0
    ka          = 0.33
    selimut     = 0.04
    
    # 2. ANALISA BEBAN
    Mu_air = 1.6 * (1/6) * gamma_air * (h_saluran**3)
    Vu_air = 1.6 * 0.5 * gamma_air * (h_saluran**2)
    
    Mu_tanah = 1.6 * (1/6) * gamma_tanah * ka * (h_saluran**3)
    Vu_tanah = 1.6 * 0.5 * gamma_tanah * ka * (h_saluran**2)
    
    Mu_desain = max(Mu_air, Mu_tanah)
    Vu_desain = max(Vu_air, Vu_tanah)
    kondisi = "Air Penuh (Internal)" if Mu_air > Mu_tanah else "Tekanan Tanah (Eksternal)"

    # 3. KEBUTUHAN STRUKTURAL
    # Cek Lentur
    d_lentur = (Mu_desain / (0.85 * 2000))**0.5
    
    # Cek Geser (INI YANG SUDAH DIPERBAIKI)
    # 0.17 * sqrt(fc_mpa) * 1000
    kuat_geser_kpa = 0.17 * math.sqrt(fc) * 1000
    denom_geser = 0.75 * kuat_geser_kpa
    d_geser = Vu_desain / denom_geser
    
    # 4. TEBAL AKHIR
    d_pakai = max(d_lentur, d_geser)
    t_struktural = d_pakai + selimut + 0.006 
    t_min_empiris = h_saluran / 12
    
    t_final = max(t_struktural, t_min_empiris, 0.10)
    
    return {
        "H (m)": h_saluran,
        "B (m)": b_saluran,
        "Mu (kNm)": round(Mu_desain, 2),
        "Vu (kN)": round(Vu_desain, 2),
        "Kondisi Kritis": kondisi,
        "Tebal Perlu (cm)": round(t_struktural * 100, 2),
        "Syarat H/12 (cm)": round(t_min_empiris * 100, 2),
        "REKOMENDASI (cm)": round(t_final * 100, 1)
    }
