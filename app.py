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

st.set_page_config(page_title="Aero-Lex Physics | แบบจำลองฟิสิกส์บรรยากาศคัดกรองต้นกำเนิดมลพิษ", layout="wide")
st.title("Aero-Lex: แบบจำลองฟิสิกส์บรรยากาศเพื่อคัดกรองและระบุแหล่งกำเนิด PM2.5")
st.caption("บูรณาการ Gaussian Plume Dispersion Model + Briggs' Thermal Buoyancy + DEM Orographic Blocking")

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
    st.session_state.place_name = "อ.เมือง จ.ลำปาง (แอ่งกระทะลำปาง)"

# --- แถบเมนูด้านซ้าย ---
st.sidebar.header("📍 1. พิกัดสถานีตรวจวัด (Receptor)")
preset_locations = {
    "กำหนดเอง / ค้นหาด้านล่าง": None,
    "อ.เมือง จ.ลำปาง": (18.2888, 99.4908),
    "อ.แม่เมาะ จ.ลำปาง": (18.2936, 99.6517),
    "รร.จุฬาภรณราชวิทยาลัย เชียงราย": (19.9575, 99.8825),
    "อ.แม่สาย จ.เชียงราย": (20.4335, 99.8806),
    "อ.เมือง จ.เชียงใหม่": (18.7883, 98.9853)
}
selected_preset = st.sidebar.selectbox("เลือกพื้นที่ศึกษาด่วน:", list(preset_locations.keys()))
if preset_locations[selected_preset] is not None:
    st.session_state.lat, st.session_state.lon = preset_locations[selected_preset]
    st.session_state.place_name = selected_preset

search_query = st.sidebar.text_input("ค้นหาชื่อสถานที่ / อำเภอ / จังหวัด:", placeholder="เช่น แม่ฟ้าหลวง เชียงราย")
if st.sidebar.button("🔍 ค้นหาพิกัด"):
    if search_query:
        try:
            geolocator = Nominatim(user_agent="aero_lex_physics_model")
            location = geolocator.geocode(search_query + " Thailand")
            if location:
                st.session_state.lat = round(location.latitude, 4)
                st.session_state.lon = round(location.longitude, 4)
                st.session_state.place_name = location.address
        except Exception as e:
            st.sidebar.error(f"ค้นหาไม่สำเร็จ: {e}")

target_lat = st.sidebar.number_input("ละติจูด (Latitude)", value=st.session_state.lat, format="%.4f")
target_lon = st.sidebar.number_input("ลองจิจูด (Longitude)", value=st.session_state.lon, format="%.4f")
st.session_state.lat = target_lat
st.session_state.lon = target_lon

st.sidebar.header("🌪️ 2. พารามิเตอร์ฟิสิกส์บรรยากาศ")
stability_class = st.sidebar.selectbox(
    "เสถียรภาพบรรยากาศ (Pasquill Stability Class)",
    options=["A (ไม่เสถียรสูง - แดดจัด ลมอ่อน)", "B (ไม่เสถียรปานกลาง)", "C (ไม่เสถียรเล็กน้อย)", "D (เป็นกลาง - มีเมฆมาก/ลมแรง)", "E (เสถียรเล็กน้อย - ช่วงค่ำ)", "F (เสถียรสูง/อุณหภูมิผกผัน - เช้ามืด)"],
    index=3
)
stab_code = stability_class[0]
back_hours = st.sidebar.slider("ระยะเวลาการเคลื่อนที่ของมวลอากาศ (ชม.)", 1, 12, 4)
use_dem_blocking = st.sidebar.checkbox("เปิดใช้การตัดสิ่งกีดขวางภูมิประเทศ (DEM Terrain Blocking)", value=True)

st.sidebar.header("📡 3. ฐานข้อมูล & ดาวเทียม")
influx_url = st.sidebar.text_input("InfluxDB URL", value=DEFAULT_URL)
influx_token = st.sidebar.text_input("InfluxDB Token", value=DEFAULT_TOKEN, type="password")
influx_org = st.sidebar.text_input("Organization", value=DEFAULT_ORG)
influx_bucket = st.sidebar.text_input("Bucket", value=DEFAULT_BUCKET)

if st.sidebar.button("📤 จำลองส่งข้อมูลเซนเซอร์เข้า InfluxDB"):
    try:
        client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = (
            Point("ground_station")
            .tag("station_id", "PHYS-ST01")
            .field("pm25", round(random.uniform(75.0, 130.0), 1))
            .field("wind_speed", round(random.uniform(8.0, 20.0), 1))
            .field("wind_dir", round(random.uniform(190.0, 260.0), 1))
            .time(datetime.now(timezone.utc))
        )
        write_api.write(bucket=influx_bucket, org=influx_org, record=point)
        client.close()
        st.sidebar.success("✅ บันทึกข้อมูลลง InfluxDB Cloud สำเร็จ!")
    except Exception as e:
        st.sidebar.error(f"ส่งข้อมูลไม่สำเร็จ: {e}")

