import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import datetime
import time
import random
import requests
try:
    from geopy.distance import geodesic
except Exception:
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
                self.km = m / 1000.0

        return _D(meters)

# ==========================================
# 0. MOBILE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="TITAN DRIVER OS",
    page_icon="🚑",
    layout="centered", # Simulates Mobile Screen
    initial_sidebar_state="collapsed"
)

# SHARED DATABASE (MUST MATCH SERVER)
DB_FILE = "titan_v52.db"
TOMTOM_API_KEY = "EH7SOW12eDLJn2bR6UvfEbnpNvnrx8o4"

# FULL HOSPITAL LIST
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

# ==========================================
# 1. ANDROID UI STYLING
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500&display=swap');
    
    .stApp { background-color: #000; color: #fff; }
    
    /* HEADER */
    .mobile-header {
        background: #111; padding: 15px; border-bottom: 3px solid #00f3ff;
        border-radius: 0 0 15px 15px; display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 20px;
    }
    
    /* SPEEDOMETER */
    .speed-circle {
        width: 160px; height: 160px; border-radius: 50%;
        border: 8px solid #333; border-top: 8px solid #00f3ff;
        margin: 0 auto; display: flex; flex-direction: column; justify-content: center; align-items: center;
        background: radial-gradient(circle, #222, #000);
        box-shadow: 0 0 25px rgba(0, 243, 255, 0.3);
    }
    .speed-val { font-family: 'Orbitron'; font-size: 48px; color: #fff; line-height: 1; text-shadow: 0 0 10px #00f3ff; }
    .speed-unit { font-family: 'Rajdhani'; font-size: 14px; color: #888; }
    
    /* WIDGETS */
    .widget-box { 
        background: #1a1a1a; border-radius: 10px; padding: 10px; 
        text-align: center; border: 1px solid #333;
    }
    .w-title { color: #888; font-size: 10px; letter-spacing: 1px; }
    .w-val { color: #00ff9d; font-size: 18px; font-family: 'Orbitron'; }
    
    /* BUTTONS */
    .stButton > button { 
        width: 100%; height: 60px; border-radius: 12px; 
        font-family: 'Orbitron'; font-size: 16px; background: #222; color: white; border: 1px solid #444; 
    }
    .stButton > button:hover { background: #333; color: #00f3ff; border-color: #00f3ff; }
    
    .accept-btn button { background: #00ff9d !important; color: black !important; font-weight: bold !important; border: none !important; }
    .end-btn button { background: #ff003c !important; color: white !important; border: none !important; }
    
    /* TABS */
    button[data-baseweb="tab"] { font-family: 'Rajdhani'; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LOGIC ENGINE
# ==========================================
# Session State
if 'driver_id' not in st.session_state: st.session_state.driver_id = "UNIT-07"
if 'gps_lat' not in st.session_state: st.session_state.gps_lat = 10.0150
if 'gps_lon' not in st.session_state: st.session_state.gps_lon = 76.3400
if 'status' not in st.session_state: st.session_state.status = "IDLE"
if 'active_org' not in st.session_state: st.session_state.active_org = None
if 'active_dst' not in st.session_state: st.session_state.active_dst = None
if 'shift_start' not in st.session_state: st.session_state.shift_start = time.time()

# --- NEW: mission lifecycle state (DB-backed) ---
if 'active_mission_id' not in st.session_state: st.session_state.active_mission_id = None
if 'driver_authenticated' not in st.session_state: st.session_state.driver_authenticated = False
if 'driver_username' not in st.session_state: st.session_state.driver_username = ""


def init_db_extensions():
    """Creates extra tables if server hasn't yet."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                driver_id TEXT PRIMARY KEY,
                status TEXT,
                current_lat REAL,
                current_lon REAL,
                last_seen DATETIME
            )
        ''')
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
        # Seed demo driver (idempotent)
        c.execute(
            "INSERT OR IGNORE INTO driver_accounts (driver_id, username, password, full_name, phone, vehicle_id, base_hospital, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("UNIT-07", "UNIT-07", "TITAN-DRIVER", "Demo Driver", "", "", "", datetime.datetime.now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

init_db_extensions()

def driver_login_screen():
    st.markdown("## 🔐 Driver Login")
    with st.form("driver_login"):
        u = st.text_input("Username", value=st.session_state.driver_username or "UNIT-07")
        p = st.text_input("Password", type="password", value="")
        if st.form_submit_button("LOGIN", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_FILE)
                row = conn.execute(
                    "SELECT driver_id, full_name FROM driver_accounts WHERE username=? AND password=?",
                    (u, p),
                ).fetchone()
                conn.close()
                if row:
                    st.session_state.driver_authenticated = True
                    st.session_state.driver_id = row[0]
                    st.session_state.driver_username = u
                    st.rerun()
            except Exception:
                pass
            st.error("Invalid username or password")

    st.caption("Default demo login: username `UNIT-07`, password `TITAN-DRIVER`")


def heartbeat():
    """Driver heartbeat so HQ can see availability."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO drivers (driver_id, status, current_lat, current_lon, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(driver_id) DO UPDATE SET
              status=excluded.status,
              current_lat=excluded.current_lat,
              current_lon=excluded.current_lon,
              last_seen=excluded.last_seen
            """,
            (st.session_state.driver_id, st.session_state.status, st.session_state.gps_lat, st.session_state.gps_lon, datetime.datetime.now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def update_server(org, dst, stat):
    """Pushes live state to server DB"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Update Driver State Table
        c.execute("INSERT INTO driver_state (driver_id, origin, destination, current_lat, current_lon, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (st.session_state.driver_id, org, dst, st.session_state.gps_lat, st.session_state.gps_lon, stat, datetime.datetime.now()))
        conn.commit()
        conn.close()
    except: pass

def send_msg(stat, msg):
    """Sends logs to server"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO driver_comms (timestamp, driver_id, status, message) VALUES (?, ?, ?, ?)",
                  (datetime.datetime.now(), st.session_state.driver_id, stat, msg))
        conn.commit()
        conn.close()
        st.toast(f"Status Updated: {stat}", icon="✅")
    except: pass

def check_orders():
    """
    Checks for new server missions.
    Prefer explicit mission assignment via missions table,
    but keep legacy mission_logs polling for backward compatibility.
    """
    # 1) Prefer missions assigned to this driver (or unassigned) and DISPATCHED
    try:
        conn = sqlite3.connect(DB_FILE)
        dfm = pd.read_sql_query(
            """
            SELECT * FROM missions
            WHERE status = 'DISPATCHED'
              AND (assigned_driver_id IS NULL OR assigned_driver_id = ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            conn,
            params=(st.session_state.driver_id,),
        )
        conn.close()
        if not dfm.empty:
            last = dfm.iloc[0]
            if (datetime.datetime.now() - pd.to_datetime(last["created_at"])).seconds < 300:
                return last
    except Exception:
        pass

    # 2) Legacy fallback: latest mission log within last 60s
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM mission_logs ORDER BY id DESC LIMIT 1", conn)
        conn.close()
        if not df.empty:
            last = df.iloc[0]
            # Logic: If mission is new (within last 60s)
            if (datetime.datetime.now() - pd.to_datetime(last['timestamp'])).seconds < 60:
                return last
    except: pass
    return None

def get_route(s, e):
    """Calculates route for map display (primary route)."""
    try:
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{s[0]},{s[1]}:{e[0]},{e[1]}/json?key={TOMTOM_API_KEY}&traffic=true&routeType=fastest&maxAlternatives=3&instructionsType=text&language=en-US"
        r = requests.get(url, timeout=10).json()
        routes = r.get("routes", [])
        if not routes:
            return [s, e], []
        coords = [[p['latitude'], p['longitude']] for p in routes[0]['legs'][0]['points']]
        instr = []
        for ins in routes[0].get("guidance", {}).get("instructions", []):
            msg = ins.get("message")
            if msg:
                instr.append(msg)
        return coords, instr
    except: return [s, e]

# ==========================================
# 3. INTERFACE
# ==========================================

# --- LOGIN GATE ---
if not st.session_state.driver_authenticated:
    driver_login_screen()
    st.stop()

# HEADER
shift_dur = int((time.time() - st.session_state.shift_start) / 60)
st.markdown(f"""
<div class="mobile-header">
    <div>
        <div style="font-family:'Orbitron'; font-size:20px;">TITAN <span style="color:#00f3ff;">GO</span></div>
        <div style="font-size:10px; color:#aaa;">{st.session_state.driver_id} • TIME: {shift_dur} MIN</div>
    </div>
    <div style="background:{'#00ff9d' if st.session_state.status == 'EN_ROUTE' else '#555'}; color:black; padding:4px 10px; border-radius:4px; font-weight:bold; font-size:10px; font-family:'Orbitron';">
        {st.session_state.status}
    </div>
</div>
""", unsafe_allow_html=True)

# Logout
if st.button("🔒 LOGOUT", use_container_width=True):
    st.session_state.driver_authenticated = False
    st.session_state.status = "IDLE"
    st.session_state.active_org = None
    st.session_state.active_dst = None
    st.session_state.active_mission_id = None
    heartbeat()
    st.rerun()

# 1. ALERT POPUP (SERVER DISPATCH)
heartbeat()
new_mission = check_orders()
if new_mission is not None and st.session_state.status == "IDLE":
    # missions table uses created_at; mission_logs uses timestamp
    org = new_mission.get("origin")
    dst = new_mission.get("destination")
    mid = new_mission.get("mission_id")
    st.warning(f"🚨 HQ COMMAND: {org} ➔ {dst}")
    col_acc, col_ign = st.columns(2)
    with col_acc:
        st.markdown('<div class="accept-btn">', unsafe_allow_html=True)
        if st.button("ACCEPT MISSION"):
            st.session_state.active_org = org
            st.session_state.active_dst = dst
            st.session_state.status = "EN_ROUTE"
            st.session_state.active_mission_id = mid
            
            # Teleport to start
            coords = HOSPITALS.get(org, [10.015, 76.34])
            st.session_state.gps_lat, st.session_state.gps_lon = coords[0], coords[1]
            
            update_server(org, dst, "EN_ROUTE")

            # NEW: mark mission accepted if it came from missions table
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute(
                    """
                    UPDATE missions
                    SET status='ACCEPTED', accepted_at=?
                    WHERE mission_id=? AND status='DISPATCHED'
                    """,
                    (datetime.datetime.now(), mid),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            heartbeat()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# 2. MAIN TABS
tab_drive, tab_map, tab_comms = st.tabs(["🏎️ DASHBOARD", "🗺️ NAV", "📡 COMMS"])

with tab_drive:
    # SPEEDOMETER
    current_speed = random.randint(45, 72) if st.session_state.status == "EN_ROUTE" else 0
    st.markdown(f"""
    <br>
    <div class="speed-circle">
        <div class="speed-val">{current_speed}</div>
        <div class="speed-unit">KM/H</div>
    </div>
    <br>
    """, unsafe_allow_html=True)
    
    # WIDGETS
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"""<div class="widget-box"><div class="w-title">WEATHER</div><div class="w-val">29°C ☀️</div></div>""", unsafe_allow_html=True)
    with c2: 
        dist_str = "--"
        if st.session_state.status == "EN_ROUTE" and st.session_state.active_dst:
            d_coords = HOSPITALS.get(st.session_state.active_dst)
            if d_coords:
                dist = geodesic((st.session_state.gps_lat, st.session_state.gps_lon), d_coords).km
                dist_str = f"{dist:.1f} KM"
        st.markdown(f"""<div class="widget-box"><div class="w-title">TARGET</div><div class="w-val">{dist_str}</div></div>""", unsafe_allow_html=True)

    if st.session_state.status == "IDLE":
        st.info("Waiting for Server Dispatch or Set Manual Route in 'NAV'.")

with tab_map:
    # MANUAL SETTING
    if st.session_state.status == "IDLE":
        st.markdown("### 🛠️ MANUAL ROUTE")
        c1, c2 = st.columns(2)
        with c1: org = st.selectbox("START", sorted(HOSPITALS.keys()), key="m_org")
        with c2: dst = st.selectbox("END", sorted(HOSPITALS.keys()), key="m_dst")
        
        if st.button("🚀 START MISSION"):
            st.session_state.active_org = org
            st.session_state.active_dst = dst
            st.session_state.status = "EN_ROUTE"
            
            c = HOSPITALS[org]
            st.session_state.gps_lat, st.session_state.gps_lon = c[0], c[1]
            
            update_server(org, dst, "EN_ROUTE")
            st.rerun()
            
    # ACTIVE NAVIGATION
    else:
        dest = HOSPITALS.get(st.session_state.active_dst, [10.015, 76.34])
        
        # MAP
        m = folium.Map(location=[st.session_state.gps_lat, st.session_state.gps_lon], zoom_start=14, tiles="CartoDB dark_matter")
        folium.Marker([st.session_state.gps_lat, st.session_state.gps_lon], icon=folium.Icon(color="blue", icon="ambulance", prefix="fa"), popup="YOU").add_to(m)
        folium.Marker(dest, icon=folium.Icon(color="red", icon="flag"), popup="TARGET").add_to(m)
        
        # Draw Route
        res = get_route([st.session_state.gps_lat, st.session_state.gps_lon], dest)
        if isinstance(res, tuple):
            path, instructions = res
        else:
            path, instructions = res, []
        folium.PolyLine(path, color="#00f3ff", weight=5, opacity=0.8).add_to(m)
        
        st_folium(m, height=350, width=None)

        if instructions:
            with st.expander("🧭 Directions"):
                st.write("\n".join([f"- {m}" for m in instructions[:25]]))
        
        # SIMULATION CONTROLS
        c_sim, c_end = st.columns(2)
        with c_sim:
            if st.button("▶️ MOVE FORWARD"):
                # Move 15% closer to destination
                st.session_state.gps_lat += (dest[0] - st.session_state.gps_lat) * 0.15
                st.session_state.gps_lon += (dest[1] - st.session_state.gps_lon) * 0.15
                update_server(st.session_state.active_org, st.session_state.active_dst, "EN_ROUTE")
                heartbeat()
                st.rerun()
        with c_end:
            st.markdown('<div class="end-btn">', unsafe_allow_html=True)
            if st.button("❌ END TRIP"):
                st.session_state.status = "IDLE"
                update_server("NONE", "NONE", "IDLE")
                # NEW: mark mission complete if it exists
                if st.session_state.active_mission_id:
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute(
                            "UPDATE missions SET status='COMPLETED', completed_at=? WHERE mission_id=?",
                            (datetime.datetime.now(), st.session_state.active_mission_id),
                        )
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                st.session_state.active_mission_id = None
                heartbeat()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

with tab_comms:
    st.markdown("### 📡 TACTICAL UPLINK")
    
    st.write("STATUS UPDATES")
    if st.button("⚠️ REQUEST TRAFFIC CLEARANCE"): send_msg("REQUEST", "Approaching major junction. Requesting Green Wave.")
    if st.button("💓 PATIENT CRITICAL"): send_msg("ALERT", "Patient vitals dropping. Increasing speed.")
    if st.button("⛽ REFUELLING NEEDED"): send_msg("WARNING", "Fuel levels low. Rerouting to station.")
    if st.button("✅ ARRIVED AT DESTINATION"): send_msg("INFO", "Unit arrived at hospital. Mission Complete.")
    
    st.write("---")
    st.caption("All messages are logged instantly to Server Control.")