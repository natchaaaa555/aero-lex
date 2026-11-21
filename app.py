import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
import folium
from streamlit_folium import st_folium
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import hashlib
import random

st.set_page_config(page_title="ระบบคัดกรองและจัดอันดับพื้นที่ต้นกำเนิดมลพิษ", layout="wide")
st.title("ระบบคัดกรองและจัดอันดับพื้นที่ต้นกำเนิดมลพิษทางอากาศ")
st.caption("บูรณาการข้อมูลตรวจวัดภาคพื้นดิน (InfluxDB) + ข้อมูลจุดความร้อนดาวเทียม (NASA FIRMS) + แบบจำลองเส้นทางมวลอากาศ")

# --- ค่าเชื่อมต่อของคุณ (ใส่ไว้ให้พร้อมใช้งานทันที) ---
DEFAULT_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
DEFAULT_TOKEN = "KP7nnhAgAvxAfzfgh6xEIOKtvW859QsOzcqfvE-x9k81aduLdB6hWJ3l8fd0nODwvMgs5OdJqqLSZT2oRpl6RQ=="
DEFAULT_ORG = "air_pollution_project"
DEFAULT_BUCKET = "air_quality_data"
DEFAULT_NASA_KEY = "9f142ebe06d50df4aeed0bc128f507c8"

st.sidebar.header("1. ฐานข้อมูลภาคพื้นดิน (InfluxDB)")
influx_url = st.sidebar.text_input("InfluxDB URL", value=DEFAULT_URL)
influx_token = st.sidebar.text_input("InfluxDB Token", value=DEFAULT_TOKEN, type="password")
influx_org = st.sidebar.text_input("Organization", value=DEFAULT_ORG)
influx_bucket = st.sidebar.text_input("Bucket", value=DEFAULT_BUCKET)

# ปุ่มจำลองการส่งข้อมูลจากสถานีภาคสนามเข้า InfluxDB
if st.sidebar.button("📡 จำลองส่งข้อมูลจากสถานีเข้า InfluxDB"):
    try:
        client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = (
            Point("ground_station")
            .tag("station_id", "LP-01")
            .field("pm25", round(random.uniform(75.0, 125.0), 1))
            .field("wind_speed", round(random.uniform(10.0, 22.0), 1))
            .field("wind_dir", round(random.uniform(180.0, 270.0), 1))
            .time(datetime.now(timezone.utc))
        )
        write_api.write(bucket=influx_bucket, org=influx_org, record=point)
        client.close()
        st.sidebar.success("✅ ส่งข้อมูลชุดใหม่เข้า InfluxDB สำเร็จ!")
    except Exception as e:
        st.sidebar.error(f"ส่งข้อมูลไม่สำเร็จ: {e}")

st.sidebar.header("2. ข้อมูลจุดความร้อน (NASA FIRMS)")
nasa_key = st.sidebar.text_input("NASA MAP_KEY", value=DEFAULT_NASA_KEY, type="password")
use_mock_hs = st.sidebar.checkbox("ใช้จุดความร้อนจำลอง (กรณีวันนี้ไม่มีจุดเผาจริงในพื้นที่)", value=False)

st.sidebar.header("3. พิกัดสถานี & แบบจำลองกรวยลม")
target_lat = st.sidebar.number_input("ละติจูด (Latitude)", value=18.2888, format="%.4f")
target_lon = st.sidebar.number_input("ลองจิจูด (Longitude)", value=99.4908, format="%.4f")
cone_angle = st.sidebar.slider("มุมกวาดกรวยลม (องศา)", 30, 90, 60)
back_hours = st.sidebar.slider("ระยะเวลาย้อนรอย (ชั่วโมง)", 1, 12, 4)

# --- ดึงข้อมูลจาก InfluxDB ---
def fetch_ground_data(url, token, org, bucket):
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
                "source": "InfluxDB Cloud (ข้อมูลจริงจากฐานข้อมูล)",
                "pm25": round(float(data["pm25"]), 1),
                "wind_speed": round(float(data["wind_speed"]), 1),
                "wind_dir": round(float(data["wind_dir"]), 1)
            }
    except Exception:
        pass
    return {
        "source": "ค่าเริ่มต้น (กดปุ่มส่งข้อมูลด้านซ้ายเพื่อทดสอบ InfluxDB)",
        "pm25": 88.5,
        "wind_speed": 12.5,
        "wind_dir": 225.0
    }

# --- ดึงข้อมูลจุดความร้อน ---
def fetch_hotspots(lat, lon, api_key, force_mock):
    if api_key and not force_mock:
        try:
            area = f"{lon-0.6},{lat-0.6},{lon+0.6},{lat+0.6}"
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_SNPP_NRT/{area}/1"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and "latitude" in resp.text:
                df = pd.read_csv(io.StringIO(resp.text))
                if "confidence" in df.columns:
                    df = df[df["confidence"].isin(["n", "h", "nominal", "high"])]
                if not df.empty:
                    return df[["latitude", "longitude", "frp"]], "NASA FIRMS VIIRS (ข้อมูลจริงจากดาวเทียม)"
                else:
                    return pd.DataFrame(columns=["latitude", "longitude", "frp"]), "NASA FIRMS VIIRS (วันนี้ไม่พบจุดความร้อนจริงในพื้นที่)"
        except Exception:
            pass
    np.random.seed(42)
    lats = lat + np.random.uniform(-0.35, 0.35, 18)
    lons = lon + np.random.uniform(-0.35, 0.35, 18)
    frp = np.random.uniform(8.0, 50.0, 18)
    return pd.DataFrame({"latitude": lats, "longitude": lons, "frp": frp}), "ข้อมูลจำลอง (สำหรับสาธิตระบบ)"

