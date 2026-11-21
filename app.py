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
import random

st.set_page_config(page_title="ระบบคัดกรองและจัดอันดับพื้นที่ต้นกำเนิดมลพิษ", layout="wide")
st.title("ระบบคัดกรองและจัดอันดับพื้นที่ต้นกำเนิดมลพิษทางอากาศ")
st.caption("บูรณาการข้อมูลตรวจวัดภาคพื้นดิน (InfluxDB) + ข้อมูลจุดความร้อนดาวเทียม (NASA FIRMS) + แบบจำลองเส้นทางมวลอากาศ")

# --- ค่าเชื่อมต่อฐานข้อมูลและ API ---
DEFAULT_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
DEFAULT_TOKEN = "KP7nnhAgAvxAfzfgh6xEIOKtvW859QsOzcqfvE-x9k81aduLdB6hWJ3l8fd0nODwvMgs5OdJqqLSZT2oRpl6RQ=="
DEFAULT_ORG = "air_pollution_project"
DEFAULT_BUCKET = "air_quality_data"
DEFAULT_NASA_KEY = "9f142ebe06d50df4aeed0bc128f507c8"

# เก็บค่าพิกัดไว้ใน Session State เพื่อให้เปลี่ยนค่าได้ทั้งจากการพิมพ์ค้นหาและการคลิกแผนที่
if "lat" not in st.session_state:
    st.session_state.lat = 18.2888
if "lon" not in st.session_state:
    st.session_state.lon = 99.4908
if "place_name" not in st.session_state:
    st.session_state.place_name = "อ.เมือง จ.ลำปาง (ค่าเริ่มต้น)"

# --- แถบเมนูด้านซ้าย: เลือกสถานที่ ---
st.sidebar.header("📍 1. เลือกสถานที่ตรวจวัด")

# ตัวเลือกสถานที่สำเร็จรูป
preset_locations = {
    "กำหนดเอง / ค้นหาด้านล่าง": None,
    "อ.เมือง จ.ลำปาง": (18.2888, 99.4908),
    "อ.แม่เมาะ จ.ลำปาง": (18.2936, 99.6517),
    "รร.จุฬาภรณราชวิทยาลัย เชียงราย": (19.9575, 99.8825),
    "อ.แม่สาย จ.เชียงราย": (20.4335, 99.8806),
    "อ.เมือง จ.เชียงใหม่": (18.7883, 98.9853)
}
selected_preset = st.sidebar.selectbox("เลือกพื้นที่ด่วน:", list(preset_locations.keys()))
if preset_locations[selected_preset] is not None:
    st.session_state.lat, st.session_state.lon = preset_locations[selected_preset]
    st.session_state.place_name = selected_preset

# ช่องพิมพ์ค้นหาชื่อสถานที่
search_query = st.sidebar.text_input("หรือพิมพ์ค้นหาชื่อสถานที่ / อำเภอ / จังหวัด:", placeholder="เช่น แม่ฟ้าหลวง เชียงราย")
if st.sidebar.button("🔍 ค้นหาพิกัด"):
    if search_query:
        try:
            geolocator = Nominatim(user_agent="aero_lex_student_project")
            location = geolocator.geocode(search_query + " Thailand")
            if location:
                st.session_state.lat = round(location.latitude, 4)
                st.session_state.lon = round(location.longitude, 4)
                st.session_state.place_name = location.address
                st.sidebar.success(f"พบพิกัด: {location.latitude:.4f}, {location.longitude:.4f}")
            else:
                st.sidebar.warning("ไม่พบสถานที่นี้ ลองระบุชื่ออำเภอหรือจังหวัดเพิ่มเติม")
        except Exception as e:
            st.sidebar.error(f"ค้นหาไม่สำเร็จ: {e}")

target_lat = st.sidebar.number_input("ละติจูด (Latitude)", value=st.session_state.lat, format="%.4f")
target_lon = st.sidebar.number_input("ลองจิจูด (Longitude)", value=st.session_state.lon, format="%.4f")
st.session_state.lat = target_lat
st.session_state.lon = target_lon

# --- ตั้งค่ากรวยลม ---
st.sidebar.header("🧭 2. แบบจำลองกรวยลม")
cone_angle = st.sidebar.slider("มุมกวาดกรวยลม (องศา)", 30, 90, 60)
back_hours = st.sidebar.slider("ระยะเวลาย้อนรอย (ชั่วโมง)", 1, 12, 4)

# --- ตั้งค่าฐานข้อมูลและดาวเทียม ---
st.sidebar.header("📡 3. ฐานข้อมูล & ดาวเทียม")
influx_url = st.sidebar.text_input("InfluxDB URL", value=DEFAULT_URL)
influx_token = st.sidebar.text_input("InfluxDB Token", value=DEFAULT_TOKEN, type="password")
influx_org = st.sidebar.text_input("Organization", value=DEFAULT_ORG)
influx_bucket = st.sidebar.text_input("Bucket", value=DEFAULT_BUCKET)

