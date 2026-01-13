import streamlit as st
import pandas as pd
import json

# --- CONFIG ---
st.set_page_config(page_title="Hydro Planner", page_icon="💧", layout="wide")

# --- CSS PREMIUM (GOOGLE FONTS & LAYOUT) ---
st.markdown("""
<style>
    /* Import Font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700;800&family=Pacifico&display=swap');

    /* Container for Centered Title */
    .title-container {
        text-align: center;
        margin-bottom: 40px;
        margin-top: 20px;
    }

    /* Wrapper to position signature relative to text */
    .title-wrapper {
        display: inline-block;
        position: relative;
    }

    /* Main Title Styling */
    .main-title {
        font-family: 'Poppins', sans-serif;
        font-size: 60px;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #0984e3, #00cec9); /* Ocean Gradient */
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1;
        margin: 0;
        padding: 0;
    }

    /* Signature "by Smart Studio" */
    .branding-tag {
        font-family: 'Pacifico', cursive;
        font-size: 16px;
        color: #ff7675; /* Salmon Color */
        position: absolute;
        bottom: -15px;
        right: -10px;
        text-shadow: 1px 1px 0px #fff;
        transform: rotate(-5deg); /* Slight tilt for handwriting effect */
    }

    /* Sub-Title */
    .sub-title {
        font-family: 'Poppins', sans-serif;
        font-size: 16px;
        color: #636e72;
        text-align: center;
        font-weight: 400;
        letter-spacing: 3px;
        margin-top: 20px;
        text-transform: uppercase;
    }

    /* Project Card Styling */
    .project-card {
        padding: 25px; 
        background-color: #ffffff; 
        border-radius: 12px; 
        box-shadow: 0 4px 20px rgba(0,0,0,0.05); 
        border: 1px solid #f1f2f6; 
        margin-bottom: 20px;
    }
    
    /* Button Styling */
    div.stButton > button {
        width: 100%; 
        border-radius: 8px; 
        font-weight: 600; 
        height: 50px;
        border: none;
        transition: 0.3s;
    }
    
    /* Success/Info Box Styling adjustments */
    .stSuccess, .stInfo {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- SAVE/LOAD FUNCTIONS ---
def serialize_session():
    """Convert session state to JSON string"""
    export = {}
    for k, v in st.session_state.items():
        # Exclude UI form triggers
        if k.startswith(("Form", "editor", "uploaded", "btn")): continue
        
        # Handle DataFrames
        if isinstance(v, pd.DataFrame):
            export[k] = {'__type__': 'df', 'data': v.to_dict(orient='records')}
        else:
            try:
                # Ensure it's serializable
                json.dumps(v)
                export[k] = v
            except: pass
    return json.dumps(export, indent=2)

def load_session(json_file):
    """Load JSON back into session state"""
    try:
        data = json.load(json_file)
        count = 0
        for k, v in data.items():
            if isinstance(v, dict) and v.get('__type__') == 'df':
                st.session_state[k] = pd.DataFrame(v['data'])
            else:
                st.session_state[k] = v
            count += 1
        return True, count
    except Exception as e: return False, str(e)

# --- INIT STATE ---
if 'nama_proyek' not in st.session_state: st.session_state['nama_proyek'] = "New Project"
if 'lokasi' not in st.session_state: st.session_state['lokasi'] = "-"
if 'tahun' not in st.session_state: st.session_state['tahun'] = 2026

# ==========================================
# HEADER DISPLAY (PREMIUM LAYOUT)
# ==========================================

st.markdown("""
<div class="title-container">
    <div class="title-wrapper">
        <div class="main-title">HYDRO PLANNER</div>
        <div class="branding-tag">by Smart Studio</div>
    </div>
    <div class="sub-title">Integrated Irrigation & Drainage Engineering Suite</div>
</div>
""", unsafe_allow_html=True)

# --- PART 1: PROJECT IDENTITY ---
st.markdown("### 1️⃣ Project Identity")
with st.container():
    # Using the CSS class defined above
    st.markdown('<div class="project-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: st.session_state['nama_proyek'] = st.text_input("Project Name", value=st.session_state['nama_proyek'])
    with c2: st.session_state['lokasi'] = st.text_input("Location / Village", value=st.session_state['lokasi'])
    with c3: st.session_state['tahun'] = st.number_input("Fiscal Year", value=st.session_state['tahun'])
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# --- PART 2: DATA MANAGEMENT ---
c_left, c_right = st.columns(2)

# LOAD SECTION
with c_left:
    st.markdown("### 📂 Load Existing Project")
    uploaded = st.file_uploader("Upload .json file", type=['json'])
    if uploaded:
        if st.button("📂 Load Project Data", type="secondary"):
            ok, msg = load_session(uploaded)
            if ok: 
                st.success(f"✅ Successfully loaded {msg} data points!")
                # Optional: st.rerun() if using new streamlit
            else: st.error(f"Failed: {msg}")

# SAVE SECTION
with c_right:
    st.markdown("### 💾 Save Project")
    st.info("This will export **ALL DATA** from every module to your local drive.")
    
    file_label = f"{str(st.session_state['nama_proyek']).replace(' ', '_')}_Backup.json"
    json_str = serialize_session()
    
    st.download_button(
        label=f"💾 Download: {file_label}",
        data=json_str,
        file_name=file_label,
        mime="application/json",
        type="primary"
    )

# --- PART 3: DATA STATUS ---
st.divider()
st.subheader("📊 Module Status Check")
st.caption("Checks active data in Random Access Memory (RAM)")

# Define modules to check
modules = [
    ('df_iklim_24', 'Climatology'), 
    ('data_nfr_manual', 'Cropping Pattern'), 
    ('df_mock_input', 'Water Availability'),
    ('hujan_rancangan', 'Flood Analysis'),
    ('df_pipa', 'Pipe Design')
]

# Create a clean grid for status
cols = st.columns(5)
for i, (key, label) in enumerate(modules):
    with cols[i]:
        if key in st.session_state:
            st.success(f"**{label}**\n\n✅ Ready")
        else:
            st.warning(f"**{label}**\n\n⬜ Empty")
