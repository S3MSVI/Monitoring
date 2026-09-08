# -*- coding: utf-8 -*-
"""
=========================================================================================
SOLAR POWER MONITORING SYSTEM
Advanced Real-Time Solar Photovoltaic Data Acquisition & Analytics Dashboard
=========================================================================================
Features:
- Live MQTT Telemetry (Voltage, Current, Power, Temperature, Lux, Irradiance)
- Robust Disconnect & Reconnect Lifecycle Tracking
- Verified Power & Non-Decreasing Cumulative Energy (Wh) Engine
- Dynamic Tehran Sun & Sky Atmosphere (Visual Only)
- Hero KPI Display (Current Power Priority)
- Real Timestamp ISO 8601 Temporal Filtering (1m, 5m, 15m, 1h, 12h, All-Time)
- Multi-Tier Visual Charts (Main Power vs. Irradiance + Secondary Metrics)
- Solar Radiation Classification & Solar Conditions Meter
- Event Logging & Data Freshness Monitoring
- Local CSV Persistence (solar_backup.csv) & Clean CSV Export
=========================================================================================
"""

import streamlit as st
import paho.mqtt.client as mqtt
import pandas as pd
import time
import requests
from datetime import datetime, timedelta
import pytz
import jdatetime
import math
import os

# =========================================================================================
# 1. PAGE CONFIGURATION & METADATA
# =========================================================================================
st.set_page_config(
    page_title="Solar Power Monitoring Dashboard",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================================================
# 2. TIMEZONE & SOLAR CALCULATIONS (TEHRAN)
# =========================================================================================
tehran_tz = pytz.timezone('Asia/Tehran')
now_tehran = datetime.now(tehran_tz)
gregorian_date_str = now_tehran.strftime("%Y-%m-%d")
time_str = now_tehran.strftime("%H:%M:%S")

try:
    j_date = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    jalali_date_str = j_date.strftime("%Y/%m/%d")
except Exception:
    jalali_date_str = gregorian_date_str

# Weather integration via Open-Meteo
@st.cache_data(ttl=300)
def get_tehran_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=35.6892&longitude=51.3890&current=temperature_2m,relative_humidity_2m"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=4)
        if response.status_code == 200:
            data = response.json()
            if 'current' in data:
                temp = data['current'].get('temperature_2m', 'N/A')
                hum = data['current'].get('relative_humidity_2m', 'N/A')
                return f"{temp} °C", f"{hum} %"
    except Exception:
        pass
    return "Unavailable", "Unavailable"

tehran_temp, tehran_hum = get_tehran_weather()

# Dynamic Solar Position & Daylight Atmosphere (Visual Only)
hour = now_tehran.hour
minute = now_tehran.minute
time_in_hours = hour + minute / 60.0

sunrise = 5.5
sunset = 18.75
day_length = sunset - sunrise

if sunrise <= time_in_hours <= sunset:
    progress = (time_in_hours - sunrise) / day_length
    sun_x = 5 + (90 * progress)
    sun_y = 80 - (50 * math.sin(math.pi * progress))
    
    if progress < 0.20:
        opacity = 0.85 - (progress * 2.0)
        sky_overlay = f"linear-gradient(rgba(15, 23, 42, {opacity*0.4}), rgba(254, 215, 170, {opacity*0.6}))"
        sun_color = "rgba(251, 146, 60, 0.85)"
        solar_phase = "Morning"
        solar_phase_icon = "🌅"
    elif progress > 0.80:
        p_sunset = progress - 0.80
        opacity = 0.30 + (p_sunset * 2.0)
        sky_overlay = f"linear-gradient(rgba(30, 41, 59, {opacity*0.4}), rgba(254, 215, 170, {opacity*0.7}))"
        sun_color = "rgba(249, 115, 22, 0.85)"
        solar_phase = "Sunset"
        solar_phase_icon = "🌇"
    elif progress > 0.55:
        opacity = 0.22
        sky_overlay = f"linear-gradient(rgba(255, 255, 255, {opacity}), rgba(254, 243, 199, {opacity + 0.1}))"
        sun_color = "rgba(252, 211, 77, 0.90)"
        solar_phase = "Afternoon"
        solar_phase_icon = "🌤️"
    else:
        opacity = 0.18
        sky_overlay = f"linear-gradient(rgba(248, 250, 252, {opacity}), rgba(224, 242, 254, {opacity + 0.1}))"
        sun_color = "rgba(254, 240, 138, 0.95)"
        solar_phase = "Daylight"
        solar_phase_icon = "☀️"
        
    sun_orb_html = f"""
    <div style="
        position: fixed; width: 150px; height: 150px; border-radius: 50%;
        background: radial-gradient(circle, {sun_color} 0%, rgba(253, 224, 71, 0.35) 40%, transparent 70%);
        box-shadow: 0 0 65px 25px rgba(251, 191, 36, 0.22);
        left: {sun_x:.1f}%; top: {sun_y:.1f}%; transform: translate(-50%, -50%);
        z-index: -1; pointer-events: none;
    "></div>
    """
else:
    sky_overlay = "linear-gradient(rgba(15, 23, 42, 0.85), rgba(30, 41, 59, 0.92))"
    solar_phase = "Night"
    solar_phase_icon = "🌙"
    sun_orb_html = ""

# =========================================================================================
# 3. CSS STYLING (MODERN PROFESSIONAL SOLAR PALETTE)
# =========================================================================================
st.markdown(f"""
<style>
    * {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif !important; }}
    
    .stApp, [data-testid="stHeader"] {{
        background-color: transparent !important;
    }}

    [data-testid="stAppViewContainer"] {{
        background: {sky_overlay}, url('https://images.unsplash.com/photo-1509391365360-2e959784a276?q=85&w=2560&auto=format&fit=crop') !important;
        background-size: cover !important;
        background-position: center center !important;
        background-attachment: fixed !important;
        background-repeat: no-repeat !important;
    }}

    [data-testid="stAppViewBlockContainer"], .main .block-container {{
        max-width: 1650px !important;
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
    }}

    /* Header Bar */
    .header-bar {{
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(14px);
        border-radius: 16px;
        padding: 16px 24px;
        border: 1px solid rgba(255, 255, 255, 0.9);
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.06);
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 15px;
    }}
    .header-title-box {{ display: flex; flex-direction: column; }}
    .header-main-title {{
        font-size: 26px; font-weight: 800; color: #0f172a;
        display: flex; align-items: center; gap: 8px; letter-spacing: 0.5px;
    }}
    .header-subtitle {{ font-size: 13.5px; color: #64748b; font-weight: 600; margin-top: 2px; }}

    .header-badges {{
        display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    }}
    .header-pill {{
        background: rgba(241, 245, 249, 0.85);
        border: 1px solid rgba(226, 232, 240, 0.9);
        border-radius: 30px;
        padding: 6px 14px;
        font-size: 13.5px;
        font-weight: 600;
        color: #1e293b;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }}
    .header-pill-val {{ font-weight: 700; color: #0f172a; }}
    .header-pill.status-green {{ background: rgba(236, 253, 245, 0.9); border-color: rgba(167, 243, 208, 0.9); color: #047857; }}
    .header-pill.status-red {{ background: rgba(254, 242, 242, 0.9); border-color: rgba(254, 202, 202, 0.9); color: #b91c1c; }}
    .header-pill.status-amber {{ background: rgba(254, 243, 199, 0.9); border-color: rgba(253, 230, 138, 0.9); color: #b45309; }}

    /* Cards */
    .glass-card {{
        background: rgba(255, 255, 255, 0.93);
        backdrop-filter: blur(14px);
        border-radius: 16px;
        padding: 18px 20px;
        border: 1px solid rgba(255, 255, 255, 0.9);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        margin-bottom: 18px;
    }}
    .card-heading {{
        font-size: 16px; font-weight: 700; color: #0f172a;
        margin-bottom: 14px; padding-bottom: 8px;
        border-bottom: 1px solid #f1f5f9;
        display: flex; justify-content: space-between; align-items: center;
    }}

    /* Hero Power Card */
    .hero-power-card {{
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.97), rgba(254, 243, 199, 0.5));
        border: 1.5px solid rgba(245, 158, 11, 0.35);
        border-radius: 16px;
        padding: 22px 20px;
        text-align: center;
        box-shadow: 0 12px 28px rgba(245, 158, 11, 0.10);
        margin-bottom: 16px;
    }}
    .hero-title {{ font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #b45309; }}
    .hero-val {{
        font-size: 46px; font-weight: 800; color: #0f172a;
        margin: 6px 0; font-family: 'Segoe UI', Tahoma, sans-serif !important;
    }}
    .hero-unit {{ font-size: 22px; font-weight: 600; color: #d97706; margin-left: 4px; }}
    .hero-sub {{ font-size: 13px; color: #64748b; font-weight: 600; }}

    /* KPI Grid */
    .kpi-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
    .kpi-item {{
        background: rgba(248, 250, 252, 0.85);
        border: 1px solid rgba(226, 232, 240, 0.85);
        border-radius: 12px;
        padding: 12px 14px;
        text-align: left;
    }}
    .kpi-item-title {{ font-size: 12.5px; font-weight: 600; color: #64748b; margin-bottom: 4px; }}
    .kpi-item-val {{ font-size: 22px; font-weight: 700; color: #0f172a; }}
    .kpi-item-unit {{ font-size: 13px; font-weight: 600; color: #64748b; }}

    /* Status Items */
    .status-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 9px 0; border-bottom: 1px solid #f1f5f9; font-size: 13.5px;
    }}
    .status-row:last-child {{ border-bottom: none; }}
    .status-label {{ color: #475569; font-weight: 600; }}
    .status-badge {{ font-weight: 700; display: inline-flex; align-items: center; gap: 5px; }}

    /* Solar Conditions Meter */
    .scale-bar {{
        height: 10px; border-radius: 6px;
        background: linear-gradient(90deg, #93c5fd 0%, #fde047 50%, #f97316 100%);
        position: relative; margin: 16px 0 10px 0;
    }}
    .scale-pointer {{
        position: absolute; top: -5px; width: 20px; height: 20px;
        background: #0f172a; border: 2.5px solid #ffffff; border-radius: 50%;
        transform: translateX(-50%); box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        transition: left 0.5s ease;
    }}
    .scale-labels {{
        display: flex; justify-content: space-between; font-size: 12px;
        font-weight: 700; color: #64748b;
    }}

    /* Event Log List */
    .event-log-container {{
        max-height: 170px; overflow-y: auto; padding-right: 4px;
    }}
    .event-entry {{
        font-size: 12.5px; padding: 7px 10px; border-radius: 8px;
        margin-bottom: 6px; display: flex; justify-content: space-between;
        align-items: center; background: rgba(248, 250, 252, 0.9);
        border-left: 3px solid #cbd5e1;
    }}
    .event-entry.info {{ border-left-color: #3b82f6; }}
    .event-entry.warning {{ border-left-color: #f59e0b; background: rgba(254, 243, 199, 0.4); }}
    .event-entry.error {{ border-left-color: #ef4444; background: rgba(254, 242, 242, 0.4); }}

    /* Clean Timeframe Radio */
    div[data-testid="stRadio"] {{
        display: flex !important; justify-content: center !important; margin-bottom: 12px;
    }}
    div[role="radiogroup"] {{
        display: inline-flex !important; justify-content: center !important; align-items: center !important;
        background: rgba(255, 255, 255, 0.95) !important; padding: 6px 14px !important;
        border-radius: 50px !important; border: 1px solid rgba(226, 232, 240, 0.9) !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05) !important; gap: 4px;
    }}
    div[role="radiogroup"] label {{
        padding: 4px 10px !important; border-radius: 20px !important; margin: 0 !important;
    }}
    div[role="radiogroup"] label p {{ font-size: 13.5px !important; font-weight: 700 !important; color: #1e293b !important; }}

    /* Charts */
    div[data-testid="stVegaLiteChart"], div[data-testid="stArrowVegaLiteChart"] {{
        background-color: #ffffff !important; border-radius: 12px !important; padding: 10px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04) !important; border: 1px solid rgba(226, 232, 240, 0.85) !important;
    }}
    div[data-testid="stVegaLiteChart"] summary, div[data-testid="stArrowVegaLiteChart"] summary {{ display: none !important; }}

    h4, h5 {{ color: #0f172a !important; font-weight: 700 !important; margin-top: 10px !important; margin-bottom: 6px !important; }}
</style>
""", unsafe_allow_html=True)

if sun_orb_html:
    st.markdown(sun_orb_html, unsafe_allow_html=True)

# =========================================================================================
# 4. BACKEND STORAGE & DATA PERSISTENCE (SOLAR DATA REPOSITORY)
# =========================================================================================
PERSISTENCE_FILE = "solar_backup.csv"

@st.cache_resource
def get_solar_data():
    store = {
        'voltage': 0.0,
        'current': 0.0,
        'power': 0.0,
        'temp': 0.0,
        'lux': 0.0,
        'watts': 0.0,
        'total_energy_mWh': 0.0,
        'last_power_time': 0.0,
        'last_msg_time': 0.0,
        'mqtt_connected': False,
        'reconnect_count': 0,
        'msg_count': 0,
        'last_topic': '-',
        'last_payload': '-',
        'logging_active': True,
        'events': [],
        'log_records': []
    }
    
    # Startup restoration from solar_backup.csv
    if os.path.exists(PERSISTENCE_FILE):
        try:
            df = pd.read_csv(PERSISTENCE_FILE)
            if not df.empty:
                records = df.tail(20000).to_dict('records')
                store['log_records'] = records
                last_rec = records[-1]
                
                # Restore last sensor values
                store['voltage'] = float(last_rec.get('voltage_V', last_rec.get('Voltage (V)', 0.0)))
                store['current'] = float(last_rec.get('current_mA', last_rec.get('Current (mA)', 0.0)))
                store['power'] = float(last_rec.get('power_mW', last_rec.get('Power (mW)', 0.0)))
                store['temp'] = float(last_rec.get('temperature_C', last_rec.get('Temp (°C)', 0.0)))
                store['lux'] = float(last_rec.get('illuminance_lux', last_rec.get('Lux', 0.0)))
                store['watts'] = float(last_rec.get('irradiance_W_m2', last_rec.get('Irradiance (W/m²)', 0.0)))
                store['total_energy_mWh'] = float(last_rec.get('energy_mWh', 0.0))
                if store['total_energy_mWh'] == 0.0 and 'energy_Wh' in last_rec:
                    store['total_energy_mWh'] = float(last_rec['energy_Wh']) * 1000.0
                elif store['total_energy_mWh'] == 0.0 and 'Energy (mWh)' in last_rec:
                    store['total_energy_mWh'] = float(last_rec['Energy (mWh)'])
                    
                store['events'].append({
                    'time': datetime.now(tehran_tz).strftime("%H:%M:%S"),
                    'text': f"Restored {len(records)} records from {PERSISTENCE_FILE}",
                    'level': 'info'
                })
        except Exception as e:
            store['events'].append({
                'time': datetime.now(tehran_tz).strftime("%H:%M:%S"),
                'text': f"Notice: Could not parse previous archive ({e})",
                'level': 'warning'
            })
            
    return store

solar_data = get_solar_data()

def add_event(msg_text, level="info"):
    now_str = datetime.now(tehran_tz).strftime("%H:%M:%S")
    solar_data['events'].append({'time': now_str, 'text': msg_text, 'level': level})
    if len(solar_data['events']) > 25:
        solar_data['events'].pop(0)

# =========================================================================================
# 5. MQTT PROTOCOL & RELIABILITY CLIENT
# =========================================================================================
def on_connect(client, userdata, flags, rc, properties=None):
    solar_data['mqtt_connected'] = True
    solar_data['reconnect_count'] += 1
    add_event("MQTT Connected to broker successfully", "info")
    client.subscribe("my_powerplant/#")

def on_disconnect(client, userdata, rc, properties=None):
    solar_data['mqtt_connected'] = False
    add_event("MQTT Connection lost (disconnected)", "error")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic.lower()
        payload_str = msg.payload.decode('utf-8', errors='ignore').replace(chr(0), '').strip()
        
        if not payload_str or payload_str.lower() in ['nan', 'null', 'none', 'inf']:
            return
            
        value = float(payload_str)
        if math.isnan(value) or math.isinf(value):
            return
            
        sensor_name = topic.split('/')[-1]
        t_now = time.time()
        solar_data['last_msg_time'] = t_now
        solar_data['msg_count'] += 1
        solar_data['last_topic'] = topic
        solar_data['last_payload'] = payload_str

        # Update sensor values
        if sensor_name == "voltage":
            solar_data['voltage'] = value
        elif sensor_name == "current":
            solar_data['current'] = value
        elif sensor_name == "power":
            solar_data['power'] = value
            # Robust cumulative energy integration (Wh)
            if solar_data['last_power_time'] > 0:
                delta_h = (t_now - solar_data['last_power_time']) / 3600.0
                if 0 < delta_h < 0.0833 and value > 0:
                    solar_data['total_energy_mWh'] += value * delta_h
            solar_data['last_power_time'] = t_now
        elif sensor_name == "temperature":
            solar_data['temp'] = value
            if value > 55.0:
                add_event(f"High panel temperature alert: {value:.1f} °C", "warning")
        elif sensor_name == "lux":
            solar_data['lux'] = value
        elif sensor_name in ["watts", "irradiance"]:
            solar_data['watts'] = value

        # Record generation (throttled by 1 second)
        current_iso = datetime.now(tehran_tz).isoformat()
        current_hhmmss = datetime.now(tehran_tz).strftime("%H:%M:%S")
        
        last_rec_time = solar_data['log_records'][-1]['time_display'] if solar_data['log_records'] else ""
        if last_rec_time != current_hhmmss:
            record = {
                'timestamp': current_iso,
                'time_display': current_hhmmss,
                'voltage_V': round(solar_data['voltage'], 2),
                'current_mA': round(solar_data['current'], 2),
                'power_W': round(solar_data['power'] / 1000.0, 3) if solar_data['power'] > 0 else 0.0,
                'power_mW': round(solar_data['power'], 2),
                'energy_Wh': round(solar_data['total_energy_mWh'] / 1000.0, 4),
                'energy_mWh': round(solar_data['total_energy_mWh'], 2),
                'temperature_C': round(solar_data['temp'], 2),
                'illuminance_lux': round(solar_data['lux'], 1),
                'irradiance_W_m2': round(solar_data['watts'], 2)
            }
            solar_data['log_records'].append(record)

            # Auto-backup append to disk
            try:
                df_row = pd.DataFrame([record])
                df_row.to_csv(PERSISTENCE_FILE, mode='a', header=not os.path.exists(PERSISTENCE_FILE), index=False)
                solar_data['logging_active'] = True
            except Exception:
                solar_data['logging_active'] = False

            # Memory ring-buffer bounding
            if len(solar_data['log_records']) > 20000:
                solar_data['log_records'].pop(0)

    except Exception:
        pass

@st.cache_resource
def init_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except Exception:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except Exception:
            client = mqtt.Client()
            
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        client.connect("broker.emqx.io", 1883, keepalive=60)
    except Exception:
        try:
            client.connect("broker.hivemq.com", 1883, keepalive=60)
        except Exception as e:
            add_event(f"MQTT init connect error: {e}", "error")

    client.loop_start()
    return client

try:
    mqtt_client = init_mqtt()
except Exception as e:
    st.error(f"MQTT Service Startup Error: {e}")

# =========================================================================================
# 6. SIDEBAR CONTROLS & DATA MANAGEMENT
# =========================================================================================
st.sidebar.markdown("### ⚙️ Dashboard Controls")
live_update = st.sidebar.checkbox("🔄 Live Update", value=True, help="Toggle periodic page refresh for live data streaming.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🗄️ Data Management")
confirm_reset = st.sidebar.checkbox("Confirm data reset", value=False, help="Must check before clearing data.")
if st.sidebar.button("⚠️ Clear All Data & Restart", disabled=not confirm_reset):
    if os.path.exists(PERSISTENCE_FILE):
        try: os.remove(PERSISTENCE_FILE)
        except Exception: pass
    solar_data['log_records'] = []
    solar_data['total_energy_mWh'] = 0.0
    solar_data['last_power_time'] = 0.0
    solar_data['voltage'] = 0.0
    solar_data['current'] = 0.0
    solar_data['power'] = 0.0
    solar_data['temp'] = 0.0
    solar_data['lux'] = 0.0
    solar_data['watts'] = 0.0
    add_event("All persistent and session data cleared by operator", "warning")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(
    "🎓 **Solar Power Monitoring System**\n\n"
    "IoT-based Photovoltaic DAQ\n\n"
    "• Protocol: MQTT on Wi-Fi\n"
    "• Broker: broker.emqx.io\n"
    "• Timezone: Asia/Tehran"
)

# =========================================================================================
# 7. FRESHNESS & SYSTEM STATUS COMPUTATION
# =========================================================================================
now_epoch = time.time()
if solar_data['last_msg_time'] > 0:
    sec_since_update = now_epoch - solar_data['last_msg_time']
    if sec_since_update < 60:
        freshness_label = f"{sec_since_update:.1f}s ago"
    elif sec_since_update < 3600:
        freshness_label = f"{int(sec_since_update // 60)}m {int(sec_since_update % 60)}s ago"
    else:
        freshness_label = f"{sec_since_update / 3600:.1f}h ago"
        
    if sec_since_update > 30:
        health_status = "Warning: Data Delayed"
        health_color = "status-amber"
        system_normal = False
    else:
        health_status = "System Normal"
        health_color = "status-green"
        system_normal = True
else:
    freshness_label = "Waiting for data..."
    health_status = "Waiting for Telemetry"
    health_color = "status-amber"
    system_normal = False

mqtt_badge_cls = "status-green" if solar_data['mqtt_connected'] else "status-red"
mqtt_badge_txt = "● MQTT Connected" if solar_data['mqtt_connected'] else "🔴 MQTT Disconnected"

# =========================================================================================
# 8. HEADER BAR
# =========================================================================================
st.markdown(f"""
<div class="header-bar">
    <div class="header-title-box">
        <div class="header-main-title">☀️ SOLAR POWER MONITORING</div>
        <div class="header-subtitle">Clean Energy • Real-time Data • A Greener Tomorrow</div>
    </div>
    <div class="header-badges">
        <div class="header-pill">📅 <span class="header-pill-val">{jalali_date_str}</span> <span style="font-size:11.5px; opacity:0.75;">({gregorian_date_str})</span></div>
        <div class="header-pill">⏰ <span class="header-pill-val">{time_str}</span></div>
        <div class="header-pill">🌤️ {tehran_temp} <span style="font-size:11.5px; opacity:0.75;">Tehran</span></div>
        <div class="header-pill {mqtt_badge_cls}">{mqtt_badge_txt}</div>
        <div class="header-pill">⏱ <span class="header-pill-val">{freshness_label}</span></div>
        <div class="header-pill">{solar_phase_icon} <span class="header-pill-val">{solar_phase}</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

# =========================================================================================
# 9. THREE-ZONE RESPONSIVE LAYOUT
# =========================================================================================
col_left, col_center, col_right = st.columns([1.1, 2.3, 1.2], gap="medium")

# -----------------------------------------------------------------------------------------
# ZONE 1 (LEFT): MAIN KPI & SYSTEM METRICS
# -----------------------------------------------------------------------------------------
with col_left:
    # 1. Hero KPI: Current Power
    raw_power_mw = solar_data['power']
    if raw_power_mw >= 1000:
        power_hero_val = f"{raw_power_mw / 1000.0:.2f}"
        power_hero_unit = "W"
    else:
        power_hero_val = f"{max(raw_power_mw, 0.0):.1f}"
        power_hero_unit = "mW"

    st.markdown(f"""
    <div class="hero-power-card">
        <div class="hero-title">⚡ CURRENT GENERATED POWER</div>
        <div class="hero-val">{power_hero_val}<span class="hero-unit">{power_hero_unit}</span></div>
        <div class="hero-sub">Live Photovoltaic Power Output</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Smaller KPI Grid
    volt_val = solar_data['voltage']
    curr_val = solar_data['current']
    irr_val = solar_data['watts']
    lux_val = solar_data['lux']
    temp_val = solar_data['temp']
    
    total_mwh = solar_data['total_energy_mWh']
    if total_mwh >= 1000:
        energy_disp = f"{total_mwh / 1000.0:.2f} Wh"
    else:
        energy_disp = f"{total_mwh:.1f} mWh"

    st.markdown(f"""
    <div class="glass-card">
        <div class="card-heading">
            <span>📊 ELECTRICAL & AMBIENT KPIS</span>
        </div>
        <div class="kpi-grid">
            <div class="kpi-item">
                <div class="kpi-item-title">⚡ Voltage</div>
                <div class="kpi-item-val">{volt_val:.2f} <span class="kpi-item-unit">V</span></div>
            </div>
            <div class="kpi-item">
                <div class="kpi-item-title">🔌 Current</div>
                <div class="kpi-item-val">{curr_val:.1f} <span class="kpi-item-unit">mA</span></div>
            </div>
            <div class="kpi-item">
                <div class="kpi-item-title">🔆 Irradiance</div>
                <div class="kpi-item-val">{irr_val:.1f} <span class="kpi-item-unit">W/m²</span></div>
            </div>
            <div class="kpi-item">
                <div class="kpi-item-title">☀️ Illuminance</div>
                <div class="kpi-item-val">{lux_val:.1f} <span class="kpi-item-unit">Lux</span></div>
            </div>
            <div class="kpi-item">
                <div class="kpi-item-title">🌡️ Panel Temp</div>
                <div class="kpi-item-val">{temp_val:.1f} <span class="kpi-item-unit">°C</span></div>
            </div>
            <div class="kpi-item">
                <div class="kpi-item-title">🔋 Total Energy</div>
                <div class="kpi-item-val">{energy_disp}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------------------
# ZONE 2 (CENTER): MAIN CHARTS & TEMPORAL TRENDS
# -----------------------------------------------------------------------------------------
with col_center:
    # 1. Real Timestamp-Based Temporal Filters
    timeframe = st.radio(
        label="Time Range Filter",
        options=["1 Min", "5 Mins", "15 Mins", "1 Hour", "12 Hours", "All-Time"],
        index=1,
        horizontal=True,
        label_visibility="collapsed"
    )

    if solar_data['log_records']:
        df_records = pd.DataFrame(solar_data['log_records'])
        df_records['dt'] = pd.to_datetime(df_records['timestamp'], errors='coerce')
        
        now_dt = datetime.now(tehran_tz)
        if timeframe == "1 Min":
            cutoff = now_dt - timedelta(minutes=1)
        elif timeframe == "5 Mins":
            cutoff = now_dt - timedelta(minutes=5)
        elif timeframe == "15 Mins":
            cutoff = now_dt - timedelta(minutes=15)
        elif timeframe == "1 Hour":
            cutoff = now_dt - timedelta(hours=1)
        elif timeframe == "12 Hours":
            cutoff = now_dt - timedelta(hours=12)
        else:
            cutoff = None

        if cutoff is not None:
            df_chart = df_records[df_records['dt'] >= cutoff]
        else:
            df_chart = df_records

        if not df_chart.empty and len(df_chart) > 1:
            span_s = (df_chart['dt'].max() - df_chart['dt'].min()).total_seconds()
            if span_s >= 3600:
                span_str = f"{int(span_s // 3600)}h {int((span_s % 3600) // 60)}m"
            elif span_s >= 60:
                span_str = f"{int(span_s // 60)}m {int(span_s % 60)}s"
            else:
                span_str = f"{int(span_s)}s"
            st.caption(f"Showing actual available data: **{span_str}** ({len(df_chart)} records)")
    else:
        df_chart = pd.DataFrame()

    # 2. Main Hero Chart: POWER & IRRADIANCE
    st.markdown("#### ⚡ Power (W) & Irradiance (W/m²)")
    if not df_chart.empty and len(df_chart) > 0:
        main_plot_df = pd.DataFrame({
            'Time': df_chart['time_display'],
            'Power (W)': df_chart['power_W'],
            'Irradiance (W/m²)': df_chart['irradiance_W_m2']
        }).set_index('Time')
        st.line_chart(main_plot_df, color=["#ea580c", "#f59e0b"], height=250)
    else:
        st.info("Collecting real-time sensor telemetry...")

    # 3. Secondary Compact Charts Grid
    col_sc1, col_sc2, col_sc3 = st.columns(3)

    with col_sc1:
        st.markdown("##### ⚡ Voltage (V)")
        if not df_chart.empty:
            st.line_chart(pd.DataFrame({'Time': df_chart['time_display'], 'Voltage (V)': df_chart['voltage_V']}).set_index('Time'), color="#2563eb", height=155)
        st.markdown("##### ☀️ Illuminance (Lux)")
        if not df_chart.empty:
            st.line_chart(pd.DataFrame({'Time': df_chart['time_display'], 'Lux': df_chart['illuminance_lux']}).set_index('Time'), color="#ca8a04", height=155)

    with col_sc2:
        st.markdown("##### 🔌 Current (mA)")
        if not df_chart.empty:
            st.line_chart(pd.DataFrame({'Time': df_chart['time_display'], 'Current (mA)': df_chart['current_mA']}).set_index('Time'), color="#d97706", height=155)
        st.markdown("##### 🔆 Irradiance (W/m²)")
        if not df_chart.empty:
            st.line_chart(pd.DataFrame({'Time': df_chart['time_display'], 'Irradiance (W/m²)': df_chart['irradiance_W_m2']}).set_index('Time'), color="#ea580c", height=155)

    with col_sc3:
        st.markdown("##### 🌡️ Temperature (°C)")
        if not df_chart.empty:
            st.line_chart(pd.DataFrame({'Time': df_chart['time_display'], 'Temp (°C)': df_chart['temperature_C']}).set_index('Time'), color="#dc2626", height=155)
        st.markdown("##### 🔋 Energy (Wh)")
        if not df_chart.empty:
            st.line_chart(pd.DataFrame({'Time': df_chart['time_display'], 'Energy (Wh)': df_chart['energy_Wh']}).set_index('Time'), color="#10b981", height=155)

# -----------------------------------------------------------------------------------------
# ZONE 3 (RIGHT): SYSTEM STATUS, SOLAR CONDITIONS, EVENTS & EXPORT
# -----------------------------------------------------------------------------------------
with col_right:
    # 1. System Status Panel
    logging_status_str = "Active" if solar_data['logging_active'] else "Error"
    logging_status_color = "#10b981" if solar_data['logging_active'] else "#ef4444"
    health_icon = "●" if system_normal else "⚠"

    st.markdown(f"""
    <div class="glass-card">
        <div class="card-heading">
            <span>🛡️ SYSTEM STATUS</span>
        </div>
        <div class="status-row">
            <span class="status-label">Overall Health</span>
            <span class="status-badge" style="color: {'#10b981' if system_normal else '#d97706'};">{health_icon} {health_status}</span>
        </div>
        <div class="status-row">
            <span class="status-label">MQTT Connection</span>
            <span class="status-badge" style="color: {'#10b981' if solar_data['mqtt_connected'] else '#ef4444'};">{'● Connected' if solar_data['mqtt_connected'] else '🔴 Disconnected'}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Data Logging</span>
            <span class="status-badge" style="color: {logging_status_color};">● {logging_status_str}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Last Packet</span>
            <span class="status-badge" style="color: #0f172a;">{freshness_label}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Reconnect Count</span>
            <span class="status-badge" style="color: #2563eb;">{solar_data['reconnect_count']}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Total Messages</span>
            <span class="status-badge" style="color: #64748b;">{solar_data['msg_count']:,}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Solar Conditions Panel & Classification
    current_irr = solar_data['watts']
    if current_irr < 200.0:
        cond_label = "Low Solar Intensity"
        pct_pin = min(max(current_irr / 200.0 * 33.0, 5.0), 33.0)
    elif current_irr <= 650.0:
        cond_label = "Moderate Solar Intensity"
        pct_pin = 33.0 + ((current_irr - 200.0) / 450.0 * 34.0)
    else:
        cond_label = "Strong Solar Radiation"
        pct_pin = 67.0 + min(((current_irr - 650.0) / 350.0 * 33.0), 31.0)

    st.markdown(f"""
    <div class="glass-card">
        <div class="card-heading">
            <span>🔆 SOLAR CONDITIONS</span>
        </div>
        <div style="font-size: 13.5px; color: #475569; margin-bottom: 6px;">
            Atmospheric Class: <b style="color: #0f172a;">{cond_label}</b>
        </div>
        <div class="scale-bar">
            <div class="scale-pointer" style="left: {pct_pin:.1f}%;"></div>
        </div>
        <div class="scale-labels">
            <span>Low (&lt;200)</span>
            <span>Moderate</span>
            <span>Strong (&gt;650 W/m²)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. Alerts & Recent Events
    event_html_items = ""
    if solar_data['events']:
        for ev in reversed(solar_data['events'][-5:]):
            lvl = ev.get('level', 'info')
            t = ev.get('time', '')
            txt = ev.get('text', '')
            event_html_items += f'<div class="event-entry {lvl}"><span style="color:#0f172a; font-weight:600;">{txt}</span><span style="color:#94a3b8; font-size:11px;">{t}</span></div>'
    else:
        event_html_items = '<div style="font-size:12.5px; color:#64748b;">No recent alerts recorded.</div>'

    st.markdown(f"""
    <div class="glass-card">
        <div class="card-heading">
            <span>🔔 RECENT EVENTS</span>
        </div>
        <div class="event-log-container">
            {event_html_items}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. Data Export Action
    if solar_data['log_records']:
        df_export = pd.DataFrame(solar_data['log_records'])
        csv_export = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV Archive",
            data=csv_export,
            file_name=f"solar_log_{gregorian_date_str}.csv",
            mime="text/csv",
            use_container_width=True
        )

# =========================================================================================
# 10. BOTTOM FULL-WIDTH ZONE: RECENT MEASUREMENTS TABLE
# =========================================================================================
st.markdown("---")
col_tbl_head, col_tbl_ctl = st.columns([3, 1])
with col_tbl_head:
    st.markdown("#### 📋 Recent Telemetry Measurements")
with col_tbl_ctl:
    row_count = st.selectbox("Rows to display", options=[5, 10, 20, 50], index=1)

if solar_data['log_records']:
    df_table = pd.DataFrame(solar_data['log_records'])
    display_cols = [
        'time_display', 'voltage_V', 'current_mA', 'power_W', 
        'energy_Wh', 'temperature_C', 'illuminance_lux', 'irradiance_W_m2'
    ]
    avail_cols = [c for c in display_cols if c in df_table.columns]
    df_display = df_table[avail_cols].tail(row_count).iloc[::-1]
    
    clean_col_names = {
        'time_display': 'Time',
        'voltage_V': 'Voltage (V)',
        'current_mA': 'Current (mA)',
        'power_W': 'Power (W)',
        'energy_Wh': 'Energy (Wh)',
        'temperature_C': 'Temp (°C)',
        'illuminance_lux': 'Illuminance (Lux)',
        'irradiance_W_m2': 'Irradiance (W/m²)'
    }
    df_display = df_display.rename(columns=clean_col_names)
    st.dataframe(df_display, use_container_width=True, height=220)
else:
    st.info("Waiting for incoming telemetry packets to populate table...")

# =========================================================================================
# 11. LIVE UPDATE AUTO-RERUN LOOP
# =========================================================================================
if live_update:
    time.sleep(3.5)
    st.rerun()