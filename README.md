# TITAN Traffic Intelligence V52

Emergency vehicle fleet management & traffic intelligence system with HQ dashboard and driver app.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Both Apps

**Terminal 1 - HQ Dashboard:**
```bash
streamlit run App.py --server.port 8501
```

**Terminal 2 - Driver App:**
```bash
streamlit run driverapp.py --server.port 8502
```

**Or use the run script (Windows):**
```bash
run.bat
```

### 3. Access
- **HQ Dashboard:** http://localhost:8501
- **Driver App:** http://localhost:8502

## Demo Credentials

**HQ (Operator):**
- Username: `COMMANDER`
- Password: `TITAN-X`

**Driver:**
- Username: `UNIT-07`
- Password: `TITAN-DRIVER`

## Features

### HQ App
- Mission Center: Dispatch missions with route preview, assign to drivers
- Live Tracking: Map with all drivers, focus by unit or mission
- Sensor Grid: Traffic flow & Green Wave status
- Engineering Report: Analytics, response time, export CSV
- V2X Comms: Message drivers, Green Wave control, templates

### Driver App
- Mission alerts with 4 route options
- Manual trips: Current location or custom coords
- Green Wave requests, SOS, hazard reporting
- Arrived-at pickup/hospital status
- Shift stats, mission history

## Environment

Optional: Set TomTom API key
```
set TOMTOM_API_KEY=your_key_here
```

## Database

Shared SQLite: `titan_v52.db` (auto-created)