nasa_key = st.sidebar.text_input("NASA MAP_KEY", value=DEFAULT_NASA_KEY, type="password")
use_mock_hs = st.sidebar.checkbox("ใช้จุดความร้อนจำลอง (สำหรับสาธิตการคำนวณ)", value=True)

# --- ฟังก์ชันดึงข้อมูลจาก InfluxDB และ NASA FIRMS ---
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
                "source": "InfluxDB Cloud (ข้อมูลจริงจากสถานี)",
                "pm25": round(float(data["pm25"]), 1),
                "wind_speed": round(float(data["wind_speed"]), 1),
                "wind_dir": round(float(data["wind_dir"]), 1)
            }
    except Exception:
        pass
    return {"source": "ค่าเริ่มต้นระบบ", "pm25": 92.4, "wind_speed": 12.0, "wind_dir": 225.0}

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
                    return df[["latitude", "longitude", "frp"]], "NASA FIRMS VIIRS (ข้อมูลดาวเทียมจริง)"
                else:
                    return pd.DataFrame(columns=["latitude", "longitude", "frp"]), "NASA FIRMS VIIRS (ไม่พบจุดความร้อนจริงในพื้นที่)"
        except Exception:
            pass
    np.random.seed(int(abs(lat * 100)))
    lats = lat + np.random.uniform(-0.32, 0.32, 15)
    lons = lon + np.random.uniform(-0.32, 0.32, 15)
    frp = np.random.uniform(10.0, 65.0, 15)
    return pd.DataFrame({"latitude": lats, "longitude": lons, "frp": frp}), "ชุดข้อมูลจำลองเชิงฟิสิกส์ (Simulation)"

# --- ฟังก์ชันตรวจสอบความสูงภูมิประเทศ (DEM Elevation Profile) ---
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

# --- แบบจำลองฟิสิกส์บรรยากาศ (Gaussian Plume + Briggs' Buoyancy) ---
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

ground = fetch_ground_data(influx_url, influx_token, influx_org, influx_bucket)
hotspots_df, hs_source = fetch_hotspots(target_lat, target_lon, nasa_key, use_mock_hs)

st.info(f"📌 **สถานีรับผลกระทบ (Receptor):** {st.session_state.place_name} (`{target_lat:.4f}, {target_lon:.4f}`) | 🛰️ **แหล่งข้อมูล:** {hs_source}")

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
        "รหัสจุด": f"HS-{idx+1:02d}",
        "ละติจูด": round(row["latitude"], 4),
        "ลองจิจูด": round(row["longitude"], 4),
        "ระยะตามลม x (กม.)": round(max(downwind_x, 0), 2),
        "ระยะเบี่ยง y (กม.)": round(crosswind_y, 2),
        "FRP (MW)": round(row["frp"], 1),
        "ความสูงควัน H (ม.)": plume_h,
        "สิ่งกีดขวางภูมิประเทศ": f"ภูเขาสูง +{int(barrier_h)}ม. (บังลม)" if blocked else "ไม่มีสิ่งกีดขวาง",
        "PM2.5 เชิงทำนาย (µg/m³)": effective_pm25
    })

res_df = pd.DataFrame(results)
if not res_df.empty:
    suspect_df = res_df[res_df["PM2.5 เชิงทำนาย (µg/m³)"] > 0.05].sort_values(by="PM2.5 เชิงทำนาย (µg/m³)", ascending=False).reset_index(drop=True)
    suspect_df.index += 1
    suspect_df.index.name = "อันดับ"
else:
    suspect_df = pd.DataFrame()

total_predicted_pm25 = round(suspect_df["PM2.5 เชิงทำนาย (µg/m³)"].sum(), 1) if not suspect_df.empty else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("PM2.5 วัดได้จริง (Observed)", f"{ground['pm25']} µg/m³")
c2.metric("PM2.5 ทำนายจากแบบจำลอง (Predicted)", f"{total_predicted_pm25} µg/m³", f"เสถียรภาพ Class {stab_code}")
c3.metric("ความเร็วลม / ทิศต้นลม", f"{ground['wind_speed']} km/h", f"ทิศ {upwind_bearing}°")
c4.metric("แหล่งกำเนิดที่มีนัยสำคัญ", f"{len(suspect_df)} จุด", f"รัศมีทำการ {max_radius_km} กม.")

st.divider()
col_map, col_tbl = st.columns([1.15, 1.15])

