import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import datetime
import time
import random
import requests
import html
import sys
import os

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
    layout="centered",
    initial_sidebar_state="collapsed"
)

# SHARED DATABASE (MUST MATCH SERVER — same path as App.py)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
from shared_utils import fetch_route_alternatives_4, distance_km, hash_password, verify_password, calculate_co2_savings
try:
    from shared_utils import HOSPITALS, MISSION_EXPIRY_SEC
except ImportError:
    MISSION_EXPIRY_SEC = 1800
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

DB_FILE = os.path.join(_APP_DIR, "titan_v52.db")

# HOSPITALS from shared_utils (single source of truth)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&family=Exo+2:wght@400;500;600;700&display=swap');
    
    .stApp { 
        background: #050508 !important;
        background-image: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,245,255,0.08), transparent),
                          radial-gradient(ellipse 60% 40% at 100% 50%, rgba(255,0,255,0.04), transparent),
                          radial-gradient(ellipse 60% 40% at 0% 80%, rgba(0,245,255,0.03), transparent) !important;
        color: #e8e8f0 !important;
    }
    
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    
    .block-container { padding-top: 1.2rem !important; padding-bottom: 2rem !important; max-width: 680px !important; margin: 0 auto !important; }
    .stTabs [data-baseweb="tab-list"] { 
        gap: 6px !important; background: rgba(10,10,18,0.8) !important; padding: 6px !important; 
        border-radius: 16px !important; border: 1px solid rgba(0,245,255,0.2) !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03) !important;
    }
    .stTabs [data-baseweb="tab"] { padding: 10px 16px !important; font-size: 12px !important; font-family: 'Exo 2' !important; font-weight: 600 !important; border-radius: 12px !important; }
    .stTabs [aria-selected="true"] { 
        background: linear-gradient(135deg, rgba(0,245,255,0.25), rgba(255,0,255,0.15)) !important; 
        color: #00f5ff !important; border: 1px solid rgba(0,245,255,0.4) !important;
        box-shadow: 0 0 20px rgba(0,245,255,0.2), inset 0 1px 0 rgba(255,255,255,0.1) !important;
    }
    
    /* FLOATING HEADER - Cyberpunk */
    .mobile-header {
        background: rgba(8,8,16,0.85);
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        padding: 20px 24px;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 20px;
        border: 1px solid rgba(0,245,255,0.3);
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 40px rgba(0,245,255,0.08), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    
    /* FLOATING SPEEDOMETER */
    .speed-circle {
        width: 200px; height: 200px; border-radius: 50%;
        margin: 0 auto; display: flex; flex-direction: column; justify-content: center; align-items: center;
        background: rgba(8,8,16,0.6);
        border: 2px solid rgba(0,245,255,0.5);
        box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 60px rgba(0,245,255,0.15), inset 0 0 60px rgba(0,245,255,0.03);
        border-radius: 50%;
    }
    .speed-val { font-family: 'Orbitron'; font-size: 52px; font-weight: 700; color: #00f5ff; line-height: 1; letter-spacing: -2px; text-shadow: 0 0 30px rgba(0,245,255,0.6); }
    .speed-unit { font-family: 'JetBrains Mono'; font-size: 10px; color: rgba(0,245,255,0.6); letter-spacing: 4px; margin-top: 4px; }
    
    /* FLOATING WIDGET CARDS */
    .widget-box { 
        background: rgba(8,8,16,0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 18px;
        text-align: center;
        border: 1px solid rgba(0,245,255,0.2);
        box-shadow: 0 8px 24px rgba(0,0,0,0.4), 0 0 20px rgba(0,245,255,0.05), inset 0 1px 0 rgba(255,255,255,0.03);
        transition: all 0.3s ease;
    }
    .widget-box:hover { 
        transform: translateY(-4px); 
        border-color: rgba(0,245,255,0.4); 
        box-shadow: 0 12px 32px rgba(0,0,0,0.5), 0 0 40px rgba(0,245,255,0.15); 
    }
    .w-title { color: rgba(0,245,255,0.7); font-size: 9px; letter-spacing: 3px; text-transform: uppercase; font-family: 'JetBrains Mono'; font-weight: 600; }
    .w-val { color: #00f5ff; font-size: 22px; font-family: 'Orbitron'; font-weight: 700; margin-top: 6px; text-shadow: 0 0 20px rgba(0,245,255,0.3); }
    
    /* FLOATING BUTTONS - Cyberpunk glow */
    .stButton > button { 
        width: 100% !important; min-height: 52px !important; border-radius: 14px !important;
        font-family: 'Exo 2' !important; font-size: 14px !important; font-weight: 600 !important;
        background: rgba(12,12,24,0.9) !important;
        color: #e8e8f0 !important; border: 1px solid rgba(0,245,255,0.25) !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03) !important;
    }
    .stButton > button:hover { 
        background: linear-gradient(135deg, rgba(0,245,255,0.2), rgba(255,0,255,0.1)) !important;
        color: #fff !important; border-color: rgba(0,245,255,0.5) !important;
        box-shadow: 0 8px 28px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.2) !important;
        transform: translateY(-2px) !important;
    }
    .stButton > button:active { transform: translateY(0) scale(0.98) !important; }
    
    /* ROUTE CARDS - Floating */
    .route-card {
        background: rgba(8,8,16,0.7);
        backdrop-filter: blur(12px);
        border-left: 4px solid rgba(0,245,255,0.3);
        padding: 18px; margin-bottom: 14px; border-radius: 16px;
        border: 1px solid rgba(0,245,255,0.15);
        box-shadow: 0 8px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.02);
        transition: all 0.3s ease;
    }
    .route-card:hover { transform: translateY(-2px); box-shadow: 0 12px 32px rgba(0,0,0,0.5), 0 0 25px rgba(0,245,255,0.08); }
    .route-card-best {
        border-left: 4px solid #00f5ff;
        border-color: rgba(0,245,255,0.4);
        box-shadow: 0 8px 28px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.12);
    }
    
    /* MISSION ALERT - Floating pulse */
    .mission-alert {
        background: rgba(8,8,16,0.85);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,0,255,0.4);
        border-radius: 20px;
        padding: 28px 24px;
        margin: 24px 0;
        box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 50px rgba(255,0,255,0.15), inset 0 1px 0 rgba(255,255,255,0.05);
        animation: cyber-pulse 2.5s ease-in-out infinite;
    }
    @keyframes cyber-pulse { 
        0%, 100% { box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 50px rgba(255,0,255,0.15), inset 0 1px 0 rgba(255,255,255,0.05); } 
        50% { box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 70px rgba(255,0,255,0.25), inset 0 1px 0 rgba(255,255,255,0.08); } 
    }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"] { display: flex !important; align-items: stretch !important; gap: 12px !important; }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"] .stButton { flex: 1; min-width: 0; width: 100%; }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"] .stButton > button {
        width: 100% !important; min-height: 56px !important; font-size: 14px !important; font-weight: 700 !important;
        border-radius: 14px !important; font-family: 'Exo 2' !important;
    }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"]:first-child .stButton > button {
        background: linear-gradient(135deg, rgba(0,255,136,0.3), rgba(0,245,255,0.2)) !important;
        color: #00ff88 !important; border: 1px solid rgba(0,255,136,0.5) !important;
        box-shadow: 0 0 25px rgba(0,255,136,0.2) !important;
    }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"]:first-child .stButton > button:hover {
        background: linear-gradient(135deg, rgba(0,255,136,0.4), rgba(0,245,255,0.3)) !important;
        box-shadow: 0 0 40px rgba(0,255,136,0.35) !important;
        transform: translateY(-3px) !important;
    }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"]:nth-child(2) .stButton > button {
        background: transparent !important; color: #ff00ff !important; border: 1px solid rgba(255,0,255,0.5) !important;
    }
    div.block-container > div:has(.mission-alert) + div [data-testid="column"]:nth-child(2) .stButton > button:hover {
        background: rgba(255,0,255,0.15) !important; box-shadow: 0 0 30px rgba(255,0,255,0.25) !important;
        transform: translateY(-3px) !important;
    }
    
    /* INPUT FIELDS */
    .stTextInput input, .stTextArea textarea { 
        background: rgba(8,8,16,0.8) !important; border-radius: 12px !important;
        border: 1px solid rgba(0,245,255,0.2) !important; padding: 12px 16px !important;
        font-family: 'Exo 2' !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus { 
        border-color: rgba(0,245,255,0.5) !important; 
        box-shadow: 0 0 0 2px rgba(0,245,255,0.15), 0 0 20px rgba(0,245,255,0.1) !important; 
    }
    
    /* FORM SUBMIT */
    [data-testid="stFormSubmitButton"] button { 
        background: linear-gradient(135deg, rgba(0,245,255,0.3), rgba(255,0,255,0.2)) !important;
        color: #00f5ff !important; font-weight: 700 !important;
        border: 1px solid rgba(0,245,255,0.4) !important; border-radius: 14px !important;
        box-shadow: 0 0 25px rgba(0,245,255,0.2) !important;
    }
    [data-testid="stFormSubmitButton"] button:hover { 
        box-shadow: 0 0 40px rgba(0,245,255,0.3) !important; 
        transform: translateY(-2px) !important;
    }
    
    /* FLOATING CARD - reusable */
    .float-card { 
        background: rgba(8,8,16,0.7); backdrop-filter: blur(12px);
        border: 1px solid rgba(0,245,255,0.2); border-radius: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4), 0 0 20px rgba(0,245,255,0.05), inset 0 1px 0 rgba(255,255,255,0.03);
        padding: 20px; margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LOGIC ENGINE
# ==========================================
if 'driver_id' not in st.session_state: st.session_state.driver_id = "UNIT-07"
if 'gps_lat' not in st.session_state: st.session_state.gps_lat = 10.0150
if 'gps_lon' not in st.session_state: st.session_state.gps_lon = 76.3400
if 'status' not in st.session_state: st.session_state.status = "IDLE"
if 'active_org' not in st.session_state: st.session_state.active_org = None
if 'active_dst' not in st.session_state: st.session_state.active_dst = None
if 'shift_start' not in st.session_state: st.session_state.shift_start = time.time()
if 'active_mission_id' not in st.session_state: st.session_state.active_mission_id = None
if 'driver_authenticated' not in st.session_state: st.session_state.driver_authenticated = False
if 'driver_username' not in st.session_state: st.session_state.driver_username = ""
if 'selected_route_id' not in st.session_state: st.session_state.selected_route_id = 0
if 'clearance_status' not in st.session_state: st.session_state.clearance_status = None  # PENDING / GRANTED / DENIED
if 'route_selection_pending' not in st.session_state: st.session_state.route_selection_pending = False
if 'route_alternatives' not in st.session_state: st.session_state.route_alternatives = []  # 4 routes after accept
if 'manual_route_alternatives' not in st.session_state: st.session_state.manual_route_alternatives = []  # 4 routes for manual trip
if 'manual_route_org' not in st.session_state: st.session_state.manual_route_org = None
if 'manual_route_dst' not in st.session_state: st.session_state.manual_route_dst = None
if 'auto_pilot_active' not in st.session_state: st.session_state.auto_pilot_active = False
if 'auth_tab' not in st.session_state: st.session_state.auth_tab = "Login"  # Login | Sign Up
if 'availability' not in st.session_state: st.session_state.availability = "ACTIVE"  # ACTIVE | BREAK | INACTIVE
if 'status_set_on_login' not in st.session_state: st.session_state.status_set_on_login = False
if 'declined_missions' not in st.session_state: st.session_state.declined_missions = set()
if 'last_poll_mission_id' not in st.session_state: st.session_state.last_poll_mission_id = None
if 'pending_end_trip' not in st.session_state: st.session_state.pending_end_trip = False
if 'pending_decline_mid' not in st.session_state: st.session_state.pending_decline_mid = None
if 'favourite_hospitals' not in st.session_state: st.session_state.favourite_hospitals = []
if 'pending_mission_sound' not in st.session_state: st.session_state.pending_mission_sound = False
if 'pending_message_sound' not in st.session_state: st.session_state.pending_message_sound = False
if 'last_seen_hq_message_id' not in st.session_state: st.session_state.last_seen_hq_message_id = 0
if 'sounds_enabled' not in st.session_state: st.session_state.sounds_enabled = True  # Default ON - alert driver when mission/HQ message arrives
if 'pending_sound_url' not in st.session_state: st.session_state.pending_sound_url = None
if 'pending_sound_ts' not in st.session_state: st.session_state.pending_sound_ts = 0
# Notification sound URLs (short, attention-grabbing)
SOUND_MISSION = "https://assets.mixkit.co/active_storage/sfx/2869-ping-high-15.mp3"
SOUND_ALERT = "https://assets.mixkit.co/active_storage/sfx/2568-simple-notification-2568.mp3"

def init_db_extensions():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                driver_id TEXT PRIMARY KEY,
                status TEXT,
                current_lat REAL,
                current_lon REAL,
                last_seen DATETIME,
                speed REAL,
                origin TEXT,
                destination TEXT,
                active_mission_id TEXT,
                clearance_status TEXT,
                selected_route_id INTEGER
            )
        ''')
        for col, typ in [
            ("speed", "REAL"), ("origin", "TEXT"), ("destination", "TEXT"),
            ("active_mission_id", "TEXT"), ("clearance_status", "TEXT"), ("selected_route_id", "INTEGER"),
        ]:
            try:
                c.execute(f"ALTER TABLE drivers ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
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
        for col, typ in [("vehicle_id", "TEXT"), ("base_hospital", "TEXT")]:
            try:
                c.execute(f"ALTER TABLE driver_accounts ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        c.execute('''
            CREATE TABLE IF NOT EXISTS hazards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL,
                lon REAL,
                type TEXT,
                timestamp DATETIME
            )
        ''')
        try:
            c.execute("ALTER TABLE missions ADD COLUMN decline_reason TEXT")
        except sqlite3.OperationalError:
            pass
        c.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                action TEXT,
                actor TEXT,
                details TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS mission_declines (
                mission_id TEXT,
                driver_id TEXT,
                declined_at DATETIME,
                reason TEXT,
                PRIMARY KEY (mission_id, driver_id)
            )
        ''')
        c.execute(
            "INSERT OR IGNORE INTO driver_accounts (driver_id, username, password, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
            ("UNIT-07", "UNIT-07", hash_password("TITAN-DRIVER"), "Unit 7", datetime.datetime.now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

# MUST run before any DB access (including restore)
init_db_extensions()

# ==========================================
# PERSISTENT LOGIN - survive page refresh (smooth, no crash)
# ==========================================
def _restore_session_from_url():
    """Restore login from URL query params on refresh. Safe, no exceptions."""
    try:
        params = st.query_params
        did = params.get("driver_id")
        uname = params.get("username")
        if not did or not uname or not isinstance(did, str) or not isinstance(uname, str):
            return False
        did, uname = str(did).strip(), str(uname).strip()
        if not did or not uname:
            return False
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute(
            "SELECT driver_id FROM driver_accounts WHERE driver_id = ? AND username = ?",
            (did, uname),
        ).fetchone()
        conn.close()
        if row:
            st.session_state.driver_authenticated = True
            st.session_state.driver_id = did
            st.session_state.driver_username = uname
            st.session_state.status_set_on_login = True  # Skip status screen on restore
            return True
    except Exception:
        pass
    return False

def _save_session_to_url():
    """Save login to URL for persistence. Only on successful login."""
    try:
        if st.session_state.get("driver_authenticated") and st.session_state.get("driver_id") and st.session_state.get("driver_username"):
            st.query_params["driver_id"] = str(st.session_state.driver_id)
            st.query_params["username"] = str(st.session_state.driver_username)
    except Exception:
        pass

def _clear_session_url():
    """Clear URL params on logout."""
    try:
        st.query_params.clear()
    except Exception:
        try:
            for key in list(st.query_params.keys()):
                del st.query_params[key]
        except Exception:
            pass

# Restore session on load (after DB is ready)
if not st.session_state.driver_authenticated:
    _restore_session_from_url()

def get_driver_profile(driver_id):
    """Fetch full driver profile from driver_accounts: id, username, full_name, phone, vehicle_id, base_hospital."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute(
            "SELECT driver_id, username, full_name, phone, vehicle_id, base_hospital FROM driver_accounts WHERE driver_id = ?",
            (driver_id,),
        ).fetchone()
        conn.close()
        if row:
            return {
                "driver_id": row[0],
                "username": row[1] or "",
                "full_name": row[2] or "",
                "phone": row[3] or "",
                "vehicle_id": row[4] or "",
                "base_hospital": row[5] or "",
            }
    except Exception:
        pass
    return None

def driver_signup(username, password, full_name, phone="", vehicle_id="", base_hospital=""):
    """Register new driver. Returns (driver_id, None) on success else (None, error_msg)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        existing = c.execute("SELECT driver_id FROM driver_accounts WHERE username=?", (username.strip(),)).fetchone()
        if existing:
            conn.close()
            return None, "Username already taken."
        driver_id = f"UNIT-{random.randint(100, 999)}"
        pwd_hash = hash_password(password)
        c.execute(
            "INSERT INTO driver_accounts (driver_id, username, password, full_name, phone, vehicle_id, base_hospital, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (driver_id, username.strip(), pwd_hash, full_name.strip(), phone.strip() or None, (vehicle_id or "").strip() or None, (base_hospital or "").strip() or None, datetime.datetime.now()),
        )
        conn.commit()
        conn.close()
        return driver_id, None
    except Exception as e:
        return None, str(e)

def driver_login_screen():
    st.markdown("""
    <div style="text-align:center; padding:48px 24px 40px;">
        <div style="width:96px; height:96px; margin:0 auto 28px; background:rgba(8,8,16,0.8); border-radius:24px; display:flex; align-items:center; justify-content:center; border:1px solid rgba(0,245,255,0.4); box-shadow:0 12px 40px rgba(0,0,0,0.5), 0 0 50px rgba(0,245,255,0.15), inset 0 1px 0 rgba(255,255,255,0.05);">
            <span style="font-size:44px;">🚑</span>
        </div>
        <div style="font-family:'Orbitron', sans-serif; font-size:38px; font-weight:700; color:#00f5ff; letter-spacing:10px; text-shadow:0 0 30px rgba(0,245,255,0.5);">TITAN DRIVER</div>
        <div style="color:rgba(255,0,255,0.8); font-size:11px; letter-spacing:8px; margin-top:10px; font-family:'JetBrains Mono';">FLEET OPERATIONS</div>
        <div style="height:2px; background:linear-gradient(90deg, transparent, #00f5ff, #ff00ff, transparent); margin:32px auto; max-width:180px; border-radius:2px; opacity:0.8;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    auth_tab1, auth_tab2 = st.tabs(["Sign In", "Create Account"])
    
    with auth_tab1:
        st.markdown("""
        <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.25); border-radius:16px; padding:28px; margin:0 0 24px; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.06);">
            <div style="color:rgba(0,245,255,0.9); font-family:'JetBrains Mono'; font-size:10px; letter-spacing:5px; margin-bottom:20px;">SIGN IN</div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("driver_login"):
            u = st.text_input("Username", placeholder="Enter username", label_visibility="collapsed")
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            p = st.text_input("Password", type="password", placeholder="Enter password", label_visibility="collapsed")
            st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
            if st.form_submit_button("Sign In", use_container_width=True, type="primary"):
                if not u or not p:
                    st.error("Enter username and password.")
                else:
                    try:
                        conn = sqlite3.connect(DB_FILE)
                        row = conn.execute(
                            "SELECT driver_id, full_name, password FROM driver_accounts WHERE username=?",
                            (u.strip(),),
                        ).fetchone()
                        conn.close()
                        if row:
                            stored_hash = row[2] if len(row) > 2 else None
                            if stored_hash and len(str(stored_hash)) == 64 and str(stored_hash).isalnum():
                                ok = verify_password(p, stored_hash)
                            else:
                                ok = (p == stored_hash)
                            if ok:
                                st.session_state.driver_authenticated = True
                                st.session_state.driver_id = row[0]
                                st.session_state.driver_username = u.strip()
                                st.session_state.status_set_on_login = False
                                _save_session_to_url()
                                st.rerun()
                            else:
                                st.error("Invalid username or password")
                        else:
                            st.error("Invalid username or password")
                    except Exception:
                        st.error("Login failed.")
        st.markdown("""
        <div style="text-align:center; color:rgba(0,245,255,0.6); font-size:11px; margin-top:20px; font-family:'JetBrains Mono';">Demo: <span style="color:#00f5ff;">UNIT-07</span> / <span style="color:#ff00ff;">TITAN-DRIVER</span></div>
        """, unsafe_allow_html=True)
    
    with auth_tab2:
        st.markdown("""
        <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.25); border-radius:16px; padding:28px; margin:0 0 24px; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.06);">
            <div style="color:rgba(0,245,255,0.9); font-family:'JetBrains Mono'; font-size:10px; letter-spacing:5px; margin-bottom:20px;">CREATE ACCOUNT</div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("driver_signup"):
            new_username = st.text_input("Username", placeholder="Choose username", label_visibility="collapsed", key="su_u")
            new_password = st.text_input("Password", type="password", placeholder="Choose password", label_visibility="collapsed", key="su_p")
            new_full_name = st.text_input("Full Name", placeholder="Full name", label_visibility="collapsed", key="su_n")
            new_phone = st.text_input("Phone", placeholder="Phone (optional)", label_visibility="collapsed", key="su_ph")
            new_vehicle = st.text_input("Vehicle", placeholder="Vehicle number", label_visibility="collapsed", key="su_v")
            new_place = st.text_input("Base", placeholder="Base / Location", label_visibility="collapsed", key="su_pl")
            if st.form_submit_button("Create Account", use_container_width=True, type="primary"):
                if not new_username or not new_password or not new_full_name:
                    st.error("Username, password, and full name required.")
                else:
                    driver_id, err = driver_signup(new_username, new_password, new_full_name, new_phone, new_vehicle, new_place)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"Account created! Unit ID: **{driver_id}**. Log in now.")
                        st.balloons()

def _current_speed():
    return random.randint(45, 72) if st.session_state.status == "EN_ROUTE" else 0

def heartbeat():
    """Push telemetry to server: lat, lon, speed, status, origin, dest, mission, clearance, selected_route."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        speed = _current_speed()
        org = st.session_state.active_org or ""
        dst = st.session_state.active_dst or ""
        mid = st.session_state.active_mission_id
        rid = st.session_state.selected_route_id
        clearance = st.session_state.clearance_status or ""
        c.execute(
            """
            INSERT INTO drivers (driver_id, status, current_lat, current_lon, last_seen, speed, origin, destination, active_mission_id, clearance_status, selected_route_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(driver_id) DO UPDATE SET
              status=excluded.status,
              current_lat=excluded.current_lat,
              current_lon=excluded.current_lon,
              last_seen=excluded.last_seen,
              speed=excluded.speed,
              origin=excluded.origin,
              destination=excluded.destination,
              active_mission_id=excluded.active_mission_id,
              clearance_status=excluded.clearance_status,
              selected_route_id=excluded.selected_route_id
            """,
            (st.session_state.driver_id, st.session_state.status, st.session_state.gps_lat, st.session_state.gps_lon, datetime.datetime.now(), speed, org, dst, mid, clearance, rid),
        )
        conn.commit()
        conn.close()
        # Push to driver_state for ghost trail when EN_ROUTE (throttled every 5s)
        if st.session_state.status == "EN_ROUTE" and org and dst:
            last_push = st.session_state.get("_last_driver_state_push")
            now = datetime.datetime.now()
            if last_push is None or (now - last_push).total_seconds() >= 5:
                update_server(org, dst, "EN_ROUTE")
                st.session_state._last_driver_state_push = now
    except Exception:
        pass


def get_my_clearance():
    """Poll server for this driver's clearance_status (GRANTED / DENIED / PENDING)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute("SELECT clearance_status FROM drivers WHERE driver_id = ?", (st.session_state.driver_id,)).fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None

def update_server(org, dst, stat):
    """Push telemetry to driver_state (lat, lon, speed) so server map updates instantly."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        speed = _current_speed()
        try:
            c.execute(
                "INSERT INTO driver_state (driver_id, origin, destination, current_lat, current_lon, speed, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (st.session_state.driver_id, org, dst, st.session_state.gps_lat, st.session_state.gps_lon, speed, stat, datetime.datetime.now()),
            )
        except sqlite3.OperationalError:
            c.execute(
                "INSERT INTO driver_state (driver_id, origin, destination, current_lat, current_lon, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (st.session_state.driver_id, org, dst, st.session_state.gps_lat, st.session_state.gps_lon, stat, datetime.datetime.now()),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass

def send_msg(stat, msg):
    """Send message to HQ (driver_comms). Server reads this for V2X Comms."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO driver_comms (timestamp, driver_id, status, message) VALUES (?, ?, ?, ?)",
                  (datetime.datetime.now(), st.session_state.driver_id, stat, msg))
        conn.commit()
        conn.close()
    except Exception:
        pass

def log_activity(action, actor, details=""):
    """Log activity for audit trail."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO activity_log (timestamp, action, actor, details) VALUES (?, ?, ?, ?)",
                  (datetime.datetime.now(), action, actor, details))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def report_hazard(hazard_type="OTHER"):
    """Inserts a hazard record at current location with specified type."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        type_str = f"{hazard_type}: {st.session_state.driver_id}" if hazard_type else "OTHER"
        c.execute("INSERT INTO hazards (lat, lon, type, timestamp) VALUES (?, ?, ?, ?)",
                  (st.session_state.gps_lat, st.session_state.gps_lon, type_str, datetime.datetime.now()))
        conn.commit()
        conn.close()
        st.toast("Hazard Reported Successfully!", icon="⚠️")
    except Exception:
        pass

def check_orders():
    """Fetch pending mission assigned to this driver (or unassigned). Expiry 30 min. Excludes persisted declines."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        driver_id = str(st.session_state.get("driver_id", ""))
        dfm = pd.read_sql_query(
            """
            SELECT m.* FROM missions m
            WHERE m.status = 'DISPATCHED'
              AND (m.assigned_driver_id IS NULL OR m.assigned_driver_id = ?)
              AND NOT EXISTS (SELECT 1 FROM mission_declines d WHERE d.mission_id = m.mission_id AND d.driver_id = ?)
            ORDER BY m.id DESC
            LIMIT 5
            """,
            conn,
            params=(driver_id, driver_id),
        )
        conn.close()
        declined = st.session_state.get("declined_missions") or set()
        for _, row in dfm.iterrows():
            mid = row.get("mission_id")
            if mid and mid in declined:
                continue
            created = pd.to_datetime(row.get("created_at"), errors="coerce")
            if pd.notna(created):
                age_sec = (datetime.datetime.now() - created).total_seconds()
                if age_sec < MISSION_EXPIRY_SEC:
                    return row.to_dict()
    except Exception:
        pass
    return None

def fetch_all_routes(s, e):
    """Fetches 4 route alternatives (shared_utils)."""
    return fetch_route_alternatives_4(s, e)

def run_auto_pilot(route_coords):
    """Simulates driving along the route"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Decimate coordinates for smoother fast-forward
    step_size = max(1, len(route_coords) // 20)
    
    status_text.write("🚀 AUTO-PILOT ENGAGED")
    
    for i, point in enumerate(route_coords[::step_size]):
        # Update State
        st.session_state.gps_lat, st.session_state.gps_lon = point[0], point[1]
        
        # Update Server
        update_server(st.session_state.active_org, st.session_state.active_dst, "EN_ROUTE")
        heartbeat()
        
        # UI Feedback
        progress = min(1.0, (i + 1) / (len(route_coords) / step_size))
        progress_bar.progress(progress)
        
        time.sleep(1) # 1 second delay
    
    progress_bar.empty()
    status_text.success("🏁 AUTO-PILOT: DESTINATION REACHED")
    st.session_state.auto_pilot_active = False

# ==========================================
# 3. INTERFACE
# ==========================================
if not st.session_state.driver_authenticated:
    driver_login_screen()
    st.stop()

# ==========================================
# STATUS SELECTION - Set availability on login
# ==========================================
def status_selection_screen():
    st.markdown("""
    <div style="text-align:center; padding:44px 24px 40px;">
        <div style="font-family:'Orbitron', sans-serif; font-size:26px; letter-spacing:6px; color:#00f5ff; text-shadow:0 0 20px rgba(0,245,255,0.4);">SET AVAILABILITY</div>
        <div style="color:rgba(0,245,255,0.6); font-size:13px; margin-top:10px; font-family:'Exo 2';">How are you starting your shift?</div>
    </div>
    """, unsafe_allow_html=True)
    
    opt1, opt2, opt3 = st.columns([1, 1, 1])
    with opt1:
        if st.button("Active", use_container_width=True, key="stat_active", help="Ready for missions"):
            try:
                st.session_state.availability = "ACTIVE"
                st.session_state.status = "IDLE"
                st.session_state.status_set_on_login = True
                heartbeat()
            except Exception:
                pass
            st.rerun()
    with opt2:
        if st.button("Break", use_container_width=True, key="stat_break", help="On break"):
            try:
                st.session_state.availability = "BREAK"
                st.session_state.status = "BREAK"
                st.session_state.status_set_on_login = True
                heartbeat()
            except Exception:
                pass
            st.rerun()
    with opt3:
        if st.button("Inactive", use_container_width=True, key="stat_inactive", help="Off duty"):
            try:
                st.session_state.availability = "INACTIVE"
                st.session_state.status = "INACTIVE"
                st.session_state.status_set_on_login = True
                heartbeat()
            except Exception:
                pass
            st.rerun()
    
    st.markdown(f"""
    <div style="text-align:center; color:rgba(0,245,255,0.6); font-size:11px; margin-top:20px; font-family:'JetBrains Mono';">Logged in as <span style="color:#00f5ff;">{st.session_state.driver_id}</span></div>
    """, unsafe_allow_html=True)

if not st.session_state.status_set_on_login:
    status_selection_screen()
    st.stop()

# Keep driver online when idle - heartbeat every 30s
@st.fragment(run_every=30)
def _keep_online():
    if st.session_state.get("driver_authenticated") and st.session_state.get("availability") == "ACTIVE":
        heartbeat()

# Live mission poller - checks every 2s for new missions (no manual refresh needed)
@st.fragment(run_every=2)
def _mission_poller():
    if not st.session_state.get("driver_authenticated"):
        return
    if st.session_state.get("status") != "IDLE" or st.session_state.get("availability") != "ACTIVE":
        return
    m = check_orders()
    if m is None:
        return
    mid = m.get("mission_id")
    declined = st.session_state.get("declined_missions") or set()
    if mid and mid in declined:
        return
    last_poll = st.session_state.get("last_poll_mission_id")
    if mid and mid != last_poll:
        st.session_state.last_poll_mission_id = mid
        st.session_state.pending_mission_sound = True
        st.rerun()

# Poll clearance on load
try:
    _clearance = get_my_clearance()
    if _clearance:
        st.session_state.clearance_status = _clearance
except Exception:
    pass

# HEADER (driver info + Online/status)
try:
    _profile = get_driver_profile(st.session_state.get("driver_id", ""))
    _display_name = (_profile.get("full_name") or st.session_state.driver_username or st.session_state.driver_id) if _profile else (st.session_state.driver_username or st.session_state.driver_id or "Driver")
    _vehicle = (_profile.get("vehicle_id") or "—") if _profile else "—"
    _place = (_profile.get("base_hospital") or "—") if _profile else "—"
except Exception:
    _display_name = st.session_state.driver_username or st.session_state.driver_id or "Driver"
    _vehicle = _place = "—"
shift_dur = int((time.time() - st.session_state.get("shift_start", time.time())) / 60)
# Status badge: Online (ACTIVE), Break, Inactive, or En Route
_av = st.session_state.get("availability", "ACTIVE")
_st = st.session_state.get("status", "IDLE")
if _st == "EN_ROUTE":
    _status_badge = "EN ROUTE"
    _status_bg = "rgba(0,255,136,0.3)"
    _status_border = "1px solid rgba(0,255,136,0.5)"
    _status_text = "#00ff88"
elif _av == "ACTIVE" and _st == "IDLE":
    _status_badge = "ONLINE"
    _status_bg = "rgba(0,245,255,0.25)"
    _status_border = "1px solid rgba(0,245,255,0.5)"
    _status_text = "#00f5ff"
elif _av == "BREAK":
    _status_badge = "BREAK"
    _status_bg = "rgba(255,0,255,0.25)"
    _status_border = "1px solid rgba(255,0,255,0.5)"
    _status_text = "#ff00ff"
elif _av == "INACTIVE":
    _status_badge = "INACTIVE"
    _status_bg = "rgba(100,100,120,0.3)"
    _status_border = "1px solid rgba(100,100,120,0.4)"
    _status_text = "#888"
else:
    _status_badge = str(_st)
    _status_bg = "rgba(100,100,120,0.3)"
    _status_border = "1px solid rgba(100,100,120,0.4)"
    _status_text = "#888"
st.markdown(f"""
<div class="mobile-header">
    <div>
        <div style="font-family:'Orbitron', sans-serif; font-size:22px; letter-spacing:4px; color:#00f5ff; text-shadow:0 0 15px rgba(0,245,255,0.3);">{st.session_state.driver_id}</div>
        <div style="font-size:13px; color:#e8e8f0; font-weight:600; margin-top:4px; font-family:'Exo 2';">{_display_name}</div>
        <div style="font-size:11px; color:rgba(0,245,255,0.6); margin-top:4px; font-family:'JetBrains Mono';">{_vehicle} • {_place} • {shift_dur}m</div>
    </div>
    <div style="background:{_status_bg}; color:{_status_text}; padding:10px 18px; border-radius:12px; font-weight:700; font-size:11px; font-family:'JetBrains Mono'; letter-spacing:2px; border:{_status_border}; box-shadow:0 0 20px rgba(0,245,255,0.1);">
        {_status_badge}
    </div>
</div>
<div style="display:flex; justify-content:flex-end; margin-top:-4px; margin-bottom:8px; align-items:center;">
    <span style="color:rgba(0,255,136,0.9); font-size:10px; font-family:'JetBrains Mono'; letter-spacing:2px;">● SYNCED</span>
</div>
""", unsafe_allow_html=True)
if st.session_state.clearance_status == "GRANTED":
    st.markdown("""
    <div style="background:rgba(0,255,136,0.1); backdrop-filter:blur(8px); border:1px solid rgba(0,255,136,0.5); border-radius:14px; padding:14px 20px; color:#00ff88; font-weight:700; font-family:'JetBrains Mono'; letter-spacing:2px; box-shadow:0 0 30px rgba(0,255,136,0.15);">
        ✓ GREEN WAVE GRANTED
    </div>
    """, unsafe_allow_html=True)
    st.session_state.clearance_status = None  # reset after showing so we can request again later
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE drivers SET clearance_status = NULL WHERE driver_id = ?", (st.session_state.driver_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass
elif st.session_state.clearance_status == "DENIED":
    st.markdown("""
    <div style="background:rgba(255,0,80,0.1); backdrop-filter:blur(8px); border:1px solid rgba(255,0,80,0.5); border-radius:14px; padding:14px 20px; color:#ff0050; font-weight:700; font-family:'JetBrains Mono'; letter-spacing:2px; box-shadow:0 0 30px rgba(255,0,80,0.15);">
        ✗ REQUEST DENIED
    </div>
    """, unsafe_allow_html=True)
    st.session_state.clearance_status = None
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE drivers SET clearance_status = NULL WHERE driver_id = ?", (st.session_state.driver_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass

# Pending alert sound — show Play button when sound queued (HQ message or mission; fallback if autoplay blocked)
if st.session_state.get("pending_sound_url") and st.session_state.get("sounds_enabled"):
    _url = st.session_state.pending_sound_url
    _ts = st.session_state.get("pending_sound_ts", 0)
    if time.time() - _ts < 45:
        st.markdown("""
        <div style="background:rgba(255,0,80,0.15); border:1px solid rgba(255,0,80,0.5); border-radius:10px; padding:10px 14px; margin-bottom:12px; display:flex; align-items:center; gap:12px;">
            <span style="color:#ff0050; font-weight:700;">🔔 New alert</span>
            <span style="color:rgba(255,255,255,0.7); font-size:12px;">Tap to play sound</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔔 Play alert", key="play_pending_sound_top", use_container_width=True, type="primary"):
            st.audio(_url, format="audio/mpeg", autoplay=True)
            st.session_state.pending_sound_url = None
            st.session_state.pending_sound_ts = 0
            st.toast("Playing alert", icon="🔊")
            st.rerun()

# Action bar — aligned layout
st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
bar1, bar2, bar3 = st.columns([1, 2, 1])
with bar1:
    if st.button("🔄 Refresh", key="manual_refresh", use_container_width=True, help="Check for new missions"):
        st.rerun()
with bar2:
    if st.session_state.status != "EN_ROUTE":
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Online", key="set_active", use_container_width=True):
                st.session_state.availability = "ACTIVE"
                st.session_state.status = "IDLE"
                heartbeat()
                st.rerun()
        with b2:
            if st.button("Break", key="set_break", use_container_width=True):
                st.session_state.availability = "BREAK"
                st.session_state.status = "BREAK"
                heartbeat()
                st.rerun()
        with b3:
            if st.button("Inactive", key="set_inactive", use_container_width=True):
                st.session_state.availability = "INACTIVE"
                st.session_state.status = "INACTIVE"
                heartbeat()
                st.rerun()
    else:
        st.caption("En route")
with bar3:
    if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
        # Clean up: mark driver offline in DB
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("UPDATE drivers SET status='OFFLINE', last_seen=? WHERE driver_id=?", (datetime.datetime.now(), st.session_state.driver_id))
        except Exception:
            pass
        st.session_state.driver_authenticated = False
        st.session_state.driver_id = ""
        st.session_state.driver_username = ""
        st.session_state.status = "IDLE"
        st.session_state.active_org = None
        st.session_state.active_dst = None
        st.session_state.active_mission_id = None
        _clear_session_url()
        st.rerun()

# 1. MISSION ALERT (or listening indicator)
heartbeat()
# Check if current mission was cancelled by HQ
if st.session_state.active_mission_id:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute("SELECT status FROM missions WHERE mission_id=?", (st.session_state.active_mission_id,)).fetchone()
        if row and row[0] == "CANCELLED":
            mid_cancelled = st.session_state.active_mission_id
            st.session_state.active_mission_id = None
            st.session_state.active_org = None
            st.session_state.active_dst = None
            st.session_state.status = "IDLE"
            st.session_state.route_alternatives = []
            st.session_state.route_selection_pending = False
            st.error(f"Mission {mid_cancelled} was CANCELLED by HQ.")
            st.rerun()
    except Exception:
        pass
new_mission = check_orders()

if st.session_state.status == "IDLE" and st.session_state.get("availability") == "ACTIVE" and new_mission is None:
    st.markdown("""
    <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.3); border-radius:16px; padding:22px 24px; margin:20px 0; color:rgba(0,245,255,0.7); font-size:14px; font-family:'Exo 2'; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.06);">
        <span style="color:#00f5ff; font-weight:700; text-shadow:0 0 15px rgba(0,245,255,0.4);">● LISTENING</span> — Updates every 2s. No refresh needed.
    </div>
    """, unsafe_allow_html=True)
    if st.session_state.get("sounds_enabled"):
        st.caption("🔊 Sound alerts ON — you'll hear when missions or HQ messages arrive")
    if st.session_state.declined_missions:
        if st.button("Undo decline", key="undo_decline"):
            st.session_state.declined_missions.clear()
            st.rerun()

if new_mission is not None and st.session_state.status == "IDLE" and st.session_state.get("availability") == "ACTIVE":
    # --- MISSION ALERT SCREEN (Premium Card) ---
    org = new_mission.get("origin") or ""
    dst = new_mission.get("destination") or ""
    mid = new_mission.get("mission_id") or ""
    prio = new_mission.get("priority") or "STANDARD"
    org_esc = html.escape(str(org))
    dst_esc = html.escape(str(dst))
    mid_esc = html.escape(str(mid))
    prio_esc = html.escape(str(prio))
    
    prio_color = "#ff0050" if prio == "CRITICAL" else "#ff00ff" if prio == "HIGH" else "#00f5ff"
    
    # Mission countdown (30 min expiry)
    created = pd.to_datetime(new_mission.get("created_at"), errors="coerce")
    mins_left = "—"
    if pd.notna(created):
        age_sec = (datetime.datetime.now() - created).total_seconds()
        remaining = max(0, 1800 - age_sec)
        mins_left = f"{int(remaining // 60)} min"
    # Build mission card HTML as single-line to avoid Streamlit multiline parsing
    countdown_part = f'<div style="color:rgba(255,0,255,0.9); font-size:11px; margin-top:12px; font-family:JetBrains Mono,sans-serif;">⏱ EXPIRES: {mins_left}</div>'
    notes_part = ""
    if new_mission.get("notes"):
        notes_escaped = html.escape(str(new_mission.get("notes", "") or ""))
        notes_part = f'<div style="color:rgba(0,245,255,0.7); font-size:12px; margin-top:14px; padding:14px; background:rgba(0,0,0,0.3); border-radius:12px; text-align:left; font-family:Exo 2,sans-serif; border:1px solid rgba(0,245,255,0.15);">📋 {notes_escaped}</div>'
    mission_card_html = (
        f'<div class="mission-alert">'
        f'<div style="text-align:center;">'
        f'<div style="color:{prio_color}; font-family:JetBrains Mono,sans-serif; font-size:10px; letter-spacing:5px; font-weight:700;">{prio_esc} PRIORITY</div>'
        f'<div style="color:#e8e8f0; font-family:Orbitron,sans-serif; font-size:22px; margin:14px 0; letter-spacing:2px;">{org_esc}</div>'
        f'<div style="color:#00f5ff; font-size:20px; text-shadow:0 0 20px rgba(0,245,255,0.4);">↓</div>'
        f'<div style="color:#e8e8f0; font-family:Orbitron,sans-serif; font-size:22px; margin:14px 0; letter-spacing:2px;">{dst_esc}</div>'
        f'<div style="color:rgba(0,245,255,0.7); font-size:11px; margin-top:10px; font-family:JetBrains Mono,sans-serif;">{mid_esc}</div>'
        f'{countdown_part}{notes_part}'
        f'</div></div>'
    )
    # Play mission alert sound when new mission arrives — auto-play to alert distracted driver
    if st.session_state.get("pending_mission_sound"):
        st.session_state.pending_mission_sound = False
        if st.session_state.get("sounds_enabled"):
            st.session_state.pending_sound_url = SOUND_MISSION
            st.session_state.pending_sound_ts = time.time()
            # Try autoplay — works if user has interacted with page (login, status select)
            st.audio(SOUND_MISSION, format="audio/mpeg", autoplay=True)
            st.toast("🔔 New mission — check below!", icon="🚨")
    st.markdown(mission_card_html, unsafe_allow_html=True)
    # Fallback: if autoplay was blocked, show tap-to-play button below mission card
    if st.session_state.get("pending_sound_url") and st.session_state.get("sounds_enabled"):
        _url = st.session_state.pending_sound_url
        _ts = st.session_state.get("pending_sound_ts", 0)
        if time.time() - _ts < 45:
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if st.button("🔔 Play alert sound (tap if you didn't hear it)", key="play_pending_sound", use_container_width=True, type="primary"):
                st.audio(_url, format="audio/mpeg", autoplay=True)
                st.session_state.pending_sound_url = None
                st.session_state.pending_sound_ts = 0
                st.rerun()
    
    s_coords = HOSPITALS.get(org, [10.015, 76.34])
    d_coords = HOSPITALS.get(dst, [10.015, 76.34])
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    col_acc, col_ign = st.columns([1, 1])
    with col_acc:
        if st.button("✓ Accept mission", key="accept_mission_btn", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                # Atomic accept: only succeed if mission still unassigned or assigned to this driver
                c.execute(
                    "UPDATE missions SET status='ACCEPTED', accepted_at=?, assigned_driver_id=? WHERE mission_id=? AND (assigned_driver_id IS NULL OR assigned_driver_id=?)",
                    (datetime.datetime.now(), st.session_state.driver_id, mid, st.session_state.driver_id),
                )
                rows = c.rowcount
                conn.commit()
                conn.close()
                if rows == 0:
                    st.warning("Mission was already accepted by another unit.")
                    st.rerun()
            except Exception as e:
                st.error("Database update failed. Mission may not sync with HQ.")
                st.rerun()
            log_activity("ACCEPT", st.session_state.driver_id, mid)
            st.session_state.active_org = org
            st.session_state.active_dst = dst
            st.session_state.status = "EN_ROUTE"
            st.session_state.active_mission_id = mid
            coords = HOSPITALS.get(org, [10.015, 76.34])
            st.session_state.gps_lat, st.session_state.gps_lon = coords[0], coords[1]
            update_server(org, dst, "EN_ROUTE")
            # 4-route logic: compute alternatives and show selection
            if s_coords and d_coords:
                with st.spinner("Loading route options..."):
                    st.session_state.route_alternatives = fetch_route_alternatives_4(s_coords, d_coords)
                st.session_state.route_selection_pending = True
            heartbeat()
            st.rerun()
    with col_ign:
        if st.session_state.pending_decline_mid == mid:
            decline_reason = st.selectbox("Reason (optional)", ["—", "Too far", "On break", "Vehicle issue", "Other"], key="decline_reason")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("Confirm decline", key="confirm_decline", use_container_width=True):
                    reason = decline_reason if decline_reason != "—" else ""
                    try:
                        with sqlite3.connect(DB_FILE) as conn:
                            conn.execute("PRAGMA journal_mode=WAL;")
                            try:
                                conn.execute("ALTER TABLE missions ADD COLUMN decline_reason TEXT")
                            except sqlite3.OperationalError:
                                pass
                            conn.execute("UPDATE missions SET decline_reason=? WHERE mission_id=?", (reason, mid))
                            conn.execute("UPDATE missions SET assigned_driver_id=NULL WHERE mission_id=?", (mid,))
                            conn.execute(
                                "INSERT OR REPLACE INTO mission_declines (mission_id, driver_id, declined_at, reason) VALUES (?, ?, ?, ?)",
                                (mid, st.session_state.driver_id, datetime.datetime.now(), reason),
                            )
                            conn.commit()
                    except Exception:
                        st.error("Failed to update mission status.")
                    send_msg("DECLINE", f"Mission {mid} declined by {st.session_state.driver_id}. Reason: {reason}".strip())
                    log_activity("DECLINE", st.session_state.driver_id, f"{mid} {reason}".strip())
                    st.session_state.declined_missions.add(mid)
                    st.session_state.pending_decline_mid = None
                    st.rerun()
            with c2:
                if st.button("← Back", key="cancel_decline", use_container_width=True):
                    st.session_state.pending_decline_mid = None
                    st.rerun()
        elif st.button("✕ Decline", key="decline_mission_btn", use_container_width=True):
            st.session_state.pending_decline_mid = mid
            st.rerun()

# Route selection (after accept)
if st.session_state.route_selection_pending and st.session_state.route_alternatives and st.session_state.status == "EN_ROUTE":
    st.markdown("### Select route")
    routes = st.session_state.route_alternatives
    dest = HOSPITALS.get(st.session_state.active_dst, [10.015, 76.34])
    start_pt = [st.session_state.gps_lat, st.session_state.gps_lon]
    m = folium.Map(location=start_pt, zoom_start=13, tiles="CartoDB dark_matter")
    folium.Marker(start_pt, icon=folium.Icon(color="blue", icon="ambulance", prefix="fa"), popup="YOU").add_to(m)
    folium.Marker(dest, icon=folium.Icon(color="red", icon="flag", prefix="fa"), popup="TARGET").add_to(m)
    colors = ["#06b6d4", "#f59e0b", "#10b981", "#ec4899"]
    for i, r in enumerate(routes):
        folium.PolyLine(r["coords"], color=colors[i % len(colors)], weight=4 if i == 0 else 2, opacity=0.8).add_to(m)
    st_folium(m, height=350, width=None, returned_objects=[])
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    for i, r in enumerate(routes):
        best_class = "route-card-best" if i == 0 else ""
        c = colors[i % len(colors)]
        r_col1, r_col2 = st.columns([3, 1])
        with r_col1:
            st.markdown(f"""
            <div class="route-card {best_class}">
                <div style="font-weight:700; color:#e8e8f0; font-size:15px; font-family:Orbitron,sans-serif; letter-spacing:2px;">{r.get('route_type', f'Route {i+1}')}</div>
                <div style="display:flex; align-items:center; gap:16px; margin-top:10px; font-size:13px; font-family:JetBrains Mono,sans-serif;">
                    <span style="color:#00f5ff; font-weight:700;">{r.get('eta', 0)} min</span>
                    <span style="color:rgba(0,245,255,0.3);">|</span>
                    <span style="color:rgba(0,245,255,0.6);">{r.get('dist', 0)} km</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with r_col2:
            if st.button("Select", key=f"sel_route_{i}", use_container_width=True):
                st.session_state.selected_route_id = i
                st.session_state.route_selection_pending = False
                heartbeat()
                st.rerun()
    st.stop()

# Main tabs
# Global notification checker - popup + sound for new HQ messages (runs every 3s, any tab)
@st.fragment(run_every=3)
def _global_hq_notify():
    if not st.session_state.get("driver_authenticated"):
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute(
            "SELECT id, message, status FROM driver_comms WHERE (status LIKE 'HQ%' OR driver_id='ALL' OR driver_id=?) ORDER BY id DESC LIMIT 1",
            (st.session_state.driver_id,)
        ).fetchone()
        conn.close()
        if row:
            max_id, msg_text, msg_type = row[0], str(row[1] or "")[:50], str(row[2] or "")
            last_seen = st.session_state.get("last_seen_hq_message_id", 0)
            if last_seen == 0:
                st.session_state.last_seen_hq_message_id = max_id
            elif max_id > last_seen:
                st.session_state.last_seen_hq_message_id = max_id
                if st.session_state.get("sounds_enabled"):
                    sound_url = SOUND_MISSION if "GREENWAVE" in msg_type else SOUND_ALERT
                    st.session_state.pending_sound_url = sound_url
                    st.session_state.pending_sound_ts = time.time()
                    # Try autoplay — works if user has interacted with page
                    st.audio(sound_url, format="audio/mpeg", autoplay=True)
                st.toast(f"📬 New from HQ: {msg_text}...", icon="🟢" if "GREENWAVE" in msg_type else "📡")
                st.rerun()  # Rerun so Play alert button appears if autoplay was blocked
    except Exception:
        pass  # Silent - don't block UI on comms fetch failure

tab_drive, tab_map, tab_comms, tab_alerts, tab_missions, tab_stats, tab_settings = st.tabs([
    "🏠 Home", "🗺️ Map", "📶 Comms", "⚠️ Alerts", "📋 Missions", "📊 Stats", "⚙️ Settings"
])

# Invoke fragments so they run (mission poller, HQ notify, heartbeat)
_keep_online()
_mission_poller()
_global_hq_notify()

with tab_drive:
    # === DASHBOARD: Rich, professional layout ===
    current_speed = random.randint(45, 72) if st.session_state.status == "EN_ROUTE" else 0
    shift_dur = int((time.time() - st.session_state.get("shift_start", time.time())) / 60)
    completed = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM missions WHERE assigned_driver_id=? AND status='COMPLETED'",
                (st.session_state.driver_id,)
            ).fetchone()
            completed = row[0] if row else 0
    except Exception:
        pass

    # Row 1: Speedometer + Active mission / status
    dash_col1, dash_col2 = st.columns([1, 1])
    with dash_col1:
        st.markdown(f"""
        <div style="padding:16px 0;">
            <div class="speed-circle">
                <div class="speed-val">{current_speed}</div>
                <div class="speed-unit">KM/H</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with dash_col2:
        if st.session_state.status == "EN_ROUTE" and st.session_state.active_dst:
            d_coords = HOSPITALS.get(st.session_state.active_dst)
            dist = geodesic((st.session_state.gps_lat, st.session_state.gps_lon), d_coords).km if d_coords else 0
            eta = int(dist * 60 / 40)
            org_short = (st.session_state.active_org or "—")[:20]
            dst_short = (st.session_state.active_dst or "—")[:20]
            st.markdown(f"""
            <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.3); border-radius:16px; padding:22px; margin:18px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.08);">
                <div style="color:rgba(0,245,255,0.9); font-size:9px; letter-spacing:4px; margin-bottom:12px; font-family:JetBrains Mono,sans-serif;">ACTIVE MISSION</div>
                <div style="color:#e8e8f0; font-family:Orbitron,sans-serif; font-size:16px; margin:6px 0; letter-spacing:1px;">{html.escape(org_short)}</div>
                <div style="color:#00f5ff; font-size:16px; text-shadow:0 0 15px rgba(0,245,255,0.4);">↓</div>
                <div style="color:#e8e8f0; font-family:Orbitron,sans-serif; font-size:16px; margin:6px 0; letter-spacing:1px;">{html.escape(dst_short)}</div>
                <div style="display:flex; justify-content:space-between; margin-top:16px; padding-top:14px; border-top:1px solid rgba(0,245,255,0.15);">
                    <div style="text-align:center;"><span style="color:rgba(0,245,255,0.6); font-size:9px; font-family:JetBrains Mono,sans-serif;">REMAINING</span><br><span style="color:#00ff88; font-weight:700; font-family:JetBrains Mono,sans-serif;">{dist:.1f} km</span></div>
                    <div style="text-align:center;"><span style="color:rgba(0,245,255,0.6); font-size:9px; font-family:JetBrains Mono,sans-serif;">ETA</span><br><span style="color:#00f5ff; font-weight:700; font-family:JetBrains Mono,sans-serif;">{eta} min</span></div>
                    <div style="text-align:center;"><span style="color:rgba(0,245,255,0.6); font-size:9px; font-family:JetBrains Mono,sans-serif;">ARRIVAL</span><br><span style="color:#e8e8f0; font-weight:700; font-family:JetBrains Mono,sans-serif;">{(datetime.datetime.now() + datetime.timedelta(minutes=eta)).strftime('%H:%M')}</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if d_coords and len(d_coords) >= 2:
                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={d_coords[0]},{d_coords[1]}&travelmode=driving"
                st.link_button("📍 Open in Google Maps", nav_url, use_container_width=True, help="Navigate to destination")
        else:
            st.markdown(f"""
            <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.2); border-radius:16px; padding:28px; margin:18px 0; text-align:center; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 25px rgba(0,245,255,0.05);">
                <div style="font-size:40px; margin-bottom:12px;">🚑</div>
                <div style="color:#00f5ff; font-weight:700; font-size:18px; font-family:Orbitron,sans-serif; letter-spacing:3px; text-shadow:0 0 20px rgba(0,245,255,0.3);">READY FOR DISPATCH</div>
                <div style="color:rgba(0,245,255,0.6); font-size:13px; margin-top:8px; font-family:Exo 2,sans-serif;">Awaiting mission assignment</div>
                <div style="color:rgba(0,245,255,0.9); font-size:11px; margin-top:14px; font-family:JetBrains Mono,sans-serif; letter-spacing:2px;">● LISTENING 2s</div>
            </div>
            """, unsafe_allow_html=True)

    # Row 2: Quick stats strip
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        st.markdown(f"""<div class="widget-box"><div class="w-title">Shift</div><div class="w-val">{shift_dur}m</div></div>""", unsafe_allow_html=True)
    with q2:
        st.markdown(f"""<div class="widget-box"><div class="w-title">Missions</div><div class="w-val">{completed}</div></div>""", unsafe_allow_html=True)
    with q3:
        status_txt = "En route" if st.session_state.status == "EN_ROUTE" else "Idle"
        status_c = "#00ff88" if st.session_state.status == "EN_ROUTE" else "#00f5ff"
        st.markdown(f"""<div class="widget-box"><div class="w-title">Status</div><div class="w-val" style="color:{status_c};">{status_txt}</div></div>""", unsafe_allow_html=True)
    with q4:
        avg_s = random.randint(48, 65) if st.session_state.status == "EN_ROUTE" else 0
        st.markdown(f"""<div class="widget-box"><div class="w-title">Avg</div><div class="w-val">{avg_s} km/h</div></div>""", unsafe_allow_html=True)

    # Row 3: Quick actions
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    _qa_lbl = "color:#8e8e93; font-size:10px; letter-spacing:4px; margin-bottom:8px"
    st.markdown(f"<div style='{_qa_lbl}; font-family:JetBrains Mono,sans-serif'>QUICK ACTIONS</div>", unsafe_allow_html=True)
    qa1, qa2, qa3, qa4 = st.columns(4)
    with qa1:
        if st.button("🆘 SOS", use_container_width=True, key="dash_sos"):
            send_msg("CRITICAL", f"SOS — {st.session_state.driver_id} EMERGENCY ASSISTANCE REQUIRED")
            st.toast("SOS sent to HQ!", icon="🚨")
            st.rerun()
    with qa2:
        if st.button("🟢 Green", use_container_width=True, key="dash_green"):
            send_msg("GREENWAVE", f"Green Wave request from {st.session_state.driver_id}")
            st.toast("Green Wave requested", icon="🟢")
            st.rerun()
    with qa3:
        if st.session_state.status == "EN_ROUTE" and st.button("👤 Patient", use_container_width=True, key="dash_patient"):
            send_msg("STATUS", f"PATIENT SECURED - {st.session_state.driver_id} en route to {st.session_state.active_dst or 'destination'}")
            st.toast("Status sent", icon="✅")
            st.rerun()
        elif st.session_state.status != "EN_ROUTE":
            st.button("👤 Patient", use_container_width=True, key="dash_patient", disabled=True)
    with qa4:
        if st.button("🚧 Obstruction", use_container_width=True, key="dash_obst"):
            send_msg("WARNING", f"TRAFFIC OBSTRUCTION - {st.session_state.driver_id}")
            st.toast("Reported to HQ", icon="⚠️")
            st.rerun()

    # Row 4: Recent activity feed
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    _rfh_lbl = "color:#8e8e93; font-size:10px; letter-spacing:4px; margin-bottom:8px"
    st.markdown(f"<div style='{_rfh_lbl}; font-family:JetBrains Mono,sans-serif'>RECENT FROM HQ</div>", unsafe_allow_html=True)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            msgs = conn.execute(
                "SELECT message, status, timestamp FROM driver_comms WHERE (status LIKE 'HQ%' OR driver_id='ALL' OR driver_id=?) ORDER BY id DESC LIMIT 4",
                (st.session_state.driver_id,)
            ).fetchall()
        if msgs:
            for msg_row in msgs:
                msg_txt = (msg_row[0] or "")[:60] + ("..." if len(str(msg_row[0] or "")) > 60 else "")
                msg_type = str(msg_row[1] or "")
                msg_time = str(msg_row[2] or "")[-8:] if msg_row[2] else ""
                icon = "🟢" if "GREENWAVE" in msg_type else "📡"
                st.markdown(f"""
                <div style="background:rgba(8,8,16,0.7); backdrop-filter:blur(8px); padding:14px 18px; border-radius:14px; margin-bottom:10px; border-left:4px solid rgba(0,245,255,0.5); font-size:13px; border:1px solid rgba(0,245,255,0.15); box-shadow:0 4px 20px rgba(0,0,0,0.3);">
                    <span style="color:#00f5ff;">{icon}</span> <span style="color:#e8e8f0; font-family:Exo 2,sans-serif;">{html.escape(msg_txt)}</span>
                    <span style="color:rgba(0,245,255,0.5); font-size:10px; float:right; font-family:JetBrains Mono,sans-serif;">{msg_time}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:rgba(8,8,16,0.6); backdrop-filter:blur(8px); padding:24px; border-radius:14px; color:rgba(0,245,255,0.5); font-size:13px; text-align:center; border:1px solid rgba(0,245,255,0.15); font-family:Exo 2,sans-serif; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
                No messages yet — HQ will appear here
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.caption("Unable to load messages")

with tab_map:
    if st.session_state.status == "EN_ROUTE":
        dest = HOSPITALS.get(st.session_state.active_dst, [10.015, 76.34])
        start_pt = [st.session_state.gps_lat, st.session_state.gps_lon]
        routes = st.session_state.route_alternatives if st.session_state.route_alternatives else fetch_all_routes(start_pt, dest)
        rid = min(st.session_state.selected_route_id, len(routes) - 1) if routes else 0
        best = routes[rid] if routes else {"coords": [start_pt, dest], "dist": 0, "eta": 0, "route_type": "—"}

        m = folium.Map(location=start_pt, zoom_start=14, tiles="CartoDB dark_matter")
        folium.Marker(start_pt, icon=folium.Icon(color="blue", icon="ambulance", prefix="fa"), popup="YOU").add_to(m)
        folium.Marker(dest, icon=folium.Icon(color="red", icon="flag"), popup="TARGET").add_to(m)
        folium.PolyLine(best["coords"], color="#00f3ff", weight=5, opacity=0.9).add_to(m)

        st_folium(m, height=350, width=None, returned_objects=[])
        
        st.markdown(f"""
        <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); padding:22px; border-radius:16px; margin:16px 0; border:1px solid rgba(0,245,255,0.25); border-left:4px solid #00f5ff; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 25px rgba(0,245,255,0.06);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="color:rgba(0,245,255,0.6); font-size:10px; font-family:JetBrains Mono,sans-serif;">ROUTE</div>
                    <div style="color:#00f5ff; font-family:Orbitron,sans-serif; font-size:18px; letter-spacing:2px;">{best.get('route_type', 'FASTEST')}</div>
                </div>
                <div style="text-align:right;">
                    <div style="color:rgba(0,245,255,0.6); font-size:10px; font-family:JetBrains Mono,sans-serif;">DELAY</div>
                    <div style="color:#ff00ff; font-size:14px; font-family:JetBrains Mono,sans-serif; font-weight:700;">+{best.get('traffic_delay_min', 0)} min</div>
                </div>
            </div>
            <div style="display:flex; justify-content:space-around; margin-top:18px; padding-top:16px; border-top:1px solid rgba(0,245,255,0.15);">
                <div style="text-align:center;">
                    <div style="color:#00ff88; font-family:JetBrains Mono,sans-serif; font-size:22px; font-weight:700;">{best.get('dist', 0)}</div>
                    <div style="color:rgba(0,245,255,0.5); font-size:10px; font-family:JetBrains Mono,sans-serif;">km</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:#00f5ff; font-family:JetBrains Mono,sans-serif; font-size:22px; font-weight:700;">{best.get('eta', 0)}</div>
                    <div style="color:rgba(0,245,255,0.5); font-size:10px; font-family:JetBrains Mono,sans-serif;">min ETA</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:#e8e8f0; font-family:JetBrains Mono,sans-serif; font-size:22px; font-weight:700;">{(datetime.datetime.now() + datetime.timedelta(minutes=best.get('eta', 0))).strftime('%H:%M')}</div>
                    <div style="color:rgba(0,245,255,0.5); font-size:10px; font-family:JetBrains Mono,sans-serif;">arrival</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Turn-by-turn directions (collapsible)
        with st.expander("Turn-by-turn directions"):
            instructions = best.get('instructions', [])
            if instructions:
                for i, ins in enumerate(instructions[:8]):
                    msg = ins if isinstance(ins, str) else (ins.get('message', '') if isinstance(ins, dict) else str(ins))
                    icon = "➡️" if "right" in msg.lower() else "⬅️" if "left" in msg.lower() else "⬆️"
                    st.markdown(f"""
                    <div style="padding:10px 8px; border-bottom:1px solid #222; display:flex; align-items:center; font-family:'Space Grotesk';">
                        <span style="font-size:16px; margin-right:10px;">{icon}</span>
                        <span style="color:#f5f5f5; font-size:12px;">{msg}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Follow the highlighted route on the map.")

        # Navigate to destination
        if dest and len(dest) >= 2:
            nav_url = f"https://www.google.com/maps/dir/?api=1&destination={dest[0]},{dest[1]}&travelmode=driving"
            st.link_button("📍 Open in Google Maps", nav_url, use_container_width=True, help="Navigate to destination")
        st.markdown("#### Status updates")
        arr1, arr2 = st.columns([1, 1])
        with arr1:
            if st.button("Arrived at pickup", use_container_width=True, key="arr_pickup"):
                send_msg("STATUS", f"ARRIVED AT PICKUP - {st.session_state.driver_id} at {st.session_state.active_org}")
                st.toast("Arrival at pickup reported to HQ", icon="📍")
                st.rerun()
        with arr2:
            if st.button("Arrived at hospital", use_container_width=True, key="arr_hospital"):
                send_msg("STATUS", f"ARRIVED AT HOSPITAL - {st.session_state.driver_id} at {st.session_state.active_dst}")
                st.toast("Arrival at hospital reported", icon="🏥")
                st.rerun()
        st.markdown("---")
        c_sim, c_end = st.columns([1, 1])
        with c_sim:
            if st.button("Move forward"):
                st.session_state.gps_lat += (dest[0] - st.session_state.gps_lat) * 0.15
                st.session_state.gps_lon += (dest[1] - st.session_state.gps_lon) * 0.15
                update_server(st.session_state.active_org, st.session_state.active_dst, "EN_ROUTE")
                heartbeat()
                st.rerun()
            if st.button("Auto-pilot"):
                run_auto_pilot(best["coords"])
                st.rerun()
        with c_end:
            if st.session_state.pending_end_trip:
                st.warning("End trip?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes, end trip", key="confirm_end"):
                        st.session_state.pending_end_trip = False
                        st.session_state.status = "IDLE"
                        st.session_state.route_alternatives = []
                        st.session_state.route_selection_pending = False
                        update_server("NONE", "NONE", "IDLE")
                        if st.session_state.active_mission_id:
                            mid_complete = st.session_state.active_mission_id
                            org_d = st.session_state.active_org or "—"
                            dst_d = st.session_state.active_dst or "—"
                            try:
                                with sqlite3.connect(DB_FILE) as conn:
                                    conn.execute("UPDATE missions SET status='COMPLETED', completed_at=? WHERE mission_id=?", (datetime.datetime.now(), mid_complete))
                                    row = conn.execute("SELECT accepted_at FROM missions WHERE mission_id=?", (mid_complete,)).fetchone()
                                    if row and row[0] and org_d in HOSPITALS and dst_d in HOSPITALS:
                                        accepted = pd.to_datetime(row[0], errors="coerce")
                                        if pd.notna(accepted):
                                            actual_min = (datetime.datetime.now() - accepted).total_seconds() / 60
                                            dist = distance_km(HOSPITALS[org_d][0], HOSPITALS[org_d][1], HOSPITALS[dst_d][0], HOSPITALS[dst_d][1])
                                            avg_speed = round(dist / (actual_min / 60), 1) if actual_min > 0 else 0
                                            time_saved = max(0, round(actual_min * 0.1, 1))
                                            co2_saved = round(calculate_co2_savings(dist, time_saved), 2)
                                            conn.execute(
                                                "UPDATE mission_logs SET time_saved=?, co2_saved=?, avg_speed=? WHERE mission_id=?",
                                                (time_saved, co2_saved, avg_speed, mid_complete),
                                            )
                                    conn.commit()
                                send_msg("STATUS", f"MISSION COMPLETE - {mid_complete} by {st.session_state.driver_id}. {org_d} → {dst_d}")
                            except Exception:
                                pass
                            log_activity("COMPLETE", st.session_state.driver_id, mid_complete)
                        st.session_state.active_mission_id = None
                        heartbeat()
                        st.rerun()
                with c2:
                    if st.button("Cancel", key="cancel_end"):
                        st.session_state.pending_end_trip = False
                        st.rerun()
            elif st.button("End trip", key="end_trip_btn"):
                st.session_state.pending_end_trip = True
                st.rerun()
    
    else:
        st.markdown("### Manual navigation")
        
        # Build location options: Favourites + Current + Custom + all hospitals
        CURRENT_LOC_LABEL = "📍 CURRENT LOCATION"
        CUSTOM_LOC_LABEL = "📌 CUSTOM COORDINATES"
        favs = [h for h in (st.session_state.favourite_hospitals or []) if h in HOSPITALS]
        start_options = [CURRENT_LOC_LABEL, CUSTOM_LOC_LABEL] + favs + [h for h in sorted(HOSPITALS.keys()) if h not in favs]
        end_options = sorted(HOSPITALS.keys())
        
        c1, c2 = st.columns(2)
        with c1: org_selection = st.selectbox("START", start_options, key="m_org")
        with c2: dst = st.selectbox("END", end_options, key="m_dst")
        
        # Custom coordinates input (show only when selected)
        custom_lat, custom_lon = st.session_state.gps_lat, st.session_state.gps_lon
        if org_selection == CUSTOM_LOC_LABEL:
            st.markdown("##### Enter custom start coordinates")
            cc1, cc2 = st.columns(2)
            with cc1:
                custom_lat = st.number_input("Latitude", value=st.session_state.gps_lat, format="%.6f", key="custom_lat")
            with cc2:
                custom_lon = st.number_input("Longitude", value=st.session_state.gps_lon, format="%.6f", key="custom_lon")
        
        # Resolve org coordinates
        if org_selection == CURRENT_LOC_LABEL:
            org_coords = [st.session_state.gps_lat, st.session_state.gps_lon]
            org_label = f"Current ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f})"
        elif org_selection == CUSTOM_LOC_LABEL:
            org_coords = [custom_lat, custom_lon]
            org_label = f"Custom ({custom_lat:.4f}, {custom_lon:.4f})"
        else:
            org_coords = HOSPITALS.get(org_selection, [st.session_state.gps_lat, st.session_state.gps_lon])
            org_label = org_selection
        
        dst_coords = HOSPITALS.get(dst, [10.015, 76.34])
        
        # If we have 4 route options ready for this org/dst, show selection
        routes_ready = (st.session_state.manual_route_alternatives and
                        st.session_state.manual_route_org == org_selection and
                        st.session_state.manual_route_dst == dst and
                        len(st.session_state.manual_route_alternatives) >= 1)
        
        if not routes_ready:
            if st.button("Get route options", use_container_width=True):
                if org_selection not in [CURRENT_LOC_LABEL, CUSTOM_LOC_LABEL] and org_selection == dst:
                    st.warning("Please select different start and end locations.")
                else:
                    with st.spinner("Loading routes..."):
                        opts = fetch_all_routes(org_coords, dst_coords)
                        st.session_state.manual_route_alternatives = opts[:4] if opts else []
                        st.session_state.manual_route_org = org_selection
                        st.session_state.manual_route_dst = dst
                    st.rerun()
        else:
            opts = st.session_state.manual_route_alternatives
            st.markdown("#### Choose route")
            st.markdown(f"""
            <div style="color:rgba(0,245,255,0.7); font-size:14px; margin-bottom:18px; padding:16px 20px; background:rgba(8,8,16,0.7); border-radius:14px; border:1px solid rgba(0,245,255,0.2); font-family:Exo 2,sans-serif; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
                <span style="color:#00f5ff;">From</span> {org_label} <span style="color:rgba(0,245,255,0.3);">→</span> <span style="color:#ff00ff;">To</span> {dst}
            </div>
            """, unsafe_allow_html=True)
            route_colors = ["#06b6d4", "#f59e0b", "#10b981", "#ec4899"]
            for idx, opt in enumerate(opts):
                c = route_colors[idx % len(route_colors)]
                is_best = idx == 0
                m_col1, m_col2 = st.columns([3, 1])
                with m_col1:
                    st.markdown(f"""
                    <div class="route-card{' route-card-best' if is_best else ''}">
                        <div style="font-weight:700; color:#e8e8f0; font-size:15px; font-family:Orbitron,sans-serif; letter-spacing:2px;">{opt.get('route_type', f'Route {idx+1}')}</div>
                        <div style="display:flex; align-items:center; gap:14px; margin-top:10px; font-size:13px; font-family:JetBrains Mono,sans-serif;">
                            <span style="color:#00f5ff; font-weight:700;">{opt.get('eta', 0)} min</span>
                            <span style="color:rgba(0,245,255,0.3);">|</span>
                            <span style="color:rgba(0,245,255,0.6);">{opt.get('dist', 0)} km</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with m_col2:
                    if st.button(f"Select", key=f"manual_sel_{idx}", use_container_width=True):
                        selected_idx = idx
                        st.session_state.active_org = org_label
                        st.session_state.active_dst = dst
                        st.session_state.status = "EN_ROUTE"
                        st.session_state.selected_route_id = selected_idx
                        st.session_state.route_alternatives = list(opts)
                        if org_selection != CURRENT_LOC_LABEL:
                            st.session_state.gps_lat, st.session_state.gps_lon = org_coords[0], org_coords[1]
                        st.session_state.manual_route_alternatives = []
                        st.session_state.manual_route_org = None
                        st.session_state.manual_route_dst = None
                        update_server(org_label, dst, "EN_ROUTE")
                        heartbeat()
                        st.rerun()
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            if st.button("Choose other routes", use_container_width=True):
                    st.session_state.manual_route_alternatives = []
                    st.session_state.manual_route_org = None
                    st.session_state.manual_route_dst = None
                    st.rerun()

with tab_comms:
    st.markdown("### 📶 Communications")
    st.caption("One-tap actions at top — no scrolling while driving")
    
    # ========== TOP: ONE-TAP ACTIONS (no scroll needed) ==========
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown("**⚡ Quick reply**")
    qr1, qr2, qr3 = st.columns(3)
    QUICK_REPLIES = [
        ("Copy", "Copy. Acknowledged."),
        ("ETA 5 min", "ETA 5 minutes to destination."),
        ("On my way", "On my way to pickup."),
        ("Arrived", "Arrived at scene."),
        ("En route", "En route to hospital."),
        ("Delayed", "Traffic delay — ETA updated."),
    ]
    for i, (label, msg) in enumerate(QUICK_REPLIES):
        with [qr1, qr2, qr3][i % 3]:
            if st.button(f"📤 {label}", key=f"qr_{i}", use_container_width=True):
                send_msg("STATUS", f"{st.session_state.driver_id}: {msg}")
                st.toast(f"Sent: {label}", icon="✅")
                st.rerun()
    
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.markdown("**🆘 Emergency & status**")
    em1, em2, em3, em4 = st.columns(4)
    with em1:
        if st.button("🆘 SOS", use_container_width=True, type="primary", key="sos_btn"):
            send_msg("CRITICAL", f"🆘 SOS - {st.session_state.driver_id} EMERGENCY at ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f}) - Immediate assistance required!")
            st.toast("SOS sent! Help is on the way.", icon="🆘")
            st.error("SOS sent to HQ. Help is on the way.")
            st.rerun()
    with em2:
        if st.button("🟢 Green", use_container_width=True):
            st.session_state.clearance_status = "PENDING"
            heartbeat()
            send_msg("REQUEST", f"GREEN WAVE REQUEST from {st.session_state.driver_id} - Location: {st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f}")
            st.toast("Green Wave requested", icon="🟢")
            st.rerun()
    with em3:
        if st.button("👤 Patient", use_container_width=True):
            send_msg("STATUS", f"PATIENT SECURED - {st.session_state.driver_id} en route to {st.session_state.active_dst or 'destination'}")
            st.toast("Status sent", icon="✅")
            st.rerun()
    with em4:
        if st.button("🚧 Obstruction", use_container_width=True):
            send_msg("WARNING", f"TRAFFIC OBSTRUCTION - {st.session_state.driver_id}. Requesting alternate route.")
            st.toast("Reported", icon="⚠️")
            st.rerun()
    
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.markdown("**⚠️ Report & share**")
    rp1, rp2, rp3 = st.columns(3)
    with rp1:
        hazard_type = st.selectbox("Hazard type", ["ACCIDENT", "ROAD CLOSURE", "FLOODING", "DEBRIS", "SIGNAL", "OTHER"], label_visibility="collapsed", key="hazard_sel")
    with rp2:
        if st.button("⚠️ Report hazard", use_container_width=True, key="report_haz"):
            try:
                report_hazard(hazard_type)
                send_msg("WARNING", f"HAZARD: {hazard_type} at ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f})")
                st.toast(f"Hazard reported", icon="⚠️")
            except Exception:
                st.error("Failed to report")
            st.rerun()
    with rp3:
        if st.button("📍 Share location", use_container_width=True):
            send_msg("STATUS", f"LOCATION - {st.session_state.driver_id}: ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f})")
            st.toast("Location shared!")
            st.rerun()
    
    if st.session_state.clearance_status == "PENDING":
        st.markdown("""
        <div style="background:rgba(255,0,255,0.08); border:1px solid rgba(255,0,255,0.4); border-radius:10px; color:#ff00ff; padding:10px; text-align:center; font-size:11px; font-family:JetBrains Mono,sans-serif; letter-spacing:1px;">
            ● PENDING — Awaiting HQ
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("**📬 Messages from HQ** (live 3s)")
    
    @st.fragment(run_every=3)
    def _hq_messages_live():
        try:
            conn = sqlite3.connect(DB_FILE)
            hq_msgs = pd.read_sql_query(
                "SELECT * FROM driver_comms WHERE status LIKE 'HQ%' OR driver_id = 'ALL' OR driver_id = ? ORDER BY id DESC LIMIT 10",
                conn,
                params=(st.session_state.driver_id,)
            )
            conn.close()
            
            if not hq_msgs.empty:
                max_id = int(hq_msgs.iloc[0].get('id', 0) or 0)
                if st.session_state.get("last_seen_hq_message_id", 0) == 0:
                    st.session_state.last_seen_hq_message_id = max_id
                for _, row in hq_msgs.iterrows():
                    msg_time = row.get('timestamp', '')
                    msg_text = row.get('message', '')
                    msg_type = row.get('status', '')
                    color = "#00ff9d" if 'GREENWAVE' in msg_type else "#ff003c" if 'ALERT' in msg_type else "#00f3ff"
                    icon = "🟢" if 'GREENWAVE' in msg_type else "🔴" if 'ALERT' in msg_type else "📡"
                    msg_esc = html.escape(str(msg_text))
                    st.markdown(f"""
                    <div style="background:rgba(8,8,16,0.7); border-left:4px solid {color}; padding:12px 14px; margin-bottom:8px; border-radius:10px; border:1px solid rgba(0,245,255,0.1);">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:{color}; font-weight:700; font-size:11px;">{icon} HQ</span>
                            <span style="color:rgba(0,245,255,0.4); font-size:10px;">{msg_time}</span>
                        </div>
                        <div style="color:#e8e8f0; font-size:13px; line-height:1.4;">{msg_esc}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("No messages yet — popup + sound when HQ sends")
        except Exception:
            st.caption("Unable to load messages")
    
    _hq_messages_live()
    
    # Extra actions in expander (optional, when parked)
    with st.expander("More actions (when parked)"):
        if st.button("🔴 Emergency preempt", use_container_width=True, key="emerg_preempt"):
            st.session_state.clearance_status = "PENDING"
            heartbeat()
            send_msg("REQUEST", f"⚠️ EMERGENCY PREEMPTION from {st.session_state.driver_id} - CRITICAL patient transport. Immediate signal clearance required!")
            st.toast("Emergency preemption requested", icon="🔴")
            st.rerun()
        if st.button("⛽ Low fuel", use_container_width=True, key="low_fuel"):
            send_msg("WARNING", f"LOW FUEL - {st.session_state.driver_id}")
            st.toast("Alert sent", icon="⚠️")
            st.rerun()
        if st.button("🔧 Mechanical issue", use_container_width=True, key="mech"):
            send_msg("WARNING", f"MECHANICAL - {st.session_state.driver_id}")
            st.toast("Alert sent", icon="⚠️")
            st.rerun()
        with st.form("driver_msg_form"):
            custom_msg = st.text_area("Custom message", placeholder="Type message...", height=60, key="custom_msg")
            if st.form_submit_button("📤 Send"):
                if custom_msg:
                    send_msg("REQUEST", f"{st.session_state.driver_id}: {custom_msg}")
                    st.toast("Sent", icon="✅")
                    st.rerun()
                else:
                    st.error("Enter a message.")

# ==========================================
# TAB: STATS - Shift & Performance
# ==========================================
with tab_stats:
    st.markdown("### Shift statistics")
    
    shift_dur = int((time.time() - st.session_state.shift_start) / 60)
    
    try:
        conn = sqlite3.connect(DB_FILE)
        completed = conn.execute(
            "SELECT COUNT(*) FROM missions WHERE status='COMPLETED' AND assigned_driver_id=?",
            (st.session_state.driver_id,)
        ).fetchone()[0]
        conn.close()
    except Exception:
        completed = 0
    
    stats_cols = st.columns([1, 1, 1, 1])
    with stats_cols[0]:
        st.markdown(f"""
        <div class="widget-box">
            <div class="w-title">Shift time</div>
            <div class="w-val">{shift_dur} min</div>
        </div>
        """, unsafe_allow_html=True)
    with stats_cols[1]:
        st.markdown(f"""
        <div class="widget-box">
            <div class="w-title">Missions done</div>
            <div class="w-val">{completed}</div>
        </div>
        """, unsafe_allow_html=True)
    with stats_cols[2]:
        status_label = "En route" if st.session_state.status == "EN_ROUTE" else "Idle"
        status_color = "#00ff88" if st.session_state.status == "EN_ROUTE" else "#00f5ff"
        st.markdown(f"""
        <div class="widget-box">
            <div class="w-title">Status</div>
            <div class="w-val" style="color:{status_color};">{status_label}</div>
        </div>
        """, unsafe_allow_html=True)
    with stats_cols[3]:
        avg_speed = random.randint(48, 65) if st.session_state.status == "EN_ROUTE" else 0
        st.markdown(f"""
        <div class="widget-box">
            <div class="w-title">Avg speed</div>
            <div class="w-val">{avg_speed} km/h</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("#### Performance")
    st.progress(min(0.95, 0.3 + completed * 0.15))
    st.caption("Performance score based on mission completion rate")
    
    st.markdown("---")
    st.markdown("#### Today's summary")
    st.info("Complete more missions to unlock detailed analytics.")

# ==========================================
# TAB: ALERTS - Nearby Hazards & Traffic
# ==========================================
with tab_alerts:
    st.markdown("### Nearby alerts")
    st.caption("Updates automatically every 5 seconds.")
    
    @st.fragment(run_every=5)
    def _alerts_live():
        try:
            conn = sqlite3.connect(DB_FILE)
            hazards = pd.read_sql_query(
                "SELECT * FROM hazards ORDER BY id DESC LIMIT 15",
                conn
            )
            conn.close()
            
            if not hazards.empty:
                hazards["dist_km"] = hazards.apply(
                    lambda r: distance_km(st.session_state.gps_lat, st.session_state.gps_lon, r["lat"], r["lon"]),
                    axis=1
                )
                hazards = hazards.sort_values("dist_km")
                
                for _, h in hazards.head(8).iterrows():
                    dist = h.get("dist_km", 0)
                    if dist < 2:
                        color = "#ff0050"
                        badge = "CRITICAL"
                    elif dist < 5:
                        color = "#ff00ff"
                        badge = "NEARBY"
                    else:
                        color = "#00f5ff"
                        badge = "AHEAD"
                    h_type = str(h.get('type', 'Hazard'))[:60]
                    st.markdown(f"""
                    <div style="background:rgba(8,8,16,0.7); backdrop-filter:blur(8px); border-left:4px solid {color}; border-radius:14px; padding:18px; margin-bottom:14px; border:1px solid rgba(0,245,255,0.15); display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
                        <div style="display:flex; align-items:flex-start; gap:14px; flex:1; min-width:200px;">
                            <span style="width:44px; height:44px; background:{color}22; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:22px; flex-shrink:0;">⚠️</span>
                            <div>
                                <div style="color:#e8e8f0; font-weight:700; font-size:14px; font-family:Exo 2,sans-serif;">{h_type}</div>
                                <div style="color:rgba(0,245,255,0.5); font-size:11px; margin-top:4px; font-family:JetBrains Mono,sans-serif;">Reported by driver</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px; flex-shrink:0;">
                            <span style="background:{color}33; color:{color}; padding:8px 14px; border-radius:10px; font-size:10px; font-weight:700; font-family:JetBrains Mono,sans-serif; letter-spacing:2px;">{badge}</span>
                            <span style="color:{color}; font-weight:700; font-size:15px; font-family:JetBrains Mono,sans-serif;">{dist:.1f} km</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:rgba(8,8,16,0.7); backdrop-filter:blur(12px); border:1px solid rgba(0,255,136,0.4); border-left:4px solid #00ff88; border-radius:16px; padding:36px; text-align:center; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,255,136,0.08);">
                    <div style="font-size:44px; margin-bottom:14px;">✅</div>
                    <div style="color:#00ff88; font-weight:700; font-size:18px; font-family:Orbitron,sans-serif; letter-spacing:3px;">NO HAZARDS NEARBY</div>
                    <div style="color:rgba(0,245,255,0.6); font-size:14px; margin-top:8px; font-family:Exo 2,sans-serif;">Clear roads ahead</div>
                </div>
                """, unsafe_allow_html=True)
        except Exception:
            st.info("Unable to fetch hazards.")
    
    _alerts_live()
    
    st.markdown("---")
    st.markdown("#### Traffic status")
    st.markdown("""
    <div style="background:rgba(8,8,16,0.7); backdrop-filter:blur(8px); border:1px solid rgba(0,245,255,0.2); border-radius:16px; padding:20px; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
        <div style="color:#00ff88; font-weight:700; font-size:15px; font-family:Orbitron,sans-serif; letter-spacing:3px;">LIVE TRAFFIC</div>
        <div style="color:rgba(0,245,255,0.6); font-size:13px; margin-top:8px; font-family:Exo 2,sans-serif;">Green Wave & V2X synced with HQ</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# TAB: MY MISSIONS - History
# ==========================================
with tab_missions:
    st.markdown("### Mission history")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        my_missions = pd.read_sql_query(
            """
            SELECT mission_id, created_at, origin, destination, priority, status, completed_at
            FROM missions
            WHERE assigned_driver_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            conn,
            params=(st.session_state.driver_id,)
        )
        conn.close()
        
        if not my_missions.empty:
            for i, (_, m) in enumerate(my_missions.iterrows()):
                status = m.get("status", "?")
                status_color = "#00ff88" if status == "COMPLETED" else "#00f5ff" if status == "ACCEPTED" else "#ff00ff"
                dst_name = m.get("destination", "?")
                dst_coords = HOSPITALS.get(dst_name)
                st.markdown(f"""
                <div class="route-card" style="border-left-color:{status_color};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="color:#e8e8f0; font-weight:700; font-family:JetBrains Mono,sans-serif;">{m.get('mission_id', '?')}</span>
                        <span style="color:{status_color}; font-size:10px; font-family:JetBrains Mono,sans-serif; letter-spacing:2px;">{status}</span>
                    </div>
                    <div style="color:rgba(0,245,255,0.7); font-size:14px; margin-top:10px; font-family:Exo 2,sans-serif;">{m.get('origin','?')} → {dst_name}</div>
                    <div style="color:rgba(0,245,255,0.4); font-size:11px; margin-top:6px; font-family:JetBrains Mono,sans-serif;">{m.get('created_at','')}</div>
                </div>
                """, unsafe_allow_html=True)
                if dst_coords and len(dst_coords) >= 2:
                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={dst_coords[0]},{dst_coords[1]}&travelmode=driving"
                    st.link_button("📍 Navigate", nav_url, key=f"nav_mission_{i}", use_container_width=True)
        else:
            st.info("No mission history yet. Accept a mission to get started!")
    except Exception:
        st.info("Unable to load mission history.")

# ==========================================
# TAB: SETTINGS - Profile & Preferences
# ==========================================
with tab_settings:
    st.markdown("### Settings")
    
    st.markdown("#### Profile")
    _prof = get_driver_profile(st.session_state.driver_id)
    if _prof:
        st.markdown(f"""
        <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.25); border-left:4px solid #00f5ff; border-radius:16px; padding:26px; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.06);">
            <div style="color:#00f5ff; font-weight:700; font-size:22px; font-family:Orbitron,sans-serif; letter-spacing:4px;">{_prof.get('driver_id', st.session_state.driver_id)}</div>
            <div style="color:rgba(0,245,255,0.7); font-size:14px; margin-top:6px; font-family:Exo 2,sans-serif;">{_prof.get('full_name') or '—'}</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px 28px; margin-top:20px; font-size:14px; font-family:Exo 2,sans-serif;">
                <div><span style="color:rgba(0,245,255,0.5); font-size:10px; font-family:JetBrains Mono,sans-serif;">VEHICLE</span><br><span style="color:#e8e8f0;">{_prof.get('vehicle_id') or '—'}</span></div>
                <div><span style="color:rgba(0,245,255,0.5); font-size:10px; font-family:JetBrains Mono,sans-serif;">BASE</span><br><span style="color:#e8e8f0;">{_prof.get('base_hospital') or '—'}</span></div>
                <div><span style="color:rgba(0,245,255,0.5); font-size:10px; font-family:JetBrains Mono,sans-serif;">PHONE</span><br><span style="color:#e8e8f0;">{_prof.get('phone') or '—'}</span></div>
            </div>
            <div style="color:#00ff88; font-size:11px; margin-top:18px; font-weight:700; font-family:JetBrains Mono,sans-serif; letter-spacing:2px;">● CONNECTED</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:rgba(8,8,16,0.8); backdrop-filter:blur(12px); border:1px solid rgba(0,245,255,0.25); border-left:4px solid #00f5ff; border-radius:16px; padding:26px; box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 30px rgba(0,245,255,0.06);">
            <div style="color:#00f5ff; font-weight:700; font-size:22px; font-family:Orbitron,sans-serif; letter-spacing:4px;">{st.session_state.driver_id}</div>
            <div style="color:#00ff88; font-size:11px; margin-top:10px; font-weight:700; font-family:JetBrains Mono,sans-serif; letter-spacing:2px;">● CONNECTED</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("#### Favourite hospitals")
    st.caption("Add hospitals to show at top in Manual Navigation")
    fav_default = [h for h in (st.session_state.favourite_hospitals or []) if h in HOSPITALS]
    fav_hospitals = st.multiselect("Select favourites", sorted(HOSPITALS.keys()), default=fav_default, key="fav_hospitals")
    st.session_state.favourite_hospitals = [h for h in fav_hospitals if h in HOSPITALS]
    
    st.markdown("---")
    st.markdown("#### Notifications")
    notif_sound = st.toggle("🔊 Sound alerts for new missions & HQ messages", value=st.session_state.get("sounds_enabled", False), key="notif_sound")
    if notif_sound != st.session_state.get("sounds_enabled"):
        st.session_state.sounds_enabled = notif_sound
        if notif_sound:
            # st.audio does NOT support key parameter - omit it
            st.audio(SOUND_MISSION, format="audio/mpeg", autoplay=True)
            st.toast("Notification sounds enabled! You'll hear alerts for missions and HQ messages.", icon="🔊")
        # Don't rerun immediately - lets the audio widget render and play
    
    st.markdown("---")
    st.markdown("#### Navigation")
    st.caption("Voice turn-by-turn and live traffic updates — coming in future release")
    
    st.markdown("---")
    st.markdown("#### App info")
    st.markdown("""
    <div style="color:rgba(0,245,255,0.6); font-size:13px; margin-top:24px; font-family:Exo 2,sans-serif;">
        <span style="color:#00f5ff; font-weight:700; font-family:Orbitron,sans-serif;">TITAN DRIVER OS v52</span> - Real-time sync with HQ<br>
        <span style="color:rgba(0,245,255,0.4); font-size:12px;">Missions, comms, location - all shared via HQ</span>
    </div>
    """, unsafe_allow_html=True)