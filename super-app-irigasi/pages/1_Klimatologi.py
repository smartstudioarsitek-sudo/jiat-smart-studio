import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="JIAT - Klimatologi", layout="wide", page_icon="🌦️")

# --- 2. CSS & HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(135deg, #0072ff 0%, #00c6ff 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .stDataFrame { border: 1px solid #eee; border-radius: 5px; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 28px;">🌦️ Analisa Klimatologi (Penman Modifikasi)</h1>
    <p style="opacity: 0.9; margin-top:5px;">Sesuai Standar Perencanaan Irigasi (KP-01)</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 3. ENGINE PERHITUNGAN (PENMAN MODIFIKASI)
# ==========================================

def hitung_ra_harian(lat_deg, bulan_idx):
    """Menghitung Radiasi Ekstraterestrial (Ra) dalam mm/hari"""
    phi = math.radians(lat_deg)
    # Deklinasi Matahari (Delta) approx
    delta = 0.409 * math.sin(2 * math.pi / 365 * (30 * bulan_idx + 15) - 1.39)
    # Jarak relatif bumi-matahari (dr)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * (30 * bulan_idx + 15))
    # Sudut jam matahari terbenam (ws)
    ws_val = -math.tan(phi) * math.tan(delta)
    ws_val = max(-1.0, min(1.0, ws_val)) # Clamp value
    ws = math.acos(ws_val)
    
    # Ra (mm/hari)
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + 
        math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return max(0, ra)

def hitung_penman_modifikasi(row, lat, c_faktor, elevasi=0):
    try:
        # Ambil Data Row
        t = float(row['Suhu (°C)'])
        rh = float(row['RH (%)'])
        u_ms = float(row['Angin (m/s)']) # Kecepatan angin m/s
        n_N = float(row['Penyinaran (%)']) / 100
        
        if pd.isna(t) or pd.isna(rh): return 0.0

        # A. Tekanan Uap Jenuh (ea) & Aktual (ed) - mbar
        # Rumus Tetens (Standard KP-01 pakai mbar)
        ea = 6.11 * math.exp((17.27 * t) / (t + 237.3)) 
        ed = ea * (rh / 100)
        
        # B. Fungsi Angin f(u)
        # Penman Modifikasi biasanya convert m/s ke km/hari atau pakai koefisien langsung
        # u (km/hari) = u (m/s) * 86.4
        u_km_day = u_ms * 86.4
        fu = 0.27 * (1 + (u_km_day / 100))
        
        # C. Faktor Pemberat (W)
        # W dikalkulasi berdasarkan suhu & elevasi (Approximation)
        # Delta = Slope vapor pressure curve
        delta_grad = (4098 * (0.6108 * math.exp((17.27 * t)/(t+237.3)))) / ((t + 237.3)**2)
        # Gamma = Psychrometric constant (approx 0.066 di elevasi rendah)
        # Koreksi gamma terhadap elevasi (P/Po)
        p = 101.3 * ((293 - 0.0065 * elevasi) / 293) ** 5.26
        gamma = 0.000665 * p
        
        # Hitung W (Weighting Factor)
        # Note: 0.6108 di delta rumus FAO itu kPa, di sini kita pakai rasio jadi aman
        w = delta_grad / (delta_grad + gamma)
        
        # D. Radiasi Bersih (Rn) dalam mm/hari
        ra = hitung_ra_harian(lat, row['Index'])
        rs = (0.25 + 0.54 * n_N) * ra  # a=0.25, b=0.54 (Standard Indonesia/KP-01)
        rns = (1 - 0.25) * rs # Albedo 0.25 (Tanaman Acuan/Rumput)
        
        # Radiasi Gelombang Panjang (Rnl)
        f_t = 2.042e-10 * ((t + 273.16)**4) # Sigma T^4 dalam mm/hari
        f_ed = 0.34 - 0.044 * math.sqrt(ed)
        f_nN = 0.1 + 0.9 * n_N
        rnl = f_t * f_ed * f_nN
        
        rn = rns - rnl
        
        # E. ETo Unadjusted (ETo*)
        # Rumus: W . Rn + (1-W) . f(u) . (ea - ed)
        term1 = w * rn
        term2 = (1 - w) * fu * (ea - ed)
        eto_star = term1 + term2
        
        # F. ETo Final (Dikali Angka Koreksi c)
        eto_final = c_faktor * eto_star
        
        return max(0, round(eto_final, 2))

    except Exception as e:
        return 0.0

