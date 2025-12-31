import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Debit Andalan (Mock)", layout="wide", page_icon="🌊")

# --- 2. HEADER ---
st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(120deg, #0277bd 0%, #039be5 50%, #4fc3f7 100%);
        padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;
    }
    .stExpander { border: 1px solid #ddd; border-radius: 5px; }
</style>
<div class="hero-box">
    <h1 style="margin:0; font-size: 35px;">🌊 Analisa Debit Andalan</h1>
    <p style="opacity: 0.9;">Metode Dr. F.J. Mock (Water Balance)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. FUNGSI DATA DEFAULT & RESET ---
def get_default_mock():
    # Cek Data ETo dari Modul 1
    if 'data_eto_transfer' in st.session_state:
        eto_12 = st.session_state['data_eto_transfer']
        sumber = "✅ Terhubung: Modul Klimatologi (Penman)"
    else:
        eto_12 = [4.5, 4.6, 4.5, 4.4, 4.2, 4.0, 3.8, 3.9, 4.2, 4.5, 4.6, 4.4] # Dummy
        sumber = "⚠️ Default (Gunakan Modul Klimatologi untuk Hasil Akurat)"
    
    # Data Hujan & Hari Hujan Dummy
    ch_dummy = [350, 300, 280, 200, 150, 100, 50, 20, 80, 150, 250, 300]
    hh_dummy = [20, 18, 16, 12, 10, 8, 4, 2, 6, 10, 15, 18]
    
    df = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'],
        'Curah Hujan (mm)': ch_dummy,
        'Hari Hujan (hari)': hh_dummy,
        'ETo (mm/hari)': eto_12
    })
    return df, sumber

if 'df_mock' not in st.session_state:
    df_init, status_init = get_default_mock()
    st.session_state.df_mock = df_init
    st.session_state.status_mock = status_init

# --- 4. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("🔧 Parameter DAS")
    
    if st.button("🔄 Reset Data", type="secondary"):
        df_new, stat_new = get_default_mock()
        st.session_state.df_mock = df_new
        st.session_state.status_mock = stat_new
        st.rerun()

    st.divider()
    luas_das = st.number_input("Luas DAS (km²)", value=500.0, step=10.0, help="Luas Daerah Aliran Sungai")
    
    with st.expander("⚙️ Kalibrasi Mock", expanded=True):
        m = st.slider("Faktor Lahan Terbuka (m)", 0, 50, 30, help="Persentase lahan tanpa tanaman (%)") / 100
        smc = st.number_input("Soil Moisture Cap. (SMC)", value=200.0, help="Kapasitas Kelembaban Tanah (mm)")
        i_coeff = st.number_input("Koef. Infiltrasi (I)", value=0.4, min_value=0.0, max_value=1.0)
        k_rec = st.number_input("Faktor Resesi (k)", value=0.6, min_value=0.0, max_value=1.0)
        
    st.info(f"Luas: {luas_das} km²")

# --- 5. INPUT DATA ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("1. Input Data Hidrologi")
    st.caption(st.session_state.get('status_mock', ""))
    st.info("💡 **Tips:** Copy data Hujan & Hari Hujan dari Excel dan Paste di sini.")
    
    edited_df = st.data_editor(
        st.session_state.df_mock,
        height=450,
        use_container_width=True,
        column_config={
            "Bulan": st.column_config.TextColumn(disabled=True),
            "ETo (mm/hari)": st.column_config.NumberColumn(disabled=True, help="Otomatis dari Modul 1"),
            "Curah Hujan (mm)": st.column_config.NumberColumn(required=True, min_value=0),
            "Hari Hujan (hari)": st.column_config.NumberColumn(required=True, min_value=0, max_value=31)
        }
    )
    st.session_state.df_mock = edited_df