with col_map:
    st.subheader("แผนที่การแพร่กระจายมวลอากาศ (Gaussian Plume Trajectory)")
    m = folium.Map(location=[target_lat, target_lon], zoom_start=10)
    folium.Marker([target_lat, target_lon], popup="สถานีตรวจวัด (Receptor)", icon=folium.Icon(color="blue", icon="home")).add_to(m)
    
    cone_pts = [[target_lat, target_lon]]
    for deg in np.linspace(upwind_bearing - 30, upwind_bearing + 30, 30):
        rad = np.radians(deg)
        d_lat = (max_radius_km / 111.32) * np.cos(rad)
        d_lon = (max_radius_km / (111.32 * np.cos(np.radians(target_lat)))) * np.sin(rad)
        cone_pts.append([target_lat + d_lat, target_lon + d_lon])
    cone_pts.append([target_lat, target_lon])
    folium.Polygon(locations=cone_pts, color="orange", fill=True, fill_opacity=0.25).add_to(m)
    
    if not res_df.empty:
        for _, r in res_df.iterrows():
            is_active = r["PM2.5 เชิงทำนาย (µg/m³)"] > 0.05
            is_blocked = "บังลม" in r["สิ่งกีดขวางภูมิประเทศ"]
            color = "red" if is_active else ("purple" if is_blocked else "gray")
            folium.CircleMarker(
                location=[r["ละติจูด"], r["ลองจิจูด"]],
                radius=8 if is_active else 5,
                color=color,
                fill=True, fill_opacity=0.9,
                popup=f"{r['รหัสจุด']} | PM2.5 ทำนาย: {r['PM2.5 เชิงทำนาย (µg/m³)']} µg/m³ | {r['สิ่งกีดขวางภูมิประเทศ']}"
            ).add_to(m)
            
    map_data = st_folium(m, width=620, height=450)
    if map_data and map_data.get("last_clicked"):
        clicked_lat = round(map_data["last_clicked"]["lat"], 4)
        clicked_lon = round(map_data["last_clicked"]["lng"], 4)
        if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
            st.session_state.lat = clicked_lat
            st.session_state.lon = clicked_lon
            st.session_state.place_name = "พิกัดที่เลือกจากแผนที่"
            st.rerun()

with col_tbl:
    st.subheader("ตารางวิเคราะห์เชิงปริมาณตามหลักฟิสิกส์บรรยากาศ")
    if not suspect_df.empty:
        st.dataframe(
            suspect_df[["รหัสจุด", "ระยะตามลม x (กม.)", "FRP (MW)", "ความสูงควัน H (ม.)", "สิ่งกีดขวางภูมิประเทศ", "PM2.5 เชิงทำนาย (µg/m³)"]],
            use_container_width=True
        )
        
        raw_str = suspect_df.to_csv() + datetime.now().strftime("%Y-%m-%d %H:%M")
        hash_val = hashlib.sha256(raw_str.encode()).hexdigest()
        st.success(f"**รหัสรับรองความถูกต้องข้อมูล (SHA-256):**\n`{hash_val}`")
        
        st.download_button(
            label="📥 ดาวน์โหลดผลการคำนวณทางฟิสิกส์ (CSV)",
            data=suspect_df.to_csv().encode("utf-8-sig"),
            file_name=f"aerolex_physics_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("ไม่พบแหล่งกำเนิดที่ส่งผลกระทบถึงสถานีตรวจวัด (หรือถูกแนวเทือกเขาขวางกั้นทั้งหมด)")

with st.expander("📐 ดูสมการฟิสิกส์และตัวแปรที่ใช้ในแบบจำลอง (สำหรับอ้างอิงในรายงาน)"):
    st.markdown(r"""
    1. **Gaussian Plume Dispersion Equation (ระดับพื้นดิน $z=2\text{ m}$):**
       $$C(x, y, z) = \frac{Q}{2\pi u \sigma_y \sigma_z} \exp\left(-\frac{y^2}{2\sigma_y^2}\right) \left[ \exp\left(-\frac{(z - H)^2}{2\sigma_z^2}\right) + \exp\left(-\frac{(z + H)^2}{2\sigma_z^2}\right) \right]$$
    2. **Briggs' Thermal Plume Rise ($\Delta h$):**
       $$\Delta h = \frac{1.6 F^{1/3} x^{2/3}}{u}, \quad F = 8.9 \times \text{FRP}$$
    3. **สัญลักษณ์สีบนแผนที่:**
       * 🔴 **สีแดง:** แหล่งกำเนิดที่ส่งผลกระทบถึงสถานีตรวจวัด
       * 🟣 **สีม่วง:** จุดความร้อนที่อยู่ในทิศต้นลม แต่ถูกแนวเทือกเขาขวางกั้น (Orographic Blocking)
       * ⚪ **สีเทา:** จุดความร้อนนอกแนวกระแสลม
    """)

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
