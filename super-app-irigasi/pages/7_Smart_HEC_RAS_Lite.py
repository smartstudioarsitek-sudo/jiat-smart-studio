import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Lite", layout="wide", page_icon="🌊")

# Sembunyikan Warning Streamlit yang mengganggu
st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #1e3c72, #2a5298); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 10px; }
    .report-box { border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-bottom: 20px; background-color: white; }
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton, .stTabs nav { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA ---
def solve_manning_y(Q, n, b, S, m):
    if S <= 0: return 0.001
    y = 0.5
    for _ in range(50):
        try:
            A = (b + m*y) * y
            P = b + 2*y * np.sqrt(1 + m**2)
            R = A/P if P > 0 else 0
            f = (1/n) * A * (R**(2/3)) * (S**0.5) - Q
            dy = 0.001
            A_d = (b + m*(y+dy)) * (y+dy)
            P_d = b + 2*(y+dy) * np.sqrt(1 + m**2)
            R_d = A_d/P_d if P_d > 0 else 0
            f_d = (1/n) * A_d * (R_d**(2/3)) * (S**0.5) - Q
            df = (f_d - f) / dy
            if df == 0: break
            y_new = y - f/df
            if abs(y_new - y) < 0.0001: return abs(y_new)
            y = abs(y_new)
        except: return 0.001
    return y

def solve_critical_y(Q, b, m):
    g = 9.81
    y = 0.5
    for _ in range(50):
        try:
            A = (b + m*y) * y
            T = b + 2*m*y
            if A <= 0.001: A = 0.001
            f = (Q**2 * T) / (g * A**3) - 1
            dy = 0.001
            A_d = (b + m*(y+dy)) * (y+dy)
            T_d = b + 2*m*(y+dy)
            if A_d <= 0.001: A_d = 0.001
            f_d = (Q**2 * T_d) / (g * A_d**3) - 1
            df = (f_d - f) / dy
            if df == 0: break
            y_new = y - f/df
            if y_new > 20.0: y_new = 20.0 
            if abs(y_new - y) < 0.0001: return abs(y_new)
            y = abs(y_new)
        except: return 0.001
    return y

# --- 1. INISIALISASI ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    data = [
        ["Saluran 1", 0.0, 64.0, 325.54, 323.00, 0.6, 1.0, 0.017],
        ["Saluran 2", 64.0, 114.0, 322.00, 321.00, 0.6, 1.0, 0.017],
        ["Saluran 3", 114.0, 142.0, 320.00, 319.00, 0.6, 1.0, 0.017],
    ]
    return pd.DataFrame(data, columns=REQUIRED_COLS)

if 'df_segments_sta' not in st.session_state:
    st.session_state['df_segments_sta'] = reset_data()

if 'q_global' not in st.session_state: st.session_state['q_global'] = 0.24

