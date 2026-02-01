
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
import sys
import os
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
from shared_utils import fetch_route_alternatives_4, distance_km, hash_password, verify_password

DB_FILE = os.path.join(_APP_DIR, "titan_v52.db")
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

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800&family=Rajdhani:wght@300;400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp { 
        background: linear-gradient(165deg, #050608 0%, #0a0d12 40%, #080b0f 80%, #060809 100%) !important;
        color: #e6edf3 !important;
    }
    
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    
    .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 680px !important; }
    
    /* HEADER */
    .mobile-header {
        background: linear-gradient(145deg, rgba(20,24,34,0.98), rgba(12,16,24,0.99));
        backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
        padding: 20px 24px; border-radius: 18px;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 24px;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04);
    }
    
    /* SPEEDOMETER */
    .speed-circle {
        width: 210px; height: 210px; border-radius: 50%;
        margin: 0 auto; display: flex; flex-direction: column; justify-content: center; align-items: center;
        background: radial-gradient(circle at 30% 30%, rgba(30,36,48,0.9), rgba(6,8,12,0.98));
        border: 2px solid rgba(255,255,255,0.06);
        box-shadow: inset 0 0 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(6,182,212,0.2), 0 20px 40px rgba(0,0,0,0.4);
    }
    .speed-val { font-family: 'Orbitron'; font-size: 58px; font-weight: 700; color: #fff; line-height: 1; letter-spacing: -2px; text-shadow: 0 0 30px rgba(6,182,212,0.3); }
    .speed-unit { font-family: 'Rajdhani'; font-size: 11px; color: #6b7280; letter-spacing: 5px; margin-top: 6px; }
    
    /* METRIC CARDS */
    .widget-box { 
        background: linear-gradient(145deg, rgba(24,28,38,0.95), rgba(14,18,26,0.98));
        border-radius: 16px; padding: 20px;
        text-align: center; border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .widget-box:hover { 
        border-color: rgba(6,182,212,0.25); 
        box-shadow: 0 8px 28px rgba(6,182,212,0.15);
        transform: translateY(-2px);
    }
    .w-title { color: #6b7280; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; font-family: 'Inter'; font-weight: 600; }
    .w-val { color: #e6edf3; font-size: 24px; font-family: 'Orbitron'; font-weight: 600; margin-top: 6px; }
    
    /* SEXY BUTTONS - Base */
    .stButton > button { 
        width: 100% !important; min-height: 52px !important; border-radius: 14px !important;
        font-family: 'Inter' !important; font-size: 14px !important; font-weight: 600 !important;
        background: linear-gradient(145deg, rgba(35,40,52,0.98), rgba(22,26,36,0.98)) !important;
        color: #e6edf3 !important; border: 1px solid rgba(255,255,255,0.1) !important;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05) !important;
    }
    .stButton > button:hover { 
        background: linear-gradient(145deg, rgba(6,182,212,0.2), rgba(6,182,212,0.08)) !important;
        border-color: rgba(6,182,212,0.5) !important;
        box-shadow: 0 8px 24px rgba(6,182,212,0.2) !important;
        transform: translateY(-2px) scale(1.01);
    }
    .stButton > button:active { transform: translateY(0) scale(0.99); }
    
    /* Accept / Primary */
    .accept-btn button { 
        background: linear-gradient(135deg, #10b981 0%, #059669 50%, #047857 100%) !important; 
        color: #fff !important; border: none !important;
        box-shadow: 0 4px 20px rgba(16,185,129,0.4), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    }
    .accept-btn button:hover { 
        background: linear-gradient(135deg, #34d399 0%, #10b981 50%, #059669 100%) !important;
        box-shadow: 0 8px 32px rgba(16,185,129,0.5) !important;
        transform: translateY(-2px);
    }
    
    /* Auto / Secondary */
    .auto-btn button { 
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #b45309 100%) !important; 
        color: #fff !important; border: none !important;
        box-shadow: 0 4px 20px rgba(245,158,11,0.35), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    }
    .auto-btn button:hover { 
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%) !important;
        box-shadow: 0 8px 28px rgba(245,158,11,0.45) !important;
        transform: translateY(-2px);
    }
    
    /* End / Danger */
    .end-btn button { 
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%) !important; 
        color: #fff !important; border: none !important;
        box-shadow: 0 4px 20px rgba(239,68,68,0.35), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    }
    .end-btn button:hover { 
        background: linear-gradient(135deg, #f87171 0%, #ef4444 50%, #dc2626 100%) !important;
        box-shadow: 0 8px 28px rgba(239,68,68,0.5) !important;
        transform: translateY(-2px);
    }
    
    /* CARDS */
    .route-card {
        background: linear-gradient(145deg, rgba(24,28,38,0.9), rgba(14,18,26,0.95));
        border-left: 4px solid #4b5563;
        padding: 18px; margin-bottom: 14px; border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.05);
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }
    .route-card-best {
        background: linear-gradient(145deg, rgba(6,182,212,0.12), rgba(6,182,212,0.03));
        border-left: 4px solid #06b6d4;
        border-color: rgba(6,182,212,0.4);
        box-shadow: 0 4px 24px rgba(6,182,212,0.15);
    }
    
    /* MISSION ALERT */
    .mission-alert {
        background: linear-gradient(145deg, rgba(220,38,38,0.12), rgba(220,38,38,0.04));
        border: 1px solid rgba(220,38,38,0.4);
        border-radius: 18px; padding: 28px; margin: 24px 0;
        box-shadow: 0 8px 32px rgba(220,38,38,0.2), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    /* Accept button (first button after mission-alert) gets green styling */
    .mission-alert ~ * .stButton > button:first-of-type,
    .block-container > div:has(.mission-alert) + div .stButton > button:first-of-type {
        background: linear-gradient(135deg, #10b981 0%, #059669 50%, #047857 100%) !important;
        color: #fff !important; border: none !important;
        box-shadow: 0 4px 20px rgba(16,185,129,0.4), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    }
    .mission-alert ~ * .stButton > button:first-of-type:hover,
    .block-container > div:has(.mission-alert) + div .stButton > button:first-of-type:hover {
        background: linear-gradient(135deg, #34d399 0%, #10b981 50%, #059669 100%) !important;
        box-shadow: 0 8px 32px rgba(16,185,129,0.5) !important;
    }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] { 
        background: rgba(18,22,30,0.9) !important; 
        border-radius: 16px !important; 
        padding: 8px !important; 
        gap: 6px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
    .stTabs [data-baseweb="tab"] { 
        border-radius: 12px !important; 
        font-family: 'Inter' !important; 
        font-weight: 500 !important;
        padding: 10px 16px !important;
    }
    .stTabs [aria-selected="true"] { 
        background: linear-gradient(135deg, rgba(6,182,212,0.25), rgba(6,182,212,0.1)) !important;
        border: 1px solid rgba(6,182,212,0.3) !important;
    }
    
    /* INPUT FIELDS */
    .stTextInput input, .stTextArea textarea { 
        background: rgba(18,22,30,0.95) !important; 
        border-radius: 12px !important; 
        border: 1px solid rgba(255,255,255,0.08) !important;
        padding: 12px 16px !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus { border-color: rgba(6,182,212,0.5) !important; box-shadow: 0 0 0 3px rgba(6,182,212,0.15) !important; }
    
    /* FORM SUBMIT */
    [data-testid="stFormSubmitButton"] button { 
        background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%) !important;
        color: #fff !important; font-weight: 700 !important;
        box-shadow: 0 4px 20px rgba(6,182,212,0.4) !important;
    }
    [data-testid="stFormSubmitButton"] button:hover { box-shadow: 0 8px 28px rgba(6,182,212,0.5) !important; }
    
    /* ACTION BAR PILLS */
    .action-pill { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 999px; font-weight: 600; font-size: 13px; transition: all 0.2s; }
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
        c.execute(
            "INSERT OR IGNORE INTO driver_accounts (driver_id, username, password, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
            ("UNIT-07", "UNIT-07", hash_password("TITAN-DRIVER"), "Demo Driver", datetime.datetime.now()),
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
    <div style="text-align:center; padding:56px 24px 40px;">
        <div style="width:96px; height:96px; margin:0 auto 28px; background:linear-gradient(145deg,rgba(24,28,38,0.95),rgba(14,18,26,0.98)); border-radius:24px; display:flex; align-items:center; justify-content:center; border:1px solid rgba(255,255,255,0.1); box-shadow:0 12px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.08);">
            <span style="font-size:44px;">🚑</span>
        </div>
        <div style="font-family:'Orbitron'; font-size:30px; font-weight:700; color:#e6edf3; letter-spacing:4px;">TITAN DRIVER</div>
        <div style="color:#6b7280; font-size:13px; letter-spacing:4px; margin-top:10px; font-family:'Inter';">FLEET OPERATIONS PLATFORM</div>
        <div style="height:2px; background:linear-gradient(90deg,transparent,rgba(6,182,212,0.5),transparent); margin:32px auto; max-width:200px; border-radius:1px;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    auth_tab1, auth_tab2 = st.tabs(["Sign In", "Create Account"])
    
    with auth_tab1:
        st.markdown("""
        <div style="background:linear-gradient(145deg,rgba(20,24,34,0.98),rgba(14,18,26,0.99)); border:1px solid rgba(255,255,255,0.08); border-radius:18px; padding:36px; margin:0 0 24px; box-shadow:0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);">
            <div style="color:#6b7280; font-family:'Inter'; font-size:11px; letter-spacing:2px; margin-bottom:24px;">SIGN IN TO YOUR ACCOUNT</div>
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
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center; color:#4b5563; font-size:12px; margin-top:20px;">Demo credentials: <span style="color:#6b7280;">UNIT-07</span> / <span style="color:#6b7280;">TITAN-DRIVER</span></div>
        """, unsafe_allow_html=True)
    
    with auth_tab2:
        st.markdown("""
        <div style="background:linear-gradient(145deg,rgba(20,24,34,0.98),rgba(14,18,26,0.99)); border:1px solid rgba(255,255,255,0.08); border-radius:18px; padding:36px; margin:0 0 24px; box-shadow:0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);">
            <div style="color:#6b7280; font-family:'Inter'; font-size:11px; letter-spacing:2px; margin-bottom:24px;">REGISTER NEW DRIVER</div>
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
        st.markdown("</div>", unsafe_allow_html=True)

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
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO driver_comms (timestamp, driver_id, status, message) VALUES (?, ?, ?, ?)",
                  (datetime.datetime.now(), st.session_state.driver_id, stat, msg))
        conn.commit()
        conn.close()
        st.toast(f"Status Updated: {stat}", icon="✅")
    except: pass

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

def report_hazard():
    """Inserts a hazard record at current location"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO hazards (lat, lon, type, timestamp) VALUES (?, ?, ?, ?)",
                  (st.session_state.gps_lat, st.session_state.gps_lon, "CAUTION: REPORTED HAZARD", datetime.datetime.now()))
        conn.commit()
        conn.close()
        st.toast("Hazard Reported Successfully!", icon="⚠️")
    except: pass

def check_orders():
    """Fetch pending mission assigned to this driver (or unassigned). Expiry 30 min."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        dfm = pd.read_sql_query(
            """
            SELECT * FROM missions
            WHERE status = 'DISPATCHED'
              AND (assigned_driver_id IS NULL OR assigned_driver_id = ?)
            ORDER BY id DESC
            LIMIT 5
            """,
            conn,
            params=(str(st.session_state.get("driver_id", "")),),
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
                if age_sec < 1800:  # 30 min expiry
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
    <div style="text-align:center; padding:48px 24px 40px;">
        <div style="font-family:'Orbitron'; font-size:22px; font-weight:600; color:#e6edf3;">SET AVAILABILITY</div>
        <div style="color:#6b7280; font-size:14px; margin-top:10px;">How are you starting your shift?</div>
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
    <div style="text-align:center; color:#4b5563; font-size:12px; margin-top:20px;">Logged in as <span style="color:#6b7280;">{st.session_state.driver_id}</span></div>
    """, unsafe_allow_html=True)

if not st.session_state.status_set_on_login:
    status_selection_screen()
    st.stop()

# No auto-poll fragment — use REFRESH button to check for missions (avoids stuck/crash)

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
_accent = "#00ff9d" if st.session_state.clearance_status == "GRANTED" else "#00f3ff"
# Status badge: Online (ACTIVE), Break, Inactive, or En Route
_av = st.session_state.get("availability", "ACTIVE")
_st = st.session_state.get("status", "IDLE")
if _st == "EN_ROUTE":
    _status_badge = "EN ROUTE"
    _status_bg = "#00ff9d"
elif _av == "ACTIVE" and _st == "IDLE":
    _status_badge = "🟢 ONLINE"
    _status_bg = "#00ff9d"
elif _av == "BREAK":
    _status_badge = "BREAK"
    _status_bg = "#ffaa00"
elif _av == "INACTIVE":
    _status_badge = "INACTIVE"
    _status_bg = "#666"
else:
    _status_badge = str(_st)
    _status_bg = "#555"
st.markdown(f"""
<div class="mobile-header">
    <div>
        <div style="font-family:'Orbitron'; font-size:18px; font-weight:600; color:#e6edf3;">{st.session_state.driver_id}</div>
        <div style="font-size:13px; color:#e6edf3; font-weight:500; margin-top:2px;">{_display_name}</div>
        <div style="font-size:11px; color:#6b7280; margin-top:4px;">{_vehicle} • {_place} • {shift_dur}m shift</div>
    </div>
    <div style="background:{_status_bg}; color:{"#000" if _status_bg in ["#00ff9d","#ffaa00"] else "#fff"}; padding:6px 14px; border-radius:8px; font-weight:600; font-size:11px; font-family:'Inter'; letter-spacing:0.5px;">
        {_status_badge}
    </div>
</div>
""", unsafe_allow_html=True)
if st.session_state.clearance_status == "GRANTED":
    st.markdown("""
    <div style="background:rgba(5,150,105,0.15); border:1px solid rgba(5,150,105,0.4); border-radius:10px; padding:12px 16px; color:#10b981; font-weight:500;">
        Signal cleared — Green Wave granted
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
    <div style="background:rgba(220,38,38,0.1); border:1px solid rgba(220,38,38,0.3); border-radius:10px; padding:12px 16px; color:#f87171;">
        Request denied
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

# Action bar — aligned layout
st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
bar1, bar2, bar3 = st.columns([1, 2, 1])
with bar1:
    if st.button("Refresh", key="manual_refresh", use_container_width=True, help="Check for new missions"):
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
    if st.button("Logout", key="logout_btn", use_container_width=True):
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
new_mission = check_orders()

if st.session_state.status == "IDLE" and st.session_state.get("availability") == "ACTIVE" and new_mission is None:
    st.markdown("""
    <div style="background:linear-gradient(145deg,rgba(6,182,212,0.12),rgba(6,182,212,0.04)); border:1px solid rgba(6,182,212,0.25); border-radius:14px; padding:20px 24px; margin:16px 0; color:#94a3b8; font-size:14px; box-shadow:0 4px 20px rgba(6,182,212,0.1);">
        Ready for missions — Click <strong style="color:#06b6d4;">Refresh</strong> to check for dispatches from HQ.
    </div>
    """, unsafe_allow_html=True)
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
    
    prio_color = "#ef4444" if prio == "CRITICAL" else "#f59e0b" if prio == "HIGH" else "#06b6d4"
    
    # Mission countdown (30 min expiry)
    created = pd.to_datetime(new_mission.get("created_at"), errors="coerce")
    mins_left = "—"
    if pd.notna(created):
        age_sec = (datetime.datetime.now() - created).total_seconds()
        remaining = max(0, 1800 - age_sec)
        mins_left = f"{int(remaining // 60)} min"
    countdown_html = f'<div style="color:#f59e0b; font-size:12px; margin-top:8px;">⏱ Expires in: {mins_left}</div>'
    
    notes_html = ""
    if new_mission.get("notes"):
        notes_escaped = html.escape(str(new_mission.get("notes", "") or ""))
        notes_html = f'<div style="color:#aaa; font-size:12px; margin-top:10px; padding:10px; background:rgba(0,0,0,0.3); border-radius:8px; text-align:left;">📋 <strong>Notes:</strong> {notes_escaped}</div>'
    st.markdown(f"""
    <div class="mission-alert">
        <div style="text-align:center; margin-bottom:16px;">
            <div style="color:{prio_color}; font-family:'Inter'; font-size:11px; letter-spacing:2px; font-weight:600;">{prio_esc} PRIORITY</div>
            <div style="color:#e6edf3; font-family:'Orbitron'; font-size:22px; margin:12px 0;">{org_esc}</div>
            <div style="color:#6b7280; font-size:16px;">↓</div>
            <div style="color:#e6edf3; font-family:'Orbitron'; font-size:22px;">{dst_esc}</div>
            <div style="color:#6b7280; font-size:12px; margin-top:12px;">Mission {mid_esc}</div>
            {countdown_html}
            {notes_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    s_coords = HOSPITALS.get(org, [10.015, 76.34])
    d_coords = HOSPITALS.get(dst, [10.015, 76.34])

    col_acc, col_ign = st.columns([1, 1])
    with col_acc:
        if st.button("Accept mission", key="accept_mission_btn"):
            log_activity("ACCEPT", st.session_state.driver_id, mid)
            st.session_state.active_org = org
            st.session_state.active_dst = dst
            st.session_state.status = "EN_ROUTE"
            st.session_state.active_mission_id = mid
            coords = HOSPITALS.get(org, [10.015, 76.34])
            st.session_state.gps_lat, st.session_state.gps_lon = coords[0], coords[1]
            update_server(org, dst, "EN_ROUTE")
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("UPDATE missions SET status='ACCEPTED', accepted_at=?, assigned_driver_id=? WHERE mission_id=?", (datetime.datetime.now(), st.session_state.driver_id, mid))
                conn.commit()
                conn.close()
            except Exception:
                pass
            # 4-route logic: compute alternatives and show selection
            if s_coords and d_coords:
                st.session_state.route_alternatives = fetch_route_alternatives_4(s_coords, d_coords)
                st.session_state.route_selection_pending = True
            heartbeat()
            st.rerun()
    with col_ign:
        if st.session_state.pending_decline_mid == mid:
            decline_reason = st.selectbox("Reason (optional)", ["—", "Too far", "On break", "Vehicle issue", "Other"], key="decline_reason")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Confirm", key="confirm_decline"):
                    reason = decline_reason if decline_reason != "—" else ""
                    if reason:
                        try:
                            conn = sqlite3.connect(DB_FILE)
                            conn.execute("PRAGMA journal_mode=WAL;")
                            try:
                                conn.execute("ALTER TABLE missions ADD COLUMN decline_reason TEXT")
                            except sqlite3.OperationalError:
                                pass
                            conn.execute("UPDATE missions SET decline_reason=? WHERE mission_id=?", (reason, mid))
                            conn.commit()
                            conn.close()
                        except Exception:
                            pass
                    log_activity("DECLINE", st.session_state.driver_id, f"{mid} {reason}".strip())
                    st.session_state.declined_missions.add(mid)
                    st.session_state.pending_decline_mid = None
                    st.rerun()
            with c2:
                if st.button("Cancel", key="cancel_decline"):
                    st.session_state.pending_decline_mid = None
                    st.rerun()
        elif st.button("Decline", key="decline_mission_btn"):
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
                <div style="font-weight:600; color:#e6edf3; font-size:15px;">{r.get('route_type', f'Route {i+1}')}</div>
                <div style="display:flex; align-items:center; gap:16px; margin-top:8px; font-size:13px;">
                    <span style="color:{c}; font-weight:500;">{r.get('eta', 0)} min</span>
                    <span style="color:#4b5563;">|</span>
                    <span style="color:#9ca3af;">{r.get('dist', 0)} km</span>
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
tab_drive, tab_map, tab_comms, tab_stats, tab_alerts, tab_missions, tab_settings = st.tabs([
    "Dashboard", "Navigation", "Comms", "Stats", "Alerts", "Missions", "Settings"
])

with tab_drive:
    current_speed = random.randint(45, 72) if st.session_state.status == "EN_ROUTE" else 0
    st.markdown(f"""
    <div style="padding:24px 0;">
        <div class="speed-circle">
            <div class="speed-val">{current_speed}</div>
            <div class="speed-unit">KM/H</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.status == "EN_ROUTE" and st.session_state.active_dst:
         d_coords = HOSPITALS.get(st.session_state.active_dst)
         dist = geodesic((st.session_state.gps_lat, st.session_state.gps_lon), d_coords).km if d_coords else 0
         eta = int(dist * 60 / 40)
         c1, c2 = st.columns(2)
         with c1: st.markdown(f"""<div class="widget-box"><div class="w-title">Remaining</div><div class="w-val">{dist:.1f} km</div></div>""", unsafe_allow_html=True)
         with c2: st.markdown(f"""<div class="widget-box"><div class="w-title">ETA</div><div class="w-val">{eta} min</div></div>""", unsafe_allow_html=True)
    else:
         st.markdown("""
         <div style="background:linear-gradient(145deg,rgba(24,28,38,0.9),rgba(14,18,26,0.95)); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:32px; text-align:center; color:#6b7280; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
             System idle — Awaiting dispatch
         </div>
         """, unsafe_allow_html=True)

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
        <div style="background:rgba(20,24,32,0.9); padding:18px; border-radius:12px; margin:12px 0; border:1px solid rgba(255,255,255,0.05); border-left:3px solid #06b6d4;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="color:#6b7280; font-size:11px;">Route</div>
                    <div style="color:#e6edf3; font-family:'Orbitron'; font-size:15px;">{best.get('route_type', 'FASTEST')}</div>
                </div>
                <div style="text-align:right;">
                    <div style="color:#6b7280; font-size:11px;">Delay</div>
                    <div style="color:#f59e0b; font-size:14px;">+{best.get('traffic_delay_min', 0)} min</div>
                </div>
            </div>
            <div style="display:flex; justify-content:space-around; margin-top:16px; padding-top:14px; border-top:1px solid rgba(255,255,255,0.06);">
                <div style="text-align:center;">
                    <div style="color:#10b981; font-family:'Orbitron'; font-size:22px;">{best.get('dist', 0)}</div>
                    <div style="color:#6b7280; font-size:11px;">km</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:#06b6d4; font-family:'Orbitron'; font-size:22px;">{best.get('eta', 0)}</div>
                    <div style="color:#6b7280; font-size:11px;">min ETA</div>
                </div>
                <div style="text-align:center;">
                    <div style="color:#e6edf3; font-family:'Orbitron'; font-size:22px;">{(datetime.datetime.now() + datetime.timedelta(minutes=best.get('eta', 0))).strftime('%H:%M')}</div>
                    <div style="color:#6b7280; font-size:11px;">arrival</div>
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
                    <div style="padding:8px; border-bottom:1px solid #222; display:flex; align-items:center;">
                        <span style="font-size:16px; margin-right:10px;">{icon}</span>
                        <span style="color:#fff; font-size:12px;">{msg}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Follow the highlighted route on the map.")

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
                            try:
                                conn = sqlite3.connect(DB_FILE)
                                c = conn.cursor()
                                c.execute("UPDATE missions SET status='COMPLETED', completed_at=? WHERE mission_id=?", (datetime.datetime.now(), st.session_state.active_mission_id))
                                conn.commit()
                                conn.close()
                            except Exception:
                                pass
                        mid_complete = st.session_state.active_mission_id
                        st.session_state.active_mission_id = None
                        if mid_complete:
                            log_activity("COMPLETE", st.session_state.driver_id, mid_complete)
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
            <div style="color:#6b7280; font-size:13px; margin-bottom:16px; padding:12px 16px; background:rgba(20,24,32,0.6); border-radius:10px; border:1px solid rgba(255,255,255,0.05);">
                <span style="color:#9ca3af;">From</span> {org_label} <span style="color:#6b7280;">→</span> <span style="color:#9ca3af;">To</span> {dst}
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
                        <div style="font-weight:600; color:#e6edf3; font-size:14px;">{opt.get('route_type', f'Route {idx+1}')}</div>
                        <div style="display:flex; align-items:center; gap:12px; margin-top:8px; font-size:13px;">
                            <span style="color:{c}; font-weight:500;">{opt.get('eta', 0)} min</span>
                            <span style="color:#4b5563;">|</span>
                            <span style="color:#9ca3af;">{opt.get('dist', 0)} km</span>
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
    st.markdown("### Communications")
    
    st.markdown("""
    <div style="background:rgba(20,24,32,0.8); border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:12px 16px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
        <span style="color:#6b7280; font-size:12px;">V2X connection</span>
        <span style="color:#10b981; font-size:12px; font-weight:600;">● Active</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("#### Emergency")
    if st.button("SOS — Emergency Alert", use_container_width=True, type="primary", key="sos_btn"):
        send_msg("CRITICAL", f"🆘 SOS - {st.session_state.driver_id} EMERGENCY at ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f}) - Immediate assistance required!")
        st.error("SOS sent to HQ. Help is on the way.")
        st.rerun()
    st.markdown("---")
    st.markdown("#### Green Wave")
    
    gw_cols = st.columns([1, 1])
    with gw_cols[0]:
        if st.button("Request Green Wave", use_container_width=True):
            st.session_state.clearance_status = "PENDING"
            heartbeat()
            send_msg("REQUEST", f"GREEN WAVE REQUEST from {st.session_state.driver_id} - Priority corridor clearance needed. Location: {st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f}")
            st.toast("Green Wave requested. Awaiting HQ authorization.")
            st.rerun()
    
    with gw_cols[1]:
        if st.button("Emergency preempt", use_container_width=True):
            st.session_state.clearance_status = "PENDING"
            heartbeat()
            send_msg("REQUEST", f"⚠️ EMERGENCY PREEMPTION from {st.session_state.driver_id} - CRITICAL patient transport. Immediate signal clearance required!")
            st.toast("Emergency preemption requested!")
            st.rerun()
    
    if st.session_state.clearance_status == "PENDING":
        st.markdown("""
        <div style="background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); color:#f59e0b; padding:14px; border-radius:10px; text-align:center; margin:12px 0; font-size:13px;">
            Green Wave request pending — Awaiting HQ authorization
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("#### Quick status")
    
    status_cols = st.columns([1, 1])
    with status_cols[0]:
        if st.button("Patient onboard", use_container_width=True):
            send_msg("STATUS", f"PATIENT SECURED - {st.session_state.driver_id} en route to {st.session_state.active_dst or 'destination'}")
        
        if st.button("Traffic obstruction", use_container_width=True):
            send_msg("WARNING", f"TRAFFIC OBSTRUCTION reported at current location by {st.session_state.driver_id}. Requesting alternate route.")
    
    with status_cols[1]:
        if st.button("Low fuel alert", use_container_width=True):
            send_msg("WARNING", f"LOW FUEL - {st.session_state.driver_id} fuel critical. May need to divert for refueling.")
        
        if st.button("Mechanical issue", use_container_width=True):
            send_msg("WARNING", f"MECHANICAL ISSUE - {st.session_state.driver_id} experiencing vehicle problems. May need assistance.")
    
    st.markdown("---")
    
    st.markdown("#### Custom message")
    with st.form("driver_msg_form"):
        msg_priority = st.selectbox("Priority", ["NORMAL", "URGENT", "CRITICAL"])
        custom_msg = st.text_area("Message", placeholder="Type your message to HQ...", height=80)
        
        if st.form_submit_button("Send to HQ", use_container_width=True):
            if custom_msg:
                status = "REQUEST" if msg_priority == "NORMAL" else "WARNING" if msg_priority == "URGENT" else "CRITICAL"
                send_msg(status, f"[{msg_priority}] {st.session_state.driver_id}: {custom_msg}")
                st.success("Message transmitted to HQ!")
            else:
                st.error("Please enter a message.")
    
    st.markdown("---")
    
    st.markdown("#### Hazard report")
    st.markdown("""
    <div style="background:linear-gradient(145deg,rgba(24,28,38,0.95),rgba(14,18,26,0.98)); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px; margin-bottom:20px; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
            <span style="width:40px; height:40px; background:rgba(239,68,68,0.2); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:20px;">⚠️</span>
            <div>
                <div style="font-weight:600; color:#e6edf3; font-size:15px;">Report road hazard</div>
                <div style="color:#6b7280; font-size:12px; margin-top:2px;">Alert HQ of incidents at your location</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='color:#6b7280; font-size:12px; margin-bottom:8px;'>Select hazard type</div>", unsafe_allow_html=True)
    hazard_type = st.selectbox("Hazard type", [
        "ACCIDENT",
        "ROAD CLOSURE",
        "FLOODING",
        "DEBRIS ON ROAD",
        "SIGNAL MALFUNCTION",
        "PEDESTRIAN HAZARD",
        "CONSTRUCTION ZONE",
        "OTHER"
    ], label_visibility="collapsed")
    
    hazard_cols = st.columns([1, 1])
    with hazard_cols[0]:
        if st.button("⚠️ Report hazard", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO hazards (lat, lon, type, timestamp) VALUES (?, ?, ?, ?)",
                          (st.session_state.gps_lat, st.session_state.gps_lon, f"{hazard_type}: Reported by {st.session_state.driver_id}", datetime.datetime.now()))
                conn.commit()
                conn.close()
                send_msg("WARNING", f"HAZARD REPORTED: {hazard_type} at location ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f})")
                st.toast(f"Hazard ({hazard_type}) reported successfully!", icon="⚠️")
            except Exception:
                st.error("Failed to report hazard")
    
    with hazard_cols[1]:
        if st.button("📍 Share location", use_container_width=True):
            send_msg("STATUS", f"LOCATION UPDATE - {st.session_state.driver_id}: ({st.session_state.gps_lat:.4f}, {st.session_state.gps_lon:.4f})")
            st.toast("Location shared with HQ!")
    
    st.markdown("---")
    
    st.markdown("#### Messages from HQ")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        hq_msgs = pd.read_sql_query(
            "SELECT * FROM driver_comms WHERE status LIKE 'HQ%' OR driver_id = 'ALL' OR driver_id = ? ORDER BY id DESC LIMIT 10",
            conn,
            params=(st.session_state.driver_id,)
        )
        conn.close()
        
        if not hq_msgs.empty:
            for _, row in hq_msgs.iterrows():
                msg_time = row.get('timestamp', '')
                msg_text = row.get('message', '')
                msg_type = row.get('status', '')
                
                if 'GREENWAVE' in msg_type:
                    color = "#00ff9d"
                    icon = "🟢"
                elif 'ALERT' in msg_type:
                    color = "#ff003c"
                    icon = "🔴"
                else:
                    color = "#00f3ff"
                    icon = "📡"
                
                st.markdown(f"""
                <div style="background:#1a1a1a; border-left:3px solid {color}; padding:10px; margin-bottom:8px; border-radius:4px;">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:{color}; font-weight:bold; font-size:11px;">{icon} HQ BROADCAST</span>
                        <span style="color:#666; font-size:10px;">{msg_time}</span>
                    </div>
                    <div style="color:#fff; font-size:12px; margin-top:5px;">{msg_text}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No messages from HQ yet.")
    except Exception:
        st.info("Unable to fetch HQ messages.")
    
    st.markdown("---")
    st.markdown("""
    <div style="background:linear-gradient(145deg,rgba(24,28,38,0.9),rgba(14,18,26,0.95)); padding:18px 20px; border-radius:14px; border:1px solid rgba(255,255,255,0.06); box-shadow:0 4px 16px rgba(0,0,0,0.3);">
        <div style="color:#6b7280; font-size:11px; margin-bottom:12px;">V2X protocol</div>
        <div style="display:flex; justify-content:space-between; color:#9ca3af; font-size:13px;">
            <span>DSRC Active</span>
            <span>5G-V2X Connected</span>
            <span style="color:#10b981; font-weight:600;">&lt;50ms</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

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
        status_color = "#10b981" if st.session_state.status == "EN_ROUTE" else "#f59e0b"
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
                    color = "#ef4444"
                    badge = "CRITICAL"
                elif dist < 5:
                    color = "#f59e0b"
                    badge = "NEARBY"
                else:
                    color = "#06b6d4"
                    badge = "AHEAD"
                h_type = str(h.get('type', 'Hazard'))[:60]
                st.markdown(f"""
                <div style="background:linear-gradient(145deg,rgba(24,28,38,0.95),rgba(14,18,26,0.98)); border-left:4px solid {color}; border-radius:14px; padding:18px; margin-bottom:14px; border:1px solid rgba(255,255,255,0.06); box-shadow:0 4px 16px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;">
                    <div style="display:flex; align-items:flex-start; gap:14px; flex:1; min-width:200px;">
                        <span style="width:44px; height:44px; background:{color}22; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:22px; flex-shrink:0;">⚠️</span>
                        <div>
                            <div style="color:#e6edf3; font-weight:600; font-size:14px;">{h_type}</div>
                            <div style="color:#6b7280; font-size:11px; margin-top:6px;">Reported by driver</div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px; flex-shrink:0;">
                        <span style="background:{color}33; color:{color}; padding:6px 12px; border-radius:8px; font-size:11px; font-weight:600;">{badge}</span>
                        <span style="color:{color}; font-weight:600; font-size:15px;">{dist:.1f} km</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:linear-gradient(145deg,rgba(16,185,129,0.1),rgba(16,185,129,0.02)); border:1px solid rgba(16,185,129,0.3); border-radius:16px; padding:32px; text-align:center; box-shadow:0 4px 20px rgba(16,185,129,0.1);">
                <div style="font-size:40px; margin-bottom:12px;">✅</div>
                <div style="color:#10b981; font-weight:600; font-size:16px;">No hazards nearby</div>
                <div style="color:#6b7280; font-size:13px; margin-top:6px;">Clear roads ahead</div>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.info("Unable to fetch hazards.")
    
    st.markdown("---")
    st.markdown("#### Traffic status")
    st.markdown("""
    <div style="background:rgba(20,24,32,0.8); border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:16px;">
        <div style="color:#10b981; font-weight:600;">Live traffic</div>
        <div style="color:#6b7280; font-size:12px; margin-top:6px;">Green Wave & V2X synced with HQ</div>
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
            for _, m in my_missions.iterrows():
                status = m.get("status", "?")
                status_color = "#00ff9d" if status == "COMPLETED" else "#ffcc00" if status == "ACCEPTED" else "#00f3ff"
                st.markdown(f"""
                <div class="route-card" style="border-left-color:{status_color};">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#fff; font-weight:bold;">{m.get('mission_id', '?')}</span>
                        <span style="color:{status_color}; font-size:11px;">{status}</span>
                    </div>
                    <div style="color:#aaa; font-size:13px; margin-top:8px;">{m.get('origin','?')} → {m.get('destination','?')}</div>
                    <div style="color:#666; font-size:10px; margin-top:5px;">{m.get('created_at','')}</div>
                </div>
                """, unsafe_allow_html=True)
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
        <div style="background:linear-gradient(145deg,rgba(24,28,38,0.95),rgba(14,18,26,0.98)); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:24px; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
            <div style="color:#e6edf3; font-weight:600; font-size:18px;">{_prof.get('driver_id', st.session_state.driver_id)}</div>
            <div style="color:#6b7280; font-size:13px; margin-top:2px;">{_prof.get('full_name') or '—'}</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px 24px; margin-top:16px; font-size:13px;">
                <div><span style="color:#6b7280;">Vehicle</span><br><span style="color:#e6edf3;">{_prof.get('vehicle_id') or '—'}</span></div>
                <div><span style="color:#6b7280;">Base</span><br><span style="color:#e6edf3;">{_prof.get('base_hospital') or '—'}</span></div>
                <div><span style="color:#6b7280;">Phone</span><br><span style="color:#e6edf3;">{_prof.get('phone') or '—'}</span></div>
            </div>
            <div style="color:#10b981; font-size:12px; margin-top:14px; font-weight:500;">● Connected</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:linear-gradient(145deg,rgba(24,28,38,0.95),rgba(14,18,26,0.98)); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:24px; box-shadow:0 4px 20px rgba(0,0,0,0.3);">
            <div style="color:#e6edf3; font-weight:600;">{st.session_state.driver_id}</div>
            <div style="color:#10b981; font-size:12px; margin-top:8px;">● Connected</div>
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
    notif_sound = st.toggle("Sound alerts for new missions", value=True)
    notif_vibration = st.toggle("Vibration on mission alert", value=True)
    
    st.markdown("---")
    st.markdown("#### Navigation")
    nav_voice = st.toggle("Voice turn-by-turn", value=True)
    nav_traffic = st.toggle("Live traffic updates", value=True)
    
    st.markdown("---")
    st.markdown("#### App info")
    st.markdown("""
    <div style="color:#4b5563; font-size:12px; margin-top:20px;">TITAN Driver OS v52 • Connected to HQ</div>
    """, unsafe_allow_html=True)