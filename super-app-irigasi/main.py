# --- MENU GRID (KARTU-KARTU) ---
st.write("") 
st.subheader("🛠️ Modul Engineering")

# CSS Tambahan biar Link tidak ada garis bawah biru & Full Block
st.markdown("""
<style>
    a { text-decoration: none; color: inherit; }
    a:hover { text-decoration: none; color: inherit; }
</style>
""", unsafe_allow_html=True)

# Baris 1
col1, col2 = st.columns(2)

with col1:
    # Perhatikan ada tag <a href="Klimatologi" target="_self"> di luar div
    st.markdown("""
    <a href="Klimatologi" target="_self">
        <div class="box-menu">
            <div class="big-icon">☀️</div>
            <h3>Klimatologi & ETo</h3>
            <p>Analisis data hidroklimatologi harian/bulanan dan perhitungan Evapotranspirasi (Penman-Monteith).</p>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <a href="Pola_Tanam" target="_self">
        <div class="box-menu">
            <div class="big-icon">🌾</div>
            <h3>Pola Tanam & NFR</h3>
            <p>Simulasi neraca air lahan, penentuan koefisien tanaman (Kc), dan perhitungan kebutuhan air bersih (NFR).</p>
        </div>
    </a>
    """, unsafe_allow_html=True)

# Baris 2
col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <a href="FJ_Mock" target="_self">
        <div class="box-menu">
            <div class="big-icon">🌊</div>
            <h3>Debit Andalan (Mock)</h3>
            <p>Analisis ketersediaan air sungai (Inflow) menggunakan Metode F.J. Mock untuk perencanaan Intake Bendung.</p>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <a href="Desain_Saluran" target="_self">
        <div class="box-menu">
            <div class="big-icon">🏗️</div>
            <h3>Desain Saluran</h3>
            <p>Kalkulator dimensi hidrolis saluran terbuka (Batch System) dengan kontrol kestabilan aliran dan Froude Number.</p>
        </div>
    </a>
    """, unsafe_allow_html=True)