# --- 6. ENGINE PERHITUNGAN MOCK (LOOPING) ---
def hitung_mock(df, luas, m_fac, smc_val, i_val, k_val):
    results = []
    # Inisialisasi awal (V_t-1 diasumsikan SMC dulu agar stabil)
    vn_prev = smc_val 
    
    # KITA JALANKAN 2X LOOP (TAHUN) AGAR NILAI AWAL STABIL (STEADY STATE)
    # Loop 1 (Pemanasan)
    for idx, row in df.iterrows():
        # Jumlah hari dalam bulan
        days = 30 # Penyederhanaan, bisa dibuat 31/28/30
        
        # 1. Evapotranspirasi Terbatas (Et)
        # Rumus: Et = ETo * (Delta E) ... Variasi Mock banyak, ini versi umum PU
        # Asumsi sederhanan: Et = ETo * Hari * Faktor Exposed
        # Kita gunakan pendekatan Eto Bulanan
        eto_bulan = row['ETo (mm/hari)'] * days
        
        # Et Limited (E_act)
        # Jika Hujan > ETo -> E_act = ETo
        # Jika tidak, tergantung SMC
        rain = row['Curah Hujan (mm)']
        
        # Water Surplus sementara
        ws_pot = rain - eto_bulan
        
        # Perubahan Soil Storage (Delta S)
        if ws_pot > 0:
            e_act = eto_bulan
            # Air sisa mengisi tanah dulu sampai penuh (SMC)
            delta_s = min(ws_pot, smc_val - vn_prev) # Berapa kurangnya utk penuh
            ws = ws_pot - delta_s # Sisa air menjadi Water Surplus benaran
        else:
            # Air kurang, ambil dari tanah
            delta_s = ws_pot # Bernilai negatif
            # Cek agar tidak kering kerontang
            if (vn_prev + delta_s) < 0:
                delta_s = -vn_prev # Kuras habis
            e_act = rain - delta_s # E_act sebenarnya lebih kecil dari ETo
            ws = 0
            
        vn = vn_prev + delta_s # Volume tanah baru
        
        # Infiltrasi & Runoff
        infil = ws * i_val
        direct_runoff = ws - infil
        
        # Baseflow (Vn = 0.5(1+k)I + k.Vn-1)
        # Rumus Mock untuk Volume Groundwater (Vn)
        gn = 0.5 * (1 + k_val) * infil + k_val * (vn_prev if idx > -99 else 0) # Simplifikasi storage
        # Baseflow = Vn - Vn-1 + Infil ??
        # Atau simple Mock: Baseflow = Infil - (Gn - Gn_prev) ...
        # Kita pakai rumus standard Mock Flow:
        # Baseflow = I - (V_g_curr - V_g_prev)
        # Dimana V_g_curr = k * V_g_prev + 0.5 * (1+k) * I
        
        # Agar simple dan stabil di kode ini, kita pakai pendekatan Baseflow langsung:
        # BF = infil * (1-k) ... (Asumsi sederhana untuk quick calc)
        # TAPI, mari pakai yang agak benar:
        
        # Recalculate Storage Groundwater (V_g)
        # V_g_new = k * V_g_old + 0.5 * (1+k) * infil
        # dV_g = V_g_new - V_g_old
        # BF = infil - dV_g
        # Untuk loop 1 ini kita hanya butuh update V_g_prev
        pass # Skip detail di loop pemanasan, just update Soil Storage
        vn_prev = vn

    # Loop 2 (Real Calculation)
    # Reset V_g (Groundwater)
    vg_prev = 100 # Asumsi awal
    
    final_data = []
    
    for idx, row in df.iterrows():
        days = 30
        eto_bulan = row['ETo (mm/hari)'] * days
        rain = row['Curah Hujan (mm)']
        
        ws_pot = rain - eto_bulan
        
        if ws_pot > 0:
            e_act = eto_bulan
            delta_s = min(ws_pot, smc_val - vn_prev)
            ws = ws_pot - delta_s
        else:
            delta_s = ws_pot
            if (vn_prev + delta_s) < 0: delta_s = -vn_prev
            e_act = rain - delta_s
            ws = 0
            
        vn = vn_prev + delta_s
        
        infil = ws * i_val
        dro = ws - infil
        
        # Groundwater Storage Calculation
        vg = k_val * vg_prev + 0.5 * (1 + k_val) * infil
        dvg = vg - vg_prev
        baseflow = infil - dvg
        
        # Total Runoff (mm)
        tro_mm = baseflow + dro
        
        # Konversi ke Debit (m3/s)
        # Q = (TRO_mm / 1000) * (Luas_km2 * 1,000,000) / (Days * 86400)
        q_m3s = (tro_mm / 1000) * (luas * 1000000) / (days * 86400)
        q_m3s = max(0, q_m3s) # Safety no negative
        
        final_data.append({
            'Bulan': row['Bulan'],
            'Hujan (mm)': rain,
            'E.Act (mm)': round(e_act, 1),
            'Surplus (mm)': round(ws, 1),
            'Baseflow (mm)': round(baseflow, 1),
            'Total Runoff (mm)': round(tro_mm, 1),
            'Debit (m³/s)': round(q_m3s, 3)
        })
        
        vn_prev = vn
        vg_prev = vg
        
    return pd.DataFrame(final_data)

# Hitung!
df_hasil_mock = hitung_mock(edited_df, luas_das, m, smc, i_coeff, k_rec)

# --- 7. VISUALISASI ---
with col2:
    st.subheader("2. Hasil Debit (Hydrograph)")
    
    # Combo Chart: Bar (Hujan) & Line (Debit)
    # Karena sumbu Y hujan biasanya dibalik (inverted), kita pakai 2 grafik terpisah agar rapi
    
    # Grafik Debit
    chart_q = alt.Chart(df_hasil_mock).mark_area(
        line={'color':'blue'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='white', offset=0),
                   alt.GradientStop(color='blue', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        )
    ).encode(
        x=alt.X('Bulan', sort=None),
        y=alt.Y('Debit (m³/s)', title='Debit Andalan (m³/s)'),
        tooltip=['Bulan', 'Debit (m³/s)', 'Hujan (mm)']
    ).properties(height=300)
    
    st.altair_chart(chart_q, use_container_width=True)
    
    # Ringkasan
    q_avg = df_hasil_mock['Debit (m³/s)'].mean()
    q_max = df_hasil_mock['Debit (m³/s)'].max()
    q_min = df_hasil_mock['Debit (m³/s)'].min()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Q Rata-rata", f"{q_avg:.2f} m³/s")
    c2.metric("Q Maksimum", f"{q_max:.2f} m³/s")
    c3.metric("Q Minimum", f"{q_min:.2f} m³/s")

# --- 8. TABEL DETAIL & EXPORT ---
st.divider()
st.subheader("3. Detail Perhitungan Neraca Air")

st.dataframe(df_hasil_mock, use_container_width=True)

# Tombol Simpan (Opsional, barangkali butuh untuk modul Pipa nanti)
if st.button("💾 Simpan Hasil Mock", type="primary"):
    st.session_state['data_debit_mock'] = df_hasil_mock['Debit (m³/s)'].tolist()
    st.toast("✅ Data Debit berhasil disimpan ke sistem.", icon="🌊")