ground = fetch_ground_data(influx_url, influx_token, influx_org, influx_bucket)
hotspots_df, hs_source = fetch_hotspots(target_lat, target_lon, nasa_key, use_mock_hs)

st.sidebar.info(f"📊 {ground['source']}")
st.sidebar.info(f"🛰️ {hs_source}")

# --- คำนวณกรวยลมและจัดอันดับ ---
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
    angle_diff = abs((bearing - upwind_bearing + 180) % 360 - 180)
    in_cone = (dist <= max_radius_km) and (angle_diff <= cone_angle / 2)
    score = ((1 / (dist + 1)) * 50 + (row["frp"] * 0.5) + ((cone_angle/2 - angle_diff) * 0.5)) if in_cone else 0.0
    results.append({
        "รหัสจุด": f"HS-{idx+1:02d}",
        "ละติจูด": round(row["latitude"], 4),
        "ลองจิจูด": round(row["longitude"], 4),
        "ระยะห่าง (กม.)": round(dist, 2),
        "มุมทิศ (องศา)": round(bearing, 1),
        "พลังงานความร้อน (FRP)": round(row["frp"], 1),
        "อยู่ในกรวยลม": in_cone,
        "คะแนนความน่าจะเป็น": round(score, 2)
    })

res_df = pd.DataFrame(results)
if not res_df.empty:
    suspect_df = res_df[res_df["อยู่ในกรวยลม"]].sort_values(by="คะแนนความน่าจะเป็น", ascending=False).reset_index(drop=True)
    suspect_df.index += 1
    suspect_df.index.name = "อันดับ"
else:
    suspect_df = pd.DataFrame()

c1, c2, c3, c4 = st.columns(4)
c1.metric("PM2.5 ภาคพื้นดิน", f"{ground['pm25']} µg/m³")
c2.metric("ความเร็วลม / ทิศต้นลม", f"{ground['wind_speed']} km/h", f"ทิศ {upwind_bearing}°")
c3.metric("รัศมีกรวยลม (R = v×t)", f"{max_radius_km} กม.", f"ย้อนหลัง {back_hours} ชม.")
c4.metric("จุดต้องสงสัยในกรวยลม", f"{len(suspect_df)} จุด", f"จากทั้งหมด {len(res_df)} จุด")

st.divider()
col_map, col_tbl = st.columns([1.2, 1])

with col_map:
    st.subheader("แผนที่จำลองเส้นทางมวลอากาศย้อนกลับ")
    m = folium.Map(location=[target_lat, target_lon], zoom_start=10)
    folium.Marker([target_lat, target_lon], popup="จุดตรวจวัด / ผู้รับผลกระทบ", icon=folium.Icon(color="blue", icon="home")).add_to(m)
    
    cone_pts = [[target_lat, target_lon]]
    for deg in np.linspace(upwind_bearing - cone_angle/2, upwind_bearing + cone_angle/2, 30):
        rad = np.radians(deg)
        d_lat = (max_radius_km / 111.32) * np.cos(rad)
        d_lon = (max_radius_km / (111.32 * np.cos(np.radians(target_lat)))) * np.sin(rad)
        cone_pts.append([target_lat + d_lat, target_lon + d_lon])
    cone_pts.append([target_lat, target_lon])
    folium.Polygon(locations=cone_pts, color="orange", fill=True, fill_opacity=0.35).add_to(m)
    
    if not res_df.empty:
        for _, r in res_df.iterrows():
            folium.CircleMarker(
                location=[r["ละติจูด"], r["ลองจิจูด"]],
                radius=7 if r["อยู่ในกรวยลม"] else 4,
                color="red" if r["อยู่ในกรวยลม"] else "gray",
                fill=True, fill_opacity=0.9,
                popup=f"{r['รหัสจุด']} | ระยะ: {r['ระยะห่าง (กม.)']} กม. | คะแนน: {r['คะแนนความน่าจะเป็น']}"
            ).add_to(m)
    st_folium(m, width=650, height=450)

with col_tbl:
    st.subheader("ตารางจัดอันดับพื้นที่ต้นกำเนิดที่เป็นไปได้")
    if not suspect_df.empty:
        st.dataframe(suspect_df[["รหัสจุด", "ละติจูด", "ลองจิจูด", "ระยะห่าง (กม.)", "พลังงานความร้อน (FRP)", "คะแนนความน่าจะเป็น"]], use_container_width=True)
        
        raw_str = suspect_df.to_csv() + datetime.now().strftime("%Y-%m-%d %H:%M")
        hash_val = hashlib.sha256(raw_str.encode()).hexdigest()
        st.success(f"**รหัสรับรองความถูกต้องของข้อมูล (SHA-256):**\n`{hash_val}`")
        
        st.download_button(
            label="ดาวน์โหลดรายงานจัดอันดับ (CSV)",
            data=suspect_df.to_csv().encode("utf-8-sig"),
            file_name=f"source_ranking_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("ไม่พบจุดความร้อนในแนวทิศทางลมช่วงเวลานี้ (หากต้องการทดสอบการสาธิต ให้ติ๊กเลือก 'ใช้จุดความร้อนจำลอง' ที่แถบด้านซ้าย)")