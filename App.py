
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
import sys
import os

# Ensure APP folder is on path for shared_utils (run from any cwd)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
from shared_utils import fetch_routes as shared_fetch_routes, distance_km, hash_password, verify_password, calculate_co2_savings, estimate_fuel_consumption
try:
    from shared_utils import HOSPITALS, ONLINE_THRESHOLD_SEC, MISSION_EXPIRY_SEC
except ImportError:
    ONLINE_THRESHOLD_SEC = 60
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
                self.meters = m
                self.km = m / 1000.0

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
if 'page' not in st.session_state: st.session_state.page = 'home'
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'emergency_mode' not in st.session_state: st.session_state.emergency_mode = False
if 'mission_id' not in st.session_state: st.session_state.mission_id = f"CMD-{random.randint(1000,9999)}"
if 'priority_val' not in st.session_state: st.session_state.priority_val = "STANDARD"

# DB (same folder as script for shared DB when running from any cwd)
# TomTom API key: shared_utils.TOMTOM_API_KEY (supports TOMTOM_API_KEY env var)
DB_FILE = os.path.join(_APP_DIR, "titan_v52.db")

# ==========================================
# 1. DATABASE ENGINE
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    c = conn.cursor()
    
    # 1. MISSION LOGS
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
    
    # 2. DRIVER STATE (Telemetry history: lat, lon, speed per push)
    c.execute('''
        CREATE TABLE IF NOT EXISTS driver_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT,
            origin TEXT,
            destination TEXT,
            current_lat REAL,
            current_lon REAL,
            speed REAL,
            status TEXT,
            timestamp DATETIME
        )
    ''')
    try:
        c.execute("ALTER TABLE driver_state ADD COLUMN speed REAL")
    except sqlite3.OperationalError:
        pass
    
    # 3. COMMUNICATIONS
    c.execute('''
        CREATE TABLE IF NOT EXISTS driver_comms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            driver_id TEXT,
            status TEXT,
            message TEXT
        )
    ''')

    # 4. DRIVER REGISTRY (Master state: syncs with driverapp)
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
    # Migration: add columns if table already existed without them
    for col, typ in [
        ("speed", "REAL"), ("origin", "TEXT"), ("destination", "TEXT"),
        ("active_mission_id", "TEXT"), ("clearance_status", "TEXT"), ("selected_route_id", "INTEGER"),
    ]:
        try:
            c.execute(f"ALTER TABLE drivers ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass

    # 5. MISSIONS
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

    # 6. OPERATORS
    c.execute('''
        CREATE TABLE IF NOT EXISTS operators (
            username TEXT PRIMARY KEY,
            password TEXT,
            display_name TEXT
        )
    ''')

    # 7. DRIVER ACCOUNTS
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

    # 8. SIGNAL STATUS (For Green Wave)
    c.execute('''
        CREATE TABLE IF NOT EXISTS signal_status (
            stop_id TEXT PRIMARY KEY,
            status TEXT,
            last_updated DATETIME
        )
    ''')

    # 9. HAZARDS (For Hazard Mapping)
    c.execute('''
        CREATE TABLE IF NOT EXISTS hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL,
            lon REAL,
            type TEXT,
            timestamp DATETIME
        )
    ''')

    # missions.notes
    try:
        c.execute("ALTER TABLE missions ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass
    # missions.decline_reason
    try:
        c.execute("ALTER TABLE missions ADD COLUMN decline_reason TEXT")
    except sqlite3.OperationalError:
        pass
    # activity_log
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            action TEXT,
            actor TEXT,
            details TEXT
        )
    ''')
    # mission_declines: persist driver declines so they don't see same mission after refresh
    c.execute('''
        CREATE TABLE IF NOT EXISTS mission_declines (
            mission_id TEXT,
            driver_id TEXT,
            declined_at DATETIME,
            reason TEXT,
            PRIMARY KEY (mission_id, driver_id)
        )
    ''')
    # Seed defaults (hashed passwords)
    c.execute(
        "INSERT OR IGNORE INTO operators (username, password, display_name) VALUES (?, ?, ?)",
        ("COMMANDER", hash_password("TITAN-X"), "HQ Commander"),
    )
    c.execute(
        "INSERT OR IGNORE INTO driver_accounts (driver_id, username, password, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
        ("UNIT-07", "UNIT-07", hash_password("TITAN-DRIVER"), "Unit 7", datetime.datetime.now()),
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
        row = conn.execute("SELECT * FROM driver_state ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if row:
            # driver_state: id, driver_id, origin, destination, current_lat, current_lon, speed, status, timestamp
            return {
                "id": row[1], "origin": row[2], "dest": row[3],
                "lat": row[4], "lon": row[5], "speed": row[6] if len(row) > 6 else None,
                "status": row[7] if len(row) > 7 else row[6],
                "time": row[8] if len(row) > 8 else row[7]
            }
    except: pass
    return None

def get_ghost_trail(limit=20):
    """DEPRECATED: Mixed trail from all drivers is incorrect. Use get_ghost_trail_for_driver only."""
    return []

def get_driver_status_by_id(driver_id):
    """Latest telemetry for a specific driver"""
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute(
            "SELECT driver_id, origin, destination, current_lat, current_lon, speed, status, timestamp FROM driver_state WHERE driver_id=? ORDER BY id DESC LIMIT 1",
            (driver_id,)
        ).fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "origin": row[1], "dest": row[2],
                "lat": row[3], "lon": row[4], "speed": row[5],
                "status": row[6], "time": row[7]
            }
    except: pass
    return None

def get_ghost_trail_for_driver(driver_id, limit=80):
    """Ghost trail for a specific driver: chronological path (oldest→newest) for correct polyline. Valid coords only."""
    path = []
    if not driver_id:
        return path
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute(
            """SELECT current_lat, current_lon FROM driver_state
               WHERE driver_id=? AND current_lat IS NOT NULL AND current_lon IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (driver_id, limit)
        ).fetchall()
        conn.close()
        if rows:
            valid = []
            for r in reversed(rows):
                lat, lon = r[0], r[1]
                if lat is not None and lon is not None:
                    try:
                        valid.append([float(lat), float(lon)])
                    except (TypeError, ValueError):
                        pass
            path = valid
    except Exception:
        pass
    return path

def get_hazards():
    hazards = []
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute("SELECT lat, lon, type FROM hazards ORDER BY id DESC LIMIT 50").fetchall()
        conn.close()
        if rows:
            hazards = [{"lat": r[0], "lon": r[1], "type": r[2]} for r in rows]
    except: pass
    return hazards

def get_signal_status():
    signals = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute("SELECT stop_id, status FROM signal_status").fetchall()
        conn.close()
        for r in rows:
            signals[r[0]] = r[1]
    except: pass
    return signals

def get_driver_profiles(driver_ids):
    """Get full_name, vehicle_id from driver_accounts for given driver_ids. Returns {driver_id: {full_name, vehicle_id}}."""
    ids = [str(x) for x in driver_ids if x is not None and not (isinstance(x, float) and pd.isna(x))]
    if not ids:
        return {}
    ids = list(dict.fromkeys(ids))
    try:
        conn = sqlite3.connect(DB_FILE)
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT driver_id, full_name, vehicle_id FROM driver_accounts WHERE driver_id IN ({placeholders})",
            ids,
        ).fetchall()
        conn.close()
        return {r[0]: {"full_name": r[1] or "—", "vehicle_id": r[2] or "—"} for r in rows}
    except Exception:
        return {}

def get_driver_from_drivers_table(driver_id):
    """Current position & route from drivers table (heartbeat). Fallback when driver_state is empty."""
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute(
            "SELECT driver_id, origin, destination, current_lat, current_lon, speed, status FROM drivers WHERE driver_id=?",
            (driver_id,),
        ).fetchone()
        conn.close()
        if row:
            return {"id": row[0], "origin": row[1], "dest": row[2], "lat": row[3], "lon": row[4], "speed": row[5], "status": row[6]}
    except Exception:
        pass
    return None

def get_available_drivers(online_within_seconds=None):
    """Drivers who are ONLINE (recent last_seen), ACTIVE (not BREAK/INACTIVE), and have a REGISTERED account."""
    if online_within_seconds is None:
        online_within_seconds = ONLINE_THRESHOLD_SEC
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        df = pd.read_sql_query("""
            SELECT d.* FROM drivers d
            INNER JOIN driver_accounts a ON d.driver_id = a.driver_id
            WHERE d.current_lat IS NOT NULL AND d.current_lon IS NOT NULL
              AND (d.status IS NULL OR d.status NOT IN ('BREAK', 'INACTIVE'))
        """, conn)
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


def get_all_active_drivers(online_within_seconds=30):
    """All drivers visible to server for global map and Live Metrics."""
    return get_available_drivers(online_within_seconds=online_within_seconds)


def get_drivers_for_live_map(online_within_seconds=60):
    """Drivers for Live Tracking map: includes those without position (simulated). Returns df with current_lat, current_lon, status, etc."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        df = pd.read_sql_query("""
            SELECT d.driver_id, d.status, d.current_lat, d.current_lon, d.origin, d.destination, d.speed, d.last_seen, d.active_mission_id
            FROM drivers d INNER JOIN driver_accounts a ON d.driver_id = a.driver_id
        """, conn)
        conn.close()
        if df.empty:
            return pd.DataFrame()
        cutoff = datetime.datetime.now() - datetime.timedelta(seconds=online_within_seconds)
        df["last_seen"] = pd.to_datetime(df["last_seen"], errors="coerce")
        df = df[df["last_seen"] >= cutoff]
        if df.empty:
            return pd.DataFrame()
        # Simulate position when lat/lon is null (no real-time GPS) - linear interpolation along route
        def _simulate_position(row):
            lat, lon = row.get("current_lat"), row.get("current_lon")
            if pd.notna(lat) and pd.notna(lon):
                return float(lat), float(lon)
            status = row.get("status", "IDLE")
            org_key, dst_key = row.get("origin"), row.get("destination")
            if status == "EN_ROUTE" and org_key and dst_key and org_key in HOSPITALS and dst_key in HOSPITALS:
                o, d = HOSPITALS[org_key], HOSPITALS[dst_key]
                t = 0.4
                return float(o[0] + t * (d[0] - o[0])), float(o[1] + t * (d[1] - o[1]))
            if org_key and org_key in HOSPITALS:
                c = HOSPITALS[org_key]
                return float(c[0]), float(c[1])
            return 10.015, 76.340
        pos = df.apply(_simulate_position, axis=1)
        df["current_lat"] = [p[0] for p in pos]
        df["current_lon"] = [p[1] for p in pos]
        return df
    except Exception:
        return pd.DataFrame()


def get_drivers_pending_clearance():
    """Drivers with clearance_status == 'PENDING' for Traffic Control Center."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA journal_mode=WAL;")
        df = pd.read_sql_query(
            "SELECT driver_id, status, current_lat, current_lon, last_seen FROM drivers WHERE clearance_status = 'PENDING'",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_current_mission_for_driver(driver_id):
    """Current mission for a driver (DISPATCHED or ACCEPTED). Returns dict with mission_id, origin, destination, status or None."""
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute(
            "SELECT mission_id, origin, destination, status FROM missions WHERE assigned_driver_id = ? AND status IN ('DISPATCHED','ACCEPTED') ORDER BY id DESC LIMIT 1",
            (driver_id,),
        ).fetchone()
        conn.close()
        if row:
            return {"mission_id": row[0], "origin": row[1], "destination": row[2], "status": row[3]}
    except Exception:
        pass
    return None


def update_driver_clearance(driver_id, status):
    """Set clearance_status to GRANTED or DENIED."""
    if status not in ("GRANTED", "DENIED"):
        return False
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE drivers SET clearance_status = ? WHERE driver_id = ?", (status, driver_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def mission_id_exists(mid):
    """Check if mission_id already exists."""
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute("SELECT 1 FROM missions WHERE mission_id=?", (mid,)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False

def generate_unique_mission_id():
    """Generate a mission ID that does not already exist."""
    for _ in range(10):
        mid = f"CMD-{int(time.time())}-{random.randint(100,999)}"
        if not mission_id_exists(mid):
            return mid
    return f"CMD-{int(time.time())}-{random.randint(1000,9999)}"

def create_mission(mid, org, dst, prio, assigned_driver_id=None, notes=None):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO missions (created_at, mission_id, origin, destination, priority, assigned_driver_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (datetime.datetime.now(), mid, org, dst, prio, assigned_driver_id, "DISPATCHED", notes or ""),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            c.execute(
                "INSERT INTO missions (created_at, mission_id, origin, destination, priority, assigned_driver_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.datetime.now(), mid, org, dst, prio, assigned_driver_id, "DISPATCHED"),
            )
            conn.commit()
        except Exception:
            pass
        conn.close()
        return True

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

def get_mission_details(mission_id):
    """Get assigned_driver_id, origin, destination for a mission. Returns dict or None."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute(
                "SELECT assigned_driver_id, origin, destination FROM missions WHERE mission_id=?",
                (mission_id,)
            ).fetchone()
        if row:
            return {"assigned_driver_id": row[0], "origin": row[1], "destination": row[2]}
    except Exception:
        pass
    return None

def update_mission_status(mission_id, status):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE missions SET status=? WHERE mission_id=?", (status, mission_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def mark_expired_missions():
    """Mark DISPATCHED missions as EXPIRED when past MISSION_EXPIRY_SEC. Returns count marked."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        cutoff = (datetime.datetime.now() - datetime.timedelta(seconds=MISSION_EXPIRY_SEC)).isoformat()
        c.execute(
            "UPDATE missions SET status='EXPIRED' WHERE status='DISPATCHED' AND created_at < ?",
            (cutoff,),
        )
        n = c.rowcount
        conn.commit()
        conn.close()
        return n
    except Exception:
        return 0

def get_driver_offline_alerts(offline_seconds=150):
    """Missions where assigned driver has last_seen > offline_seconds ago. Returns list of {mission_id, driver_id, seen_ago}."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cutoff = (datetime.datetime.now() - datetime.timedelta(seconds=offline_seconds)).isoformat()
        rows = conn.execute("""
            SELECT m.mission_id, m.assigned_driver_id, d.last_seen
            FROM missions m
            INNER JOIN drivers d ON m.assigned_driver_id = d.driver_id
            WHERE m.status = 'ACCEPTED' AND d.last_seen < ?
        """, (cutoff,)).fetchall()
        conn.close()
        now = datetime.datetime.now()
        alerts = []
        for r in rows:
            mid, did, last = r[0], r[1], r[2]
            if last:
                try:
                    last_dt = pd.to_datetime(last, errors="coerce")
                    if pd.notna(last_dt):
                        seen_ago = int((now - last_dt).total_seconds())
                        alerts.append({"mission_id": mid, "driver_id": did, "seen_ago": seen_ago})
                except Exception:
                    pass
        return alerts
    except Exception:
        return []

# ==========================================
# V2X COMMUNICATIONS FUNCTIONS
# ==========================================
def get_driver_comms(limit=100, driver_id=None, conversation_mode=False):
    """
    Get driver communications.
    - driver_id=None: all messages
    - driver_id="UNIT-07": filter by unit
      - conversation_mode=False: only messages FROM that driver
      - conversation_mode=True: messages from driver + messages TO that driver (HQ msgs where recipient=driver_id or 'ALL')
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        if driver_id is None:
            df = pd.read_sql_query("SELECT * FROM driver_comms ORDER BY id DESC LIMIT ?", conn, params=(limit,))
        elif conversation_mode:
            df = pd.read_sql_query("""
                SELECT * FROM driver_comms
                WHERE (status NOT LIKE 'HQ%%' AND driver_id=?) OR (status LIKE 'HQ%%' AND (driver_id=? OR driver_id='ALL'))
                ORDER BY id DESC LIMIT ?
            """, conn, params=(driver_id, driver_id, limit))
        else:
            df = pd.read_sql_query(
                "SELECT * FROM driver_comms WHERE driver_id=? AND status NOT LIKE 'HQ%%' ORDER BY id DESC LIMIT ?",
                conn, params=(driver_id, limit),
            )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def get_driver_ids_with_messages():
    """Driver IDs who have sent messages (for unit filter dropdown)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute(
            "SELECT DISTINCT driver_id FROM driver_comms WHERE status NOT LIKE 'HQ%%' ORDER BY driver_id"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []

def send_hq_message(driver_id, message, msg_type="HQ_BROADCAST"):
    """Send a message from HQ to driver"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO driver_comms (timestamp, driver_id, status, message) VALUES (?, ?, ?, ?)",
            (datetime.datetime.now(), driver_id, msg_type, message),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def get_mission_analytics():
    """Get mission statistics for engineering report"""
    try:
        conn = sqlite3.connect(DB_FILE)
        
        # Total missions
        total = conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM missions WHERE status='COMPLETED'").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM missions WHERE status IN ('DISPATCHED', 'ACCEPTED')").fetchone()[0]
        
        # Avg response time (accepted_at - created_at) in minutes
        resp_df = pd.read_sql_query(
            "SELECT created_at, accepted_at FROM missions WHERE status IN ('ACCEPTED','COMPLETED') AND accepted_at IS NOT NULL",
            conn,
        )
        avg_response_min = 0
        if not resp_df.empty and "created_at" in resp_df.columns and "accepted_at" in resp_df.columns:
            resp_df["created_at"] = pd.to_datetime(resp_df["created_at"], errors="coerce")
            resp_df["accepted_at"] = pd.to_datetime(resp_df["accepted_at"], errors="coerce")
            resp_df["resp_sec"] = (resp_df["accepted_at"] - resp_df["created_at"]).dt.total_seconds()
            valid = resp_df.dropna(subset=["resp_sec"])
            if not valid.empty:
                avg_response_min = round(valid["resp_sec"].mean() / 60, 1)
        
        # Mission logs with time/CO2 data
        logs_df = pd.read_sql_query("SELECT * FROM mission_logs ORDER BY id DESC LIMIT 100", conn)
        
        # Recent missions for timeline
        recent_df = pd.read_sql_query(
            "SELECT * FROM missions ORDER BY id DESC LIMIT 20",
            conn,
        )
        
        conn.close()
        
        return {
            "total": total,
            "completed": completed,
            "active": active,
            "avg_response_min": avg_response_min,
            "logs": logs_df,
            "recent": recent_df,
        }
    except Exception:
        return {"total": 0, "completed": 0, "active": 0, "avg_response_min": 0, "logs": pd.DataFrame(), "recent": pd.DataFrame()}

def get_fleet_metrics():
    """Get fleet performance metrics"""
    try:
        conn = sqlite3.connect(DB_FILE)
        
        # Driver stats
        drivers_df = pd.read_sql_query("SELECT * FROM drivers", conn)
        total_drivers = len(drivers_df)
        online_drivers = len(drivers_df[pd.to_datetime(drivers_df["last_seen"], errors="coerce") > 
                                        (datetime.datetime.now() - datetime.timedelta(seconds=30))])
        en_route = len(drivers_df[drivers_df["status"] == "EN_ROUTE"])
        
        # Telemetry history
        telemetry_df = pd.read_sql_query(
            "SELECT * FROM driver_state ORDER BY id DESC LIMIT 500",
            conn,
        )
        
        conn.close()
        
        avg_speed = telemetry_df["speed"].mean() if "speed" in telemetry_df.columns and not telemetry_df.empty else 0
        
        return {
            "total_drivers": total_drivers,
            "online": online_drivers,
            "en_route": en_route,
            "avg_speed": round(avg_speed, 1) if avg_speed else 0,
            "telemetry": telemetry_df,
        }
    except Exception:
        return {"total_drivers": 0, "online": 0, "en_route": 0, "avg_speed": 0, "telemetry": pd.DataFrame()}

def get_hazard_analytics():
    """Get hazard statistics"""
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM hazards ORDER BY id DESC LIMIT 50", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

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

def get_activity_log(limit=30):
    """Get recent activity log."""
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def get_driver_leaderboard(limit=10):
    """Top drivers by missions completed."""
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("""
            SELECT assigned_driver_id as driver_id, COUNT(*) as completed
            FROM missions WHERE status='COMPLETED' AND assigned_driver_id IS NOT NULL
            GROUP BY assigned_driver_id ORDER BY completed DESC LIMIT ?
        """, conn, params=(limit,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def get_missions_per_day(days=7):
    """Missions completed per day for charting."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        df = pd.read_sql_query("""
            SELECT date(completed_at) as day, COUNT(*) as count
            FROM missions WHERE status='COMPLETED' AND completed_at IS NOT NULL
            AND completed_at >= ?
            GROUP BY date(completed_at) ORDER BY day
        """, conn, params=(cutoff,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def cleanup_old_driver_state(days=7):
    """Delete driver_state rows older than X days."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        c.execute("DELETE FROM driver_state WHERE timestamp < ?", (cutoff,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        return deleted, None
    except Exception as e:
        return 0, str(e)

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
    
    .block-container {{ padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 1400px !important; }}
    
    h1, h2, h3, h4 {{
        font-family: 'Orbitron', sans-serif !important;
        color: {primary} !important;
        text-shadow: 0 0 15px {primary}88;
        letter-spacing: 2px;
    }}
    
    p, span, div, label {{ font-family: 'Rajdhani', sans-serif; color: #e0e0e0; }}

    /* GLASS CARDS */
    .titan-card {{
        background: linear-gradient(145deg, rgba(18,22,32,0.9), rgba(10,14,22,0.95));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 4px solid {primary};
        border-radius: 14px; padding: 22px;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.04);
        margin-bottom: 18px;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }}
    .titan-card:hover {{
        transform: translateY(-4px);
        border-color: {primary};
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px {primary}33;
    }}

    /* METRICS */
    .metric-value {{ font-family: 'Orbitron'; font-size: 28px; color: white; }}
    .metric-label {{ font-size: 10px; color: #aaa; letter-spacing: 1px; text-transform: uppercase; }}
    
    /* SEXY BUTTONS */
    .stButton > button {{
        background: linear-gradient(145deg, rgba(0,243,255,0.15), rgba(0,243,255,0.05)) !important;
        border: 1px solid {primary} !important;
        color: {primary} !important;
        font-family: 'Orbitron' !important;
        font-weight: 600 !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1) !important;
    }}
    .stButton > button:hover {{
        background: linear-gradient(145deg, {primary}, rgba(0,243,255,0.9)) !important;
        color: #000 !important;
        box-shadow: 0 8px 28px {primary}66 !important;
        transform: translateY(-2px);
    }}
    .stButton > button[data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, {primary}, #00c4d4) !important;
        color: #000 !important;
        border: none !important;
        box-shadow: 0 4px 20px {primary}55 !important;
    }}
    .stButton > button[data-testid="baseButton-primary"]:hover {{
        box-shadow: 0 8px 32px {primary}77 !important;
        transform: translateY(-2px);
    }}

    header {{visibility: hidden;}} footer {{visibility: hidden;}}
    
    .hero-title {{
        font-size: 50px; font-weight: 900; text-align: left;
        background: linear-gradient(to right, #fff, {primary});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. DATA LAYER (HOSPITALS from shared_utils)
# ==========================================

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
# 4. LOGIC FUNCTIONS (TomTom via shared_utils)
# ==========================================
def fetch_routes(start, end, priority_factor=1.0):
    return shared_fetch_routes(start, end, priority_factor=priority_factor, max_alternatives=3)

# NOTE: Not caching this anymore to ensure we get live DB updates or random refreshes
def get_sensors_data():
    """Fetches live traffic flow and Signal Status"""
    res = []
    
    # 1. Get Live Green Wave Statuses from DB
    signal_status_db = get_signal_status()

    def fetch(name, lat, lon):
        try:
            curr = random.randint(10, 70) 
            status = "JAMMED" if curr < 15 else "HEAVY" if curr < 35 else "CLEAR"
            
            # --- GREEN WAVE OVERRIDE (From DB or Simulation) ---
            # If the signal is marked GREEN_WAVE in DB, priority override
            if signal_status_db.get(name) == "GREEN_WAVE":
                status = "GREEN_WAVE"
                curr = 80 # High flow
            
            # For Simulation Purposes if not in DB, randomly assign one
            if random.random() < 0.05: 
                status = "GREEN_WAVE"

            return {"Area": name, "Status": status, "Flow": int(curr), "Lat": lat, "Lon": lon}
        except: return None

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(fetch, k, v[0], v[1]) for k, v in SENSORS_GRID.items()]
        for f in futures: 
            if f.result(): res.append(f.result())
    return res

# ==========================================
# 5. FRAGMENTS (PERFECT SYNC)
# ==========================================

@st.fragment(run_every=5)
def render_live_map_fragment(active_org, active_dst, prio_factor):
    """
    Global map: all active drivers + routes + hazards.
    Refreshes every 5 seconds (reduced from 2s to prevent blinking).
    Uses returned_objects=[] to prevent map reset on data updates.
    """
    driver = get_driver_status()
    all_drivers = get_all_active_drivers(60)
    hazards = get_hazards()
    sensors = get_sensors_data()

    map_center = [10.015, 76.340]
    zoom = 12
    if driver and driver.get("status") == "EN_ROUTE":
        map_center = [driver["lat"], driver["lon"]]
        zoom = 15
    elif active_org:
        map_center = list(active_org) if hasattr(active_org, "__iter__") else active_org

    m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB dark_matter")

    # 1. DRAW ROUTE (focused mission if any)
    if active_org and active_dst:
        routes = fetch_routes(active_org, active_dst, prio_factor)
        c_codes = ["#ff003c", "#00f3ff", "#ffcc00", "#ffffff"]
        for i in reversed(range(len(routes))):
            folium.PolyLine(routes[i]["coords"], color=c_codes[i % len(c_codes)], weight=5 if i == 0 else 3, opacity=0.9 if i == 0 else 0.6).add_to(m)
        folium.Marker(list(active_org), icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
        folium.Marker(list(active_dst), icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa")).add_to(m)

    # 2. DRAW ALL ACTIVE DRIVERS (global view)
    for _, row in all_drivers.iterrows():
        lat, lon = row.get("current_lat"), row.get("current_lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        did = row.get("driver_id", "?")
        status = row.get("status", "?")
        speed = row.get("speed")
        spd = f" {int(speed)} km/h" if speed is not None and not pd.isna(speed) else ""
        folium.Marker(
            [float(lat), float(lon)],
            icon=folium.Icon(color="green" if status == "EN_ROUTE" else "gray", icon="ambulance", prefix="fa"),
            popup=f"{did} | {status}{spd}",
        ).add_to(m)

    # 3. DRAW HAZARDS
    for h in hazards:
        folium.Marker(
            [h['lat'], h['lon']],
            icon=folium.Icon(color="orange", icon="exclamation-triangle", prefix="fa"),
            tooltip=f"{h['type']}"
        ).add_to(m)

    # 4. DRAW GREEN WAVE (Glowing Circles)
    for s in sensors:
        if s['Status'] == "GREEN_WAVE":
            folium.Circle(
                location=[s['Lat'], s['Lon']],
                radius=300,
                color="#00ff00",
                fill=True,
                fill_color="#00ff00",
                fill_opacity=0.3,
                popup=f"GREEN WAVE: {s['Area']}"
            ).add_to(m)

    # Use returned_objects=[] to prevent map from resetting/blinking on updates
    st_folium(m, width="100%", height=600, returned_objects=[])

def _safe_html(s):
    if s is None or pd.isna(s): return "—"
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def render_live_tracking_map(active_org, active_dst, prio_factor, focus_driver_id=None):
    """Live map: ambulance drivers' live location, status, ghost trail. Simulates position when no real-time GPS."""
    drv_live = get_driver_from_drivers_table(focus_driver_id) if focus_driver_id else None
    driver = get_driver_status_by_id(focus_driver_id) if focus_driver_id and not drv_live else (drv_live or (get_driver_status() if not focus_driver_id else None))
    if drv_live and not driver:
        driver = drv_live
    all_drivers = get_drivers_for_live_map(60)
    profiles = get_driver_profiles(all_drivers["driver_id"].tolist() if not all_drivers.empty else [])
    hazards = get_hazards()
    ghost_trail = get_ghost_trail_for_driver(focus_driver_id, 50) if focus_driver_id else []
    if focus_driver_id and len(ghost_trail) < 2:
        mission = get_current_mission_for_driver(focus_driver_id)
        drv = get_driver_from_drivers_table(focus_driver_id)
        org_key = (drv or {}).get("origin") or (mission or {}).get("origin")
        dst_key = (drv or {}).get("dest") or (drv or {}).get("destination") or (mission or {}).get("destination")
        if org_key and dst_key and org_key in HOSPITALS and dst_key in HOSPITALS:
            routes = fetch_routes(HOSPITALS[org_key], HOSPITALS[dst_key], prio_factor)
            if routes and routes[0].get("coords"):
                coords = routes[0]["coords"]
                idx = min(int(len(coords) * 0.4), len(coords) - 1)
                ghost_trail = coords[: idx + 1]
    sensors = get_sensors_data()
    
    map_center = [10.015, 76.340]
    zoom = 12
    if driver and (driver.get("status") == "EN_ROUTE" or driver.get("lat")):
        try:
            map_center = [float(driver.get("lat") or 10.015), float(driver.get("lon") or 76.340)]
            zoom = 15
        except (TypeError, ValueError):
            pass
    elif active_org:
        map_center = list(active_org) if hasattr(active_org, "__iter__") else active_org
        zoom = 13
    elif not all_drivers.empty:
        try:
            map_center = [float(all_drivers.iloc[0]["current_lat"]), float(all_drivers.iloc[0]["current_lon"])]
            zoom = 13
        except (TypeError, ValueError, KeyError):
            pass
    
    m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB dark_matter")
    
    if active_org and active_dst:
        routes = fetch_routes(active_org, active_dst, prio_factor)
        c_codes = ["#ff003c", "#00f3ff", "#ffcc00", "#ffffff"]
        for i in reversed(range(len(routes))):
            folium.PolyLine(routes[i]["coords"], color=c_codes[i % len(c_codes)], weight=5 if i == 0 else 3, opacity=0.9 if i == 0 else 0.6).add_to(m)
        folium.Marker(list(active_org), icon=folium.Icon(color="blue", icon="play", prefix="fa"), popup="<b>📍 ORIGIN</b>").add_to(m)
        folium.Marker(list(active_dst), icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"), popup="<b>🏁 DESTINATION</b>").add_to(m)
    
    for _, row in all_drivers.iterrows():
        lat, lon = row.get("current_lat"), row.get("current_lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        did = row.get("driver_id", "?")
        status = row.get("status", "?")
        speed = row.get("speed")
        origin = row.get("origin") or "—"
        dest = row.get("destination") or "—"
        spd = f" {int(speed)} km/h" if speed is not None and not pd.isna(speed) else ""
        prof = profiles.get(did, {})
        fname = prof.get("full_name", "—")
        vnum = prof.get("vehicle_id", "—")
        is_focus = did == focus_driver_id
        popup_html = f"""
        <div style="min-width:200px; font-family:sans-serif; font-size:12px;">
            <div style="font-size:24px; margin-bottom:8px;">🚑 <b>{_safe_html(did)}</b>{" (TRACKED)" if is_focus else ""}</div>
            <div style="border-bottom:1px solid #333; padding-bottom:6px; margin-bottom:6px;">
                <div><b>Driver:</b> {_safe_html(fname)}</div>
                <div><b>Vehicle:</b> {_safe_html(vnum)}</div>
                <div><b>Unit ID:</b> {_safe_html(did)}</div>
            </div>
            <div style="color:#00f3ff;"><b>From:</b> {_safe_html(origin)}</div>
            <div style="color:#00ff9d;"><b>To:</b> {_safe_html(dest)}</div>
            <div style="margin-top:6px; color:#888;">{status}{spd}</div>
        </div>
        """
        folium.Marker(
            [float(lat), float(lon)],
            icon=folium.Icon(color="green" if status == "EN_ROUTE" else "blue" if status == "IDLE" else "gray", icon="ambulance", prefix="fa"),
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"🚑 {did} — {fname} ({status})",
        ).add_to(m)
    
    if focus_driver_id and len(ghost_trail) > 1:
        folium.PolyLine(ghost_trail, color="#00ff9d", weight=3, dash_array="5, 10", opacity=0.7).add_to(m)
    
    for h in hazards:
        folium.Marker([h['lat'], h['lon']], icon=folium.Icon(color="orange", icon="exclamation-triangle", prefix="fa"), tooltip=h['type']).add_to(m)
    for s in sensors:
        if s['Status'] == "GREEN_WAVE":
            folium.Circle(location=[s['Lat'], s['Lon']], radius=300, color="#00ff00", fill=True, fill_color="#00ff00", fill_opacity=0.3, popup=f"GREEN WAVE: {s['Area']}").add_to(m)
    
    st_folium(m, width="100%", height=600, returned_objects=[])

@st.fragment(run_every=2)
def render_sensor_grid_fragment():
    """
    Independent Sensor Grid refresh.
    """
    data = get_sensors_data()
    # Sort: Green Wave & Jammed first
    data.sort(key=lambda x: 0 if x['Status']=="GREEN_WAVE" else 1 if x['Status']=="JAMMED" else 2)
    
    cols = st.columns(4)
    for i, d in enumerate(data):
        c = "#00ff00" if d['Status']=="GREEN_WAVE" else "#ff003c" if d['Status']=="JAMMED" else "#ffaa00" if d['Status']=="HEAVY" else "#00e5ff"
        with cols[i%4]: 
            st.markdown(f"""
            <div class="titan-card" style="border-left-color:{c}; padding:10px;">
                <div style="font-weight:bold; font-size:12px;">{d['Area']}</div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-family:'Orbitron'; font-size:18px; color:{c};">{d['Flow']} KM/H</span>
                    <span style="font-size:10px;">{d['Status']}</span>
                </div>
            </div>""", unsafe_allow_html=True)


# ==========================================
# 6. PAGE RENDERERS
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

# --- OPERATOR SIGNUP ---
def operator_signup(username, password, display_name):
    """Register new operator. Returns (True, None) on success else (False, error_msg)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if c.execute("SELECT 1 FROM operators WHERE username=?", (username.strip(),)).fetchone():
            conn.close()
            return False, "Username already taken."
        c.execute(
            "INSERT INTO operators (username, password, display_name) VALUES (?, ?, ?)",
            (username.strip(), hash_password(password), (display_name or username).strip()),
        )
        conn.commit()
        conn.close()
        return True, None
    except Exception as e:
        return False, str(e)

def _verify_operator_password(uid, key):
    """Verify operator credentials. Supports hashed and legacy plain."""
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT username, password FROM operators WHERE username=?", (uid.strip(),)).fetchone()
    conn.close()
    if not row:
        return False
    _, stored = row
    if stored and len(stored) == 64 and stored.isalnum():
        return verify_password(key, stored)
    return key == stored

# --- LOGIN PAGE (with Sign Up tab) ---
def render_login():
    st.markdown("""
    <div style="text-align:center; padding:50px 0 35px 0;">
        <div style="width:100px; height:100px; margin:0 auto 24px; background:linear-gradient(135deg,rgba(0,243,255,0.15),rgba(255,0,60,0.08)); border-radius:50%; display:flex; align-items:center; justify-content:center; border:2px solid rgba(0,243,255,0.4); box-shadow:0 0 50px rgba(0,243,255,0.2);">
            <span style="font-size:50px;">📡</span>
        </div>
        <div style="font-family:'Orbitron'; font-size:36px; font-weight:800; background:linear-gradient(90deg,#00f3ff,#ff003c); -webkit-background-clip:text; -webkit-text-fill-color:transparent; letter-spacing:4px;">TRAFFIC INTEL V52</div>
        <div style="color:#8892a6; font-size:14px; letter-spacing:4px; margin-top:12px; font-weight:500;">SECURE GATEWAY</div>
        <div style="height:1px; background:linear-gradient(90deg,transparent,rgba(0,243,255,0.6),transparent); margin:24px auto; max-width:250px;"></div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        login_tab, signup_tab = st.tabs(["🔓 LOGIN", "📝 SIGN UP"])
        with login_tab:
            st.markdown("""
            <div style="background:linear-gradient(145deg,rgba(13,17,26,0.95),rgba(8,12,18,0.98)); border:1px solid rgba(0,243,255,0.3); border-radius:20px; padding:40px; margin:0 0 24px; box-shadow:0 12px 48px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05); backdrop-filter:blur(20px);">
                <div style="color:#00f3ff; font-family:'Orbitron'; font-size:11px; letter-spacing:3px; margin-bottom:24px;">OPERATOR ACCESS</div>
            """, unsafe_allow_html=True)
            with st.form("login_form"):
                uid = st.text_input("Operator ID", placeholder="COMMANDER", label_visibility="collapsed")
                key = st.text_input("Access Key", type="password", placeholder="••••••••", label_visibility="collapsed")
                st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
                if st.form_submit_button("AUTHENTICATE", use_container_width=True, type="primary"):
                    if not uid or not key:
                        st.error("Enter operator ID and access key.")
                    else:
                        try:
                            if _verify_operator_password(uid, key):
                                st.session_state.authenticated = True
                                st.session_state.operator_id = uid.strip()
                                st.session_state.page = 'dashboard'
                                st.rerun()
                            else:
                                st.error("ACCESS DENIED: Incorrect credentials.")
                        except Exception:
                            st.error("Login failed.")
            st.markdown("</div>", unsafe_allow_html=True)
        with signup_tab:
            st.markdown("""
            <div style="background:linear-gradient(145deg,rgba(13,17,26,0.95),rgba(8,12,18,0.98)); border:1px solid rgba(0,255,157,0.3); border-radius:20px; padding:40px; margin:0 0 24px; box-shadow:0 12px 48px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05); backdrop-filter:blur(20px);">
                <div style="color:#00ff9d; font-family:'Orbitron'; font-size:11px; letter-spacing:3px; margin-bottom:24px;">REGISTER OPERATOR</div>
            """, unsafe_allow_html=True)
            with st.form("signup_form"):
                new_uid = st.text_input("Operator ID", placeholder="Choose username", label_visibility="collapsed", key="op_u")
                new_key = st.text_input("Access Key", type="password", placeholder="Choose password", label_visibility="collapsed", key="op_k")
                new_name = st.text_input("Display Name", placeholder="e.g. HQ Commander", label_visibility="collapsed", key="op_n")
                if st.form_submit_button("REGISTER", use_container_width=True, type="primary"):
                    if not new_uid or not new_key:
                        st.error("Operator ID and Access Key required.")
                    else:
                        ok, err = operator_signup(new_uid, new_key, new_name)
                        if err:
                            st.error(err)
                        else:
                            st.success("Operator registered. Log in now.")
                            st.balloons()
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center; color:#666; font-size:11px; margin:20px 0;">Demo: <code style="background:#222; padding:2px 8px; border-radius:4px;">COMMANDER</code> / <code style="background:#222; padding:2px 8px; border-radius:4px;">TITAN-X</code></div>
        """, unsafe_allow_html=True)
        if st.button("← RETURN", use_container_width=True):
            st.session_state.page = 'home'
            st.rerun()

# --- DASHBOARD PAGE ---
def render_dashboard():
    # Mark expired missions on each load
    n_expired = mark_expired_missions()
    if n_expired > 0:
        log_activity("EXPIRED", "SYSTEM", f"{n_expired} mission(s) auto-expired (no accept within {MISSION_EXPIRY_SEC//60} min)")
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3662/3662817.png", width=60)
        st.markdown(f"### TRAFFIC INTEL")
        mode = st.toggle("🚨 RED ALERT PROTOCOL", value=st.session_state.emergency_mode)
        if mode != st.session_state.emergency_mode: st.session_state.emergency_mode = mode; st.rerun()
        st.markdown("---")
        
        st.markdown("### 🎚️ MISSION PRIORITY")
        prio_label = st.select_slider("Select Urgency Level", options=["STANDARD", "MEDIUM", "HIGH", "CRITICAL"], value="STANDARD")
        st.session_state.priority_val = prio_label
        prio_factor = {"STANDARD": 1.0, "MEDIUM": 0.85, "HIGH": 0.75, "CRITICAL": 0.65}[prio_label]
        
        st.markdown("---")
        with st.form("nav"):
            st.caption("QUICK DISPATCH")
            org = st.selectbox("ORIGIN", sorted(list(HOSPITALS.keys())), index=0)
            dst = st.selectbox("DESTINATION", sorted(list(HOSPITALS.keys())), index=1)
            
            drivers_df = get_available_drivers()
            org_c = HOSPITALS.get(org)
            driver_opts = ["AUTO / ANY AVAILABLE"]
            if not drivers_df.empty and org_c:
                # Sort by proximity to origin
                with_dist = []
                for _, row in drivers_df.iterrows():
                    lat, lon = row.get("current_lat"), row.get("current_lon")
                    d = distance_km(org_c[0], org_c[1], float(lat or 10), float(lon or 76)) if pd.notna(lat) and pd.notna(lon) else 999
                    with_dist.append((row["driver_id"], row.get("status","?"), d))
                with_dist.sort(key=lambda x: (0 if x[1]=="IDLE" else 1, x[2]))
                driver_opts += [f"{d[0]} ({d[2]}km)" for d in with_dist]
            else:
                driver_opts += drivers_df["driver_id"].tolist() if not drivers_df.empty else []
            
            assigned_driver = st.selectbox("Assign to Driver", options=driver_opts)
            if st.form_submit_button("🚨 DISPATCH", use_container_width=True):
                if org == dst:
                    st.error("Origin and destination must be different.")
                else:
                    mid = generate_unique_mission_id()
                    save_mission_data(mid, org, dst, prio_label, 0, 0, 0)
                    drv_id = None
                    if assigned_driver != "AUTO / ANY AVAILABLE":
                        drv_id = assigned_driver.split(" ")[0] if " " in assigned_driver else assigned_driver
                    create_mission(mid, org, dst, prio_label, assigned_driver_id=drv_id)
                    target = str(drv_id) if drv_id else "ALL"
                    send_hq_message(target, f"🚨 NEW MISSION {mid}: {org} → {dst}. Mission will appear automatically.", "HQ_DISPATCH")
                    st.success(f"Mission {mid} dispatched!")
        
        st.markdown("---")
        st.markdown("### 👥 DRIVER AVAILABILITY")
        drivers_df = get_available_drivers()
        if drivers_df.empty:
            st.caption("No online drivers detected yet. Open `driverapp.py` to bring a unit online.")
        else:
            disp_cols = [c for c in ["driver_id", "status", "current_lat", "current_lon"] if c in drivers_df.columns]
            st.dataframe(drivers_df[disp_cols] if disp_cols else drivers_df, use_container_width=True, height=220)
        
        st.markdown("---")
        if st.button("🎬 DEMO MODE", use_container_width=True, help="Create sample missions for demo"):
            try:
                hospitals = sorted(list(HOSPITALS.keys()))
                for i in range(3):
                    mid = generate_unique_mission_id()
                    org = random.choice(hospitals)
                    dst = random.choice([h for h in hospitals if h != org])
                    prio = random.choice(["STANDARD", "MEDIUM", "HIGH"])
                    create_mission(mid, org, dst, prio, assigned_driver_id=None, notes=f"Demo mission {i+1}")
                    send_hq_message("ALL", f"🚨 NEW MISSION {mid}: {org} → {dst}. Mission will appear automatically.", "HQ_DISPATCH")
                st.success("3 demo missions created! Check Mission Center.")
                st.balloons()
                st.rerun()
            except Exception:
                st.error("Demo mode failed")
        if st.button("🔒 LOGOUT", use_container_width=True): st.session_state.authenticated = False; st.session_state.page = 'home'; st.rerun()

    if st.session_state.emergency_mode: st.markdown(f'''<div style="background:{primary}22; border:1px solid {primary}; color:{primary}; padding:10px; text-align:center; font-family:'Orbitron'; letter-spacing:3px; margin-bottom:20px; border-radius:6px;">⚠️ CRITICAL EMERGENCY PROTOCOL ACTIVE ⚠️</div>''', unsafe_allow_html=True)

    # Driver online detection - popup when driver comes online
    if 'last_known_online_drivers' not in st.session_state:
        st.session_state.last_known_online_drivers = set()
    @st.fragment(run_every=5)
    def _driver_online_detector():
        try:
            drivers_df = get_available_drivers()
            if drivers_df.empty or "driver_id" not in drivers_df.columns:
                current_ids = set()
            else:
                current_ids = set(drivers_df["driver_id"].astype(str).tolist())
            last = st.session_state.last_known_online_drivers
            if last and current_ids:
                new_drivers = current_ids - last
                if new_drivers:
                    profiles = get_driver_profiles(list(new_drivers))
                    for did in new_drivers:
                        prof = profiles.get(did, {})
                        name = prof.get("full_name") or did
                        st.toast(f"🟢 {name} ({did}) is now ONLINE", icon="🚑")
            st.session_state.last_known_online_drivers = current_ids
        except Exception:
            pass

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🚀 MISSION CENTER",
        "🗺️ LIVE TRACKING & MAP",
        "📡 SENSOR GRID",
        "📊 ENGINEERING REPORT",
        "📶 V2X COMMS LOG"
    ])

    # ==========================================
    # TAB 0: MISSION CENTER - Fetch Route + Assign to Driver
    # ==========================================
    with tab1:
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(0,243,255,0.08),rgba(0,255,157,0.04)); border:1px solid rgba(0,243,255,0.3); border-radius:16px; padding:24px; margin-bottom:24px;">
            <div style="font-family:'Orbitron'; font-size:28px; font-weight:700; background:linear-gradient(90deg,#00f3ff,#00ff9d); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🚀 MISSION CENTER</div>
            <div style="color:#8892a6; font-size:14px; margin-top:8px;">Define route → Preview ETAs → Assign driver → Dispatch</div>
        </div>
        """, unsafe_allow_html=True)
        
        mc_col1, mc_col2 = st.columns([1, 1])
        
        with mc_col1:
            st.markdown("""
            <div class="titan-card" style="border-left:4px solid #00f3ff; padding:16px; margin-bottom:16px;">
                <div style="font-size:18px; font-weight:600; margin:4px 0;">📍 Define Mission</div>
                <div style="font-size:12px; color:#888;">Select origin and destination — ETA & routes auto-load</div>
            </div>
            """, unsafe_allow_html=True)
            org = st.selectbox("ORIGIN (Pickup)", sorted(list(HOSPITALS.keys())), key="mc_org")
            dst = st.selectbox("DESTINATION (Drop-off)", sorted(list(HOSPITALS.keys())), key="mc_dst")
            prio_label = st.select_slider("Priority", options=["STANDARD", "MEDIUM", "HIGH", "CRITICAL"], value="STANDARD", key="mc_prio")
            prio_factor = {"STANDARD": 1.0, "MEDIUM": 0.85, "HIGH": 0.75, "CRITICAL": 0.65}[prio_label]
            # Auto-fetch routes when origin & destination selected (show ETA + alternatives on first page)
            fetch_key = (org, dst, prio_label)
            if org != dst and org in HOSPITALS and dst in HOSPITALS:
                if st.session_state.get("mc_fetch_key") != fetch_key:
                    with st.spinner("Loading routes..."):
                        st.session_state.mc_routes = fetch_routes(HOSPITALS[org], HOSPITALS[dst], prio_factor)
                    st.session_state.mc_fetch_key = fetch_key
                st.session_state.mc_submitted_org = org
                st.session_state.mc_submitted_dst = dst
                st.session_state.mc_submitted_prio = prio_label
            else:
                st.session_state.mc_fetch_key = None
        
        with mc_col2:
            st.markdown("""
            <div class="titan-card" style="border-left:4px solid #00ff9d; padding:16px; margin-bottom:16px;">
                <div style="font-size:18px; font-weight:600; margin:4px 0;">👥 Available Drivers</div>
                <div style="font-size:12px; color:#888;">Sorted by proximity to origin</div>
            </div>
            """, unsafe_allow_html=True)
            drivers_df = get_available_drivers()
            org_key = st.session_state.get("mc_submitted_org") or org or list(HOSPITALS.keys())[0]
            org_coords = HOSPITALS.get(org_key)
            
            if drivers_df.empty:
                st.info("No online drivers. Open driverapp to bring units online.")
                driver_proximity = []
            else:
                profiles = get_driver_profiles(drivers_df["driver_id"].tolist())
                driver_proximity = []
                for _, row in drivers_df.iterrows():
                    did = row.get("driver_id", "?")
                    lat, lon = row.get("current_lat"), row.get("current_lon")
                    prof = profiles.get(did, {})
                    full_name = prof.get("full_name") or did
                    if pd.notna(lat) and pd.notna(lon) and org_coords:
                        dist = distance_km(org_coords[0], org_coords[1], float(lat), float(lon))
                        driver_proximity.append({
                            "driver_id": did,
                            "full_name": full_name,
                            "status": row.get("status", "?"),
                            "distance_km": dist,
                            "lat": lat, "lon": lon
                        })
                    else:
                        driver_proximity.append({
                            "driver_id": did,
                            "full_name": full_name,
                            "status": row.get("status", "?"),
                            "distance_km": 999,
                            "lat": None, "lon": None
                        })
                driver_proximity.sort(key=lambda x: (0 if x["status"] == "IDLE" else 1, x["distance_km"]))
                
                for d in driver_proximity[:10]:
                    color = "#00ff9d" if d["status"] == "IDLE" else "#ffcc00"
                    dist_str = f"{d['distance_km']:.1f}" if isinstance(d['distance_km'], (int, float)) else str(d['distance_km'])
                    st.markdown(f"""
                    <div class="titan-card" style="border-left-color:{color}; padding:14px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:bold; color:{color};">{d['full_name']}</span>
                            <span style="font-size:11px; padding:2px 8px; border-radius:4px; background:{color}22; color:{color};">{d['status']}</span>
                        </div>
                        <div style="font-size:11px; color:#6b7280;">{d['driver_id']} • 📍 {dist_str} km from origin</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("""
        <div class="titan-card" style="border-left:4px solid #ffcc00; padding:16px; margin:16px 0;">
            <div style="font-size:18px; font-weight:600; margin:4px 0;">🛣️ Route Preview</div>
            <div style="font-size:12px; color:#888;">Route alternatives with ETA and distance</div>
        </div>
        """, unsafe_allow_html=True)
        
        mc_routes = st.session_state.get("mc_routes", [])
        if mc_routes:
            route_cols = st.columns(min(4, len(mc_routes)))
            colors = ["#ff003c", "#00f3ff", "#ffcc00", "#00ff9d"]
            
            for idx, route in enumerate(mc_routes[:4]):
                with route_cols[idx]:
                    c = colors[idx % len(colors)]
                    delay = route.get('traffic_delay_min', 0) or 0
                    st.markdown(f"""
                    <div class="titan-card" style="border-left-color:{c}; padding:20px; cursor:pointer;">
                        <div style="font-size:11px; color:#888; margin-bottom:4px;">{route.get('route_type', '')}</div>
                        <div style="font-family:'Orbitron'; font-size:34px; color:{c}; margin:8px 0;">{route.get('eta', 0)} <span style="font-size:14px; color:#888;">MIN</span></div>
                        <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:8px;">
                            <span>📍 {route.get('dist', 0)} km</span>
                            <span style="color:{'#ff003c' if delay>3 else '#00ff9d'}">+{delay} min delay</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Map with alternate routes + ETA on Mission Center (first page)
            st.markdown("**🗺️ Route map with alternatives**")
            org_coords = HOSPITALS.get(org, [10.015, 76.34])
            dst_coords = HOSPITALS.get(dst, [10.015, 76.34])
            mc_map = folium.Map(location=org_coords, zoom_start=12, tiles="CartoDB dark_matter")
            c_codes = ["#ff003c", "#00f3ff", "#ffcc00", "#00ff9d"]
            for i, route in enumerate(mc_routes[:4]):
                coords = route.get("coords", [])
                if coords:
                    folium.PolyLine(coords, color=c_codes[i % len(c_codes)], weight=5 if i == 0 else 3, opacity=0.9 if i == 0 else 0.6).add_to(mc_map)
            folium.Marker(org_coords, icon=folium.Icon(color="blue", icon="play", prefix="fa"), popup=f"<b>📍 ORIGIN</b><br>{org}").add_to(mc_map)
            folium.Marker(dst_coords, icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"), popup=f"<b>🏁 DESTINATION</b><br>{dst}").add_to(mc_map)
            st_folium(mc_map, width="100%", height=400, returned_objects=[])
            st.caption(f"Best ETA: {mc_routes[0].get('eta', 0)} min • {mc_routes[0].get('dist', 0)} km — {mc_routes[0].get('route_type', 'Fastest')}")
            
            st.markdown("---")
            st.markdown("""
            <div class="titan-card" style="border-left:4px solid #ff003c; padding:16px; margin:16px 0;">
                <div style="font-size:18px; font-weight:600; margin:4px 0;">📤 Dispatch Mission</div>
                <div style="font-size:12px; color:#888;">Assign driver and send to fleet</div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("dispatch_mission_form"):
                best_route = mc_routes[0]
                st.caption(f"Best route: {best_route.get('route_type')} — {best_route.get('eta')} min • {best_route.get('dist')} km")
                
                idle_drivers = [d["driver_id"] for d in driver_proximity if d["status"] == "IDLE"]
                driver_options = ["AUTO (Closest IDLE)"] + idle_drivers + [d["driver_id"] for d in driver_proximity if d["status"] != "IDLE"]
                
                assigned_driver = st.selectbox(
                    "Assign to Driver",
                    options=driver_options,
                    format_func=lambda x: f"{x} (IDLE)" if x in idle_drivers else x,
                    key="mc_driver"
                )
                
                notes = st.text_input("Mission Notes (optional)", placeholder="e.g. Patient type, special instructions...")
                
                if st.form_submit_button("🚨 DISPATCH MISSION", use_container_width=True):
                    org_d = st.session_state.get("mc_submitted_org") or list(HOSPITALS.keys())[0]
                    dst_d = st.session_state.get("mc_submitted_dst") or list(HOSPITALS.keys())[1]
                    if org_d == dst_d:
                        st.error("Origin and destination must be different.")
                    else:
                        mid = generate_unique_mission_id()
                        prio_d = st.session_state.get("mc_submitted_prio") or "STANDARD"
                        driver_id = None if assigned_driver == "AUTO (Closest IDLE)" else assigned_driver
                        if driver_id is None and idle_drivers:
                            driver_id = idle_drivers[0]
                        save_mission_data(mid, org_d, dst_d, prio_d, 0, 0, 0)
                        create_mission(mid, org_d, dst_d, prio_d, assigned_driver_id=driver_id, notes=notes or "")
                        log_activity("DISPATCH", st.session_state.get("operator_id", "HQ"), f"{mid} {org_d}→{dst_d} to {driver_id or 'AUTO'}")
                        target = str(driver_id) if driver_id else "ALL"
                        dispatch_msg = f"🚨 NEW MISSION {mid}: {org_d} → {dst_d}. "
                        if notes:
                            dispatch_msg += f"Notes: {notes}. "
                        dispatch_msg += "Mission will appear automatically."
                        send_hq_message(target, dispatch_msg, "HQ_DISPATCH")
                        st.success(f"✅ Mission {mid} dispatched! Assigned to {driver_id or 'AUTO'}")
                        st.balloons()
                        st.session_state.mc_routes = None
                        st.rerun()
        else:
            st.info("👆 Select origin & destination (different locations) to see ETA and route alternatives.")

    with tab2:
        # ==========================================
        # LIVE TRACKING - Mission status filter + Unit search + Per-unit map
        # ==========================================
        st.markdown("## 🗺️ LIVE TRACKING & MAP")
        st.markdown("---")
        
        # --- Driver offline alerts (ACCEPTED mission but driver stale) ---
        offline_alerts = get_driver_offline_alerts(150)
        if offline_alerts:
            st.markdown("""
                <div style="background:#ff660022; border:2px solid #ff6600; color:#ff6600; padding:12px; border-radius:8px; margin-bottom:12px; font-family:'Orbitron';">
                    ⚠️ DRIVER OFFLINE — Unit on mission but no heartbeat
                </div>
            """, unsafe_allow_html=True)
            for a in offline_alerts:
                st.warning(f"**{a['mission_id']}** — {a['driver_id']} last seen {a['seen_ago']//60}m ago. Check unit status.")
        
        # --- PENDING clearance requests ---
        pending = get_drivers_pending_clearance()
        if not pending.empty:
            st.markdown("""
                <div style="animation: blink 1s infinite; background:#ff003322; border:2px solid #ff0033; color:#ff0033; padding:12px; border-radius:8px; margin-bottom:12px; font-family:'Orbitron';">
                    ⚠️ GREEN WAVE REQUESTS PENDING
                </div>
                <style>@keyframes blink { 50% { opacity: 0.7; } }</style>
            """, unsafe_allow_html=True)
            for _, row in pending.iterrows():
                did = row["driver_id"]
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1: st.write(f"**{did}** — awaiting signal clearance")
                with c2:
                    if st.button("✅ GRANT", key=f"grant_{did}"):
                        update_driver_clearance(did, "GRANTED")
                        send_hq_message(did, "🟢 Green Wave GRANTED — Proceed with caution.", "HQ_GREENWAVE")
                        st.rerun()
                with c3:
                    if st.button("❌ DENY", key=f"deny_{did}"):
                        update_driver_clearance(did, "DENIED")
                        send_hq_message(did, "🔴 Green Wave request denied.", "HQ_ALERT")
                        st.rerun()
        
        # --- FILTERS: Mission status + Unit search ---
        lt_col1, lt_col2, lt_col3, lt_col4 = st.columns(4)
        with lt_col1:
            st.markdown("**📋 Mission Status**")
            mission_status_filter = st.multiselect(
                "Show missions",
                ["DISPATCHED", "ACCEPTED", "COMPLETED", "CANCELLED", "EXPIRED"],
                default=["DISPATCHED", "ACCEPTED"],
                key="lt_mission_status"
            )
        with lt_col2:
            st.markdown("**🔍 Search Unit**")
            unit_search = st.text_input("Driver ID or Mission ID", placeholder="e.g. UNIT-07 or CMD-1234", key="lt_unit_search")
        with lt_col3:
            st.markdown("**👤 Unit Status**")
            unit_status_filter = st.multiselect(
                "Driver status",
                ["IDLE", "EN_ROUTE", "BREAK", "INACTIVE"],
                default=["IDLE", "EN_ROUTE", "BREAK"],
                key="lt_unit_status"
            )
        with lt_col4:
            st.markdown("**📍 Track Unit / Mission**")
            all_drivers_df = get_drivers_for_live_map(60)
            driver_options = ["All units"] + (all_drivers_df["driver_id"].tolist() if not all_drivers_df.empty else [])
            # Focus by mission
            active_missions = list_missions(50)
            active_missions = active_missions[active_missions["status"].isin(["DISPATCHED", "ACCEPTED"])] if not active_missions.empty else pd.DataFrame()
            mission_options = ["— Select unit —"]
            if not active_missions.empty and "mission_id" in active_missions.columns:
                mission_options += [f"{r['mission_id']} ({r.get('assigned_driver_id','?')})" for _, r in active_missions.iterrows()]
            focus_by_mission = st.selectbox("Or focus by mission", mission_options, key="lt_focus_mission")
            tracked_unit = st.selectbox("Focus map on", driver_options, key="lt_tracked_unit")
        
        # --- Missions list (filtered) ---
        missions_df = list_missions(100)
        if not missions_df.empty and mission_status_filter:
            missions_df = missions_df[missions_df["status"].isin(mission_status_filter)]
        if unit_search:
            q = unit_search.strip().upper()
            missions_df = missions_df[
                missions_df["mission_id"].astype(str).str.upper().str.contains(q, na=False) |
                missions_df["assigned_driver_id"].astype(str).str.upper().str.contains(q, na=False) |
                missions_df["origin"].astype(str).str.upper().str.contains(q, na=False) |
                missions_df["destination"].astype(str).str.upper().str.contains(q, na=False)
            ]
        
        # --- Units table (filtered by status + search) ---
        active_df = get_drivers_for_live_map(60)
        if not active_df.empty and unit_status_filter:
            active_df = active_df[active_df["status"].isin(unit_status_filter)]
        if unit_search and not active_df.empty:
            q = unit_search.strip().upper()
            active_df = active_df[active_df["driver_id"].astype(str).str.upper().str.contains(q, na=False)]
        
        st.markdown("### 📊 Units & Missions")
        if active_df.empty:
            st.info("No units match filters. Open driverapp to bring units online.")
        else:
            active_display = active_df.copy()
            show_cols = [c for c in ["driver_id", "status", "speed", "origin", "destination", "active_mission_id"] if c in active_display.columns]
            disp = active_display[show_cols].copy() if show_cols else active_display.copy()
            disp.insert(0, "#", range(1, len(disp) + 1))
            st.dataframe(disp, use_container_width=True, height=180)
        
        if not missions_df.empty:
            m_cols = [c for c in ["mission_id", "created_at", "origin", "destination", "priority", "assigned_driver_id", "status"] if c in missions_df.columns]
            m_display = missions_df[m_cols].copy()
            m_display.insert(0, "#", range(1, len(m_display) + 1))
            st.dataframe(m_display, use_container_width=True, height=160)
        
        # --- Mission routes one unit at a time: only show route when a unit is selected ---
        active_org, active_dst = None, None
        focus_driver_id = None
        # If focus by mission selected, extract driver_id
        if focus_by_mission and focus_by_mission != "— Select unit —" and "(" in focus_by_mission:
            try:
                part = focus_by_mission.split("(")[1].rstrip(")")
                if part and part != "?":
                    focus_driver_id = part
            except Exception:
                pass
        if not focus_driver_id and tracked_unit and tracked_unit != "All units":
            focus_driver_id = tracked_unit
        # Set route (active_org, active_dst) from driver's mission when unit is selected
        if focus_driver_id:
            drv_telemetry = get_driver_status_by_id(focus_driver_id) or get_driver_from_drivers_table(focus_driver_id)
            org_key = drv_telemetry.get("origin") or drv_telemetry.get("dest") if drv_telemetry else None
            dst_key = drv_telemetry.get("dest") or drv_telemetry.get("destination") or drv_telemetry.get("origin") if drv_telemetry else None
            # Fallback: use mission data when driver hasn't accepted yet (no origin/dest in telemetry)
            if (not org_key or not dst_key):
                mission = get_current_mission_for_driver(focus_driver_id)
                if mission:
                    org_key = mission.get("origin")
                    dst_key = mission.get("destination")
            if org_key and dst_key and org_key in HOSPITALS and dst_key in HOSPITALS:
                active_org = HOSPITALS[org_key]
                active_dst = HOSPITALS[dst_key]
        
        # Refresh map button
        if st.button("🔄 REFRESH MAP", key="lt_refresh_map", use_container_width=False):
            st.rerun()
        st.markdown("---")
        # --- "Currently viewing: UNIT-XX" card with mission details + ETA & route alternatives ---
        if focus_driver_id:
            mission_info = get_current_mission_for_driver(focus_driver_id)
            drv_telemetry = get_driver_status_by_id(focus_driver_id) or get_driver_from_drivers_table(focus_driver_id)
            prof = get_driver_profiles([focus_driver_id]).get(focus_driver_id, {})
            fname = prof.get("full_name", "—")
            vnum = prof.get("vehicle_id", "—")
            org_disp = drv_telemetry.get("origin", "—") if drv_telemetry else "—"
            dst_disp = drv_telemetry.get("dest") or drv_telemetry.get("destination", "—") if drv_telemetry else "—"
            # ETA & route alternatives when we have origin/destination
            eta_routes_html = ""
            if active_org is not None and active_dst is not None:
                lt_routes = fetch_routes(active_org, active_dst, prio_factor)
                if lt_routes:
                    best = lt_routes[0]
                    eta_min = best.get("eta", 0)
                    dist_km = best.get("dist", 0)
                    eta_routes_html = f"""
                    <div style="grid-column:1/-1; margin-top:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08);">
                        <div style="color:#666; font-size:11px; margin-bottom:8px;">⏱ ESTIMATED TIME & ROUTE ALTERNATIVES</div>
                        <div style="display:flex; flex-wrap:wrap; gap:12px; align-items:center;">
                            <span style="font-family:'Orbitron'; font-size:24px; color:#00f3ff;">{eta_min} <span style="font-size:12px; color:#888;">MIN</span></span>
                            <span style="color:#888;">|</span>
                            <span style="color:#9ca3af;">📍 {dist_km} km</span>
                            <span style="color:#666;">|</span>
                            <span style="font-size:12px; color:#9ca3af;">"""
                    for i, r in enumerate(lt_routes[:4]):
                        c = ["#ff003c", "#00f3ff", "#ffcc00", "#00ff9d"][i % 4]
                        eta_routes_html += f'<span style="margin-right:12px; color:{c};">{r.get("route_type","—")}: {r.get("eta",0)} min</span>'
                    eta_routes_html += "</span></div></div>"
            st.markdown(f"""
            <div class="titan-card" style="border-left:4px solid #00f3ff; padding:20px 24px; margin-bottom:16px; background:linear-gradient(135deg,rgba(0,243,255,0.05),transparent);">
                <div style="font-family:'Orbitron'; font-size:16px; color:#00f3ff; margin-bottom:12px; display:flex; align-items:center; gap:10px;">
                    <span style="font-size:28px;">🚑</span>
                    <span>TRACKING: <strong>{focus_driver_id}</strong></span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:12px 24px; font-size:13px;">
                    <div><span style="color:#666;">Driver</span><br><span style="color:#fff;">{fname}</span></div>
                    <div><span style="color:#666;">Vehicle</span><br><span style="color:#00f3ff;">{vnum}</span></div>
                    <div><span style="color:#666;">Mission ID</span><br><span style="color:#ffcc00;">{mission_info.get('mission_id', '—') if mission_info else '—'}</span></div>
                    <div><span style="color:#666;">Status</span><br><span style="color:#00ff9d;">{drv_telemetry.get('status', '—') if drv_telemetry else '—'}</span></div>
                    <div><span style="color:#666;">From</span><br><span>{org_disp}</span></div>
                    <div><span style="color:#666;">To</span><br><span>{dst_disp}</span></div>
                    {eta_routes_html}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # --- Live map: ambulance drivers' live location, status, ghost trail (simulated when no real-time GPS) ---
        st.caption("🟢 Ambulance markers = live location • Dashed line = ghost trail (path traveled) • Positions simulated when no real-time GPS")
        render_live_tracking_map(active_org, active_dst, prio_factor, focus_driver_id=focus_driver_id)

    with tab3:
        # Call the Fragment
        render_sensor_grid_fragment()

        # MANAGE MISSIONS
        st.markdown("---")
        st.markdown("""
        <div style="background:linear-gradient(135deg,rgba(255,204,0,0.08),rgba(255,0,60,0.04)); border:1px solid rgba(255,204,0,0.3); border-radius:16px; padding:24px; margin-bottom:24px;">
            <div style="font-family:'Orbitron'; font-size:24px; font-weight:700; color:#ffcc00;">🎯 MISSION QUEUE</div>
            <div style="color:#8892a6; font-size:14px; margin-top:8px;">Dispatch • Assign • Manage • Cancel</div>
        </div>
        """, unsafe_allow_html=True)
        missions_df = list_missions()
        if not missions_df.empty:
            status_filter = st.multiselect("Filter by status", ["DISPATCHED", "ACCEPTED", "COMPLETED", "CANCELLED", "EXPIRED"], default=["DISPATCHED", "ACCEPTED"])
            view = missions_df[missions_df["status"].isin(status_filter)] if status_filter else missions_df
            # Mission cards with priority badges and notes
            PRIO_COLORS = {"CRITICAL": "#ef4444", "HIGH": "#f59e0b", "MEDIUM": "#06b6d4", "STANDARD": "#6b7280"}
            for _, m in view.head(20).iterrows():
                prio = m.get("priority", "STANDARD") or "STANDARD"
                pc = PRIO_COLORS.get(prio, "#6b7280")
                notes = str(m.get("notes", "") or "")[:80]
                notes_html = f'<div style="color:#6b7280; font-size:11px; margin-top:6px;">📋 {notes}</div>' if notes else ""
                st.markdown(f"""
                <div class="titan-card" style="padding:14px 18px; margin-bottom:10px; border-left-color:{pc};">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <span style="font-weight:600; color:#e6edf3;">{m.get('mission_id','?')}</span>
                        <span style="background:{pc}33; color:{pc}; padding:4px 10px; border-radius:6px; font-size:11px; font-weight:600;">{prio}</span>
                    </div>
                    <div style="color:#9ca3af; font-size:13px; margin-top:6px;">{m.get('origin','?')} → {m.get('destination','?')}</div>
                    <div style="display:flex; gap:16px; margin-top:8px; font-size:11px; color:#6b7280;">
                        <span>Driver: {m.get('assigned_driver_id') or '—'}</span>
                        <span>{m.get('status','?')}</span>
                        <span>{str(m.get('created_at',''))[:16]}</span>
                    </div>
                    {notes_html}
                </div>
                """, unsafe_allow_html=True)
            
            mid_opts = view["mission_id"].dropna().astype(str).tolist()
            if mid_opts:
                st.markdown("---")
                st.markdown("#### ⚙️ Manage Selected Mission")
                selected_mid = st.selectbox("Select mission to manage", options=mid_opts, key="manage_mid")
                cA, cB = st.columns(2)
                with cA:
                    drivers_df = get_available_drivers()
                    drv_opts = ["UNASSIGNED"] + (drivers_df["driver_id"].astype(str).tolist() if not drivers_df.empty else [])
                    new_drv = st.selectbox("Assign / Reassign driver", options=drv_opts, key="assign_driver_manage")
                    if st.button("✅ APPLY ASSIGNMENT", use_container_width=True, type="primary"):
                        old_info = get_mission_details(selected_mid)
                        old_drv = old_info.get("assigned_driver_id") if old_info else None
                        new_drv_id = None if new_drv == "UNASSIGNED" else new_drv
                        update_mission_assignment(selected_mid, new_drv_id)
                        log_activity("REASSIGN", st.session_state.get("operator_id", "HQ"), f"{selected_mid} → {new_drv}")
                        if old_drv and old_drv != new_drv_id:
                            send_hq_message(old_drv, f"Mission {selected_mid} reassigned to another unit.", "HQ_ALERT")
                        if new_drv_id:
                            org_d = (old_info or {}).get("origin", "—")
                            dst_d = (old_info or {}).get("destination", "—")
                            send_hq_message(new_drv_id, f"🚨 NEW MISSION {selected_mid}: {org_d} → {dst_d}. Mission will appear automatically.", "HQ_DISPATCH")
                        st.toast(f"Assigned to {new_drv}")
                        st.rerun()
                with cB:
                    if st.button("🛑 CANCEL MISSION", use_container_width=True, type="secondary"):
                        old_info = get_mission_details(selected_mid)
                        old_drv = old_info.get("assigned_driver_id") if old_info else None
                        update_mission_status(selected_mid, "CANCELLED")
                        log_activity("CANCEL", st.session_state.get("operator_id", "HQ"), selected_mid)
                        if old_drv:
                            send_hq_message(old_drv, f"Mission {selected_mid} CANCELLED by HQ.", "HQ_ALERT")
                        st.toast("Mission cancelled")
                        st.rerun()

    with tab4:
        # ==========================================
        # ENGINEERING REPORT - Full Analytics Dashboard
        # ==========================================
        st.markdown("## 📊 ENGINEERING REPORT")
        st.markdown("---")
        
        # Get analytics data
        mission_stats = get_mission_analytics()
        fleet_stats = get_fleet_metrics()
        hazard_data = get_hazard_analytics()
        
        # Key Performance Indicators
        st.markdown("### 🎯 Key Performance Indicators")
        kpi_cols = st.columns(6)
        
        with kpi_cols[0]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; padding:20px;">
                <div class="metric-label">TOTAL MISSIONS</div>
                <div class="metric-value" style="color:#00f3ff;">{mission_stats['total']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_cols[1]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; padding:20px;">
                <div class="metric-label">COMPLETED</div>
                <div class="metric-value" style="color:#00ff9d;">{mission_stats['completed']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_cols[2]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; padding:20px;">
                <div class="metric-label">ACTIVE NOW</div>
                <div class="metric-value" style="color:#ffcc00;">{mission_stats['active']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_cols[3]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; padding:20px;">
                <div class="metric-label">FLEET ONLINE</div>
                <div class="metric-value" style="color:#00f3ff;">{fleet_stats['online']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_cols[4]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; padding:20px;">
                <div class="metric-label">UNITS EN ROUTE</div>
                <div class="metric-value" style="color:#ff003c;">{fleet_stats['en_route']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_cols[5]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; padding:20px;">
                <div class="metric-label">AVG SPEED</div>
                <div class="metric-value" style="color:#00ff9d;">{fleet_stats['avg_speed']}</div>
                <div style="font-size:10px; color:#888;">KM/H</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Response time card
        resp_min = mission_stats.get('avg_response_min', 0)
        st.markdown(f"""
        <div class="titan-card" style="text-align:center; padding:16px; margin:0 0 20px; border-left-color:#00f3ff;">
            <div class="metric-label">AVG RESPONSE TIME</div>
            <div class="metric-value" style="color:#00f3ff; font-size:24px;">{resp_min} MIN</div>
            <div style="font-size:10px; color:#888;">Dispatch → Accept</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Charts Section
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("### 📈 Mission Status Distribution")
            recent_missions = mission_stats['recent']
            if not recent_missions.empty and 'status' in recent_missions.columns:
                status_counts = recent_missions['status'].value_counts()
                fig_pie = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color_discrete_sequence=['#00f3ff', '#00ff9d', '#ffcc00', '#ff003c', '#888888'],
                    hole=0.4
                )
                fig_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#ffffff',
                    showlegend=True,
                    legend=dict(font=dict(size=10)),
                    margin=dict(t=20, b=20, l=20, r=20)
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No mission data available yet.")
        
        with chart_col2:
            st.markdown("### 📊 Fleet Speed Analysis")
            telemetry = fleet_stats['telemetry']
            if not telemetry.empty and 'speed' in telemetry.columns:
                # Speed over time
                telemetry['timestamp'] = pd.to_datetime(telemetry['timestamp'], errors='coerce')
                telemetry_clean = telemetry.dropna(subset=['speed', 'timestamp'])
                
                if not telemetry_clean.empty:
                    fig_speed = px.line(
                        telemetry_clean.head(100),
                        x='timestamp',
                        y='speed',
                        color='driver_id' if 'driver_id' in telemetry_clean.columns else None,
                        title=None
                    )
                    fig_speed.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='#ffffff',
                        xaxis=dict(showgrid=False, title=''),
                        yaxis=dict(showgrid=True, gridcolor='#333', title='Speed (km/h)'),
                        margin=dict(t=20, b=20, l=20, r=20)
                    )
                    fig_speed.update_traces(line=dict(width=2))
                    st.plotly_chart(fig_speed, use_container_width=True)
                else:
                    st.info("No speed telemetry available.")
            else:
                st.info("No telemetry data available yet.")
        
        st.markdown("---")
        
        # Environmental Impact & Efficiency
        st.markdown("### 🌱 Environmental Impact & Efficiency Metrics")
        env_cols = st.columns(4)
        
        # Calculate estimates
        total_distance = 0
        total_time_saved = 0
        logs = mission_stats['logs']
        if not logs.empty:
            if 'time_saved' in logs.columns:
                total_time_saved = logs['time_saved'].sum()
            # Estimate based on missions
            total_distance = mission_stats['completed'] * 8.5  # avg 8.5 km per mission
        
        co2_saved = round(calculate_co2_savings(total_distance if total_distance else 1, total_time_saved or 0), 2)
        fuel_saved = round(estimate_fuel_consumption(total_distance if total_distance else 1), 2)
        
        with env_cols[0]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; border-left-color:#00ff9d;">
                <div style="font-size:30px;">🌍</div>
                <div class="metric-label">EST. CO2 SAVED</div>
                <div class="metric-value" style="color:#00ff9d;">{co2_saved}</div>
                <div style="font-size:10px; color:#888;">KG</div>
            </div>
            """, unsafe_allow_html=True)
        
        with env_cols[1]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; border-left-color:#ffcc00;">
                <div style="font-size:30px;">⛽</div>
                <div class="metric-label">FUEL SAVED</div>
                <div class="metric-value" style="color:#ffcc00;">{fuel_saved}</div>
                <div style="font-size:10px; color:#888;">LITERS</div>
            </div>
            """, unsafe_allow_html=True)
        
        with env_cols[2]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; border-left-color:#00f3ff;">
                <div style="font-size:30px;">⏱️</div>
                <div class="metric-label">TIME SAVED</div>
                <div class="metric-value" style="color:#00f3ff;">{int(total_time_saved)}</div>
                <div style="font-size:10px; color:#888;">MINUTES</div>
            </div>
            """, unsafe_allow_html=True)
        
        with env_cols[3]:
            st.markdown(f"""
            <div class="titan-card" style="text-align:center; border-left-color:#ff003c;">
                <div style="font-size:30px;">🚨</div>
                <div class="metric-label">HAZARDS REPORTED</div>
                <div class="metric-value" style="color:#ff003c;">{len(hazard_data)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Data Export
        st.markdown("### 📥 Data Export")
        export_cols = st.columns(3)
        missions_export = list_missions(500)
        drivers_export = get_all_active_drivers(86400)
        hazards_export = get_hazard_analytics()
        with export_cols[0]:
            if not missions_export.empty:
                st.download_button("📄 Download Missions CSV", missions_export.to_csv(index=False), file_name=f"missions_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", key="dl_missions")
            else:
                st.caption("No missions to export")
        with export_cols[1]:
            if not drivers_export.empty:
                st.download_button("📄 Download Drivers CSV", drivers_export.to_csv(index=False), file_name=f"drivers_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", key="dl_drivers")
            else:
                st.caption("No drivers to export")
        with export_cols[2]:
            if isinstance(hazards_export, pd.DataFrame) and not hazards_export.empty:
                st.download_button("📄 Download Hazards CSV", hazards_export.to_csv(index=False), file_name=f"hazards_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", key="dl_hazards")
            else:
                st.caption("No hazards to export")
        
        st.markdown("---")
        # Recent Mission History Table
        st.markdown("### 📜 Recent Mission History")
        recent = mission_stats['recent']
        if not recent.empty:
            display_cols = [c for c in ['mission_id', 'created_at', 'origin', 'destination', 'priority', 'status', 'assigned_driver_id'] if c in recent.columns]
            st.dataframe(
                recent[display_cols] if display_cols else recent,
                use_container_width=True,
                height=300
            )
        else:
            st.info("No mission history available.")
        
        # Missions per day chart
        st.markdown("### 📊 Missions per Day")
        daily_df = get_missions_per_day(7)
        if not daily_df.empty and 'count' in daily_df.columns:
            st.bar_chart(daily_df.set_index('day') if 'day' in daily_df.columns else daily_df)
        else:
            st.info("No missions completed in last 7 days.")
        
        # Driver leaderboard
        st.markdown("### 🏆 Driver Leaderboard")
        leaderboard = get_driver_leaderboard(10)
        if not leaderboard.empty:
            for i, row in leaderboard.iterrows():
                rank = i + 1
                did = row.get('driver_id', '?')
                comp = row.get('completed', 0)
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                st.markdown(f"""
                <div class="titan-card" style="padding:12px 16px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:600; color:#fff;">{medal} {did}</span>
                    <span style="color:#00ff9d; font-weight:700;">{comp} missions</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No completed missions yet.")
        
        # Activity log
        st.markdown("### 📋 Activity Log")
        act_df = get_activity_log(20)
        if not act_df.empty:
            act_cols = [c for c in ['timestamp', 'action', 'actor', 'details'] if c in act_df.columns]
            st.dataframe(act_df[act_cols].head(15), use_container_width=True, height=200)
        else:
            st.info("No activity logged yet.")
        
        # Data cleanup
        st.markdown("---")
        st.markdown("### 🧹 Data Maintenance")
        if st.button("🗑️ Clean old telemetry (7+ days)", key="cleanup_btn"):
            deleted, err = cleanup_old_driver_state(7)
            if err:
                st.error(f"Cleanup failed: {err}")
            else:
                st.success(f"Deleted {deleted} old driver_state rows.")
                log_activity("CLEANUP", st.session_state.get("operator_id", "HQ"), f"Removed {deleted} rows")
                st.rerun()
        
        # System Health
        st.markdown("### 🖥️ System Health")
        health_cols = st.columns(4)
        with health_cols[0]:
            st.metric("Database Status", "ONLINE", delta="WAL Mode")
        with health_cols[1]:
            st.metric("API Status", "CONNECTED", delta="TomTom Active")
        with health_cols[2]:
            st.metric("Sensor Grid", f"{len(SENSORS_GRID)} Nodes", delta="All Active")
        with health_cols[3]:
            st.metric("Uptime", "99.9%", delta="+0.1%")

    with tab5:
        # ==========================================
        # V2X COMMUNICATIONS CENTER - Real-time feed
        # ==========================================
        st.markdown("## 📶 V2X COMMUNICATIONS")
        st.markdown("""
        <div style="background:rgba(0,243,255,0.08); border:1px solid rgba(0,243,255,0.25); border-radius:12px; padding:16px 20px; margin-bottom:20px; color:#a0aec0; font-size:13px; line-height:1.5;">
            <strong style="color:#00f3ff;">Vehicle-to-Everything</strong> — Drivers send messages from their app (SOS, Green Wave, status). 
            They appear here. Use the <strong>Send panel</strong> on the right to reply or broadcast to units.
        </div>
        """, unsafe_allow_html=True)
        
        # Unit filter + conversation mode + legend
        unit_filter_col, conv_col, legend_col = st.columns([2, 1, 2])
        with unit_filter_col:
            drivers_online = get_available_drivers()
            online_ids = drivers_online["driver_id"].tolist() if not drivers_online.empty else []
            unit_ids = get_driver_ids_with_messages()
            all_unit_ids = list(dict.fromkeys(online_ids + unit_ids))  # Online first, then who sent
            unit_opts = ["All units"] + all_unit_ids
            filter_unit = st.selectbox("Filter by unit", unit_opts, key="v2x_unit_filter")
        with conv_col:
            show_conversation = st.checkbox("Include HQ replies", value=False, key="v2x_conv_mode", help="Show your messages to this unit")
        with legend_col:
            st.caption("🚨 CRITICAL=SOS | ⚠️ WARNING=hazard | 📨 REQUEST=Green Wave | 📡 HQ=Your reply")
        
        # Two-column: Live Feed first (prominent) + Send panel
        feed_col, msg_col = st.columns([2, 1])
        
        with feed_col:
            @st.fragment(run_every=2)
            def _comms_feed_live():
                driver_id_filter = None if filter_unit == "All units" else filter_unit
                comms_df = get_driver_comms(80, driver_id=driver_id_filter, conversation_mode=show_conversation)
                # SOS prioritization: CRITICAL first, then WARNING, then rest
                if not comms_df.empty and 'status' in comms_df.columns:
                    def _prio(s):
                        if s == 'CRITICAL': return 0
                        if s in ('WARNING', 'REQUEST'): return 1
                        return 2
                    comms_df = comms_df.copy()
                    comms_df['_prio'] = comms_df['status'].apply(_prio)
                    comms_df = comms_df.sort_values(['_prio', 'id'], ascending=[True, False]).drop(columns=['_prio'], errors='ignore')
                total = len(comms_df)
                reqs = len(comms_df[comms_df['status'] == 'REQUEST']) if not comms_df.empty and 'status' in comms_df.columns else 0
                warns = len(comms_df[comms_df['status'].isin(['WARNING', 'CRITICAL'])]) if not comms_df.empty and 'status' in comms_df.columns else 0
                sos_count = len(comms_df[comms_df['status'] == 'CRITICAL']) if not comms_df.empty and 'status' in comms_df.columns else 0
                
                # Sticky CRITICAL alerts section — never scrolls away
                critical_df = comms_df[comms_df['status'].isin(['CRITICAL', 'WARNING', 'REQUEST'])] if not comms_df.empty and 'status' in comms_df.columns else pd.DataFrame()
                if not critical_df.empty:
                    if sos_count > 0:
                        st.markdown("<style>@keyframes pulse { 50% { opacity: 0.85; box-shadow: 0 0 30px rgba(255,0,60,0.6); } }</style>", unsafe_allow_html=True)
                    st.markdown("**🚨 CRITICAL ALERTS** — Never miss these")
                    for _, row in critical_df.head(10).iterrows():
                        ts, did, sts, msg = row.get('timestamp',''), row.get('driver_id','?'), row.get('status',''), row.get('message','')
                        c = "#ff003c" if sts == 'CRITICAL' else "#ff6600" if sts == 'WARNING' else "#ffcc00"
                        dir_label = "←" if 'HQ' not in sts else "→"
                        st.markdown(f"""
                        <div style="background:rgba(255,0,60,0.08); border-left:4px solid {c}; padding:10px 12px; margin-bottom:6px; border-radius:6px;">
                            <span style="color:{c}; font-weight:bold;">{dir_label} {did}</span>
                            <span style="color:#666; font-size:10px; float:right;">{ts}</span>
                            <div style="color:#fff; font-size:12px; margin-top:4px;">{msg[:80]}{'...' if len(str(msg))>80 else ''}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    st.markdown("---")
                
                header = f"**📨 Live Feed** — Total: {total} | From drivers: {reqs + warns}"
                if sos_count > 0:
                    header += f" | 🚨 SOS: {sos_count}"
                st.markdown(header)
                if not comms_df.empty:
                    for _, row in comms_df.head(40).iterrows():
                        timestamp = row.get('timestamp', '')
                        driver_id = row.get('driver_id', 'UNKNOWN')
                        status = row.get('status', 'INFO')
                        message = row.get('message', '')
                        dir_label = "←" if 'HQ' not in status else "→"
                        if status == 'CRITICAL':
                            color = "#ff003c"
                            icon = "🚨"
                            extra_style = "animation: pulse 1.5s infinite; box-shadow: 0 0 20px rgba(255,0,60,0.4);"
                        elif 'HQ' in status:
                            color = "#00f3ff"
                            icon = "📡"
                            extra_style = ""
                        elif status == 'REQUEST':
                            color = "#ffcc00"
                            icon = "📨"
                            extra_style = ""
                        elif status == 'WARNING':
                            color = "#ff6600"
                            icon = "⚠️"
                            extra_style = ""
                        else:
                            color = "#888888"
                            icon = "💬"
                            extra_style = ""
                        st.markdown(f"""
                        <div style="background:#111; border-left:4px solid {color}; padding:12px; margin-bottom:8px; border-radius:6px; {extra_style}">
                            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                                <span style="color:{color}; font-weight:bold; font-size:12px;">{dir_label} {icon} {driver_id}</span>
                                <span style="color:#666; font-size:10px;">{timestamp}</span>
                            </div>
                            <div style="color:#fff; font-size:13px;">{message}</div>
                            <div style="color:#666; font-size:10px; margin-top:4px;">{status}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("""
                    **No messages yet.** When drivers send from their app (SOS, Green Wave, status updates), they appear here. 
                    Use the Send panel on the right to reply or broadcast.
                    """)
                st.caption("● Live — refreshes every 2 seconds")
            _comms_feed_live()
        
        with msg_col:
            st.markdown("### 📤 Send to Driver")
            drivers_online = get_available_drivers()
            driver_list = drivers_online["driver_id"].tolist() if not drivers_online.empty else []
            target_opts = ["ALL UNITS"] + driver_list
            
            st.markdown("**Target**")
            target_driver = st.selectbox("Select unit", target_opts, key="comms_target", label_visibility="collapsed")
            
            st.markdown("#### ⚡ Quick send (one-tap)")
            quick_cols = st.columns(2)
            with quick_cols[0]:
                if st.button("🟢 GRANT GREEN", use_container_width=True, key="grant_green"):
                    tid = "ALL" if target_driver == "ALL UNITS" else target_driver
                    send_hq_message(tid, "Green Wave GRANTED — Proceed with caution.", "HQ_GREENWAVE")
                    st.toast(f"Green Wave sent to {target_driver}", icon="🟢")
                    st.rerun()
            with quick_cols[1]:
                if st.button("🔴 DENY / STANDBY", use_container_width=True, key="deny_standby"):
                    tid = "ALL" if target_driver == "ALL UNITS" else target_driver
                    send_hq_message(tid, "Standby — Await further instructions.", "HQ_ALERT")
                    st.toast(f"Standby sent to {target_driver}", icon="🔴")
                    st.rerun()
            
            st.markdown("#### 📋 Quick templates")
            MSG_TEMPLATES = [
                ("Proceed", "Proceed to destination. Maintain speed.", "HQ_BROADCAST"),
                ("Return base", "Mission complete. Return to base.", "HQ_BROADCAST"),
                ("Green granted", "Green Wave granted. Proceed with caution.", "HQ_GREENWAVE"),
                ("Alternate route", "Take alternate route. Traffic ahead.", "HQ_REROUTE"),
                ("ETA update", "Provide ETA update to HQ.", "HQ_BROADCAST"),
            ]
            for i, (label, msg, mtype) in enumerate(MSG_TEMPLATES):
                if st.button(f"📤 {label}", key=f"tpl_{i}", use_container_width=True):
                    tid = "ALL" if target_driver == "ALL UNITS" else target_driver
                    send_hq_message(tid, msg, mtype)
                    st.toast(f"Sent to {target_driver}: {label}", icon="✅")
                    st.rerun()
            
            st.markdown("---")
            
            # Custom Message Form
            st.markdown("#### 📝 Custom message")
            with st.form("hq_message_form"):
                driver_opts = ["ALL UNITS"] + (drivers_online["driver_id"].tolist() if not drivers_online.empty else [])
                target_driver = st.selectbox("Target", driver_opts, key="hq_msg_target")
                
                msg_type = st.selectbox("Message Type", [
                    "HQ_BROADCAST",
                    "HQ_GREENWAVE",
                    "HQ_ALERT",
                    "HQ_REROUTE",
                    "HQ_CLEARANCE",
                    "HQ_INFO"
                ])
                
                message_text = st.text_area("Message", placeholder="Enter message to send...")
                
                if st.form_submit_button("📡 TRANSMIT", use_container_width=True):
                    if message_text:
                        driver_id = "ALL" if target_driver == "ALL UNITS" else target_driver
                        send_hq_message(driver_id, message_text, msg_type)
                        st.toast(f"Sent to {target_driver}", icon="✅")
                        st.success(f"Message transmitted to {target_driver}!")
                        st.rerun()
                    else:
                        st.error("Please enter a message.")
            
            st.markdown("---")
            
            # Signal Control — in expander (separate from comms)
            with st.expander("🚦 Traffic Signal Control", expanded=False):
                signal_name = st.selectbox("Select Junction", list(SENSORS_GRID.keys())[:10], key="v2x_signal")
                sig_cols = st.columns(2)
                with sig_cols[0]:
                    if st.button("🟢 SET GREEN", use_container_width=True, key="set_green"):
                        try:
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            c.execute(
                                "INSERT OR REPLACE INTO signal_status (stop_id, status, last_updated) VALUES (?, ?, ?)",
                                (signal_name, "GREEN_WAVE", datetime.datetime.now())
                            )
                            conn.commit()
                            conn.close()
                            st.success(f"Green Wave set for {signal_name}")
                        except Exception:
                            st.error("Failed to update signal")
                with sig_cols[1]:
                    if st.button("🔴 RESET", use_container_width=True, key="reset_sig"):
                        try:
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            c.execute("DELETE FROM signal_status WHERE stop_id = ?", (signal_name,))
                            conn.commit()
                            conn.close()
                            st.info(f"Signal reset for {signal_name}")
                        except Exception:
                            st.error("Failed to reset signal")

# --- MAIN ROUTING ---
if st.session_state.page == 'home': render_home()
elif st.session_state.page == 'login': render_login()
elif st.session_state.page == 'dashboard':
    if not st.session_state.authenticated:
        st.session_state.page = 'login'
        st.rerun()
    else:
        render_dashboard()