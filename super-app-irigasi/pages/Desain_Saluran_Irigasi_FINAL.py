import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="JIAT Smart Studio - Desain Irigasi",
    layout="wide",
    page_icon="🌊"
)

# ==========================================
# OPTIONAL: EZDXF
# ==========================================
try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    from ezdxf.tools.standards import setup_linetypes
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

# ==========================================
# FUNGSI HIDRAULIK SALURAN (KP-03)
# ==========================================

def get_freeboard_kp03(Q):
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.20
    elif Q < 5.0: return 0.25
    elif Q < 10.0: return 0.30
    elif Q < 15.0: return 0.40
    else: return 0.50

def solve_strickler_y(Q, b, m, k, S):
    if Q <= 0 or b <= 0 or S <= 0:
        return 0.0

    y = 0.5
    for _ in range(50):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        if P == 0: break
        R = A / P
        Q_calc = A * k * (R**(2/3)) * (S**0.5)

        if abs(Q_calc - Q) < 1e-4:
            break
        y = y * (Q / Q_calc) ** 0.6 if Q_calc > 0 else y + 0.05

    return y

def cek_keamanan_desain(Q, b, m, y, k, S):
    A = (b + m * y) * y
    if A <= 0:
        return 0, 0, "ERROR", "Dimensi tidak valid"

    V = Q / A
    T = b + 2 * m * y
    D = A / T if T > 0 else 0
    g = 9.81
    Fr = V / np.sqrt(g * D) if D > 0 else 0

    status = "AMAN"
    warning = []

    if Fr >= 1.0:
        status = "KRITIS"
        warning.append(f"Superkritis (Fr={Fr:.2f})")
    elif Fr > 0.5:
        warning.append(f"Mendekati kritis (Fr={Fr:.2f})")

    v_max = 2.0 if k >= 60 else 0.7
    v_min = 0.6

    if V > v_max:
        status = "TIDAK AMAN"
        warning.append(f"Potensi erosi (V={V:.2f})")
    elif V < v_min:
        if status == "AMAN":
            status = "PERHATIAN"
        warning.append(f"Potensi endapan (V={V:.2f})")

    return V, Fr, status, "; ".join(warning)

# ==========================================
# FLUME – PARSHALL (USBR)
# ==========================================

def parshall_flume_Q(H, W):
    C = 1.55 * W
    n = 1.6
    return C * (H ** n)

def parshall_flume_H(Q, W):
    C = 1.55 * W
    n = 1.6
    return (Q / C) ** (1 / n)

# ==========================================
# USER INTERFACE
# ==========================================

st.title("🛠️ Aplikasi Desain Irigasi Terintegrasi")
st.markdown("Desain saluran, verifikasi KP-03, **bangunan ukur flume**, DXF & Excel")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("📌 Parameter Global")
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Awal (+m)", value=100.0)

    st.divider()
    st.header("📏 Bangunan Ukur Debit (Flume)")
    use_flume = st.checkbox("Aktifkan Parshall Flume")

    if use_flume:
        flume_width = st.number_input("Lebar Flume W (m)", value=0.30)
        flume_mode = st.radio(
            "Mode Flume",
            ["Hitung Q dari H", "Hitung H dari Q"]
        )
        if flume_mode == "Hitung Q dari H":
            H_flume_input = st.number_input("Tinggi Muka Air H (m)", value=0.30)

# ==========================================
# DATA INPUT
# ==========================================
if 'df_input' not in st.session_state:
    st.session_state.df_input = pd.DataFrame({
        'Nama Saluran': ['Saluran 1'],
        'Panjang (m)': [50.0],
        'Offset (m)': [0.0],
        'Debit (Q)': [2.5],
        'Lebar (b)': [1.5],
        'Talud (m)': [1.0],
        'Slope (S)': [0.0008],
        'Strickler (k)': [60]
    })

st.subheader("1️⃣ Input Data Saluran")
df_edit = st.data_editor(
    st.session_state.df_input,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic"
)

# ==========================================
# HITUNG
# ==========================================
if st.button("▶️ HITUNG & VERIFIKASI", type="primary", use_container_width=True):
    hasil = []
    curr_sta = start_sta
    curr_elv = start_elv

    for _, r in df_edit.iterrows():
        Q = float(r['Debit (Q)'])
        b = float(r['Lebar (b)'])
        m = float(r['Talud (m)'])
        S = float(r['Slope (S)'])
        k = float(r['Strickler (k)'])
        L = float(r['Panjang (m)'])
        offset = float(r.get('Offset (m)', 0))

        y = solve_strickler_y(Q, b, m, k, S)
        Fb = get_freeboard_kp03(Q)
        h = y + Fb

        V, Fr, status, warn = cek_keamanan_desain(Q, b, m, y, k, S)

        Q_flume = None
        H_flume = None
        dev = None

        if use_flume:
            if flume_mode == "Hitung Q dari H":
                Q_flume = parshall_flume_Q(H_flume_input, flume_width)
                dev = abs(Q_flume - Q) / Q * 100
            else:
                H_flume = parshall_flume_H(Q, flume_width)

            if dev and dev > 5:
                status = "PERLU CEK FLUME"

        elv_awal = curr_elv
        elv_akhir = elv_awal - S * L

        hasil.append({
            'Nama Saluran': r['Nama Saluran'],
            'STA Awal': curr_sta,
            'STA Akhir': curr_sta + L,
            'Elv Dasar Awal': elv_awal,
            'Elv Dasar Akhir': elv_akhir,
            'Debit (Q)': Q,
            'Tinggi Air (y)': y,
            'Freeboard (Fb)': Fb,
            'Tinggi Total (h)': h,
            'Kecepatan (V)': V,
            'Froude (Fr)': Fr,
            'Status': status,
            'Catatan': warn,
            'Q Flume': Q_flume,
            'H Flume': H_flume,
            'Deviasi Flume (%)': dev
        })

        curr_sta += L
        curr_elv = elv_akhir + offset

    st.session_state.df_hasil = pd.DataFrame(hasil)
    st.success("✅ Perhitungan selesai")

# ==========================================
# OUTPUT
# ==========================================
if 'df_hasil' in st.session_state:
    st.subheader("2️⃣ Hasil Perhitungan")
    st.dataframe(st.session_state.df_hasil, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer:
        st.session_state.df_hasil.to_excel(writer, index=False, sheet_name="Rekap")

    st.download_button(
        "📊 Download Excel Laporan",
        output.getvalue(),
        "Laporan_Desain_Irigasi.xlsx",
        use_container_width=True
    )
