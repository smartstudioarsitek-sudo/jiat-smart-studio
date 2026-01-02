import streamlit as st
import sqlite3
import pandas as pd

# Konfigurasi Halaman
st.set_page_config(page_title="Hydro Planner RAB", layout="wide")
DB_NAME = "rab_project_v1.db"

# --- FUNGSI DATABASE ---
def get_connection():
    return sqlite3.connect(DB_NAME)

def load_resources(search_term=""):
    conn = get_connection()
    query = "SELECT kode, nama, satuan, harga_dasar, kategori FROM resources"
    if search_term:
        query += f" WHERE nama LIKE '%{search_term}%'"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_ahsp_categories():
    conn = get_connection()
    query = "SELECT DISTINCT kategori_file FROM ahsp_header"
    df = pd.read_sql(query, conn)
    conn.close()
    return df['kategori_file'].tolist()

def get_ahsp_list(category):
    conn = get_connection()
    query = "SELECT id, kode_analisa, uraian_pekerjaan FROM ahsp_header WHERE kategori_file = ?"
    df = pd.read_sql(query, conn, params=(category,))
    conn.close()
    return df

def get_ahsp_detail(ahsp_id):
    conn = get_connection()
    # Join tabel detail dengan tabel resources untuk ambil harga satuan update
    query = '''
        SELECT 
            d.kategori_komponen,
            COALESCE(r.nama, d.nama_komponen_raw) as nama_item,
            d.satuan,
            d.koefisien,
            COALESCE(r.harga_dasar, 0) as harga_satuan
        FROM ahsp_detail d
        LEFT JOIN resources r ON d.resource_id = r.id
        WHERE d.ahsp_id = ?
    '''
    df = pd.read_sql(query, conn, params=(ahsp_id,))
    conn.close()
    return df

# --- UI APLIKASI ---

st.title("🏗️ Hydro Planner - Construction Cost Estimator")
st.markdown("---")

# Sidebar Menu
menu = st.sidebar.selectbox("Menu Utama", ["Kalkulator Pekerjaan (AHSP)", "Master Harga Satuan (SDA)"])

if menu == "Master Harga Satuan (SDA)":
    st.header("📦 Master Data Sumber Daya (Bahan, Upah, Alat)")
    
    search_box = st.text_input("Cari Material/Upah:", placeholder="Ketik misal: Semen, Pasir, Tukang...")
    
    df_res = load_resources(search_box)
    
    # Tampilkan Dataframe dengan formatting uang
    st.dataframe(
        df_res.style.format({"harga_dasar": "Rp {:,.2f}"}),
        use_container_width=True,
        height=500
    )
    st.caption(f"Menampilkan {len(df_res)} item.")

elif menu == "Kalkulator Pekerjaan (AHSP)":
    st.header("🧮 Analisa & Hitungan Biaya")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # 1. Pilih Kategori File (Misal: PONDASI, BETON)
        categories = get_ahsp_categories()
        if not categories:
            st.warning("Database kosong atau belum di-ingest. Jalankan script ingestion dulu ya kak!")
            st.stop()
            
        selected_cat = st.selectbox("Pilih Kategori Pekerjaan:", categories)
        
        # 2. Pilih Item Pekerjaan
        df_items = get_ahsp_list(selected_cat)
        item_options = df_items.set_index('id')['uraian_pekerjaan'].to_dict()
        
        selected_id = st.selectbox(
            "Pilih Uraian Pekerjaan:", 
            options=df_items['id'].tolist(),
            format_func=lambda x: item_options[x]
        )
        
        # 3. Input Volume
        st.markdown("### Input Rencana")
        volume_input = st.number_input("Volume Pekerjaan:", min_value=1.0, value=1.0, step=0.1)
        st.info(f"Kode Analisa: {df_items[df_items['id']==selected_id]['kode_analisa'].values[0]}")

    with col2:
        # 4. Tampilkan Detail Perhitungan
        st.subheader("Rincian Biaya (Breakdown)")
        
        if selected_id:
            df_detail = get_ahsp_detail(selected_id)
            
            # Hitung Subtotal per baris
            df_detail['Total Harga'] = df_detail['koefisien'] * df_detail['harga_satuan']
            
            # Hitung Total AHSP per satuan
            harga_satuan_pekerjaan = df_detail['Total Harga'].sum()
            
            # Hitung Total Proyek (dikali Volume input user)
            total_proyek = harga_satuan_pekerjaan * volume_input
            
            # Tampilkan Tabel Detail
            st.dataframe(
                df_detail.style.format({
                    "koefisien": "{:.4f}",
                    "harga_satuan": "Rp {:,.2f}",
                    "Total Harga": "Rp {:,.2f}"
                }),
                use_container_width=True
            )
            
            st.markdown("---")
            
            # Tampilkan Summary Angka Besar
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Harga Satuan per m3/m2", f"Rp {harga_satuan_pekerjaan:,.2f}")
            with c2:
                st.metric(f"Total Biaya (Vol: {volume_input})", f"Rp {total_proyek:,.2f}")
                
            # Breakdown Chart (Visualisasi)
            if not df_detail.empty:
                st.markdown("#### Komposisi Biaya")
                chart_data = df_detail.groupby("kategori_komponen")["Total Harga"].sum().reset_index()
                st.bar_chart(chart_data, x="kategori_komponen", y="Total Harga")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Developed by SmartStudio | Hydro Planner Version")
