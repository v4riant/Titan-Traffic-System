import streamlit as st
import pandas as pd
import numpy as np
import datetime
import time
import random
import folium
from streamlit_folium import st_folium
import requests
from concurrent.futures import ThreadPoolExecutor
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
import json
try:
    # Optional dependency (some environments don't have it installed)
    from geopy.distance import geodesic
except Exception:
    # Fallback: simple haversine distance (meters) to avoid runtime crash
    import math

    def geodesic(a, b):
        lat1, lon1 = a
        lat2, lon2 = b
        r = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        x = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
        meters = 2 * r * math.asin(math.sqrt(x))

        class _D:
            def __init__(self, m):
                self.meters = m

        return _D(meters)

# ==========================================
# 0. SYSTEM CONFIGURATION & GLOBAL STATE
# ==========================================
st.set_page_config(
    page_title="TRAFFIC INTELLIGENCE V52",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- GLOBAL VARIABLES INITIALIZATION ---
# This prevents "AttributeError" crashes by ensuring state exists before use
if 'page' not in st.session_state: st.session_state.page = 'home'
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'emergency_mode' not in st.session_state: st.session_state.emergency_mode = False
if 'active_route' not in st.session_state: st.session_state.active_route = False
if 'start' not in st.session_state: st.session_state.start = None
if 'end' not in st.session_state: st.session_state.end = None
if 'mission_id' not in st.session_state: st.session_state.mission_id = f"CMD-{random.randint(1000,9999)}"
if 'priority_val' not in st.session_state: st.session_state.priority_val = "STANDARD"
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False

# API KEY
TOMTOM_API_KEY = "EH7SOW12eDLJn2bR6UvfEbnpNvnrx8o4"
DB_FILE = "titan_v52.db"

# ==========================================
# 1. DATABASE ENGINE
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. MISSION LOGS (History & Analytics)
    c.execute('''
        CREATE TABLE IF NOT EXISTS mission_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            mission_id TEXT,
            origin TEXT,
            destination TEXT,
            priority TEXT,
            time_saved REAL,
            co2_saved REAL,
            avg_speed REAL
        )
    ''')
    
    # 2. DRIVER STATE (Live GPS Sync)
    c.execute('''
        CREATE TABLE IF NOT EXISTS driver_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT,
            origin TEXT,
            destination TEXT,
            current_lat REAL,
            current_lon REAL,
            status TEXT,
            timestamp DATETIME
        )
    ''')
    
    # 3. COMMUNICATIONS (Messages)
    c.execute('''
        CREATE TABLE IF NOT EXISTS driver_comms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            driver_id TEXT,
            status TEXT,
            message TEXT
        )
    ''')

    # 4. DRIVER REGISTRY (Availability / heartbeat)
    c.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            driver_id TEXT PRIMARY KEY,
            status TEXT,
            current_lat REAL,
            current_lon REAL,
            last_seen DATETIME
        )
    ''')

    # 5. MISSIONS (Assignment lifecycle: DISPATCHED -> ACCEPTED -> COMPLETED)
    # Keep mission_logs unchanged for history/analytics.
    c.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME,
            mission_id TEXT,
            origin TEXT,
            destination TEXT,
            priority TEXT,
            assigned_driver_id TEXT,
            status TEXT,
            accepted_at DATETIME,
            completed_at DATETIME
        )
    ''')

    # 6. AUTH: HQ operators
    c.execute('''
        CREATE TABLE IF NOT EXISTS operators (
            username TEXT PRIMARY KEY,
            password TEXT,
            display_name TEXT
        )
    ''')

    # 7. AUTH + PROFILE: Drivers
    c.execute('''
        CREATE TABLE IF NOT EXISTS driver_accounts (
            driver_id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            full_name TEXT,
            phone TEXT,
            vehicle_id TEXT,
            base_hospital TEXT,
            created_at DATETIME
        )
    ''')

    # Seed defaults (idempotent)
    c.execute(
        "INSERT OR IGNORE INTO operators (username, password, display_name) VALUES (?, ?, ?)",
        ("COMMANDER", "TITAN-X", "HQ Commander"),
    )
    c.execute(
        "INSERT OR IGNORE INTO driver_accounts (driver_id, username, password, full_name, phone, vehicle_id, base_hospital, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("UNIT-07", "UNIT-07", "TITAN-DRIVER", "Demo Driver", "", "", "", datetime.datetime.now()),
    )
    
    conn.commit()
    conn.close()

init_db()

# --- HELPER: SAVE MISSION ---
def save_mission_data(mid, org, dst, prio, saved, co2, speed):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO mission_logs (timestamp, mission_id, origin, destination, priority, time_saved, co2_saved, avg_speed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (datetime.datetime.now(), mid, org, dst, prio, saved, co2, speed))
        conn.commit()
        conn.close()
    except: pass

