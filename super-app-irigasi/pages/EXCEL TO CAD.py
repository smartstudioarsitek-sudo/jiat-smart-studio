import pandas as pd
import numpy as np
from scipy.optimize import newton
from scipy.interpolate import interp1d

def run_professional_design():
    # 1. LOAD & CLEAN DATA (Anti-Error Space/Typo)
    try:
        # Load file (sesuaikan path jika perlu)
        df_ground = pd.read_csv('IMPORT NOKAN.xlsx - 2026-01-05T19-35_export.csv')
        df_drops = pd.read_csv('STA TERJUNAN.xlsx - 2026-01-05T19-35_export.csv')
        
        # Bersihkan nama kolom dari spasi (misal "STA " jadi "STA")
        df_ground.columns = [c.strip() for c in df_ground.columns]
        df_drops.columns = [c.strip() for c in df_drops.columns]
        
        # Pastikan kolom TERJUNAN positif
        if 'TERJUNAN (m)' in df_drops.columns:
            df_drops['TERJUNAN (m)'] = df_drops['TERJUNAN (m)'].fillna(0).abs()
        
    except Exception as e:
        return None, f"Error Load File: {str(e)}"

    # 2. SETUP INTERPOLASI TANAH
    # Mengubah data segmen menjadi titik kontinyu untuk interpolasi
    pts = []
    for _, row in df_ground.iterrows():
        pts.append((row['STA Awal (m)'], row['Elev Awal (m)']))
    # Titik terakhir
    last = df_ground.iloc[-1]
    pts.append((last['STA Akhir (m)'], last['Elev Akhir (m)']))
    
    df_pts = pd.DataFrame(pts, columns=['STA', 'Z']).drop_duplicates('STA').sort_values('STA')
    get_z_ground = interp1d(df_pts['STA'], df_pts['Z'], kind='linear', fill_value="extrapolate")

    # 3. PARAMETER DESAIN
    Q_des = df_ground.iloc[0].get('Debit Q (m3/s)', 0.17)
    b_des = 0.6
    m_des = 1.0
    n_des = 0.017
    CUT_IDEAL = 1.0 # Galian ideal 1 meter
    
    # 4. LOOP PERHITUNGAN (Boundary Control)
    control_stas = sorted(list(set([0] + df_drops['STA'].tolist() + [df_pts['STA'].max()])))
    
    results_detail = []
    current_z = get_z_ground(0) - CUT_IDEAL # Start Elevasi Desain
    
    for i in range(len(control_stas) - 1):
        s_start = control_stas[i]
        s_end = control_stas[i+1]
        L = s_end - s_start
        if L <= 0: continue
        
        # Cek Drop di ujung segmen
        drop_h = 0.0
        row_d = df_drops[df_drops['STA'] == s_end]
        if not row_d.empty:
            drop_h = row_d.iloc[0]['TERJUNAN (m)']
            
        # Hitung Slope
        z_end_target = get_z_ground(s_end) - CUT_IDEAL
        slope = (current_z - z_end_target) / L
        
        # Safety: Jika slope negatif (nanjak), paksa datar minimal
        if slope < 0.0005: slope = 0.0005
            
        # Generate Points per 25m
        stas = np.arange(s_start, s_end, 25.0)
        if stas[-1] != s_end: stas = np.append(stas, s_end)
        
        for st in stas:
            z_d = current_z - (slope * (st - s_start))
            results_detail.append({
                'STA': st,
                'Elev Desain': z_d,
                'Keterangan': 'Normal'
            })
            
        # Update Z untuk next loop (dikurangi drop jika ada)
        z_end_final = current_z - (slope * L)
        if drop_h > 0:
            # Tambah titik drop vertikal untuk AutoCAD
            results_detail.append({
                'STA': s_end,
                'Elev Desain': z_end_final - drop_h,
                'Keterangan': f'Bottom Drop {drop_h}m'
            })
        current_z = z_end_final - drop_h

    # 5. RETURN DATAFRAME
    return pd.DataFrame(results_detail), None