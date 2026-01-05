import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import newton
from scipy.interpolate import interp1d

# ==========================================
# 1. SETUP & KONFIGURASI DESAIN
# ==========================================
CONFIG = {
    'Q_desain': 0.17,      # Debit Desain (m3/s) - Sesuaikan jika perlu
    'n_manning': 0.017,    # Kekasaran (Beton/Pasangan)
    'b_lebar': 0.60,       # Lebar dasar (m)
    'm_talud': 1.0,        # Kemiringan talud (1:m)
    'cut_ideal': 1.0,      # Target galian ideal (m) sebelum terjunan
    'interval_out': 25.0,  # Interval output data (meter)
}

# ==========================================
# 2. FUNGSI HIDROLIKA (PROFESSIONAL GRADE)
# ==========================================
def solve_manning_properties(Q, b, m, n, S):
    """
    Menghitung kedalaman normal (yn), Kecepatan (V), dan Froude (Fr)
    berdasarkan Rumus Manning dan Kontinuitas.
    """
    if S <= 0:
        return np.nan, np.nan, np.nan, "Slope Negatif/Nol"

    # Fungsi error untuk solver (Q_hitung - Q_target = 0)
    def func_manning(y):
        if y <= 0: return -Q
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P
        return (1/n) * A * (R**(2/3)) * (S**0.5) - Q

    try:
        # Solver Iteratif (Newton-Raphson)
        yn = newton(func_manning, x0=0.5, maxiter=50)
        
        # Hitung properti lain
        A = (b + m * yn) * yn
        V = Q / A
        T = b + 2 * m * yn # Lebar atas
        D = A / T          # Hydraulic Depth
        Fr = V / np.sqrt(9.81 * D)
        
        status = "Sub-Kritis" if Fr < 1 else "Super-Kritis"
        if Fr > 0.9 and Fr < 1.1: status = "Kritis (Bahaya)"
        
        return yn, V, Fr, status
    except:
        return np.nan, np.nan, np.nan, "Error Solver"

