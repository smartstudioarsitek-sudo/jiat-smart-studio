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
    <p style="opacity: 0.9;">Metode F.J. Mock (Water Balance)</p>
</div>
""", unsafe_allow_html=True)

# --- 3. FUNGSI DATA DEFAULT ---
def get_default_mock():
    # Cek Data ETo dari Modul 1
    if 'data_eto_transfer' in st.session_state:
        eto_12 = st.session_state['data_eto_transfer']
        sumber = "✅ Terhubung: Modul Klimatologi (Penman)"
        link_status = True
    else:
        eto_12 = [4.5, 4.6, 4.5, 4.4, 4.2, 4.0, 3.8, 3.9, 4.2, 4.5, 4.6, 4.4] 
        sumber = "⚠️ Warning: Data ETo Belum Ada (Menggunakan Data Dummy)."
        link_status = False
    
    # Data Hujan & Hari Hujan Default
    ch_dummy = [350, 300, 280, 200, 150, 100, 50, 20, 80, 150, 250, 300]
    hh_dummy = [20, 18, 16, 12, 10, 8, 4, 2, 6, 10, 15, 18]
    
    df = pd.DataFrame({
        'Bulan': ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'],
        'Curah Hujan (mm)': ch_dummy,
        'Hari Hujan (hari)': hh_dummy,
        'ETo (mm/hari)': eto_12
    })
    return df, sumber, link_status

# Inisialisasi State
if 'df_mock' not in st.session_state:
    df_init, status_init, link_init = get_default_mock()
    st.session_state.df_mock = df_init
    st.session_state.status_mock = status_init
    st.session_state.link_ok = link_init

# Cek Ulang Link (Refresh Logic)
if 'data_eto_transfer' in st.session_state and not st.session_state.get('link_ok', False):
    st.session_state.df_mock['ETo (mm/hari)'] = st.session_state['data_eto_transfer']
    st.session_state.status_mock = "✅ Terhubung: Modul Klimatologi (Penman)"
    st.session_state.link_ok = True
    st.toast("Data ETo berhasil disinkronisasi!", icon="🔗")

# --- 4. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("🔧 Parameter DAS")
    
    if st.button("🔄 Reset Data Tabel", type="secondary"):
        df_new, stat_new, link_new = get_default_mock()
        st.session_state.df_mock = df_new
        st.session_state.status_mock = stat_new
        st.session_state.link_ok = link_new
        st.rerun()

    st.divider()
    luas_das = st.number_input("Luas DAS (km²)", value=500.0, step=10.0)
    
    with st.expander("⚙️ Kalibrasi Mock", expanded=True):
        m = st.slider("Faktor Lahan Terbuka (m)", 0, 50, 30) / 100
        smc = st.number_input("Soil Moisture Cap. (SMC)", value=200.0)
        i_coeff = st.number_input("Koef. Infiltrasi (I)", value=0.4, max_value=1.0)
        k_rec = st.number_input("Faktor Resesi (k)", value=0.6, max_value=1.0)

# --- 5. INPUT DATA (LABEL LEBIH JELAS) ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("1. Input Data Hidrologi")
    
    if st.session_state.get('link_ok', False):
        st.success(st.session_state.status_mock)
    else:
        st.warning(st.session_state.status_mock)
        
    # INFO PENTING soal Hujan Bulanan
    st.info("ℹ️ **Catatan:** Masukkan **TOTAL curah hujan** selama satu bulan (akumulasi), BUKAN hujan harian maksimum.")
    
    edited_df = st.data_editor(
        st.session_state.df_mock,
        height=480,
        use_container_width=True,
        key="editor_mock_jelas_v3", 
        column_config={
            "Bulan": st.column_config.TextColumn(
                "📅 Bulan", disabled=True
            ),
            "ETo (mm/hari)": st.column_config.NumberColumn(
                "🔒 ETo (Link)", 
                help="Otomatis dari Modul Klimatologi",
                disabled=True, 
                format="%.2f"
            ),
            # LABEL DIPERJELAS DI SINI
            "Curah Hujan (mm)": st.column_config.NumberColumn(
                "✏️ Tot. Hujan Bulanan (mm)", 
                help="Masukkan jumlah total hujan dalam satu bulan (mm/bulan).",
                required=True, min_value=0
            ),
            "Hari Hujan (hari)": st.column_config.NumberColumn(
                "✏️ Hari Hujan", 
                help="Jumlah hari terjadinya hujan dalam bulan tersebut.",
                required=True, min_value=0, max_value=31
            )
        }
    )
    st.session_state.df_mock = edited_df

# --- 6. ENGINE MOCK ---
def hitung_mock(df, luas, m_fac, smc_val, i_val, k_val):
    # Loop Pemanasan
    vn_prev = smc_val 
    for idx, row in df.iterrows():
        days = 30
        eto_bulan = row['ETo (mm/hari)'] * days 
        rain = row['Curah Hujan (mm)']
        ws_pot = rain - eto_bulan
        if ws_pot > 0:
            delta_s = min(ws_pot, smc_val - vn_prev)
        else:
            delta_s = ws_pot
            if (vn_prev + delta_s) < 0: delta_s = -vn_prev
        vn = vn_prev + delta_s
        vn_prev = vn

    # Loop Real
    vg_prev = 100 
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
        
        vg = k_val * vg_prev + 0.5 * (1 + k_val) * infil
        dvg = vg - vg_prev
        baseflow = infil - dvg
        
        tro_mm = baseflow + dro
        q_m3s = (tro_mm / 1000) * (luas * 1000000) / (days * 86400)
        q_m3s = max(0, q_m3s)
        
        final_data.append({
            'Bulan': row['Bulan'],
            'Hujan (mm)': rain,
            'E.Act (mm)': round(e_act, 1),
            'Surplus (mm)': round(ws, 1),
            'Baseflow (mm)': round(baseflow, 1),
            'Debit (m³/s)': round(q_m3s, 3)
        })
        vn_prev = vn
        vg_prev = vg
        
    return pd.DataFrame(final_data)

# Hitung
df_hasil_mock = hitung_mock(edited_df, luas_das, m, smc, i_coeff, k_rec)

# --- 7. VISUALISASI ---
with col2:
    st.subheader("2. Grafik Debit Andalan")
    
    chart = alt.Chart(df_hasil_mock).mark_area(
        line={'color':'#0288d1'},
        color=alt.Gradient(
            gradient='linear', stops=[alt.GradientStop(color='white', offset=0), alt.GradientStop(color='#03a9f4', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        )
    ).encode(
        x=alt.X('Bulan', sort=None),
        y=alt.Y('Debit (m³/s)'),
        tooltip=['Bulan', 'Debit (m³/s)', 'Hujan (mm)']
    ).properties(height=350)
    
    st.altair_chart(chart, use_container_width=True)
    
    # Ringkasan Angka
    q_avg = df_hasil_mock['Debit (m³/s)'].mean()
    c1, c2 = st.columns(2)
    c1.metric("Q Rata-rata", f"{q_avg:.2f} m³/s")
    c2.metric("Q Andalan (80%)", f"{df_hasil_mock['Debit (m³/s)'].quantile(0.2):.2f} m³/s", help="Estimasi Q80")

# --- 8. TABEL DETAIL & EXPORT ---
st.divider()
st.subheader("3. Hasil Analisa & Ekspor")

col_res1, col_res2 = st.columns([3, 1])

with col_res1:
    st.dataframe(df_hasil_mock, use_container_width=True, height=300)

with col_res2:
    st.write("### 💾 Simpan Data")
    st.caption("Simpan hasil perhitungan Debit Andalan ini untuk digunakan pada modul Irigasi Pipa/Pompa.")
    
    if st.button("🚀 Simpan Hasil Debit", type="primary", use_container_width=True):
        st.session_state['data_debit_mock'] = df_hasil_mock['Debit (m³/s)'].tolist()
        st.session_state['data_debit_bulan'] = df_hasil_mock['Bulan'].tolist()
        st.toast("✅ Data Debit Berhasil Disimpan! Siap dipakai di Modul Pipa.", icon="🌊")