# --- 2. HEADER & SIDEBAR ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 32px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.9;">Steady Flow Analysis & HEC-RAS Style Plot</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Plan Data")
    st.session_state['q_global'] = st.number_input("Flow (Q) m³/s", 0.001, 100.0, st.session_state['q_global'], 0.01)
    
    st.divider()
    
    # SAVE/LOAD PROJECT
    st.subheader("💾 Manajemen File")
    project_data = {'q': st.session_state['q_global'], 'segments': st.session_state['df_segments_sta'].to_dict(orient='records')}
    st.download_button("💾 Simpan Project (.json)", json.dumps(project_data, indent=2), "hecras_project.json", "application/json")
    
    uploaded_json = st.file_uploader("Buka Project (.json)", type=['json'])
    if uploaded_json:
        try:
            loaded = json.load(uploaded_json)
            st.session_state['q_global'] = float(loaded['q'])
            st.session_state['df_segments_sta'] = pd.DataFrame(loaded['segments'])
            st.success("Data Dimuat!")
            st.rerun()
        except: st.error("File JSON rusak.")
    
    st.divider()
    
    aspect_ratio_fix = st.slider("📐 Skala Vertikal (Long Section)", 0.1, 10.0, 1.0, 0.1)
    use_manual_zoom = st.checkbox("Manual Scaling", value=False)
    if use_manual_zoom:
        c1, c2 = st.columns(2)
        with c1: y_min = st.number_input("Min Elev", 0.0, 1000.0, 318.0)
        with c2: y_max = st.number_input("Max Elev", 0.0, 1000.0, 330.0)
    
    st.divider()
    
    # --- FITUR IMPORT EXCEL (PERBAIKAN TOTAL) ---
    st.subheader("📥 Excel Import")
    
    # Template
    df_temp = pd.DataFrame([["Saluran 1", 0, 50, 100, 99.5, 0.6, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("📄 Download Template Excel", buf.getvalue(), "Template_HECRAS.xlsx")
    
    up_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    if up_file:
        try:
            # 1. Baca Excel Tanpa Engine Spesifik (Biar Pandas Pilih Sendiri)
            df_up = pd.read_excel(up_file)
            
            # 2. Normalisasi Nama Kolom (Hilangkan spasi, lowercase, tanda kurung)
            # Biar "Lebar b" terbaca sama dengan "Lebar b (m)"
            def clean_col(txt):
                return str(txt).lower().replace(" ", "").replace("(m)", "").replace(".", "")
            
            df_up.columns = [clean_col(c) for c in df_up.columns]
            
            # 3. Mapping Kolom Kita -> Kolom Excel
            # Format: 'Kolom Sistem': ['kemungkinan1', 'kemungkinan2']
            mapping = {
                "Nama Segmen": ["nama", "reach", "segmen"],
                "STA Awal (m)": ["staawal", "start", "hulu"],
                "STA Akhir (m)": ["staakhir", "end", "hilir"],
                "Elev Awal (m)": ["elevawal", "z1", "startelv"],
                "Elev Akhir (m)": ["elevakhir", "z2", "endelv"],
                "Lebar b (m)": ["lebar", "width", "b"],
                "Talud m": ["talud", "slope", "m", "z"],
                "Kekasaran n": ["kekasaran", "manning", "n"]
            }
            
            new_data = pd.DataFrame()
            cols_found = 0
            
            for system_col, keywords in mapping.items():
                found = False
                for kw in keywords:
                    for excel_col in df_up.columns:
                        if kw in excel_col:
                            new_data[system_col] = df_up[excel_col]
                            found = True
                            cols_found += 1
                            break
                    if found: break
            
            if cols_found >= 6: # Jika minimal 6 kolom penting ketemu
                if st.button("✅ Load Data Excel"):
                    st.session_state['df_segments_sta'] = new_data
                    st.rerun()
            else:
                st.error("Gagal mencocokkan kolom. Gunakan Template di atas.")
                
        except Exception as e: st.error(f"Error baca file: {e}")

    if st.button("🔄 Reset Default"): 
        st.session_state['df_segments_sta'] = reset_data()
        st.rerun()

# --- 3. LOGIC ---
edited_df = st.session_state['df_segments_sta']
results = []
plot_x, plot_bed, plot_ws, plot_egl, plot_crit = [], [], [], [], []

if not edited_df.empty:
    try:
        # Pastikan Numeric
        num_cols = ["STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
        calc_df = edited_df.copy()
        
        # Perbaiki jika ada kolom yang hilang saat import
        for c in num_cols:
            if c not in calc_df.columns: calc_df[c] = 0.0
        
        for col in num_cols: calc_df[col] = pd.to_numeric(calc_df[col], errors='coerce')
        calc_df = calc_df.sort_values(by="STA Awal (m)")
        
        for idx, row in calc_df.iterrows():
            if row[num_cols].isnull().any(): continue
            
            nama = str(row.get('Nama Segmen', f'Segmen {idx}'))
            sta1, sta2 = row['STA Awal (m)'], row['STA Akhir (m)']
            z1, z2 = row['Elev Awal (m)'], row['Elev Akhir (m)']
            b, m, n = row['Lebar b (m)'], row['Talud m'], row['Kekasaran n']
            
            L = sta2 - sta1
            if L <= 0: continue
            
            S = (z1 - z2) / L
            Q = st.session_state['q_global']
            
            yn = solve_manning_y(Q, n, b, S, m)
            yc = solve_critical_y(Q, b, m)
            
            A = (b + m*yn) * yn
            P = b + 2*yn * np.sqrt(1 + m**2)
            R = A/P if P > 0 else 0
            TopW = b + 2*m*yn
            V = Q/A if A > 0 else 0
            Fr = V / np.sqrt(9.81 * (A/TopW)) if TopW > 0 else 0
            
            Vel_Head = (V**2) / (2*9.81)
            EGL = (z2 + yn) + Vel_Head
            EG_Slope = (n * V)**2 / (R**(4/3)) if R>0 else 0
            
            status = "SUPERKRITIS" if Fr > 1.1 else ("SUBKRITIS" if Fr < 0.9 else "KRITIS")
            note = status
            if V > 3.0: note += " (Erosi!)"
            elif V < 0.6: note += " (Endapan)"
            
            results.append({
                "Reach": nama, "Sta Start": sta1, "Sta Finish": sta2,
                "Q Total": Q, "Min Ch El": z2, "W.S. Elev": z2 + yn, "Crit W.S.": z2 + yc,
                "E.G. Elev": EGL, "E.G. Slope": S, "Vel Chnl": V,
                "Flow Area": A, "Bottom Width": b, "Talud": m, "Top Width": TopW, "Froude # Chl": Fr,
                "Keterangan": note
            })
            
            plot_x.extend([sta1, sta2]); plot_bed.extend([z1, z2])
            plot_ws.extend([z1 + yn, z2 + yn]); plot_egl.extend([z1 + yn + Vel_Head, z2 + yn + Vel_Head])
            plot_crit.extend([z1 + yc, z2 + yc])
            
    except Exception as e: st.error(f"Error Perhitungan: {e}")

# --- 4. TABS UI ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Geometry", "📈 Profile Plot", "🖼️ Cross Section", "📋 Output Table", "📄 Laporan Teknis"])

with tab1:
    st.subheader("Data Geometri Saluran")
    # Gunakan st.data_editor dengan key agar state tersimpan
    new_df = st.data_editor(st.session_state['df_segments_sta'], num_rows="dynamic", use_container_width=True, key="editor_geom")
    # Simpan perubahan manual user ke state
    if not new_df.equals(st.session_state['df_segments_sta']):
        st.session_state['df_segments_sta'] = new_df
        st.rerun()

with tab2:
    if len(plot_x) > 0:
        fig_h = max(4, 6 * aspect_ratio_fix)
        fig, ax = plt.subplots(figsize=(14, fig_h))
        ax.set_facecolor('white')
        
        ax.plot(plot_x, plot_bed, 'k-', lw=2, marker='.', label='Ground')
        ax.plot(plot_x, plot_ws, 'b-', lw=1.5, label='W.S.')
        ax.fill_between(plot_x, plot_bed, plot_ws, color='#00FFFF', alpha=1.0)
        
        clean_crit = [c if c < w + 5 else np.nan for c, w in zip(plot_crit, plot_ws)]
        ax.plot(plot_x, clean_crit, 'r--', lw=1, label='Crit')
        ax.plot(plot_x, plot_egl, 'g--', lw=1, label='E.G.')
        
        ax.set_xlabel("Station (m)"); ax.set_ylabel("Elevation (m)")
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='black')
        
        if use_manual_zoom: 
            ax.set_ylim(y_min, y_max)
        
        st.pyplot(fig)
    else: st.info("Belum ada data.")

with tab3:
    if len(results) > 0:
        sel = st.selectbox("Pilih Segmen:", [r['Reach'] for r in results])
        d = next(r for r in results if r['Reach'] == sel)
        
        b, m, y, yc = d['Bottom Width'], d['Talud'], d['W.S. Elev'] - d['Min Ch El'], d['Crit W.S.'] - d['Min Ch El']
        h_max = max(y, yc) * 1.5 if max(y, yc) > 0 else 1.0
        
        x = [-(b/2 + m*h_max), -b/2, b/2, b/2 + m*h_max]
        y_g = [h_max, 0, 0, h_max]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x, y_g, 'k-', lw=2, label='Ground')
        
        top_w = b + 2*m*y
        ax.fill([-top_w/2, -b/2, b/2, top_w/2], [y, 0, 0, y], '#00FFFF', label='Water')
        ax.plot([-top_w/2, top_w/2], [y, y], 'b-', lw=1.5)
        ax.text(0, y, '▼', color='blue', ha='center', va='bottom', fontsize=14)
        
        ax.hlines(yc, x[0], x[3], 'r', '--', label='Crit')
        
        ax.set_aspect('equal')
        ax.set_title(f"Cross Section: {d['Reach']}")
        ax.set_xlabel("Width (m)")
        ax.grid(True, linestyle=':')
        ax.legend()
        st.pyplot(fig)

with tab4:
    if len(results) > 0:
        df_res = pd.DataFrame(results)
        cols = ["Reach", "Sta Start", "Sta Finish", "Q Total", "Min Ch El", "W.S. Elev", "Crit W.S.", "E.G. Elev", "E.G. Slope", "Vel Chnl", "Flow Area", "Top Width", "Froude # Chl", "Keterangan"]
        
        final = df_res[cols].rename(columns={
            "Min Ch El": "Min Ch El (m)", 
            "W.S. Elev": "W.S. Elev (m)",
            "Crit W.S.": "Crit W.S. (m)",
            "Vel Chnl": "Vel (m/s)",
            "Froude # Chl": "Froude"
        })
        
        # Format Angka
        for c in final.columns:
            if final[c].dtype == 'float64': final[c] = final[c].map('{:,.2f}'.format)
            
        st.dataframe(final, use_container_width=True, hide_index=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: final.to_excel(writer, index=False)
        st.download_button("💾 Export Excel", buf.getvalue(), "Hasil_HEC_RAS.xlsx", "application/vnd.ms-excel", type="primary")

with tab5:
    if len(results) > 0:
        st.markdown(f"""
        <div class='report-box'>
            <h2 style='text-align:center;'>LAPORAN ANALISIS HIDROLIS</h2>
            <hr>
            <h3>1. Ringkasan Eksekutif</h3>
            <p>Debit Desain: <b>{st.session_state['q_global']} m³/s</b></p>
            <p>Panjang Saluran: <b>{results[-1]['Sta Finish'] - results[0]['Sta Start']:.1f} m</b></p>
        </div>
        """, unsafe_allow_html=True)
        
        count_super = sum(1 for r in results if r['Froude # Chl'] > 1.1)
        if count_super > 0:
            st.warning(f"⚠️ Terdeteksi {count_super} segmen dengan aliran SUPERKRITIS (Froude > 1.1).")
            st.info("💡 REKOMENDASI: Pasang Kolam Olak (Stilling Basin) di hilir segmen tersebut untuk meredam energi.")
        else:
            st.success("✅ Aliran dominan SUBKRITIS (Tenang). Saluran relatif aman dari gerusan ekstrim.")
            
        st.markdown("### 2. Tabel Detail")
        st.dataframe(final, use_container_width=True, hide_index=True)
        
        st.markdown("""<button onclick="window.print()" style="background:#28a745; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer;">🖨️ Cetak PDF</button>""", unsafe_allow_html=True)