# --- 4. DATA DEFAULT ---
def get_default_meteo():
    return pd.DataFrame({
        'Index': range(12),
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'],
        'Suhu (°C)': [27.2, 27.5, 27.8, 28.0, 28.1, 27.9, 27.5, 27.8, 28.0, 28.2, 27.9, 27.4],
        'RH (%)': [85, 84, 83, 82, 82, 81, 80, 78, 79, 81, 83, 85],
        'Angin (m/s)': [1.2]*12,
        'Penyinaran (%)': [45, 50, 55, 60, 65, 70, 75, 80, 70, 60, 50, 45]
    })

if 'df_klimatologi' not in st.session_state:
    st.session_state.df_klimatologi = get_default_meteo()

# --- 5. SIDEBAR & INPUT ---
with st.sidebar:
    st.header("⚙️ Parameter KP-01")
    
    st.info("💡 **Tips:** Copy data Excel (Suhu, RH, Angin, Sinar), klik pojok kiri atas tabel input, lalu Ctrl+V.")

    lintang = st.number_input("📍 Lintang (Derajat)", value=-5.40, step=0.1, help="Negatif (-) untuk Lintang Selatan.")
    elevasi = st.number_input("⛰️ Elevasi (mdpl)", value=10, step=10, help="Ketinggian lokasi dari permukaan laut.")
    
    st.divider()
    
    c_faktor = st.number_input("🎚️ Angka Koreksi (c)", value=1.1, step=0.1, min_value=0.5, max_value=1.5,
                               help="Faktor koreksi akibat kondisi iklim. Standar KP-01: 0.9 - 1.1 (Default aman: 1.1)")
    
    if st.button("🔄 Reset Data Default"):
        st.session_state.df_klimatologi = get_default_meteo()
        st.rerun()

# --- 6. MAIN CONTENT ---
col_input, col_output = st.columns([1.3, 1])

with col_input:
    st.subheader("📝 Input Data Bulanan")
    st.caption("Pastikan urutan kolom Excel: Suhu | RH | Angin | Penyinaran")
    
    edited_df = st.data_editor(
        st.session_state.df_klimatologi,
        use_container_width=True,
        height=450,
        column_config={
            "Index": None,
            "Bulan": st.column_config.TextColumn(disabled=True),
            "Suhu (°C)": st.column_config.NumberColumn(required=True, format="%.1f"),
            "RH (%)": st.column_config.NumberColumn(required=True, max_value=100, format="%d"),
            "Angin (m/s)": st.column_config.NumberColumn(required=True, format="%.2f"),
            "Penyinaran (%)": st.column_config.NumberColumn(required=True, max_value=100, format="%d")
        }
    )
    st.session_state.df_klimatologi = edited_df

# --- HITUNG OTOMATIS ---
eto_results = []
for idx, row in edited_df.iterrows():
    val = hitung_penman_modifikasi(row, lintang, c_faktor, elevasi)
    eto_results.append(val)

df_final = edited_df[['Bulan']].copy()
df_final['ETo (mm/hari)'] = eto_results

with col_output:
    st.subheader("📊 Hasil ETo (mm/hari)")
    st.caption(f"Metode: Penman Modifikasi (c={c_faktor})")
    
    st.dataframe(
        df_final.style.background_gradient(cmap="Blues", subset=['ETo (mm/hari)']).format("{:.2f}"),
        use_container_width=True,
        height=450
    )

# --- 7. GRAFIK & NEXT STEP ---
st.divider()
c1, c2 = st.columns([2, 1])

with c1:
    st.markdown("### 📈 Grafik Evapotranspirasi")
    # Simple Chart
    st.line_chart(df_final.set_index('Bulan'), color="#0072ff")

with c2:
    st.markdown("### 🏁 Tindakan")
    avg_eto = sum(eto_results)/12
    st.metric("Rata-rata Tahunan", f"{avg_eto:.2f} mm/hari")
    
    st.write("")
    if st.button("💾 Simpan & Hubungkan Data ➡️", type="primary", use_container_width=True):
        # Simpan ke Session State Global agar bisa dipanggil modul lain
        st.session_state['data_klimatologi_fix'] = df_final.to_dict('records')
        st.session_state['eto_rata_rata'] = avg_eto
        st.success("Data ETo berhasil disimpan! Silakan pindah ke halaman Pola Tanam.")
