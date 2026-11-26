import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
import folium
from streamlit_folium import st_folium
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from geopy.geocoders import Nominatim
from datetime import datetime, timezone
import hashlib

st.set_page_config(
    page_title="Aero-Lex | แบบจำลองฟิสิกส์บรรยากาศเพื่อระบุแหล่งกำเนิด PM2.5",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- บังคับธีมสว่างแบบเอกสารวิจัย (Light Academic Theme) และฟอนต์ TH Sarabun New ---
st.markdown("""
    <style>
    @font-face {
        font-family: 'THSarabunNew';
        src: url('https://cdn.jsdelivr.net/gh/lazywasabi/thai-web-fonts@7/fonts/THSarabunNew/THSarabunNew.woff2') format('woff2'),
             url('https://cdn.jsdelivr.net/gh/lazywasabi/thai-web-fonts@7/fonts/THSarabunNew/THSarabunNew.woff') format('woff');
        font-weight: normal;
        font-style: normal;
    }
    @font-face {
        font-family: 'THSarabunNew';
        src: url('https://cdn.jsdelivr.net/gh/lazywasabi/thai-web-fonts@7/fonts/THSarabunNew/THSarabunNew-Bold.woff2') format('woff2'),
             url('https://cdn.jsdelivr.net/gh/lazywasabi/thai-web-fonts@7/fonts/THSarabunNew/THSarabunNew-Bold.woff') format('woff');
        font-weight: bold;
        font-style: normal;
    }

    .stApp {
        background-color: #FFFFFF !important;
        color: #1E293B !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
    }

    html, body, .stApp, p, h1, h2, h3, h4, h5, h6, label, input, select, textarea, button, .stMarkdown, .stDataFrame, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        font-family: 'THSarabunNew', 'TH Sarabun New', 'TH SarabunPSK', sans-serif !important;
        color: #1E293B !important;
    }

    p, label, .stMarkdown, li {
        font-size: 1.25rem !important;
        line-height: 1.5 !important;
    }

    .research-header {
        border-top: 4px solid #1E3A8A;
        border-bottom: 1px solid #CBD5E1;
        padding: 1.2rem 0 1rem 0;
        margin-bottom: 1.2rem;
    }
    .research-meta {
        font-size: 1.1rem;
        color: #475569 !important;
        letter-spacing: 0.02em;
        margin-bottom: 0.25rem;
        font-weight: bold;
    }
    .research-title {
        font-size: 2.35rem;
        font-weight: bold;
        color: #0F172A !important;
        line-height: 1.25;
        margin: 0;
    }

    .abstract-box {
        background-color: #F8FAFC;
        border: 1px solid #CBD5E1;
        border-left: 4px solid #1E3A8A;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        font-size: 1.28rem;
        line-height: 1.55;
        color: #334155 !important;
    }

    .guide-card {
        background-color: #F8FAFC;
        border: 1px solid #CBD5E1;
        padding: 0.9rem 1.1rem;
        border-radius: 3px;
        height: 100%;
    }
    .guide-step {
        color: #1E3A8A !important;
        font-weight: bold;
        font-size: 1.3rem;
        margin-bottom: 0.35rem;
    }

    h2, h3 {
        color: #1E3A8A !important;
        font-weight: bold !important;
        font-size: 1.65rem !important;
        border-bottom: 1px solid #E2E8F0;
        padding-bottom: 0.3rem;
        margin-top: 1.2rem !important;
    }

    [data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 2px !important;
        padding: 0.8rem 1rem !important;
        box-shadow: none !important;
    }
    [data-testid="stMetricLabel"] p {
        font-size: 1.2rem !important;
        font-weight: bold !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.95rem !important;
        font-weight: bold !important;
        color: #0F172A !important;
    }

    .stButton > button, .stDownloadButton > button {
        background-color: #1E3A8A !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 3px !important;
        font-weight: bold !important;
        font-size: 1.25rem !important;
        padding: 0.45rem 1rem !important;
    }
    .stButton > button p, .stDownloadButton > button p {
        color: #FFFFFF !important;
        font-size: 1.25rem !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #172554 !important;
    }

    input, select, [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        border-color: #CBD5E1 !important;
        color: #1E293B !important;
        font-size: 1.2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- ส่วนหัวเอกสารวิชาการ ---
st.markdown("""
<div class="research-header">
    <div class="research-meta">ATMOSPHERIC PHYSICS & ENVIRONMENTAL FORENSICS MODEL | VERSION 3.2 (USER GUIDE & EXCEL EXPORT)</div>
    <div class="research-title">แบบจำลองทางฟิสิกส์บรรยากาศเพื่อการคัดกรองและระบุแหล่งกำเนิดฝุ่นละอองขนาดเล็ก (PM2.5)</div>
</div>
<div class="abstract-box">
    <strong>หลักการและกรอบแนวคิดเชิงทฤษฎี:</strong> ระบบประมวลผลเชิงปริมาณสำหรับวิเคราะห์การเคลื่อนที่และแพร่กระจายของอนุภาคฝุ่นละอองขนาดเล็กในชั้นบรรยากาศระดับล่าง (Atmospheric Boundary Layer) โดยบูรณาการข้อมูลอุตุนิยมวิทยาและคุณภาพอากาศจากระบบตรวจวัดเวลาจริง (Open-Meteo API & InfluxDB) ร่วมกับข้อมูลการแผ่รังสีความร้อนจากดาวเทียม (NASA FIRMS VIIRS 375m) คำนวณผ่านสมการการแพร่กระจายแบบเกาส์เซียน (Gaussian Plume Dispersion Model) สมการแรงลอยตัวทางความร้อนของบริกส์ (Briggs' Plume Rise) และเกณฑ์การขวางกั้นทางภูมิประเทศจากแบบจำลองระดับความสูงเชิงเลข (DEM Orographic Blocking)
</div>
""", unsafe_allow_html=True)

# --- หน้าต่างคู่มือการใช้งานแบบเข้าใจง่าย ---
with st.expander("คู่มือการใช้งานระบบเบื้องต้น (คลิกเพื่อเปิด/ปิดคำแนะนำ 4 ขั้นตอน)", expanded=True):
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.markdown("""
        <div class="guide-card">
            <div class="guide-step">ขั้นตอนที่ 1: เลือกจุดรับผลกระทบ</div>
            เลือกสถานีอ้างอิงที่แถบเมนูด้านซ้าย พิมพ์ค้นหาชื่ออำเภอ/จังหวัด หรือ <strong>คลิกจุดที่ต้องการบนแผนที่</strong> ได้โดยตรง ระบบจะดึงค่าฝุ่นและทิศทางลมจริงของจุดนั้นทันที
        </div>
        """, unsafe_allow_html=True)
    with g2:
        st.markdown("""
        <div class="guide-card">
            <div class="guide-step">ขั้นตอนที่ 2: ปรับเงื่อนไขบรรยากาศ</div>
            เลือกระดับความนิ่งของอากาศ (Class A–F) และปรับแถบเลื่อน <strong>คาบเวลาเคลื่อนที่ของลม</strong> เพื่อขยายหรือย่อรัศมีกรวยลมสีส้มในการค้นหาต้นตอฝุ่น
        </div>
        """, unsafe_allow_html=True)
    with g3:
        st.markdown("""
        <div class="guide-card">
            <div class="guide-step">ขั้นตอนที่ 3: อ่านผลบนแผนที่และตาราง</div>
            • <strong>จุดสีแดง:</strong> จุดเผาไหม้ที่ลมพัดมาถึงจุดศึกษา<br>
            • <strong>จุดสีม่วง:</strong> ถูกภูเขาสูงขวางกั้นกลุ่มควัน<br>
            • <strong>จุดสีเหลืองส้ม:</strong> อยู่นอกแนวทิศทางลม
        </div>
        """, unsafe_allow_html=True)
    with g4:
        st.markdown("""
        <div class="guide-card">
            <div class="guide-step">ขั้นตอนที่ 4: บันทึกและดาวน์โหลด</div>
            กดปุ่ม <strong>บันทึกชุดข้อมูลลง InfluxDB</strong> เพื่อเก็บสถิติ และกดปุ่ม <strong>ดาวน์โหลด (.xlsx)</strong> ใต้ตารางเพื่อนำข้อมูลไปเปิดในโปรแกรม Excel ได้ทันที
        </div>
        """, unsafe_allow_html=True)

# --- ค่าเชื่อมต่อฐานข้อมูลและ API ---
DEFAULT_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
DEFAULT_TOKEN = "KP7nnhAgAvxAfzfgh6xEIOKtvW859QsOzcqfvE-x9k81aduLdB6hWJ3l8fd0nODwvMgs5OdJqqLSZT2oRpl6RQ=="
DEFAULT_ORG = "air_pollution_project"
DEFAULT_BUCKET = "air_quality_data"
DEFAULT_NASA_KEY = "9f142ebe06d50df4aeed0bc128f507c8"

if "lat" not in st.session_state:
    st.session_state.lat = 18.2888
if "lon" not in st.session_state:
    st.session_state.lon = 99.4908
if "place_name" not in st.session_state:
    st.session_state.place_name = "อำเภอเมืองลำปาง จังหวัดลำปาง (แอ่งกระทะลำปาง)"
if "zoom_level" not in st.session_state:
    st.session_state.zoom_level = 9

# --- ฟังก์ชันสร้างไฟล์ Excel (.xlsx) แท้ๆ พร้อมระบบสำรองป้องกัน Error ---
def to_clean_excel(df, sheet_name="Report"):
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns, 1):
                max_len = max(
                    df[col].astype(str).map(len).max() if not df.empty else 0,
                    len(str(col))
                ) + 6
                col_letter = worksheet.cell(row=1, column=idx).column_letter
                worksheet.column_dimensions[col_letter].width = min(max_len, 55)
        return output.getvalue(), "xlsx"
    except Exception:
        return df.to_csv(index=False).encode("utf-8-sig"), "csv"

@st.cache_data(ttl=86400)
def reverse_geocode_landmark(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&accept-language=th"
        headers = {"User-Agent": "AeroLex_Research_Project_TH/1.0"}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            addr = data.get("address", {})
            poi = addr.get("amenity") or addr.get("shop") or addr.get("building") or addr.get("tourism") or addr.get("road") or addr.get("village") or addr.get("hamlet")
            subdistrict = addr.get("subdistrict") or addr.get("quarter") or addr.get("suburb") or ""
            district = addr.get("district") or addr.get("county") or addr.get("city") or ""
            province = addr.get("province") or addr.get("state") or ""
            
            parts = []
            if poi:
                parts.append(f"บริเวณใกล้เคียง {poi}")
            if subdistrict:
                parts.append(subdistrict)
            if district:
                parts.append(district)
            if province and province not in district:
                parts.append(province)
                
            if parts:
                return " ".join(parts)
            disp = data.get("display_name", "")
            if disp:
                return ", ".join(disp.split(",")[:3])
    except Exception:
        pass
    return f"พิกัด ({lat:.4f}, {lon:.4f})"

def parse_station_to_location(st_id):
    st_str = str(st_id)
    if st_str == "LP-01":
        return "สถานีตรวจวัดหลัก อ.เมืองลำปาง (18.2888, 99.4908)", "https://www.google.com/maps?q=18.2888,99.4908"
    elif st_str == "CUSTOM-01":
        return "จุดตรวจวัดภาคสนามกำหนดเอง (18.2888, 99.4908)", "https://www.google.com/maps?q=18.2888,99.4908"
    elif st_str.startswith("ST-"):
        try:
            parts = st_str.split("-")
            lat_v = float(parts[1])
            lon_v = float(parts[2])
            place = reverse_geocode_landmark(lat_v, lon_v)
            return place, f"https://www.google.com/maps?q={lat_v},{lon_v}"
        except Exception:
            pass
    return f"รหัสสถานี {st_str}", "https://www.google.com/maps"

def degree_to_thai_dir(deg):
    dirs = [
        "ทิศเหนือ (N)", "ทิศตะวันออกเฉียงเหนือ (NE)", "ทิศตะวันออก (E)", "ทิศตะวันออกเฉียงใต้ (SE)",
        "ทิศใต้ (S)", "ทิศตะวันตกเฉียงใต้ (SW)", "ทิศตะวันตก (W)", "ทิศตะวันตกเฉียงเหนือ (NW)"
    ]
    idx = int((deg + 22.5) // 45) % 8
    return f"{dirs[idx]} ({deg}°)"

def classify_pm25_thai(val):
    if val <= 15.0:
        return "ดีมาก (สีฟ้า)"
    elif val <= 25.0:
        return "ดี (สีเขียว)"
    elif val <= 37.5:
        return "ปานกลาง (สีเหลือง)"
    elif val <= 75.0:
        return "เริ่มมีผลกระทบต่อสุขภาพ (สีส้ม)"
    else:
        return "มีผลกระทบต่อสุขภาพ (สีแดง)"

# --- แถบควบคุมพารามิเตอร์ (Sidebar) ---
st.sidebar.markdown("### 1. กำหนดพิกัดจุดรับผลกระทบ (Receptor)")
preset_locations = {
    "กำหนดพิกัดเอง / สืบค้นด้านล่าง": None,
    "อำเภอเมืองลำปาง จังหวัดลำปาง": (18.2888, 99.4908),
    "อำเภอแม่เมาะ จังหวัดลำปาง": (18.2936, 99.6517),
    "โรงเรียนวิทยาศาสตร์จุฬาภรณราชวิทยาลัย เชียงราย": (19.9575, 99.8825),
    "อำเภอแม่สาย จังหวัดเชียงราย": (20.4335, 99.8806),
    "อำเภอเมืองเชียงใหม่ จังหวัดเชียงใหม่": (18.7883, 98.9853)
}
selected_preset = st.sidebar.selectbox("สถานีอ้างอิงในพื้นที่ศึกษา:", list(preset_locations.keys()))
if preset_locations[selected_preset] is not None:
    st.session_state.lat, st.session_state.lon = preset_locations[selected_preset]
    st.session_state.place_name = selected_preset

search_query = st.sidebar.text_input("สืบค้นพิกัดภูมิศาสตร์ (ชื่อสถานที่ / อำเภอ / จังหวัด):", placeholder="ระบุชื่อพื้นที่ศึกษา")
if st.sidebar.button("สืบค้นพิกัด"):
    if search_query:
        try:
            geolocator = Nominatim(user_agent="aero_lex_academic_v15")
            location = geolocator.geocode(search_query + " Thailand")
            if location:
                st.session_state.lat = round(location.latitude, 4)
                st.session_state.lon = round(location.longitude, 4)
                st.session_state.place_name = location.address
        except Exception as e:
            st.sidebar.error(f"ข้อผิดพลาดในการสืบค้นพิกัด: {e}")

target_lat = st.sidebar.number_input("ละติจูด (Latitude, °N)", value
