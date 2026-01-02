import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- CONFIG ---
st.set_page_config(page_title="Desain Saluran & Got Miring", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #0d47a1, #1976d2); color: white;
        border-radius: 10px; text-align: center; margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f1f8e9; border-left: 5px solid #33691e; padding: 15px; border-radius: 5px;
    }
    .danger-box {
        background-color: #ffebee; border: 1px solid #ef5350; padding: 15px; border-radius: 5px; color: #c62828;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. RUMUS CANGGIH (HEC-RAS LITE ENGINE) ---
def solve_manning_y(Q, n, b, S, m):
    """Mencari kedalaman normal (yn) secara iteratif (Newton-Raphson)"""
    y = 0.5 # Tebakan awal
    for _ in range(20):
        A = (b + m*y) * y
        P = b + 2*y * np.sqrt(1 + m**2)
        R = A/P
        # Q = (1/n) * A * R^(2/3) * S^(1/2)
        f = (1/n) * A * (R**(2/3)) * (S**0.5) - Q
        
        # Turunan f (df/dy) didekati secara numerik
        dy = 0.001
        A_d = (b + m*(y+dy)) * (y+dy)
        P_d = b + 2*(y+dy) * np.sqrt(1 + m**2)
        R_d = A_d/P_d
        f_d = (1/n) * A_d * (R_d**(2/3)) * (S**0.5) - Q
        df = (f_d - f) / dy
        
        y_new = y - f/df
        if abs(y_new - y) < 0.0001: return y_new
        y = y_new
    return y

def hitung_got_miring(Q, b, m, L, H_drop, n_beton=0.014):
    # 1. Geometri
    S_bed = H_drop / L # Kemiringan Dasar (3.33% di kasus Nokan)
    
    # 2. Kedalaman Normal (yn) - Kondisi saat aliran stabil di kecepatan tinggi
    y_n = solve_manning_y(Q, n_beton, b, S_bed, m)
    
    # 3. Properti Aliran Superkritis
    A_n = (b + m*y_n) * y_n
    V_n = Q / A_n
    
    # Froude Number
    T_top = b + 2*m*y_n
    D_hyd = A_n / T_top
    Fr = V_n / np.sqrt(9.81 * D_hyd)
    
    # 4. AERASI (AIR ENTRAINMENT) - KP-04
    # Air "mengembang" karena bercampur udara pada kecepatan tinggi
    # Rumus pendekatan (Gumensky): Bulking Factor
    if V_n > 6.0: # Biasanya aerasi mulai signifikan di V > 6 m/s
        # Persentase udara (C)
        # C = 0.2 * (V - 9) -> Empiris kasar
        # Kita pakai safety factor tinggi dinding (Freeboard)
        h_aerasi = 0.6 * (V_n**2 / (2*9.81)) # Kriteria USBR untuk freeboard chute
    else:
        h_aerasi = 0.2 + (0.1 * V_n) # Freeboard standar KP-03
        
    h_total_perlu = y_n + h_aerasi
    
    # 5. KOLAM OLAK (STILLING BASIN)
    # Tentukan tipe berdasarkan Froude
    if Fr < 4.5:
        tipe_olak = "USBR Tipe IV (Gigi Ompong) atau Vlugter"
    elif Fr > 4.5 and V_n < 18:
        tipe_olak = "USBR Tipe III (Gigi Penghadang)"
    else:
        tipe_olak = "USBR Tipe II (Untuk V sangat tinggi)"
        
    return {
        'S_bed': S_bed * 100, # persen
        'yn': y_n,
        'V': V_n,
        'Fr': Fr,
        'h_aerasi': h_aerasi,
        'h_desain': h_total_perlu,
        'tipe_olak': tipe_olak
    }

def plot_chute(L, H, y_air):
    fig, ax = plt.subplots(figsize=(10, 4))
    
    # Koordinat Dasar Saluran (Miring)
    x = [0, L]
    y_bed = [H, 0] # Dari H turun ke 0
    
    # Muka Air
    y_water = [H + y_air, 0 + y_air]
    
    ax.plot(x, y_bed, 'k-', linewidth=3, label='Dasar Saluran')
    ax.plot(x, y_water, 'c--', linewidth=2, label='Muka Air (Teoretis)')
    
    # Fill air
    ax.fill_between(x, y_bed, y_water, color='cyan', alpha=0.3)
    
    # Anotasi
    ax.set_title(f"Profil Memanjang Got Miring (L={L}m, Drop={H}m)", fontsize=12)
    ax.set_xlabel("Jarak (m)")
    ax.set_ylabel("Elevasi (m)")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    
    return fig

# --- UI UTAMA ---
st.markdown('<div class="header-box"><h1>🚀 Advanced Channel & Chute Designer</h1><p>Solusi Khusus Topografi Ekstrim (Nokan Case)</p></div>', unsafe_allow_html=True)

# TAB NAVIGASI
mode = st.radio("Pilih Mode Desain:", ["🏗️ Saluran Irigasi Biasa (Manning)", "🎢 Got Miring Ekstrim (Chute)"], horizontal=True)

if mode == "🏗️ Saluran Irigasi Biasa (Manning)":
    st.info("Mode ini untuk saluran tersier/sekunder yang landai (Slope < 1%). Gunakan fitur standard.")
    # (Kode lama untuk saluran biasa bisa ditaruh disini atau di-skip demi fokus ke challenge)
    st.write("Silakan gunakan modul standard untuk saluran landai. Pindah ke tab sebelah untuk kasus Nokan.")

else:
    # --- MODE GOT MIRING (NOKAN SPECIAL) ---
    st.markdown("""
    <div style="background-color: #fff3e0; padding: 15px; border-left: 5px solid #ff9800; margin-bottom: 20px;">
        <strong>⚠️ CHUTE DESIGN MODE</strong><br>
        Modul ini menggunakan algoritma aliran superkritis untuk menghitung dimensi <strong>Got Miring</strong>, 
        analisa <strong>Aerasi (Bulking)</strong>, dan rekomendasi <strong>Kolam Olak</strong>.
    </div>
    """, unsafe_allow_html=True)
    
    col_in, col_out = st.columns([1, 1.5])
    
    with col_in:
        st.subheader("1. Parameter Ekstrim")
        Q_desain = st.number_input("Debit Desain (m³/s)", 0.1, 50.0, 2.0, 0.1)
        L_saluran = st.number_input("Panjang Saluran (m)", 10.0, 5000.0, 1200.0, 10.0)
        H_drop = st.number_input("Beda Tinggi / Drop (m)", 1.0, 500.0, 40.0, 1.0)
        
        st.subheader("2. Geometri Penampang")
        b_lebar = st.number_input("Lebar Dasar (m)", 0.5, 10.0, 1.5, 0.1)
        m_talud = st.number_input("Kemiringan Talud (m)", 0.0, 5.0, 0.0, 0.1, help="0 untuk Persegi (Beton), 1 untuk Trapesium")
        n_mat = st.number_input("Kekasaran Manning (n)", 0.010, 0.040, 0.017, 0.001, help="Beton Halus: 0.013, Beton Kasar: 0.017")

        if st.button("🔥 HITUNG ANALISA EKSTRIM", type="primary", use_container_width=True):
            res = hitung_got_miring(Q_desain, b_lebar, m_talud, L_saluran, H_drop, n_mat)
            st.session_state['res_chute'] = res

    with col_out:
        if 'res_chute' in st.session_state:
            res = st.session_state['res_chute']
            
            st.subheader("3. Hasil Analisa Hidrolis")
            
            # KPI Cards
            c1, c2, c3 = st.columns(3)
            c1.metric("Slope", f"{res['S_bed']:.2f} %", "Curam!")
            c2.metric("Kecepatan (V)", f"{res['V']:.2f} m/s", "Superkritis" if res['Fr']>1 else "Subkritis")
            c3.metric("Froude (Fr)", f"{res['Fr']:.2f}", "Butuh Peredam")
            
            # Warning System
            if res['V'] > 3.0:
                st.markdown(f"""
                <div class="danger-box">
                    <strong>⚠️ BAHAYA KAVITASI & EROSI!</strong><br>
                    Kecepatan mencapai {res['V']:.2f} m/s (Batas aman beton biasa: 3 m/s).<br>
                    <strong>Wajib:</strong> Gunakan Beton Mutu Tinggi (K-350 ke atas) + Tulangan Ganda.
                </div>
                """, unsafe_allow_html=True)
            
            # Analisa Dimensi
            st.markdown("### 4. Rekomendasi Dimensi (Safety)")
            st.markdown(f"""
            - **Kedalaman Air Murni:** {res['yn']:.3f} m
            - **Tinggi Jagaan (Aerasi/Bulking):** +{res['h_aerasi']:.3f} m
            - **Tinggi Dinding MINIMAL:** <span style="font-size:24px; font-weight:bold; color:blue;">{res['h_desain']:.2f} m</span>
            """, unsafe_allow_html=True)
            
            st.info(f"💡 **Rekomendasi Kolam Olak:** Gunakan **{res['tipe_olak']}** di ujung saluran untuk meredam energi Froude {res['Fr']:.2f}.")
            
            # Visualisasi
            st.pyplot(plot_chute(L_saluran, H_drop, res['yn']))
            
        else:
            st.info("Masukkan data dan tekan tombol HITUNG.")

# Tambahan: Library Edukasi
st.divider()
with st.expander("📚 Referensi: Mengapa Perlu Analisa Khusus?"):
    st.markdown("""
    **Kasus Nokan (L=1.2km, H=40m)** memiliki kemiringan 3.33%. 
    Ini bukan lagi saluran irigasi, tapi **Peluncur (Chute)**.
    1.  **Bulking Air:** Pada kecepatan tinggi, udara masuk ke air, membuat volume air bertambah. Jika pakai rumus biasa, air pasti meluap (overtopping).
    2.  **Kavitasi:** Kecepatan > 10-15 m/s bisa meledakkan permukaan beton karena tekanan uap.
    3.  **Loncatan Air:** Di ujung saluran, air akan "menabrak" air tenang, menciptakan ledakan energi. Aplikasi ini menghitung tipe kolam olak yang kuat menahannya.
    """)