if st.sidebar.button("📤 จำลองส่งข้อมูลจากสถานีเข้า InfluxDB"):
    try:
        client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = (
            Point("ground_station")
            .tag("station_id", "CUSTOM-01")
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

nasa_key = st.sidebar.text_input("NASA MAP_KEY", value=DEFAULT_NASA_KEY, type="password")
use_mock_hs = st.sidebar.checkbox("ใช้จุดความร้อนจำลอง (สำหรับสาธิต)", value=False)

# --- ฟังก์ชันดึงข้อมูล ---
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
                    return pd.DataFrame(columns=["latitude", "longitude", "frp"]), "NASA FIRMS VIIRS (ไม่พบจุดความร้อนจริงในพื้นที่นี้)"
        except Exception:
            pass
    np.random.seed(int(abs(lat * 100)))
    lats = lat + np.random.uniform(-0.35, 0.35, 18)
    lons = lon + np.random.uniform(-0.35, 0.35, 18)
    frp = np.random.uniform(8.0, 50.0, 18)
    return pd.DataFrame({"latitude": lats, "longitude": lons, "frp": frp}), "ข้อมูลจำลอง (สำหรับสาธิตระบบ)"

ground = fetch_ground_data(influx_url, influx_token, influx_org, influx_bucket)
hotspots_df, hs_source = fetch_hotspots(target_lat, target_lon, nasa_key, use_mock_hs)

st.info(f"📌 **พื้นที่ที่กำลังวิเคราะห์:** {st.session_state.place_name} (`{target_lat:.4f}, {target_lon:.4f}`) | 🛰️ **แหล่งจุดความร้อน:** {hs_source}")

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
    st.subheader("แผนที่จำลองเส้นทางมวลอากาศ (คลิกบนแผนที่เพื่อย้ายจุดได้)")
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
            
    # รับค่าพิกัดเมื่อผู้ใช้คลิกบนแผนที่
    map_data = st_folium(m, width=650, height=450)
    if map_data and map_data.get("last_clicked"):
        clicked_lat = round(map_data["last_clicked"]["lat"], 4)
        clicked_lon = round(map_data["last_clicked"]["lng"], 4)
        if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
            st.session_state.lat = clicked_lat
            st.session_state.lon = clicked_lon
            st.session_state.place_name = "พิกัดที่เลือกจากแผนที่"
            st.rerun()

with col_tbl:
    st.subheader("ตารางจัดอันดับพื้นที่ต้นกำเนิดที่เป็นไปได้")
    if not suspect_df.empty:
        st.dataframe(suspect_df[["รหัสจุด", "ละติจูด", "ลองจิจูด", "ระยะห่าง (กม.)", "พลังงานความร้อน (FRP)", "คะแนนความน่าจะเป็น"]], use_container_width=True)
        
        raw_str = suspect_df.to_csv() + datetime.now().strftime("%Y-%m-%d %H:%M")
        hash_val = hashlib.sha256(raw_str.encode()).hexdigest()
        st.success(f"**รหัสรับรองความถูกต้องของข้อมูล (SHA-256):**\n`{hash_val}`")
        
        st.download_button(
            label="📥 ดาวน์โหลดรายงานจัดอันดับ (CSV)",
            data=suspect_df.to_csv().encode("utf-8-sig"),
            file_name=f"source_ranking_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("ไม่พบจุดความร้อนในแนวทิศทางลมช่วงเวลานี้ (หากต้องการทดสอบการสาธิต ให้ติ๊กเลือก 'ใช้จุดความร้อนจำลอง' ที่แถบด้านซ้าย)")

st.divider()
st.subheader("🗄️ ดาวน์โหลดประวัติข้อมูลตรวจวัดภาคพื้นดิน (InfluxDB)")
if st.button("เตรียมไฟล์ประวัติข้อมูลย้อนหลัง 7 วัน"):
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
            cols = [c for c in ["_time", "station_id", "pm25", "wind_speed", "wind_dir"] if c in df_hist.columns]
            st.download_button(
                label="คลิกเพื่อดาวน์โหลดไฟล์ CSV (ข้อมูลจาก InfluxDB)",
                data=df_hist[cols].to_csv(index=False).encode("utf-8-sig"),
                file_name=f"influxdb_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("ยังไม่มีข้อมูลประวัติในฐานข้อมูล กดปุ่มส่งข้อมูลด้านซ้ายเพื่อสร้างข้อมูลตัวอย่างก่อนได้ครับ")
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
