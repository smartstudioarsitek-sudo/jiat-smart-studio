import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- CONFIG ---
st.set_page_config(page_title="Chute Designer (Nokan)", layout="wide", page_icon="🚀")

st.markdown("""
<style>
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #b71c1c, #d32f2f); color: white;
        border-radius: 10px; text-align: center; margin-bottom: 20px;
    }
    .danger-box {
        background-color: #ffebee; border: 1px solid #ef5350; padding: 15px; border-radius: 5px; color: #c62828;
    }
</style>
""", unsafe_allow_html=True)

# --- ENGINE ---
def solve_manning_y(Q, n, b, S, m):
    y = 0.5 
    for _ in range(20):
        A = (b + m*y) * y
        P = b + 2*y * np.sqrt(1 + m**2)
        R = A/P
        f = (1/n) * A * (R**(2/3)) * (S**0.5) - Q
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
    S_bed = H_drop / L 
    y_n = solve_manning_y(Q, n_beton, b, S_bed, m)
    A_n = (b + m*y_n) * y_n
    V_n = Q / A_n
    T_top = b + 2*m*y_n
    D_hyd = A_n / T_top
    Fr = V_n / np.sqrt(9.81 * D_hyd)
    
    if V_n > 6.0: h_aerasi = 0.6 * (V_n**2 / (2*9.81)) 
    else: h_aerasi = 0.2 + (0.1 * V_n)
    
    h_total_perlu = y_n + h_aerasi
    
    if Fr < 4.5: tipe_olak = "USBR Tipe IV (Gigi Ompong) atau Vlugter"
    elif Fr > 4.5 and V_n < 18: tipe_olak = "USBR Tipe III (Gigi Penghadang)"
    else: tipe_olak = "USBR Tipe II (Untuk V sangat tinggi)"
        
    return {'S_bed': S_bed * 100, 'yn': y_n, 'V': V_n, 'Fr': Fr, 'h_aerasi': h_aerasi, 'h_desain': h_total_perlu, 'tipe_olak': tipe_olak}

def plot_chute(L, H, y_air):
    fig, ax = plt.subplots(figsize=(10, 4))
    x = [0, L]
    y_bed = [H, 0]
    y_water = [H + y_air, 0 + y_air]
    ax.plot(x, y_bed, 'k-', linewidth=3, label='Dasar Saluran')
    ax.plot(x, y_water, 'c--', linewidth=2, label='Muka Air (Aerated)')
    ax.fill_between(x, y_bed, y_water, color='cyan', alpha=0.3)
    ax.set_title(f"Profil Got Miring (L={L}m, Drop={H}m)", fontsize=12)
    ax.legend()
    return fig

# --- UI ---
st.markdown('<div class="header-box"><h1>🚀 Advanced Chute Designer</h1><p>Solusi Khusus Topografi Ekstrim (Nokan Case)</p></div>', unsafe_allow_html=True)
st.warning("⚠️ Halaman ini khusus untuk analisa Got Miring/Peluncur dengan kemiringan curam.")

col_in, col_out = st.columns([1, 1.5])
with col_in:
    st.subheader("1. Parameter Ekstrim")
    Q_desain = st.number_input("Debit Desain (m³/s)", 0.1, 50.0, 2.0, 0.1)
    L_saluran = st.number_input("Panjang Saluran (m)", 10.0, 5000.0, 1200.0, 10.0)
    H_drop = st.number_input("Beda Tinggi (m)", 1.0, 500.0, 40.0, 1.0)
    st.subheader("2. Geometri")
    b_lebar = st.number_input("Lebar Dasar (m)", 0.5, 10.0, 1.5, 0.1)
    m_talud = st.number_input("Kemiringan Talud (m)", 0.0, 5.0, 0.0, 0.1)
    n_mat = st.number_input("Kekasaran Manning (n)", 0.010, 0.040, 0.017, 0.001)

    if st.button("🔥 HITUNG ANALISA", type="primary", use_container_width=True):
        st.session_state['res_chute'] = hitung_got_miring(Q_desain, b_lebar, m_talud, L_saluran, H_drop, n_mat)

with col_out:
    if 'res_chute' in st.session_state:
        res = st.session_state['res_chute']
        st.subheader("3. Hasil Analisa")
        c1, c2, c3 = st.columns(3)
        c1.metric("Slope", f"{res['S_bed']:.2f} %")
        c2.metric("Kecepatan", f"{res['V']:.2f} m/s")
        c3.metric("Froude", f"{res['Fr']:.2f}")
        
        if res['V'] > 3.0:
            st.markdown(f'<div class="danger-box">⚠️ BAHAYA EROSI! Kecepatan {res["V"]:.2f} m/s. Gunakan Beton Mutu Tinggi.</div>', unsafe_allow_html=True)
        
        st.markdown(f"**Tinggi Dinding Perlu (safety): {res['h_desain']:.2f} m**")
        st.info(f"💡 Kolam Olak: {res['tipe_olak']}")
        st.pyplot(plot_chute(L_saluran, H_drop, res['yn']))
