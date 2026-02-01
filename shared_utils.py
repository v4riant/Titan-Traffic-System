"""
Shared TomTom routing utilities for App.py (HQ) and driverapp.py (Driver).
Single source of truth for API calls and route alternatives.
"""
import math
import hashlib
import requests

TOMTOM_API_KEY = "EH7SOW12eDLJn2bR6UvfEbnpNvnrx8o4"
BASE_URL = "https://api.tomtom.com/routing/1/calculateRoute"


def _build_url(start, end, route_type="fastest", max_alternatives=0, instructions=True):
    start_s = f"{start[0]},{start[1]}"
    end_s = f"{end[0]},{end[1]}"
    url = f"{BASE_URL}/{start_s}:{end_s}/json?key={TOMTOM_API_KEY}&traffic=true&routeType={route_type}"
    if max_alternatives > 0:
        url += f"&maxAlternatives={max_alternatives}"
    if instructions:
        url += "&instructionsType=text&language=en-US"
    return url


def fetch_routes(start, end, priority_factor=1.0, max_alternatives=3):
    """
    Fetches up to 4 route alternatives (1 main + 3 alt) - Fastest type.
    Returns list of {id, coords, eta, raw_eta, dist, instructions}.
    """
    url = _build_url(start, end, route_type="fastest", max_alternatives=max_alternatives)
    data = []
    try:
        r = requests.get(url, timeout=10).json()
        if "routes" not in r:
            return data
        for idx, route in enumerate(r["routes"]):
            summ = route.get("summary", {})
            adjusted_eta = int((summ.get("travelTimeInSeconds", 0) * priority_factor) / 60)
            raw_eta = int(summ.get("travelTimeInSeconds", 0) / 60)
            coords = [[p["latitude"], p["longitude"]] for p in route["legs"][0]["points"]]
            instr = []
            for ins in route.get("guidance", {}).get("instructions", []):
                msg = ins.get("message")
                if msg:
                    instr.append(msg)
            data.append({
                "id": idx,
                "coords": coords,
                "eta": adjusted_eta,
                "raw_eta": raw_eta,
                "dist": round(summ.get("lengthInMeters", 0) / 1000, 1),
                "instructions": instr,
                "route_type": "Fastest" if idx == 0 else f"Alternative {idx + 1}",
            })
    except Exception:
        pass
    return data


def fetch_route_alternatives_4(start, end):
    """
    Fetches 4 route alternatives: Fastest, Shortest, Eco, and Fastest Alternate.
    Returns list of 4 dicts: {id, route_type, coords, eta, dist, instructions}.
    """
    results = []
    try:
        url = _build_url(start, end, route_type="fastest", max_alternatives=3)
        r = requests.get(url, timeout=10).json()
        routes = r.get("routes", [])[:4]
        labels = ["Fastest", "Alternative 2", "Alternative 3", "Alternative 4"]
        for idx, route in enumerate(routes):
            summ = route.get("summary", {})
            coords = [[p["latitude"], p["longitude"]] for p in route["legs"][0]["points"]]
            instr = []
            for ins in route.get("guidance", {}).get("instructions", []):
                msg = ins.get("message")
                if msg:
                    instr.append(msg)
            results.append({
                "id": idx,
                "route_type": labels[idx] if idx < len(labels) else f"Route {idx + 1}",
                "coords": coords,
                "eta": int(summ.get("travelTimeInSeconds", 0) / 60),
                "dist": round(summ.get("lengthInMeters", 0) / 1000, 1),
                "instructions": instr,
            })
        if len(results) < 4:
            for rtype, label in [("shortest", "Shortest"), ("eco", "Eco")]:
                if len(results) >= 4:
                    break
                url = _build_url(start, end, route_type=rtype, max_alternatives=0)
                r = requests.get(url, timeout=10).json()
                route_list = r.get("routes", [])
                if route_list:
                    route = route_list[0]
                    summ = route.get("summary", {})
                    coords = [[p["latitude"], p["longitude"]] for p in route["legs"][0]["points"]]
                    instr = []
                    for ins in route.get("guidance", {}).get("instructions", []):
                        msg = ins.get("message")
                        if msg:
                            instr.append(msg)
                    results.append({
                        "id": len(results),
                        "route_type": label,
                        "coords": coords,
                        "eta": int(summ.get("travelTimeInSeconds", 0) / 60),
                        "dist": round(summ.get("lengthInMeters", 0) / 1000, 1),
                        "instructions": instr,
                    })
    except Exception:
        pass
    if not results and start and end:
        results = [{
            "id": 0,
            "route_type": "Fastest",
            "coords": [list(start), list(end)],
            "eta": 0,
            "dist": 0,
            "instructions": [],
        }]
    return results[:4]


def distance_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km between two points."""
    r = 6371000.0  # Earth radius in meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    meters = 2 * r * math.asin(math.sqrt(x))
    return meters / 1000.0


def hash_password(password):
    """Return SHA-256 hash of password as hex string."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain, hashed):
    """Verify plain password against stored hash."""
    return hashlib.sha256(plain.encode()).hexdigest() == hashed


def calculate_co2_savings(distance_km_val, time_saved_minutes):
    """Estimate CO2 saved (kg) from optimized routing. ~120g CO2/km for typical car."""
    return (distance_km_val * 0.12) * max(0.1, min(1.0, time_saved_minutes / 10))


def estimate_fuel_consumption(distance_km_val):
    """Estimate fuel used (L) for distance. ~7.5 L/100km typical."""
    return distance_km_val * 0.075