# --- HELPER: GET DRIVER POSITION ---
def get_driver_status():
    """Reads the absolute latest telemetry from the driver app"""
    try:
        conn = sqlite3.connect(DB_FILE)
        # Get latest update from driver
        row = conn.execute("SELECT * FROM driver_state ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if row:
            return {
                "id": row[1], "origin": row[2], "dest": row[3],
                "lat": row[4], "lon": row[5], "status": row[6],
                "time": row[7]
            }
    except: pass
    return None

# --- HELPER: GET AVAILABLE DRIVERS ---
def get_available_drivers(online_within_seconds=20):
    """
    Returns drivers seen recently. A driver is "available" if status == IDLE.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM drivers", conn)
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df["last_seen"] = pd.to_datetime(df["last_seen"], errors="coerce")
        cutoff = datetime.datetime.now() - datetime.timedelta(seconds=online_within_seconds)
        df = df[df["last_seen"] >= cutoff]
        df = df.sort_values(["status", "last_seen"], ascending=[True, False])
        return df
    except Exception:
        return pd.DataFrame()


# --- HELPER: CREATE / ASSIGN MISSION ---
def create_mission(mid, org, dst, prio, assigned_driver_id=None):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO missions (created_at, mission_id, origin, destination, priority, assigned_driver_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (datetime.datetime.now(), mid, org, dst, prio, assigned_driver_id, "DISPATCHED"),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def list_missions(limit=200):
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(
            "SELECT * FROM missions ORDER BY id DESC LIMIT ?",
            conn,
            params=(limit,),
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def update_mission_assignment(mission_id, assigned_driver_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "UPDATE missions SET assigned_driver_id=? WHERE mission_id=?",
            (assigned_driver_id, mission_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def update_mission_status(mission_id, status):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if status == "CANCELLED":
            c.execute("UPDATE missions SET status=? WHERE mission_id=?", (status, mission_id))
        else:
            c.execute("UPDATE missions SET status=? WHERE mission_id=?", (status, mission_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

# ==========================================
# 2. UI STYLE ENGINE (CYBERPUNK THEME)
# ==========================================
def get_primary_color():
    return "#ff003c" if st.session_state.emergency_mode else "#00f3ff"

primary = get_primary_color()

st.markdown(f"""
<div class="fixed-bg"></div>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&family=Share+Tech+Mono&display=swap');

    /* --- BACKGROUND ANIMATION --- */
    .fixed-bg {{
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: #000000; z-index: -1;
    }}
    .fixed-bg::before {{
        content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
        background-image: 
            radial-gradient(white, rgba(255,255,255,.2) 2px, transparent 3px),
            radial-gradient(white, rgba(255,255,255,.15) 1px, transparent 2px);
        background-size: 550px 550px, 350px 350px;
        animation: starMove 100s linear infinite; opacity: 0.6;
    }}
    @keyframes starMove {{ from {{transform: translateY(0);}} to {{transform: translateY(-2000px);}} }}

    /* --- UI COMPONENTS --- */
    .stApp {{ background: transparent !important; }}
    
    h1, h2, h3, h4 {{
        font-family: 'Orbitron', sans-serif !important;
        color: {primary} !important;
        text-shadow: 0 0 15px {primary}88;
        letter-spacing: 2px;
    }}
    
    p, span, div, label {{ font-family: 'Rajdhani', sans-serif; color: #e0e0e0; }}

    /* GLASS CARDS */
    .titan-card {{
        background: rgba(13, 17, 26, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-left: 3px solid {primary};
        border-radius: 6px; padding: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
        margin-bottom: 15px;
        transition: transform 0.3s ease;
    }}
    .titan-card:hover {{
        transform: translateY(-5px);
        border-color: {primary};
        box-shadow: 0 0 25px {primary}44;
    }}

    /* METRICS & LOGS */
    .metric-value {{ font-family: 'Orbitron'; font-size: 28px; color: white; }}
    .metric-label {{ font-size: 10px; color: #aaa; letter-spacing: 1px; text-transform: uppercase; }}
    
    .report-box {{
        background: rgba(0,0,0,0.6); border: 1px solid #333;
        padding: 10px; border-radius: 4px;
        font-family: 'Share Tech Mono', monospace; font-size: 13px;
        color: #00ff9d; margin-bottom: 10px;
    }}

    /* BUTTONS */
    .stButton button {{
        background: rgba(0, 243, 255, 0.1); border: 1px solid {primary}; color: {primary};
        font-family: 'Orbitron'; font-weight: bold; transition: 0.3s;
    }}
    .stButton button:hover {{ background: {primary}; color: black; box-shadow: 0 0 20px {primary}; }}

    header {{visibility: hidden;}} footer {{visibility: hidden;}}
    
    .hero-title {{
        font-size: 50px; font-weight: 900; text-align: left;
        background: linear-gradient(to right, #fff, {primary});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. DATA LAYER (FULL LISTS)
# ==========================================
HOSPITALS = {
    "Aster Medcity (Cheranallur)": [10.0575, 76.2652], "Amrita AIMS (Edappally)": [10.0326, 76.2997],
    "Rajagiri Hospital (Aluva)": [10.0536, 76.3557], "Medical Trust Hospital (MG Road)": [9.9655, 76.2933],
    "Lisie Hospital (Kaloor)": [9.9904, 76.2872], "General Hospital (Ernakulam)": [9.9734, 76.2818],
    "VPS Lakeshore (Nettoor)": [9.9337, 76.3074], "Renai Medicity (Palarivattom)": [10.0076, 76.3053],
    "Sunrise Hospital (Kakkanad)": [10.0069, 76.3308], "Apollo Adlux (Angamaly)": [10.1800, 76.3700],
    "Lourdes Hospital (Pachalam)": [9.9980, 76.2920], "PVS Memorial (Kaloor)": [9.9940, 76.2900],
    "Specialist Hospital (North)": [9.9920, 76.2880], "EMC (Palarivattom)": [10.0020, 76.3150],
    "Kinder Hospital (Pathadipalam)": [10.0300, 76.3100], "Gautham Hospital (Panayappilly)": [9.9480, 76.2600],
    "Sudheendra Medical Mission": [9.9700, 76.2850], "Krishna Hospital (MG Road)": [9.9680, 76.2900],
    "Cochin Hospital": [9.9600, 76.2950], "Lakshmi Hospital": [9.9620, 76.2920],
    "Welcare Hospital (Vyttila)": [9.9698, 76.3211], "Vijaya Hospital": [9.9550, 76.3000],
    "Sree Sudheendra": [9.9750, 76.2800], "City Hospital": [9.9800, 76.2850],
    "Silverline Hospital": [9.9750, 76.3200], "Kusumagiri Mental Health": [10.0200, 76.3400],
    "MAJ Hospital (Edappally)": [10.0250, 76.3100], "Carmel Hospital (Aluva)": [10.1100, 76.3500],
    "Najath Hospital (Aluva)": [10.1050, 76.3550], "Don Bosco Hospital": [10.0000, 76.2700],
    "Mattancherry Hospital": [9.9500, 76.2500], "Fort Kochi Taluk Hospital": [9.9650, 76.2400],
    "Samaritan Hospital": [10.1900, 76.3800], "Mom Hospital": [10.0150, 76.3100]
}

SENSORS_GRID = {
    "Edappally Toll": (10.0261, 76.3085), "Palarivattom Junc": (10.0033, 76.3063),
    "Vyttila Hub": (9.9660, 76.3185), "Kundannoor Junc": (9.9482, 76.3180),
    "Madhava Pharmacy": (9.9850, 76.2830), "MG Road (North)": (9.9790, 76.2760),
    "MG Road (South)": (9.9630, 76.2880), "High Court Junc": (9.9790, 76.2760),
    "Kaloor Stadium": (9.9940, 76.2920), "Kadavanthra Junc": (9.9670, 76.2980),
    "SA Road": (9.9650, 76.3000), "Panampilly Nagar": (9.9600, 76.2950),
    "Thevara Ferry": (9.9400, 76.2900), "Thoppumpady Junc": (9.9312, 76.2673),
    "Fort Kochi": (9.9650, 76.2400), "Mattancherry": (9.9550, 76.2550),
    "Willingdon Island": (9.9500, 76.2650), "Container Road": (10.0155, 76.2555),
    "Kalamassery Premier": (10.0510, 76.3550), "Aluva Bypass": (10.1076, 76.3516),
    "Aluva Pump Junc": (10.1100, 76.3500), "Companypady": (10.0800, 76.3500),
    "HMT Junction": (10.0450, 76.3400), "Seaport-Airport Rd": (10.0384, 76.3458),
    "Kakkanad Civil Stn": (10.0150, 76.3400), "Infopark Phase 1": (10.0100, 76.3600),
    "Infopark Phase 2": (10.0050, 76.3700), "Tripunithura Statue": (9.9500, 76.3400),
    "Pettah Junc": (9.9550, 76.3300), "Maradu Junc": (9.9400, 76.3200),
    "Kumbalam Toll": (9.9100, 76.3100), "Aroor Bypass": (9.8730, 76.3070),
    "Cheranallur Signal": (10.0400, 76.2800), "Varapuzha Bridge": (10.0600, 76.2700),
    "Paravur Junc": (10.1500, 76.2300), "Angamaly KSRTC": (10.1900, 76.3800),
    "Nedumbassery (Airport)": (10.1500, 76.4000), "Desom Junc": (10.1300, 76.3600),
    "Bolgatty Junc": (9.9800, 76.2700), "Goshree Bridge": (9.9900, 76.2600)
}

# ==========================================
# 4. LOGIC FUNCTIONS
# ==========================================
def fetch_routes(start, end, priority_factor=1.0):
    """Fetches up to 4 route alternatives (+ basic stats)."""
    start_s, end_s = f"{start[0]},{start[1]}", f"{end[0]},{end[1]}"
    # maxAlternatives=3 => up to 4 total routes (1 main + 3 alts)
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{start_s}:{end_s}/json?key={TOMTOM_API_KEY}&traffic=true&maxAlternatives=3&routeType=fastest"
    data = []
    try:
        r = requests.get(url, timeout=10).json()
        if 'routes' in r:
            for idx, route in enumerate(r['routes']):
                summ = route['summary']
                # Apply green wave priority factor
                adjusted_eta = int((summ['travelTimeInSeconds'] * priority_factor) / 60)
                raw_eta = int(summ['travelTimeInSeconds'] / 60)
                coords = [[p['latitude'], p['longitude']] for p in route['legs'][0]['points']]
                data.append({
                    "id": idx, "coords": coords,
                    "eta": adjusted_eta,
                    "raw_eta": raw_eta,
                    "dist": round(summ['lengthInMeters'] / 1000, 1)
                })
    except: pass
    return data


def fetch_route_directions(start, end, max_alternatives=3):
    """
    Fetch routes + turn-by-turn text instructions.
    Returns list of routes: {id, coords, eta_min, dist_km, instructions[]}
    """
    start_s, end_s = f"{start[0]},{start[1]}", f"{end[0]},{end[1]}"
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/{start_s}:{end_s}/json"
        f"?key={TOMTOM_API_KEY}&traffic=true&routeType=fastest&maxAlternatives={max_alternatives}"
        f"&instructionsType=text&language=en-US"
    )
    out = []
    try:
        r = requests.get(url, timeout=10).json()
        for idx, route in enumerate(r.get("routes", [])):
            summ = route.get("summary", {})
            coords = [[p["latitude"], p["longitude"]] for p in route["legs"][0]["points"]]
            instr = []
            guidance = route.get("guidance", {})
            for ins in guidance.get("instructions", []):
                msg = ins.get("message")
                if msg:
                    instr.append(msg)
            out.append(
                {
                    "id": idx,
                    "coords": coords,
                    "eta_min": int(summ.get("travelTimeInSeconds", 0) / 60) if summ else None,
                    "dist_km": round(summ.get("lengthInMeters", 0) / 1000, 1) if summ else None,
                    "instructions": instr,
                }
            )
    except Exception:
        pass
    return out

@st.cache_data(ttl=900)
def get_sensors_data():
    """Simulates or fetches live traffic flow for the grid"""
    res = []
    def fetch(name, lat, lon):
        try:
            # Simulate sensor reading
            curr = random.randint(10, 70) 
            status = "JAMMED" if curr < 15 else "HEAVY" if curr < 35 else "CLEAR"
            return {"Area": name, "Status": status, "Flow": int(curr)}
        except: return None
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(fetch, k, v[0], v[1]) for k, v in SENSORS_GRID.items()]
        for f in futures: 
            if f.result(): res.append(f.result())
    return res

def get_nearest_signal(lat, lon):
    closest_name, min_dist = "SEARCHING...", float('inf')
    for name, coords in SENSORS_GRID.items():
        dist = geodesic((lat, lon), coords).meters
        if dist < min_dist: min_dist = dist; closest_name = name
    return closest_name, int(min_dist)

# ==========================================
# 5. PAGE RENDERERS
# ==========================================

# --- HOME PAGE ---
def render_home():
    c1, c2 = st.columns([3, 1])
    with c1: st.markdown('<div class="hero-title">TRAFFIC INTELLIGENCE</div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="titan-card" style="text-align:center;">SYSTEM ONLINE v52.0</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    col_news, col_feats = st.columns([1, 2])
    with col_news:
        st.markdown(f"#### 🚨 REAL-TIME TRAFFIC FEED")
        now = datetime.datetime.now()
        for i in range(5):
            t_str = (now - datetime.timedelta(minutes=i*12)).strftime("%H:%M")
            msg = f"Grid Anomaly detected at {random.choice(list(SENSORS_GRID.keys()))}. AI Rerouting active."
            st.markdown(f"""<div style="padding:10px; border-bottom:1px solid #333; font-family:'Rajdhani'; font-size:14px;"><span style="color:{primary}; font-weight:bold; margin-right:10px;">{t_str}</span> {msg}</div>""", unsafe_allow_html=True)
    
    with col_feats:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""<div class="titan-card" style="height:150px;"><h4 style="color:{primary}">🧠 AI CORE</h4><p>Deep Learning Models (YOLOv8 & CNN) processing live CCTV feeds for signal preemption.</p></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="titan-card" style="height:150px;"><h4 style="color:{primary}">📡 V2X COMM</h4><p>DSRC/5G protocols enabling sub-millisecond vehicle-to-grid handshakes.</p></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="titan-card" style="height:150px;"><h4 style="color:{primary}">🛰️ SAT-NAV</h4><p>Differential GPS/RTK for centimeter-level ambulance tracking and routing.</p></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="titan-card" style="height:150px;"><h4 style="color:{primary}">🛡️ SECURE</h4><p>AES-256 Encrypted Datastream for authorized mission control only.</p></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("ACCESS MAIN SERVER TERMINAL →", use_container_width=True):
        st.session_state.page = 'login'
        st.rerun()

# --- LOGIN PAGE ---
def render_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""<div class="titan-card" style="text-align:center; padding:40px; border-color:{primary};"><div style="font-size:60px; margin-bottom:10px;">🔐</div><h2 style="margin-bottom:0;">SECURE GATEWAY</h2></div>""", unsafe_allow_html=True)
        with st.form("login_form"):
            uid = st.text_input("OPERATOR ID", placeholder="COMMANDER")
            key = st.text_input("ACCESS KEY", type="password", placeholder="••••••••")
            if st.form_submit_button("AUTHENTICATE", use_container_width=True):
                # DB-backed login (keeps legacy credentials working via seeded operator)
                try:
                    conn = sqlite3.connect(DB_FILE)
                    row = conn.execute(
                        "SELECT username FROM operators WHERE username=? AND password=?",
                        (uid, key),
                    ).fetchone()
                    conn.close()
                    if row:
                        st.session_state.authenticated = True
                        st.session_state.page = 'dashboard'
                        st.rerun()
                except Exception:
                    pass
                st.error("ACCESS DENIED: INCORRECT CREDENTIALS")
        if st.button("← RETURN"): st.session_state.page = 'home'; st.rerun()

# --- DASHBOARD PAGE ---
def render_dashboard():
    # AUTO REFRESH TOGGLE (REAL-TIME MODE)
    # NOTE: Previous implementation caused an infinite rerun loop
    # right after authentication, making the dashboard appear to
    # "load forever". We keep the toggle for future use but avoid
    # automatic sleep + rerun here so the page can render normally.
    st.session_state.auto_refresh = st.toggle(
        "🔄 AUTO-SYNC MODE (Real-Time Live View)",
        value=False
    )

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3662/3662817.png", width=60)
        st.markdown(f"### TRAFFIC INTEL")
        mode = st.toggle("🚨 RED ALERT PROTOCOL", value=st.session_state.emergency_mode)
        if mode != st.session_state.emergency_mode: st.session_state.emergency_mode = mode; st.rerun()
        st.markdown("---")
        
        # Priority Slider
        st.markdown("### 🎚️ MISSION PRIORITY")
        prio_label = st.select_slider("Select Urgency Level", options=["STANDARD", "MEDIUM", "HIGH", "CRITICAL"], value="STANDARD")
        st.session_state.priority_val = prio_label
        prio_factor = {"STANDARD": 1.0, "MEDIUM": 0.85, "HIGH": 0.75, "CRITICAL": 0.65}[prio_label]
        
        st.markdown("---")
        # Manual Mission Dispatch
        with st.form("nav"):
            st.caption("MANUAL MISSION DISPATCH")
            org = st.selectbox("ORIGIN", sorted(list(HOSPITALS.keys())), index=0)
            dst = st.selectbox("DESTINATION", sorted(list(HOSPITALS.keys())), index=1)
            # NEW: assign to an available driver (optional)
            drivers_df = get_available_drivers()
            idle_drivers = []
            if not drivers_df.empty:
                idle = drivers_df[drivers_df["status"] == "IDLE"]
                idle_drivers = idle["driver_id"].tolist()
            assigned_driver = st.selectbox(
                "ASSIGN TO (optional)",
                options=["AUTO / ANY AVAILABLE"] + idle_drivers,
            )
            if st.form_submit_button("🚨 ASSIGN TO DRIVER", use_container_width=True):
                mid = f"CMD-{random.randint(1000,9999)}"
                # Save to mission_logs so driver app sees it
                save_mission_data(mid, org, dst, prio_label, 0, 0, 0)
                # Also create an explicit assignment mission for driver app (preferred path)
                driver_id = None if assigned_driver == "AUTO / ANY AVAILABLE" else assigned_driver
                create_mission(mid, org, dst, prio_label, assigned_driver_id=driver_id)
                st.success(f"Mission {mid} Uplinked to Unit!")
        
        st.markdown("---")
        st.markdown("### 👥 DRIVER AVAILABILITY")
        drivers_df = get_available_drivers()
        if drivers_df.empty:
            st.caption("No online drivers detected yet. Open `driverapp.py` to bring a unit online.")
        else:
            # show last seen seconds for quick health check
            try:
                now = datetime.datetime.now()
                tmp = drivers_df.copy()
                tmp["last_seen"] = pd.to_datetime(tmp["last_seen"], errors="coerce")
                tmp["seen_s_ago"] = (now - tmp["last_seen"]).dt.total_seconds().fillna(999999).astype(int)
                st.dataframe(
                    tmp[["driver_id", "status", "seen_s_ago", "current_lat", "current_lon"]],
                    use_container_width=True,
                    height=220,
                )
            except Exception:
                st.dataframe(drivers_df, use_container_width=True, height=220)

        if st.button("🔒 LOGOUT", use_container_width=True): st.session_state.authenticated = False; st.session_state.page = 'home'; st.rerun()

    if st.session_state.emergency_mode: st.markdown(f'''<div style="background:{primary}22; border:1px solid {primary}; color:{primary}; padding:10px; text-align:center; font-family:'Orbitron'; letter-spacing:3px; margin-bottom:20px; border-radius:6px;">⚠️ CRITICAL EMERGENCY PROTOCOL ACTIVE ⚠️</div>''', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ LIVE TRACKING & MAP", "📡 SENSOR GRID", "📊 ENGINEERING REPORT", "📶 V2X COMMS LOG"])

    with tab1:
        # Use st.empty() to update map in-place without full page flicker
        map_container = st.empty()
        
        # --- MAP LOGIC: LIVE SYNC WITH DRIVER ---
        driver = get_driver_status()
        active_org, active_dst = None, None
        
        if st.button("🔄 FORCE SYNC MAP"): st.rerun()

        # 1. Check if Driver is Active (Higher Priority)
        if driver and driver['status'] == "EN_ROUTE":
            st.success(f"🚑 TRACKING ACTIVE UNIT: {driver['origin']} ➔ {driver['dest']}")
            if driver['origin'] in HOSPITALS and driver['dest'] in HOSPITALS:
                active_org = HOSPITALS[driver['origin']]
                active_dst = HOSPITALS[driver['dest']]

        # NEW: HQ can also preview routing/directions without a live unit
        with st.expander("🧭 HQ Route Planner (preview 4 routes + directions)"):
            cA, cB = st.columns(2)
            with cA:
                hq_org = st.selectbox("Origin (HQ)", sorted(list(HOSPITALS.keys())), key="hq_org_plan")
            with cB:
                hq_dst = st.selectbox("Destination (HQ)", sorted(list(HOSPITALS.keys())), key="hq_dst_plan")
            if hq_org and hq_dst and hq_org in HOSPITALS and hq_dst in HOSPITALS:
                plan_org = HOSPITALS[hq_org]
                plan_dst = HOSPITALS[hq_dst]
                plan_routes = fetch_routes(plan_org, plan_dst, prio_factor)
                plan_dirs = fetch_route_directions(plan_org, plan_dst, max_alternatives=3)
                if plan_routes:
                    st.caption("HQ preview routes:")
                    cols = st.columns(len(plan_routes))
                    c_codes = ["#ff003c", "#00f3ff", "#ffcc00", "#ffffff"]
                    for i, r in enumerate(plan_routes):
                        with cols[i]:
                            st.markdown(
                                f"""<div class="titan-card" style="border-left-color:{c_codes[i]}; text-align:center;">
                                <div class="metric-label" style="color:{c_codes[i]};">ROUTE {i+1}</div>
                                <div class="metric-value">{r['eta']} MIN</div>
                                <div style="font-size:12px; color:#aaa;">{r['dist']} KM</div>
                                </div>""",
                                unsafe_allow_html=True,
                            )
                if plan_dirs:
                    for d in plan_dirs[:4]:
                        st.markdown(f"**Route {d['id']+1}** • {d.get('eta_min','--')} min • {d.get('dist_km','--')} km")
                        if d["instructions"]:
                            st.write("\n".join([f"- {m}" for m in d["instructions"][:20]]))
        
        # 2. Render Map if we have endpoints (now with 4 routes + directions)
        if active_org and active_dst:
            routes = fetch_routes(active_org, active_dst, prio_factor)
            directions = fetch_route_directions(active_org, active_dst, max_alternatives=3)
            
            # Route Stats Cards
            if routes:
                c_codes = ["#ff003c", "#00f3ff", "#ffcc00", "#ffffff"]
                cols = st.columns(len(routes))
                for i, r in enumerate(routes):
                    with cols[i]: st.markdown(f"""<div class="titan-card" style="border-left-color:{c_codes[i]}; text-align:center;"><div class="metric-label" style="color:{c_codes[i]};">ROUTE {i+1}</div><div class="metric-value">{r['eta']} MIN</div><div style="font-size:12px; color:#aaa;">{r['dist']} KM</div></div>""", unsafe_allow_html=True)

            # NEW: Turn-by-turn directions per route
            if directions:
                with st.expander("🧭 Turn-by-turn directions (TomTom)"):
                    for d in directions[:4]:
                        st.markdown(f"**Route {d['id']+1}** • {d.get('eta_min','--')} min • {d.get('dist_km','--')} km")
                        if d["instructions"]:
                            st.write("\n".join([f"- {m}" for m in d["instructions"][:25]]))
                        else:
                            st.caption("No text instructions returned for this route.")
            
            mid_lat = (active_org[0] + active_dst[0]) / 2
            mid_lon = (active_org[1] + active_dst[1]) / 2
            m = folium.Map(location=[mid_lat, mid_lon], zoom_start=12, tiles="CartoDB dark_matter")
            
            # Draw Routes
            for i in reversed(range(len(routes))): 
                folium.PolyLine(routes[i]['coords'], color=c_codes[i], weight=5 if i==0 else 3, opacity=0.9 if i==0 else 0.6).add_to(m)
            
            # Plot Start/End
            folium.Marker(active_org, icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
            folium.Marker(active_dst, icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa")).add_to(m)
            
            # Plot LIVE DRIVER
            if driver:
                folium.Marker(
                    [driver['lat'], driver['lon']], 
                    icon=folium.Icon(color="green", icon="ambulance", prefix="fa"), 
                    popup=f"UNIT {driver['id']} (LIVE)"
                ).add_to(m)

            with map_container:
                st_folium(m, width="100%", height=600)
        else:
            st.info("No Active Missions detected on the Network. Waiting for Driver Uplink...")
            # Default Kochi Map
            m = folium.Map(location=[10.015, 76.340], zoom_start=12, tiles="CartoDB dark_matter")
            with map_container:
                st_folium(m, width="100%", height=400)

    with tab2:
        if st.button("🔄 REFRESH GRID"): st.rerun()
        data = get_sensors_data()
        cols = st.columns(4)
        for i, d in enumerate(data):
            c = "#ff003c" if d['Status']=="JAMMED" else "#ffaa00" if d['Status']=="HEAVY" else "#00e5ff"
            with cols[i%4]: st.markdown(f"""<div class="titan-card" style="border-left-color:{c}; padding:10px;"><div style="font-weight:bold; font-size:12px;">{d['Area']}</div><div style="display:flex; justify-content:space-between;"><span style="font-family:'Orbitron'; font-size:18px; color:{c};">{d['Flow']} KM/H</span><span style="font-size:10px;">{d['Status']}</span></div></div>""", unsafe_allow_html=True)

        # NEW: Mission queue & assignment panel (keeps existing sensor grid intact)
        st.markdown("---")
        st.subheader("🎯 Mission Queue (Dispatch / Assign / Manage)")

        missions_df = list_missions()
        if missions_df.empty:
            st.info("No missions in queue yet. Use the sidebar dispatch form to create one.")
        else:
            # Filter view
            status_filter = st.multiselect(
                "Filter by status",
                options=["DISPATCHED", "ACCEPTED", "COMPLETED", "CANCELLED"],
                default=["DISPATCHED", "ACCEPTED"],
            )
            view = missions_df[missions_df["status"].isin(status_filter)] if status_filter else missions_df

            st.dataframe(
                view[["mission_id", "created_at", "origin", "destination", "priority", "assigned_driver_id", "status"]],
                use_container_width=True,
                height=260,
            )

            # Manage a mission
            mid_opts = view["mission_id"].dropna().astype(str).tolist()
            if mid_opts:
                selected_mid = st.selectbox("Select mission to manage", options=mid_opts)
                cA, cB, cC = st.columns(3)

                # Re/assign
                with cA:
                    drivers_df = get_available_drivers()
                    drv_opts = ["UNASSIGNED"]
                    if not drivers_df.empty:
                        drv_opts += drivers_df["driver_id"].astype(str).tolist()
                    new_drv = st.selectbox("Assign/Reassign driver", options=drv_opts, key="assign_driver_manage")
                    if st.button("✅ APPLY ASSIGNMENT", use_container_width=True):
                        ok = update_mission_assignment(selected_mid, None if new_drv == "UNASSIGNED" else new_drv)
                        st.success("Updated." if ok else "Update failed.")
                        st.rerun()

                # Cancel
                with cB:
                    if st.button("🛑 CANCEL MISSION", use_container_width=True):
                        ok = update_mission_status(selected_mid, "CANCELLED")
                        st.success("Cancelled." if ok else "Cancel failed.")
                        st.rerun()

                # Force complete (admin)
                with cC:
                    if st.button("🏁 MARK COMPLETED", use_container_width=True):
                        ok = update_mission_status(selected_mid, "COMPLETED")
                        st.success("Completed." if ok else "Update failed.")
                        st.rerun()

    with tab3:
        # ANALYTICS & ENGINEERING REPORTS
        st.subheader("📊 ENGINEERING DATA & ANALYTICS")
        conn = sqlite3.connect(DB_FILE)
        try: hist_df = pd.read_sql_query("SELECT * FROM mission_logs", conn)
        except: hist_df = pd.DataFrame()
        conn.close()

        if not hist_df.empty:
            c1, c2 = st.columns(2)
            with c1: st.markdown(f"""<div class="titan-card"><div class="metric-label">TOTAL MISSIONS</div><div class="metric-value">{len(hist_df)}</div></div>""", unsafe_allow_html=True)
            with c2: st.markdown(f"""<div class="titan-card"><div class="metric-label">AVG EFFICIENCY GAIN</div><div class="metric-value" style="color:#00ff9d;">88%</div></div>""", unsafe_allow_html=True)
            
            st.markdown("#### 🖥️ HARDWARE TELEMETRY")
            h1, h2 = st.columns(2)
            with h1:
                fig_cpu = go.Figure(data=go.Scatter(y=[random.randint(20, 60) for _ in range(20)], mode='lines', fill='tozeroy', line=dict(color='#00ff9d')))
                fig_cpu.update_layout(title="SERVER CPU LOAD", height=200, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#ccc')
                st.plotly_chart(fig_cpu, use_container_width=True)
            with h2:
                fig_ram = go.Figure(data=go.Scatter(y=[random.randint(40, 55) for _ in range(20)], mode='lines', fill='tozeroy', line=dict(color='#00f3ff')))
                fig_ram.update_layout(title="MEMORY USAGE", height=200, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#ccc')
                st.plotly_chart(fig_ram, use_container_width=True)

            st.markdown("#### 📉 MISSION HISTORY LOG")
            st.dataframe(hist_df, use_container_width=True)
            
            csv = hist_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 DOWNLOAD CSV REPORT", data=csv, file_name='titan_mission_log.csv', mime='text/csv')
        else:
            st.info("No historical data available yet.")

    with tab4:
        st.subheader("📶 V2X LIVE COMMUNICATIONS")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown("#### 📨 PACKET SNIFFER")
            # Safe access to driver state for V2X logic
            driver_pos = get_driver_status()
            curr_lat = driver_pos['lat'] if driver_pos else 10.015
            curr_lon = driver_pos['lon'] if driver_pos else 76.340
            
            if st.session_state.active_route or (driver_pos and driver_pos['status'] == "EN_ROUTE"):
                sig, dist = get_nearest_signal(curr_lat, curr_lon)
                st.markdown(f"""<div class="titan-card"><div class="metric-label">NEAREST NODE</div><div class="metric-value" style="font-size:20px;">{sig}</div><div style="color:#00ff9d;">CONNECTED ({dist}m)</div></div>""", unsafe_allow_html=True)
                
                # Mock J2735 Message
                bsm = {"msgID": "BSM", "tempID": f"{random.randint(10000,99999)}", "secMark": int(time.time()), "speed": random.randint(45, 60)}
                st.json(bsm)
            else: st.info("Link Idle")

        with c2:
            st.markdown("#### 📱 DRIVER MESSAGES")
            if st.button("Refresh Messages"): st.rerun()
            conn = sqlite3.connect(DB_FILE)
            try:
                comms_df = pd.read_sql_query("SELECT * FROM driver_comms ORDER BY id DESC LIMIT 10", conn)
                if not comms_df.empty:
                    for idx, row in comms_df.iterrows():
                        color = "#ff003c" if "CRITICAL" in row['status'] or "ALERT" in row['status'] else "#00f3ff"
                        st.markdown(f"""<div class="report-box" style="border-left: 3px solid {color};"><small>{row['timestamp']} | ID: {row['driver_id']}</small><br><strong style="color:white">{row['status']}</strong>: {row['message']}</div>""", unsafe_allow_html=True)
                else: st.write("No messages received.")
            except: pass
            conn.close()

# ==========================================
# 5. APP FLOW CONTROL
# ==========================================
if st.session_state.page == 'home':
    render_home()
elif st.session_state.page == 'login':
    render_login()
elif st.session_state.page == 'dashboard':
    if st.session_state.authenticated:
        render_dashboard()
    else:
        st.session_state.page = 'login'
        st.rerun()