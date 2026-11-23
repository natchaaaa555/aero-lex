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
        margin-bottom: 1.5rem;
        font-size: 1.28rem;
        line-height: 1.55;
        color: #334155 !important;
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
    <div class="research-meta">ATMOSPHERIC PHYSICS & ENVIRONMENTAL FORENSICS MODEL | VERSION 2.6 (REAL-TIME SATELLITE VIIRS)</div>
    <div class="research-title">แบบจำลองทางฟิสิกส์บรรยากาศเพื่อการคัดกรองและระบุแหล่งกำเนิดฝุ่นละอองขนาดเล็ก (PM2.5)</div>
</div>
<div class="abstract-box">
    <strong>หลักการและกรอบแนวคิดเชิงทฤษฎี:</strong> ระบบประมวลผลเชิงปริมาณสำหรับวิเคราะห์การเคลื่อนที่และแพร่กระจายของอนุภาคฝุ่นละอองขนาดเล็กในชั้นบรรยากาศระดับล่าง (Atmospheric Boundary Layer) โดยบูรณาการข้อมูลอุตุนิยมวิทยาและคุณภาพอากาศจากระบบตรวจวัดเวลาจริง (Open-Meteo API & InfluxDB) ร่วมกับข้อมูลการแผ่รังสีความร้อนจากดาวเทียม (NASA FIRMS VIIRS 375m) คำนวณผ่านสมการการแพร่กระจายแบบเกาส์เซียน (Gaussian Plume Dispersion Model) สมการแรงลอยตัวทางความร้อนของบริกส์ (Briggs' Plume Rise) และเกณฑ์การขวางกั้นทางภูมิประเทศจากแบบจำลองระดับความสูงเชิงเลข (DEM Orographic Blocking)
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

# --- ฟังก์ชันช่วยแปลข้อมูลทางวิชาการ ---
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
            geolocator = Nominatim(user_agent="aero_lex_academic_v10")
            location = geolocator.geocode(search_query + " Thailand")
            if location:
                st.session_state.lat = round(location.latitude, 4)
                st.session_state.lon = round(location.longitude, 4)
                st.session_state.place_name = location.address
        except Exception as e:
            st.sidebar.error(f"ข้อผิดพลาดในการสืบค้นพิกัด: {e}")

target_lat = st.sidebar.number_input("ละติจูด (Latitude, °N)", value=st.session_state.lat, format="%.4f")
target_lon = st.sidebar.number_input("ลองจิจูด (Longitude, °E)", value=st.session_state.lon, format="%.4f")
st.session_state.lat = target_lat
st.session_state.lon = target_lon

st.sidebar.markdown("---")
st.sidebar.markdown("### 2. เงื่อนไขขอบเขตทางฟิสิกส์บรรยากาศ")
stability_class = st.sidebar.selectbox(
    "เสถียรภาพชั้นบรรยากาศ (Pasquill-Gifford Class):",
    options=[
        "Class A: ไม่เสถียรสูง (รังสีอาทิตย์เข้มข้น ลมอ่อน)",
        "Class B: ไม่เสถียรปานกลาง",
        "Class C: ไม่เสถียรเล็กน้อย",
        "Class D: สภาวะเป็นกลาง (เมฆปกคลุม/ลมปานกลาง)",
        "Class E: เสถียรเล็กน้อย (ช่วงค่ำ)",
        "Class F: เสถียรสูง/อุณหภูมิผกผัน (ช่วงเช้ามืด)"
    ],
    index=3
)
stab_code = stability_class.split(":")[0].replace("Class ", "").strip()
back_hours = st.sidebar.slider("คาบเวลาการเคลื่อนที่ของมวลอากาศ (ชั่วโมง):", 1, 24, 12)
satellite_days = st.sidebar.slider("ช่วงเวลาย้อนหลังข้อมูลดาวเทียม NASA (วัน):", 1, 10, 7)
use_dem_blocking = st.sidebar.checkbox("คำนวณการขวางกั้นทางภูมิประเทศ (DEM Blocking)", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### 3. แหล่งข้อมูลและฐานข้อมูลอนุกรมเวลา")
data_mode = st.sidebar.radio(
    "ชุดข้อมูลอุตุนิยมวิทยาและฝุ่น:",
    ["ข้อมูลเวลาจริงตามพิกัด (Open-Meteo API)", "ข้อมูลล่าสุดจากคลังข้อมูล (InfluxDB)"]
)

with st.sidebar.expander("ตั้งค่าการเชื่อมต่อฐานข้อมูลและ API Key"):
    influx_url = st.text_input("InfluxDB Endpoint URL", value=DEFAULT_URL)
    influx_token = st.text_input("InfluxDB Access Token", value=DEFAULT_TOKEN, type="password")
    influx_org = st.text_input("Organization ID", value=DEFAULT_ORG)
    influx_bucket = st.text_input("Data Bucket", value=DEFAULT_BUCKET)
    nasa_key = st.text_input("NASA FIRMS API Key", value=DEFAULT_NASA_KEY, type="password")

use_mock_hs = st.sidebar.checkbox("ใช้ชุดข้อมูลจุดความร้อนจำลอง (Benchmark Dataset)", value=False)

# --- ฟังก์ชันดึงข้อมูล ---
@st.cache_data(ttl=600)
def fetch_open_meteo_data(lat, lon):
    try:
        aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5"
        wx_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m"
        
        aq_resp = requests.get(aq_url, timeout=8).json()
        wx_resp = requests.get(wx_url, timeout=8).json()
        
        pm25 = aq_resp.get("current", {}).get("pm2_5")
        wind_speed = wx_resp.get("current", {}).get("wind_speed_10m")
        wind_dir = wx_resp.get("current", {}).get("wind_direction_10m")
        
        if pm25 is not None and wind_speed is not None and wind_dir is not None:
            return {
                "source": "Open-Meteo Atmospheric & Air Quality API",
                "pm25": round(float(pm25), 1),
                "wind_speed": max(round(float(wind_speed), 1), 1.0),
                "wind_dir": round(float(wind_dir), 1)
            }
    except Exception:
        pass
    return None

def fetch_influx_data(url, token, org, bucket):
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        query_api = client.query_api()
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -7d)
          |> filter(fn: (r) => r["_measurement"] == "ground_station")
          |> last()
        '''
        tables = query_api.query(query, org=org)
        data = {}
        for table in tables:
            for record in table.records:
                data[record.get_field()] = record.get_value()
        client.close()
        if "pm25" in data and "wind_speed" in data and "wind_dir" in data:
            return {
                "source": "ฐานข้อมูลอนุกรมเวลา InfluxDB Cloud",
                "pm25": round(float(data["pm25"]), 1),
                "wind_speed": round(float(data["wind_speed"]), 1),
                "wind_dir": round(float(data["wind_dir"]), 1)
            }
    except Exception:
        pass
    return None

ground = None
if data_mode == "ข้อมูลเวลาจริงตามพิกัด (Open-Meteo API)":
    ground = fetch_open_meteo_data(target_lat, target_lon)
if ground is None:
    ground = fetch_influx_data(influx_url, influx_token, influx_org, influx_bucket)
if ground is None:
    ground = {"source": "ค่าพารามิเตอร์มาตรฐานอ้างอิง", "pm25": 45.0, "wind_speed": 10.0, "wind_dir": 225.0}

if st.sidebar.button("บันทึกชุดข้อมูลปัจจุบันลง InfluxDB"):
    try:
        client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = (
            Point("ground_station")
            .tag("station_id", f"ST-{target_lat:.2f}-{target_lon:.2f}")
            .field("pm25", float(ground["pm25"]))
            .field("wind_speed", float(ground["wind_speed"]))
            .field("wind_dir", float(ground["wind_dir"]))
            .time(datetime.now(timezone.utc))
        )
        write_api.write(bucket=influx_bucket, org=influx_org, record=point)
        client.close()
        st.sidebar.success("บันทึกข้อมูลลงฐานข้อมูลเรียบร้อยแล้ว")
    except Exception as e:
        st.sidebar.error(f"ข้อผิดพลาดในการบันทึกข้อมูล: {e}")

@st.cache_data(ttl=900)
def fetch_hotspots(lat, lon, api_key, force_mock, days_back):
    if api_key and not force_mock:
        try:
            # ขยายขอบเขต ±2.5 องศา (ครอบคลุมภาคเหนือตอนบนและพื้นที่ใกล้เคียง)
            area = f"{lon-2.5},{lat-2.5},{lon+2.5},{lat+2.5}"
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_SNPP_NRT/{area}/{days_back}"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and "latitude" in resp.text:
                df = pd.read_csv(io.StringIO(resp.text))
                if "confidence" in df.columns:
                    df = df[df["confidence"].isin(["n", "h", "nominal", "high"])]
                if not df.empty:
                    df["acq_datetime"] = df["acq_date"].astype(str) + " " + df["acq_time"].astype(str).str.zfill(4) + " UTC"
                    return df[["latitude", "longitude", "frp", "acq_datetime"]], f"ดาวเทียม NASA FIRMS VIIRS 375m (ข้อมูลจริงย้อนหลัง {days_back} วัน)"
                else:
                    return pd.DataFrame(columns=["latitude", "longitude", "frp", "acq_datetime"]), f"ดาวเทียม NASA FIRMS VIIRS (ไม่พบจุดความร้อนจริงในรอบ {days_back} วัน)"
        except Exception:
            pass
    np.random.seed(int(abs(lat * 100)))
    lats = lat + np.random.uniform(-0.32, 0.32, 15)
    lons = lon + np.random.uniform(-0.32, 0.32, 15)
    frp = np.random.uniform(10.0, 65.0, 15)
    dt_str = [datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")] * 15
    return pd.DataFrame({"latitude": lats, "longitude": lons, "frp": frp, "acq_datetime": dt_str}), "ชุดข้อมูลจำลองมาตรฐาน (Synthetic Benchmark)"

@st.cache_data(ttl=3600)
def check_terrain_blocking(lat1, lon1, lat2, lon2, plume_height_m):
    try:
        pts = []
        for f in [0.0, 0.25, 0.5, 0.75, 1.0]:
            pts.append({"latitude": lat1 + f*(lat2 - lat1), "longitude": lon1 + f*(lon2 - lon1)})
        resp = requests.post("https://api.open-elevation.com/api/v1/lookup", json={"locations": pts}, timeout=5)
        if resp.status_code == 200:
            elevs = [r["elevation"] for r in resp.json()["results"]]
            receptor_elev = elevs[0]
            source_elev = elevs[-1]
            max_barrier = max(elevs[1:-1])
            plume_asl = source_elev + plume_height_m
            is_blocked = max_barrier > (plume_asl + 150)
            return is_blocked, round(max_barrier - receptor_elev, 0)
    except Exception:
        pass
    return False, 0

def gaussian_plume_physics(dist_km, crosswind_km, frp_mw, wind_speed_kmh, stab):
    if dist_km <= 0.1:
        return 0.0, 0.0
    x = dist_km * 1000.0
    y = crosswind_km * 1000.0
    u = max(wind_speed_kmh / 3.6, 0.5)
    
    F = 8.9 * frp_mw
    delta_h = 1.6 * (F ** (1/3)) * ((min(x, 2000.0)) ** (2/3)) / u
    H = 2.0 + min(delta_h, 800.0)
    
    pg_params = {
        "A": (0.22, 0.20),
        "B": (0.16, 0.12),
        "C": (0.11, 0.08),
        "D": (0.08, 0.06),
        "E": (0.06, 0.03),
        "F": (0.04, 0.016)
    }
    ay, az = pg_params.get(stab, (0.08, 0.06))
    sigma_y = ay * x * ((1 + 0.0001 * x) ** -0.5)
    sigma_z = az * x * ((1 + 0.0002 * x) ** -0.5)
    
    Q = frp_mw * 0.15 * 1e6
    z = 2.0
    term_y = np.exp(-0.5 * ((y / sigma_y) ** 2))
    term_z = np.exp(-0.5 * (((z - H) / sigma_z) ** 2)) + np.exp(-0.5 * (((z + H) / sigma_z) ** 2))
    conc_ug_m3 = (Q / (2 * np.pi * u * sigma_y * sigma_z)) * term_y * term_z
    
    return round(float(conc_ug_m3), 2), round(float(H), 1)

hotspots_df, hs_source = fetch_hotspots(target_lat, target_lon, nasa_key, use_mock_hs, satellite_days)

st.markdown(f"**ข้อมูลเมตาของการประมวลผล (Metadata):** พื้นที่ศึกษา: *{st.session_state.place_name}* (`{target_lat:.4f}°N, {target_lon:.4f}°E`) | แหล่งข้อมูลจุดความร้อน: *{hs_source}* (ตรวจพบทั้งหมด {len(hotspots_df)} จุดในภูมิภาค) | แหล่งข้อมูลอุตุนิยมวิทยา: *{ground['source']}*")

upwind_bearing = ground["wind_dir"] % 360
max_radius_km = round(ground["wind_speed"] * back_hours, 2)

def calc_dist_bearing(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    dist = 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    y = np.sin(dlambda) * np.cos(phi2)
    x = np.cos(phi1)*np.sin(phi2) - np.sin(phi1)*np.cos(phi2)*np.cos(dlambda)
    bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
    return dist, bearing

results = []
for idx, row in hotspots_df.iterrows():
    dist, bearing = calc_dist_bearing(target_lat, target_lon, row["latitude"], row["longitude"])
    angle_diff_rad = np.radians((bearing - upwind_bearing + 180) % 360 - 180)
    
    downwind_x = dist * np.cos(angle_diff_rad)
    crosswind_y = abs(dist * np.sin(angle_diff_rad))
    
    if downwind_x > 0 and dist <= max_radius_km:
        pred_pm25, plume_h = gaussian_plume_physics(downwind_x, crosswind_y, row["frp"], ground["wind_speed"], stab_code)
        blocked, barrier_h = check_terrain_blocking(target_lat, target_lon, row["latitude"], row["longitude"], plume_h) if use_dem_blocking else (False, 0)
        effective_pm25 = 0.0 if blocked else pred_pm25
    else:
        pred_pm25, plume_h, blocked, barrier_h, effective_pm25 = 0.0, 0.0, False, 0, 0.0

    results.append({
        "รหัสจุดความร้อน": f"HS-{idx+1:03d}",
        "เวลาตรวจพบดาวเทียม": row.get("acq_datetime", "-"),
        "ละติจูด (°N)": round(row["latitude"], 4),
        "ลองจิจูด (°E)": round(row["longitude"], 4),
        "ระยะห่างรวม (km)": round(dist, 2),
        "ระยะตามแนวลม x (km)": round(max(downwind_x, 0), 2),
        "ระยะเบี่ยงแนวลม y (km)": round(crosswind_y, 2),
        "FRP (MW)": round(row["frp"], 1),
        "ความสูงกลุ่มควัน H (m)": plume_h,
        "สภาพภูมิประเทศ": f"แนวเขาสูง +{int(barrier_h)} m (ขวางกั้น)" if blocked else "เปิดโล่ง (ไม่มีสิ่งกีดขวาง)",
        "ความเข้มข้นทำนาย (µg/m³)": effective_pm25
    })

res_df = pd.DataFrame(results)
if not res_df.empty:
    suspect_df = res_df[res_df["ความเข้มข้นทำนาย (µg/m³)"] > 0.05].sort_values(by="ความเข้มข้นทำนาย (µg/m³)", ascending=False).reset_index(drop=True)
    suspect_df.index += 1
    suspect_df.index.name = "ลำดับที่"
else:
    suspect_df = pd.DataFrame()

total_predicted_pm25 = round(suspect_df["ความเข้มข้นทำนาย (µg/m³)"].sum(), 1) if not suspect_df.empty else 0.0
rel_error = round(abs(ground["pm25"] - total_predicted_pm25) / max(ground["pm25"], 1.0) * 100, 1)

# --- สรุปค่าพารามิเตอร์หลัก ---
st.subheader("1. ค่าพารามิเตอร์ทางอุตุนิยมวิทยาและผลลัพธ์เชิงปริมาณ")
c1, c2, c3, c4 = st.columns(4)
c1.metric("ความเข้มข้นตรวจวัดจริง (C_obs)", f"{ground['pm25']} µg/m³", classify_pm25_thai(ground['pm25']))
c2.metric("ความเข้มข้นเชิงทำนายรวม (C_pred)", f"{total_predicted_pm25} µg/m³", f"ความคลาดเคลื่อนสัมพัทธ์ {rel_error}%")
c3.metric("เวกเตอร์ลมต้นทาง (Wind Vector)", f"{ground['wind_speed']} km/h", degree_to_thai_dir(upwind_bearing))
c4.metric("จุดความร้อนในแนวลม / ทั้งหมด", f"{len(suspect_df)} / {len(res_df)} จุด", f"รัศมีทำการลม {max_radius_km} km")

col_map, col_tbl = st.columns([1.15, 1.15])

with col_map:
    st.subheader("2. แบบจำลองเชิงพื้นที่และการแพร่กระจายของกลุ่มควัน")
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, max_zoom=20, tiles=None)
    
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}&hl=th",
        attr="Google Satellite Hybrid",
        name="ภาพถ่ายดาวเทียมความละเอียดสูง (Google Satellite)",
        max_zoom=20,
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}&hl=th",
        attr="Google Terrain",
        name="แผนที่ภูมิประเทศและเส้นชั้นความสูง (Terrain)",
        max_zoom=20,
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}&hl=th",
        attr="Google Maps",
        name="แผนที่โครงข่ายคมนาคม (Street Map)",
        max_zoom=20,
        overlay=False,
        control=True
    ).add_to(m)

    folium.Marker(
        [target_lat, target_lon],
        popup="จุดรับผลกระทบ / สถานีตรวจวัด (Receptor)",
        icon=folium.Icon(color="darkblue", icon="info-sign")
    ).add_to(m)
    
    cone_pts = [[target_lat, target_lon]]
    for deg in np.linspace(upwind_bearing - 30, upwind_bearing + 30, 30):
        rad = np.radians(deg)
        d_lat = (max_radius_km / 111.32) * np.cos(rad)
        d_lon = (max_radius_km / (111.32 * np.cos(np.radians(target_lat)))) * np.sin(rad)
        cone_pts.append([target_lat + d_lat, target_lon + d_lon])
    cone_pts.append([target_lat, target_lon])
    folium.Polygon(locations=cone_pts, color="#D97706", weight=1.5, fill=True, fill_opacity=0.22).add_to(m)
    
    if not res_df.empty:
        for _, r in res_df.iterrows():
            is_active = r["ความเข้มข้นทำนาย (µg/m³)"] > 0.05
            is_blocked = "ขวางกั้น" in r["สภาพภูมิประเทศ"]
            color = "#DC2626" if is_active else ("#7C3AED" if is_blocked else "#F59E0B")
            folium.CircleMarker(
                location=[r["ละติจูด (°N)"], r["ลองจิจูด (°E)"]],
                radius=7 if is_active else 4,
                color=color,
                fill=True, fill_opacity=0.85,
                popup=f"{r['รหัสจุดความร้อน']} ({r['เวลาตรวจพบดาวเทียม']}) | FRP: {r['FRP (MW)']} MW | C_pred: {r['ความเข้มข้นทำนาย (µg/m³)']} µg/m³"
            ).add_to(m)

    folium.LayerControl(position="topright").add_to(m)
            
    map_data = st_folium(m, width=620, height=440)
    st.caption("ภาพที่ 1: ตำแหน่งจุดความร้อนจริงจากดาวเทียม NASA FIRMS VIIRS (สีแดง: อยู่ในแนวกระแสลมส่งผลกระทบ, สีม่วง: ถูกแนวเขาขวางกั้น, สีเหลืองส้ม: จุดความร้อนจริงในภูมิภาคที่อยู่นอกแนวลม)")
    if map_data and map_data.get("last_clicked"):
        clicked_lat = round(map_data["last_clicked"]["lat"], 4)
        clicked_lon = round(map_data["last_clicked"]["lng"], 4)
        if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
            st.session_state.lat = clicked_lat
            st.session_state.lon = clicked_lon
            st.session_state.place_name = "พิกัดกำหนดเองจากแผนที่เชิงพื้นที่"
            st.rerun()

with col_tbl:
    st.subheader("3. ตารางผลการวิเคราะห์เชิงปริมาณและการจัดลำดับ")
    if not suspect_df.empty:
        st.dataframe(
            suspect_df[["รหัสจุดความร้อน", "เวลาตรวจพบดาวเทียม", "ระยะตามแนวลม x (km)", "FRP (MW)", "สภาพภูมิประเทศ", "ความเข้มข้นทำนาย (µg/m³)"]],
            use_container_width=True
        )
        st.caption("ตารางที่ 1: ผลการคำนวณค่าความเข้มข้นฝุ่นละอองขนาดเล็ก ณ จุดรับผลกระทบ จำแนกตามแหล่งกำเนิดความร้อน")
        
        raw_str = suspect_df.to_csv() + datetime.now().strftime("%Y-%m-%d %H:%M")
        hash_val = hashlib.sha256(raw_str.encode()).hexdigest()
        st.markdown(f"<div style='background:#F8FAFC; border:1px solid #CBD5E1; padding:0.75rem; font-size:1.1rem; margin-bottom:0.75rem;'><strong>รหัสตรวจสอบความถูกต้องของข้อมูล (SHA-256 Checksum):</strong><br><code>{hash_val}</code></div>", unsafe_allow_html=True)
        
        csv_suspect = "sep=,\n" + suspect_df.to_csv()
        st.download_button(
            label="ส่งออกตารางผลการวิเคราะห์ (Excel CSV)",
            data=csv_suspect.encode("utf-8-sig"),
            file_name=f"aerolex_quantitative_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.markdown(f"<div style='background:#FFFBEB; border:1px solid #FDE68A; color:#92400E; padding:0.85rem; font-size:1.2rem;'>ตรวจพบจุดความร้อนจริงในภูมิภาคทั้งหมด {len(res_df)} จุด แต่ไม่มีจุดใดตกอยู่ในแนวกรวยลมของสถานีตรวจวัดในช่วงเวลาที่กำหนด (สามารถทดลองปรับเพิ่มคาบเวลาการเคลื่อนที่ของมวลอากาศที่แถบด้านซ้ายเพื่อขยายรัศมีกรวยลม)</div>", unsafe_allow_html=True)
        if not res_df.empty:
            with st.expander(f"ดูรายการจุดความร้อนจริงทั้งหมดที่ดาวเทียมตรวจพบในภูมิภาค ({len(res_df)} จุด)"):
                st.dataframe(res_df[["รหัสจุดความร้อน", "เวลาตรวจพบดาวเทียม", "ละติจูด (°N)", "ลองจิจูด (°E)", "ระยะห่างรวม (km)", "FRP (MW)"]].head(50), use_container_width=True)

st.subheader("4. ระเบียบวิธีวิจัยและสมการทางคณิตศาสตร์ที่ใช้อ้างอิง")
st.markdown(r"""
1. **แบบจำลองการแพร่กระจายแบบเกาส์เซียน (Gaussian Plume Dispersion Model):** คำนวณความเข้มข้นของมวลสารมลพิษ $C(x, y, z)$ ณ ระดับความสูงจุดตรวจวัด $z = 2.0\text{ m}$
   $$C(x, y, z) = \frac{Q}{2\pi u \sigma_y \sigma_z} \exp\left(-\frac{y^2}{2\sigma_y^2}\right) \left[ \exp\left(-\frac{(z - H)^2}{2\sigma_z^2}\right) + \exp\left(-\frac{(z + H)^2}{2\sigma_z^2}\right) \right]$$
   โดยกำหนดให้อัตราการปลดปล่อยมวลฝุ่น $Q$ แปรผันตรงกับพลังงานการแผ่รังสีความร้อนจากไฟ ($\text{FRP}$) และค่าสัมประสิทธิ์การฟุ้งกระจาย $\sigma_y, \sigma_z$ คำนวณตามเกณฑ์เสถียรภาพบรรยากาศของ Pasquill-Gifford (Pasquill, 1961)

2. **สมการแรงลอยตัวทางความร้อนของบริกส์ (Briggs' Thermal Plume Rise):** คำนวณระยะยกตัวของกลุ่มควัน $\Delta h$ เนื่องจากความแตกต่างของความหนาแน่นอากาศจากความร้อน (Briggs, 1969)
   $$\Delta h = \frac{1.6 F^{1/3} x^{2/3}}{u}, \quad F = 8.9 \times \text{FRP}$$

3. **การวิเคราะห์สิ่งกีดขวางทางภูมิประเทศ (Orographic Blocking Criterion):** ตรวจสอบความสูงภูมิประเทศตามแนวตัดขวาง (Elevation Profile) จากข้อมูล DEM โดยกำหนดเงื่อนไขการขวางกั้นเมื่อระดับความสูงสันเขา $Z_{\text{terrain}} > (Z_{\text{source}} + H + 150\text{ m})$
""")

st.subheader("5. คลังข้อมูลอนุกรมเวลาภาคพื้นดิน (InfluxDB Time-Series Archive)")
if st.button("ประมวลผลและแปลความหมายข้อมูลอนุกรมเวลาย้อนหลัง 7 วัน"):
    try:
        client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
        query_api = client.query_api()
        hist_query = f'''
        from(bucket: "{influx_bucket}")
          |> range(start: -7d)
          |> filter(fn: (r) => r["_measurement"] == "ground_station")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        df_hist = query_api.query_data_frame(hist_query, org=influx_org)
        client.close()
        if not df_hist.empty:
            df_hist["วัน-เวลา (เวลาประเทศไทย)"] = pd.to_datetime(df_hist["_time"]).dt.tz_convert("Asia/Bangkok").dt.strftime("%Y-%m-%d %H:%M:%S")
            df_hist["รหัสสถานีตรวจวัด"] = df_hist.get("station_id", "N/A")
            df_hist["ความเข้มข้น PM2.5 (µg/m³)"] = df_hist["pm25"].round(1)
            df_hist["เกณฑ์คุณภาพอากาศ (กรมควบคุมมลพิษ)"] = df_hist["pm25"].apply(classify_pm25_thai)
            df_hist["ความเร็วลม (km/h)"] = df_hist["wind_speed"].round(1)
            df_hist["ทิศทางลมต้นทาง"] = df_hist["wind_dir"].apply(degree_to_thai_dir)

            export_cols = [
                "วัน-เวลา (เวลาประเทศไทย)",
                "รหัสสถานีตรวจวัด",
                "ความเข้มข้น PM2.5 (µg/m³)",
                "เกณฑ์คุณภาพอากาศ (กรมควบคุมมลพิษ)",
                "ความเร็วลม (km/h)",
                "ทิศทางลมต้นทาง"
            ]
            df_clean = df_hist[export_cols].sort_values(by="วัน-เวลา (เวลาประเทศไทย)", ascending=False)
            
            st.dataframe(df_clean, use_container_width=True)
            
            csv_output = "sep=,\n" + df_clean.to_csv(index=False)
            st.download_button(
                label="ดาวน์โหลดรายงานข้อมูลที่แปลผลแล้ว (Excel CSV)",
                data=csv_output.encode("utf-8-sig"),
                file_name=f"aerolex_interpreted_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.markdown("<div style='background:#F8FAFC; border:1px solid #CBD5E1; padding:0.75rem; font-size:1.15rem;'>ไม่พบระเบียนข้อมูลในฐานข้อมูลอนุกรมเวลาช่วง 7 วันที่ผ่านมา</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"ข้อผิดพลาดในการสืบค้นฐานข้อมูล: {e}")

st.markdown("""
<div style="margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #CBD5E1; font-size: 1.1rem; color: #64748B; line-height: 1.55;">
    <strong>เอกสารอ้างอิงทางวิชาการ (References):</strong><br>
    [1] Pasquill, F. (1961). The estimation of the dispersion of windborne material. <em>Meteorological Magazine</em>, 90, 33–49.<br>
    [2] Briggs, G. A. (1969). <em>Plume Rise</em>. U.S. Atomic Energy Commission Critical Review Series, TID-25075.<br>
    [3] NASA FIRMS (Fire Information for Resource Management System). VIIRS 375m Active Fire Data Product.
</div>
""", unsafe_allow_html=True)
