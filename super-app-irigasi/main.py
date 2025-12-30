import streamlit as st

st.set_page_config(
    page_title="Sistem Irigasi Terpadu",
    page_icon="💧",
    layout="wide"
)

st.title("💧 Sistem Perencanaan Irigasi Terpadu")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.image("https://img.freepik.com/free-vector/irrigation-system-concept-illustration_114360-17029.jpg")

with col2:
    st.info("👋 **Selamat Datang, Engineer!**")
    st.markdown("""
    Silakan pilih modul di Sidebar sebelah kiri:
    
    1.  **☀️ Klimatologi:** Data ETo & Iklim.
    2.  **🌾 Pola Tanam:** Rencana Tanam & NFR.
    3.  **🌊 Analisis Sungai:** Ketersediaan Air (FJ Mock).
    4.  **🏗️ Desain Saluran:** Dimensi Saluran (Batch).
    """)
    st.success("JIAT Smart Studio © 2025")