# ==========================================
# 3. PROSES DATA (CORE LOGIC)
# ==========================================
def run_professional_design():
    print("--- MEMULAI ANALISA HIDROLIKA & DESAIN ---")
    
    # --- A. Load Data Tanah (Ground) ---
    try:
        df_ground = pd.read_csv('IMPORT NOKAN.xlsx - 2026-01-05T19-35_export.csv')
        # Buat fungsi interpolasi tanah (agar bisa cek elevasi di STA berapapun)
        # Ambil titik unik STA dan Elevasi
        ground_points_sta = []
        ground_points_z = []
        
        for idx, row in df_ground.iterrows():
            # Tambahkan titik awal segmen
            ground_points_sta.append(row['STA Awal (m)'])
            ground_points_z.append(row['Elev Awal (m)'])
        # Tambahkan titik akhir dari data terakhir
        ground_points_sta.append(df_ground.iloc[-1]['STA Akhir (m)'])
        ground_points_z.append(df_ground.iloc[-1]['Elev Akhir (m)'])
        
        # Buat interpolator Linear
        get_ground_z = interp1d(ground_points_sta, ground_points_z, kind='linear', fill_value="extrapolate")
        max_sta = max(ground_points_sta)
        print(f"✅ Data Tanah Terload: 0 s.d {max_sta} m")
        
    except Exception as e:
        return f"❌ Error Load Data Tanah: {e}"

    # --- B. Load Data Terjunan (Drop Structures) ---
    try:
        df_drops = pd.read_csv('STA TERJUNAN.xlsx - 2026-01-05T19-35_export.csv')
        df_drops['TERJUNAN (m)'] = df_drops['TERJUNAN (m)'].abs() # Pastikan positif
        df_drops = df_drops.sort_values('STA ')
        print(f"✅ Data Terjunan Terload: {len(df_drops)} titik terjunan")
    except Exception as e:
        return f"❌ Error Load Data Terjunan: {e}"

    # --- C. Algoritma Desain (Boundary Control) ---
    # Kita akan membagi saluran menjadi segmen-segmen berdasarkan lokasi terjunan
    # Segmen 1: STA 0 -> STA Terjunan 1
    # Segmen 2: STA Terjunan 1 -> STA Terjunan 2, dst.
    
    control_points = [0] + df_drops['STA '].tolist() + [max_sta]
    control_points = sorted(list(set(control_points))) # Hapus duplikat & urutkan
    
    design_results = [] # Menampung hasil perhitungan per segmen
    detail_points = []  # Menampung titik per 25m untuk AutoCAD/Excel
    
    # Inisiasi Elevasi Awal Desain
    # Asumsi: Awal saluran digali sedalam 'cut_ideal' dari tanah asli
    current_z_design = get_ground_z(0) - CONFIG['cut_ideal']
    
    # Loop antar Control Points
    for i in range(len(control_points) - 1):
        sta_start = control_points[i]
        sta_end = control_points[i+1]
        dist = sta_end - sta_start
        
        if dist <= 0: continue # Skip jika jarak 0
        
        # 1. Cek apakah di STA End ada terjunan?
        drop_row = df_drops[df_drops['STA '] == sta_end]
        if not drop_row.empty:
            h_drop = drop_row.iloc[0]['TERJUNAN (m)']
        else:
            h_drop = 0.0 # Akhir saluran tanpa terjunan
            
        # 2. Tentukan Target Elevasi di Ujung Segmen
        # Strategi: Kita ingin di ujung segmen (sebelum terjunan), elevasi desain
        # kurang lebih = Elevasi Tanah - Cut Ideal.
        z_ground_end = get_ground_z(sta_end)
        z_target_end = z_ground_end - CONFIG['cut_ideal']
        
        # 3. Hitung Slope (I) yang dibutuhkan
        # I = (Z_awal - Z_target) / Panjang
        slope_calc = (current_z_design - z_target_end) / dist
        
        # Safety Check: Jika slope negatif (nanjak), kita paksa datar minimal atau landai
        if slope_calc <= 0.0001:
            slope_calc = 0.0005 # Slope minimum teknis
            z_target_end = current_z_design - (slope_calc * dist) # Recalculate target
            
        # 4. Hitung Hidrolika
        yn, V, Fr, status_aliran = solve_manning_properties(
            CONFIG['Q_desain'], CONFIG['b_lebar'], CONFIG['m_talud'], 
            CONFIG['n_manning'], slope_calc
        )
        
        # 5. Simpan Hasil Segmen
        design_results.append({
            'STA Awal': sta_start,
            'STA Akhir': sta_end,
            'Panjang': dist,
            'Elev Awal': current_z_design,
            'Elev Akhir (Sblm Drop)': z_target_end,
            'Drop (m)': h_drop,
            'Elev Akhir (Stlh Drop)': z_target_end - h_drop,
            'Slope Desain': slope_calc,
            'Kecepatan (V)': V,
            'Froude (Fr)': Fr,
            'Kedalaman (h)': yn,
            'Status': status_aliran
        })
        
        # 6. Generate Titik Detail (Per Interval 25m) untuk AutoCAD
        # Generate points: start, start+25, ..., end
        seg_points = np.arange(sta_start, sta_end, CONFIG['interval_out'])
        if seg_points[-1] != sta_end:
            seg_points = np.append(seg_points, sta_end)
            
        for p_sta in seg_points:
            # Interpolasi linear elevasi desain di titik ini
            fraction = (p_sta - sta_start) / dist
            z_des = current_z_design - (fraction * (current_z_design - z_target_end))
            z_gr = get_ground_z(p_sta)
            
            detail_points.append({
                'STA': p_sta,
                'Elev Tanah': z_gr,
                'Elev Desain': z_des,
                'Tinggi Galian': z_gr - z_des,
                'Ket': 'Normal'
            })
            
        # Jika ada drop, tambahkan titik "bottom" drop di STA yang sama untuk grafik tegak
        if h_drop > 0:
            z_after = z_target_end - h_drop
            detail_points.append({
                'STA': sta_end,
                'Elev Tanah': get_ground_z(sta_end),
                'Elev Desain': z_after,
                'Tinggi Galian': get_ground_z(sta_end) - z_after,
                'Ket': f'Bottom Drop {h_drop}m'
            })
            
        # Update Start Elevasi untuk loop berikutnya
        current_z_design = z_target_end - h_drop

    # --- D. Export & Plotting ---
    df_result_segmen = pd.DataFrame(design_results)
    df_detail = pd.DataFrame(detail_points)
    
    # 1. Plotting Matplotlib
    plt.figure(figsize=(15, 8))
    
    # Plot Tanah
    plt.plot(df_detail['STA'], df_detail['Elev Tanah'], 'g--', label='Tanah Asli', alpha=0.7)
    
    # Plot Desain
    plt.plot(df_detail['STA'], df_detail['Elev Desain'], 'b-', linewidth=2, label='Desain Dasar Saluran')
    
    # Plot Lokasi Terjunan (Garis Merah Vertikal)
    for idx, row in df_drops.iterrows():
        plt.axvline(x=row['STA '], color='red', linestyle=':', alpha=0.5)
        # plt.text(row['STA '], 300, f"Drop {row['TERJUNAN (m)']}m", rotation=90, verticalalignment='bottom', fontsize=8)

    plt.title("Profil Memanjang Desain Saluran Irigasi (Boundary Control Method)")
    plt.xlabel("Station (m)")
    plt.ylabel("Elevasi (m)")
    plt.legend()
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.savefig('Desain_Profil_Professional.png')
    
    # 2. Export Excel Professional
    output_excel = "HASIL_DESAIN_PROFESIONAL.xlsx"
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        # Sheet 1: Ringkasan
        summary_data = {
            'Parameter': ['Total Panjang', 'Total Terjunan', 'Total Drop Height', 'Debit Desain'],
            'Nilai': [max_sta, len(df_drops), df_drops['TERJUNAN (m)'].sum(), CONFIG['Q_desain']],
            'Satuan': ['m', 'bh', 'm', 'm3/s']
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='RINGKASAN', index=False)
        
        # Sheet 2: Analisa Per Segmen
        df_result_segmen.to_excel(writer, sheet_name='ANALISA_HIDROLIKA', index=False)
        
        # Sheet 3: Detail Per 25m
        df_detail.to_excel(writer, sheet_name='DETAIL_STA_25', index=False)
        
        # Sheet 4: Format AutoCAD (X, Y)
        # Format simple: STA, Elev Desain
        df_acad = df_detail[['STA', 'Elev Desain']].copy()
        df_acad.to_excel(writer, sheet_name='DATA_AUTOCAD', index=False)
        
    print(f"✅ Selesai. File tersimpan: {output_excel}")
    print("✅ Grafik tersimpan: Desain_Profil_Professional.png")
    
    return df_result_segmen, df_detail

# Jalankan Fungsi Utama
df_segmen, df_detil = run_professional_design()

# Tampilkan Preview Hasil Analisa Segmen (Area S40 tadi)
print("\n--- PREVIEW HASIL ANALISA SEGMEN (Area Kritis) ---")
print(df_segmen[df_segmen['STA Awal'] > 600].head(10)[['STA Awal', 'STA Akhir', 'Drop (m)', 'Slope Desain', 'Kecepatan (V)', 'Status']])
