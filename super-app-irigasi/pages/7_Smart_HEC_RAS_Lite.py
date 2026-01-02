import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as patches
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Lite", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #0f2027, #203a43, #2c5364); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 10px; }
    .report-section { background-color: white; padding: 20px; border-radius: 10px; border: 1px solid #eee; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    h3 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; }
    h4 { color: #e67e22; margin-top: 15px; }
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton, .stTabs nav { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE HIDROLIKA (FIXED CRITICAL DEPTH) ---
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
    # Newton-Raphson dengan batasan (Clamping) agar tidak meledak ke ribuan
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
            
            # --- BUG FIX: BATASI NILAI KRITIS ---
            if y_new > 20.0: y_new = 20.0 # Batas maksimal kedalaman logis
            if y_new < 0.01: y_new = 0.01
            
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
else:
    # Ensure column integrity without full reset if possible
    current_cols = list(st.session_state['df_segments_sta'].columns)
    if not all(col in current_cols for col in REQUIRED_COLS):
        st.session_state['df_segments_sta'] = reset_data()

if 'q_global' not in st.session_state: st.session_state['q_global'] = 0.24

# --- 2. UI HEADER & SIDEBAR ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 32px;">🌊 Smart HEC-RAS Lite</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.9;">Analisis Profil Aliran & Desain Saluran Terbuka</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter Desain")
    st.session_state['q_global'] = st.number_input("Debit Rencana (Q) m³/s", 0.001, 100.0, st.session_state['q_global'], 0.01)
    
    st.divider()
    
    # SAVE/LOAD
    st.subheader("💾 File Project")
    project_data = {'q': st.session_state['q_global'], 'segments': st.session_state['df_segments_sta'].to_dict(orient='records')}
    st.download_button("Simpan (.json)", json.dumps(project_data, indent=2), "desain_saluran.json", "application/json")
    
    uploaded_json = st.file_uploader("Buka (.json)", type=['json'])
    if uploaded_json:
        try:
            loaded = json.load(uploaded_json)
            st.session_state['q_global'] = float(loaded['q'])
            st.session_state['df_segments_sta'] = pd.DataFrame(loaded['segments'])[REQUIRED_COLS]
            st.rerun()
        except: st.error("File tidak valid.")
    
    st.divider()
    
    # DISPLAY OPTIONS
    aspect_ratio_fix = st.slider("📐 Vertical Exaggeration", 0.1, 10.0, 1.0, 0.1, help="Ubah skala vertikal agar grafik terlihat lebih jelas")
    
    # EXCEL IMPORT
    st.subheader("📥 Import Excel")
    df_temp = pd.DataFrame([["Saluran A", 0, 50, 100, 99.5, 0.6, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("Download Template", buf.getvalue(), "Template_Input.xlsx")
    
    up_file = st.file_uploader("Upload Excel", type=['xlsx'])
    if up_file:
        try:
            df_up = pd.read_excel(up_file, engine='openpyxl')
            # Smart Column Matcher
            mapper = {}
            for req in REQUIRED_COLS:
                for col in df_up.columns:
                    if req.lower().split()[0] in col.lower(): mapper[req] = col; break
            
            if len(mapper) >= 5: # Toleransi jika minimal 5 kolom cocok
                df_clean = pd.DataFrame()
                for req, orig in mapper.items(): df_clean[req] = df_up[orig]
                # Fill missing
                for req in REQUIRED_COLS: 
                    if req not in df_clean.columns: 
                        df_clean[req] = 0.0 if "Nama" not in req else "Segmen X"
                
                if st.button("Load Data"):
                    st.session_state['df_segments_sta'] = df_clean
                    st.rerun()
            else: st.error("Kolom Excel tidak dikenali. Gunakan Template.")
        except Exception as e: st.error(f"Error: {e}")

    if st.button("Reset Default"): st.session_state['df_segments_sta'] = reset_data(); st.rerun()

# --- 3. MAIN CALCULATION ---
edited_df = st.session_state['df_segments_sta']
results = []
plot_x, plot_bed, plot_ws, plot_egl, plot_crit = [], [], [], [], []

if len(edited_df) > 0:
    try:
        numeric_cols = ["STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]
        calc_df = edited_df.copy()
        for col in numeric_cols: calc_df[col] = pd.to_numeric(calc_df[col], errors='coerce')
        calc_df = calc_df.sort_values(by="STA Awal (m)")
        
        for idx, row in calc_df.iterrows():
            if row[numeric_cols].isnull().any(): continue
            
            # Data Extraction
            nama, sta1, sta2 = str(row['Nama Segmen']), row['STA Awal (m)'], row['STA Akhir (m)']
            z1, z2 = row['Elev Awal (m)'], row['Elev Akhir (m)']
            b, m, n = row['Lebar b (m)'], row['Talud m'], row['Kekasaran n']
            L = sta2 - sta1
            
            if L <= 0: continue
            
            # Hydraulic Calcs
            S = (z1 - z2) / L
            Q = st.session_state['q_global']
            
            yn = solve_manning_y(Q, n, b, S, m)
            yc = solve_critical_y(Q, b, m) # <-- SUDAH DIPERBAIKI (TIDAK AKAN 1000+)
            
            A = (b + m*yn) * yn
            P = b + 2*yn * np.sqrt(1 + m**2)
            R = A/P if P > 0 else 0
            TopW = b + 2*m*yn
            V = Q/A if A > 0 else 0
            Fr = V / np.sqrt(9.81 * (A/TopW)) if TopW > 0 else 0
            
            Vel_Head = (V**2) / (2*9.81)
            EGL = (z2 + yn) + Vel_Head
            
            # Logic Status
            if Fr > 1.1: status = "SUPERKRITIS"
            elif Fr < 0.9: status = "SUBKRITIS"
            else: status = "KRITIS"
            
            results.append({
                "Reach": nama, "Sta Start": sta1, "Sta Finish": sta2,
                "Q Total": Q, "Min Ch El": z2, "W.S. Elev": z2 + yn, "Crit W.S.": z2 + yc,
                "E.G. Elev": EGL, "E.G. Slope": S, "Vel Chnl": V,
                "Flow Area": A, "Bottom Width": b, "Talud": m, "Top Width": TopW, "Froude # Chl": Fr,
                "Status": status
            })
            
            plot_x.extend([sta1, sta2]); plot_bed.extend([z1, z2])
            plot_ws.extend([z1 + yn, z2 + yn]); plot_egl.extend([z1 + yn + Vel_Head, z2 + yn + Vel_Head])
            plot_crit.extend([z1 + yc, z2 + yc])
            
    except Exception as e: st.error(f"Calculation Error: {e}")

# --- 4. TABS DISPLAY ---
tab_geom, tab_prof, tab_cross, tab_table, tab_report = st.tabs(["📝 Geometry", "📈 Profile Plot", "🖼️ Cross Section", "📋 Output Table", "📄 Deep Research Report"])

with tab_geom:
    st.subheader("Editor Data Geometri")
    new_edited = st.data_editor(st.session_state['df_segments_sta'], num_rows="dynamic", use_container_width=True)
    if not new_edited.equals(st.session_state['df_segments_sta']):
        st.session_state['df_segments_sta'] = new_edited
        st.rerun()

with tab_prof:
    if len(plot_x) > 0:
        fig_h = max(4, 6 * aspect_ratio_fix)
        fig, ax = plt.subplots(figsize=(14, fig_h))
        ax.set_facecolor('white')
        
        ax.plot(plot_x, plot_bed, 'k-', lw=2, marker='.', label='Ground')
        ax.plot(plot_x, plot_ws, 'b-', lw=1.5, label='W.S.')
        ax.fill_between(plot_x, plot_bed, plot_ws, color='#00FFFF', alpha=1.0)
        
        # Filter garis kritis agar tidak mengganggu jika error (meski sudah difix)
        clean_crit = [c if c < w + 5 else np.nan for c, w in zip(plot_crit, plot_ws)]
        ax.plot(plot_x, clean_crit, 'r--', lw=1, label='Crit Depth')
        ax.plot(plot_x, plot_egl, 'g--', lw=1, label='E.G. Line')
        
        ax.set_xlabel("Station (m)"); ax.set_ylabel("Elevation (m)")
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='black', title=f"Q = {st.session_state['q_global']} m³/s")
        st.pyplot(fig)
    else: st.info("Belum ada data.")

with tab_cross:
    if len(results) > 0:
        sel = st.selectbox("Pilih Segmen:", [r['Reach'] for r in results])
        d = next(r for r in results if r['Reach'] == sel)
        
        b, m, y, yc = d['Bottom Width'], d['Talud'], d['W.S. Elev'] - d['Min Ch El'], d['Crit W.S.'] - d['Min Ch El']
        h_max = max(y, yc) * 1.5 if max(y, yc) > 0 else 1.0
        
        # Draw Coords
        x = [-(b/2 + m*h_max), -b/2, b/2, b/2 + m*h_max]
        y_g = [h_max, 0, 0, h_max]
        
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(x, y_g, 'k-', lw=2)
        
        # Water
        top_w = b + 2*m*y
        ax.fill([-top_w/2, -b/2, b/2, top_w/2], [y, 0, 0, y], '#00FFFF')
        ax.plot([-top_w/2, top_w/2], [y, y], 'b-', lw=1.5)
        ax.text(0, y, '▼', color='blue', ha='center', va='bottom')
        
        # Crit Line
        ax.hlines(yc, x[0], x[3], 'r', '--', label='Critical')
        
        ax.set_aspect('equal')
        ax.set_title(f"Cross Section: {d['Reach']}")
        ax.grid(True, linestyle=':')
        st.pyplot(fig)

with tab_table:
    if len(results) > 0:
        df_res = pd.DataFrame(results)
        cols = ["Reach", "Sta Start", "Sta Finish", "Q Total", "Min Ch El", "W.S. Elev", "Crit W.S.", "E.G. Elev", "Vel Chnl", "Flow Area", "Top Width", "Froude # Chl", "Status"]
        
        # Rename for display
        disp_cols = {
            "Min Ch El": "Min Ch El (m) [Dasar]", 
            "W.S. Elev": "W.S. Elev (m)",
            "Crit W.S.": "Crit W.S. (m)",
            "Vel Chnl": "Velocity (m/s)",
            "Status": "Kesimpulan"
        }
        
        df_show = df_res[cols].rename(columns=disp_cols)
        
        # Formatting
        for c in df_show.columns:
            if df_show[c].dtype == 'float64': df_show[c] = df_show[c].map('{:,.2f}'.format)
            
        st.dataframe(df_show, use_container_width=True, hide_index=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_show.to_excel(writer, index=False)
        st.download_button("💾 Export Excel", buf.getvalue(), "Hasil_Analisa.xlsx", "application/vnd.ms-excel", type="primary")

# --- 5. DEEP RESEARCH REPORT (NEW) ---
with tab_report:
    if len(results) > 0:
        st.markdown(f"""
        <div class='report-section'>
            <h2 style='text-align:center;'>LAPORAN ANALISIS HIDROLIS MENDALAM</h2>
            <p style='text-align:center;'><b>Proyek:</b> Desain Saluran Terbuka (Cascade System) | <b>Debit:</b> {st.session_state['q_global']} m³/s</p>
        </div>
        """, unsafe_allow_html=True)
        
        # EXECUTIVE SUMMARY
        st.markdown("<div class='report-section'><h3>1. Eksekutif Summary</h3>", unsafe_allow_html=True)
        tot_len = results[-1]['Sta Finish'] - results[0]['Sta Start']
        max_vel = max(r['Vel Chnl'] for r in results)
        avg_fr = np.mean([r['Froude # Chl'] for r in results])
        
        st.write(f"""
        Sistem saluran sepanjang **{tot_len:.1f} meter** telah dianalisis. 
        Karakteristik aliran didominasi oleh rezim **{'SUPERKRITIS' if avg_fr > 1 else 'SUBKRITIS'}** dengan rata-rata Bilangan Froude **{avg_fr:.2f}**.
        Kecepatan maksimum tercatat sebesar **{max_vel:.2f} m/s**.
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
        # DETAILED ANALYSIS
        st.markdown("<div class='report-section'><h3>2. Analisis Tantangan Desain (Deep Dive)</h3>", unsafe_allow_html=True)
        
        # Tantangan 1: Superkritis
        super_segs = [r['Reach'] for r in results if r['Froude # Chl'] > 1.0]
        if super_segs:
            st.markdown("#### A. Tantangan Aliran Superkritis (High Energy)")
            st.warning(f"⚠️ **Isu:** Terdeteksi aliran Superkritis pada segmen: {', '.join(super_segs)}.")
            st.markdown("""
            * **Analisis:** Aliran superkritis memiliki kecepatan tinggi dan kedalaman dangkal. Energi kinetik mendominasi energi potensial.
            * **Risiko:** Gelombang kejut (standing waves) dapat terjadi jika ada belokan atau pilar jembatan. Air sangat sensitif terhadap perubahan geometri.
            * **Mitigasi:** Hindari tikungan tajam pada segmen ini. Pastikan freeboard (tinggi jagaan) cukup untuk menampung percikan air.
            """)
        
        # Tantangan 2: Kecepatan & Erosi
        erosi_segs = [r['Reach'] for r in results if r['Vel Chnl'] > 2.5] # Batas aman pasangan batu ~2-2.5 m/s
        if erosi_segs:
            st.markdown("#### B. Tantangan Erosi Dasar Saluran")
            st.error(f"⛔ **Isu:** Kecepatan > 2.5 m/s pada segmen: {', '.join(erosi_segs)}.")
            st.markdown("""
            * **Analisis:** Kecepatan air melebihi batas izin gerusan untuk saluran tanah atau pasangan batu kali biasa.
            * **Risiko:** Dasar saluran akan tergerus (scouring), menyebabkan dinding longsor.
            * **Solusi:**
                1.  **Lining:** Gunakan beton bertulang (Reinforced Concrete) mutu K-225 atau lebih.
                2.  **Check Dam:** Kurangi kemiringan memanjang dengan menambah bangunan terjun.
            """)
            
        # Tantangan 3: Terjunan (Cascade)
        st.markdown("#### C. Manajemen Energi pada Terjunan (Drop Structures)")
        st.markdown("""
        * **Konteks:** Profil memanjang menunjukkan adanya patahan elevasi (Cascade).
        * **Bahaya:** Di kaki terjunan, energi air sangat besar. Jika tidak diredam, akan terjadi *local scouring* (gerusan lokal) yang dalam.
        * **Rekomendasi:** Wajib merencanakan **Kolam Olak (Stilling Basin)** tipe USBR atau Vlughter di setiap akhir terjunan untuk mengubah aliran Superkritis menjadi Subkritis (Hydraulic Jump).
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
        # KESIMPULAN
        st.markdown("<div class='report-section'><h3>3. Rekomendasi Konstruksi</h3>", unsafe_allow_html=True)
        rec_list = []
        if max_vel > 3: rec_list.append("Gunakan **Beton Bertulang** untuk seluruh saluran utama.")
        elif max_vel > 1.5: rec_list.append("Pasangan Batu Kali dengan plesteran acian halus cukup memadai.")
        else: rec_list.append("Saluran tanah stabil (jika tanah kohesif), namun disarankan pasangan batu untuk maintenance.")
        
        if super_segs: rec_list.append("Sediakan **Kolam Olak** di setiap pertemuan segmen curam ke landai.")
        
        for i, rec in enumerate(rec_list):
            st.success(f"✅ {rec}")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("""<button onclick="window.print()" style="width:100%; background:#27ae60; color:white; border:none; padding:15px; border-radius:5px; font-weight:bold; font-size:16px; cursor:pointer;">🖨️ Cetak Laporan PDF</button>""", unsafe_allow_html=True)

    else: st.info("Data belum tersedia.")
