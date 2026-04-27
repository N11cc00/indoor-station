import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Indoor Station Dashboard",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Timezone
timezone = pytz.timezone('Europe/Berlin')

# API Configuration
API_URL = "http://localhost:6666/sensor"
API_TOKEN = os.environ.get("API_TOKEN")  # Read API token from .env
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")  # Set in .env file

SESSION_FILE = Path(".streamlit/sessions.json")


def _load_sessions():
    """Load active sessions from file."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_sessions(sessions):
    """Save sessions to file with restrictive permissions."""
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(sessions, f)
    # Only owner can read/write (chmod 600)
    SESSION_FILE.chmod(0o600)


def _get_session_token():
    """Get session token from session_state or URL query params."""
    # Check session_state first (fastest)
    if "session_token" in st.session_state:
        return st.session_state.session_token

    # Check URL query params (survives refresh)
    query_params = st.query_params
    if "session_token" in query_params:
        token = query_params["session_token"]
        st.session_state.session_token = token
        return token

    return None


def _validate_session():
    """Check if user has valid session token."""
    token = _get_session_token()
    if not token:
        return False

    sessions = _load_sessions()
    if token not in sessions:
        return False

    # Check if session expired (30 days)
    created_at = datetime.fromisoformat(sessions[token])
    if datetime.now() - created_at > timedelta(days=30):
        # Session expired
        sessions.pop(token)
        _save_sessions(sessions)
        st.session_state.session_token = None
        return False

    return True


def _create_session():
    """Create new session after password is correct."""
    import secrets
    sessions = _load_sessions()
    token = secrets.token_urlsafe(32)
    sessions[token] = datetime.now().isoformat()
    _save_sessions(sessions)

    # Store in session_state
    st.session_state.session_token = token
    # Also set in URL query params so it persists on refresh
    st.query_params["session_token"] = token


def require_login():
    """Simple password-based login for self-only access."""
    if _validate_session():
        # Already authenticated
        return

    # Not authenticated - show login
    st.title("🔐 Dashboard Login")
    st.markdown("Enter password to access the dashboard.")

    if not DASHBOARD_PASSWORD:
        st.error("❌ DASHBOARD_PASSWORD not set. Set it in your .env file.")
        st.stop()

    # Rate limiting: max 5 attempts per 15 minutes
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
        st.session_state.login_time = datetime.now()

    # Reset attempts after 15 minutes
    if datetime.now() - st.session_state.login_time > timedelta(minutes=15):
        st.session_state.login_attempts = 0
        st.session_state.login_time = datetime.now()

    if st.session_state.login_attempts >= 5:
        st.error("❌ Too many failed attempts. Try again in 15 minutes.")
        st.stop()

    password = st.text_input("Password", type="password", key="dashboard_pass")
    submit_button = st.button("Login", key="login_btn", use_container_width=True)

    if submit_button and password:
        if password == DASHBOARD_PASSWORD:
            st.session_state.login_attempts = 0
            _create_session()
            st.rerun()
        else:
            st.session_state.login_attempts += 1
            remaining = 5 - st.session_state.login_attempts
            st.error(f"❌ Incorrect password ({remaining} attempts left)")
    elif not submit_button and password:
        # Allow Enter key to trigger login
        if password == DASHBOARD_PASSWORD:
            st.session_state.login_attempts = 0
            _create_session()
            st.rerun()

    st.stop()


def render_user_controls():
    """Show logout button."""
    if st.sidebar.button("🚪 Logout"):
        sessions = _load_sessions()
        token = _get_session_token()
        if token and token in sessions:
            sessions.pop(token)
            _save_sessions(sessions)
        # Clear session
        st.session_state.session_token = None
        if "session_token" in st.query_params:
            del st.query_params["session_token"]
        st.rerun()


require_login()

@st.cache_data(ttl=60)  # Cache for 60 seconds
def fetch_sensor_data(from_time, to_time):
    """Fetch sensor data from Flask API"""
    try:
        params = {
            'from': from_time.strftime('%Y-%m-%d %H:%M:%S %z'),
            'to': to_time.strftime('%Y-%m-%d %H:%M:%S %z')
        }
        headers = {
            'Authorization': f'Bearer {API_TOKEN}'
        }
        response = requests.get(API_URL, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                # Convert temperature and humidity by dividing by 10
                df['temperature'] = df['temperature'] / 10.0
                df['humidity'] = df['humidity'] / 10.0
                df = df.sort_values('timestamp')
                return df
            else:
                return pd.DataFrame()
        else:
            st.error(f"API Error: {response.status_code}")
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return pd.DataFrame()

# Title and header
st.title("🏠 Indoor Station Dashboard")
st.markdown("Real-time temperature and humidity monitoring")
render_user_controls()

st.sidebar.markdown("---")

#
# Sidebar controls
st.sidebar.header("Settings")

# Time range selection
time_range = st.sidebar.selectbox(
    "Select Time Range",
    ["Last Hour", "Last 6 Hours", "Last 12 Hours", "Last 24 Hours", "Last 7 Days", "Custom"]
)

# Calculate time range
now = datetime.now(timezone)
if time_range == "Last Hour":
    from_time = now - timedelta(hours=1)
    to_time = now
elif time_range == "Last 6 Hours":
    from_time = now - timedelta(hours=6)
    to_time = now
elif time_range == "Last 12 Hours":
    from_time = now - timedelta(hours=12)
    to_time = now
elif time_range == "Last 24 Hours":
    from_time = now - timedelta(days=1)
    to_time = now
elif time_range == "Last 7 Days":
    from_time = now - timedelta(days=7)
    to_time = now
else:  # Custom
    col1, col2 = st.sidebar.columns(2)
    with col1:
        from_date = st.date_input("From Date", now.date() - timedelta(days=1))
        from_time_input = st.time_input("From Time", now.time())
    with col2:
        to_date = st.date_input("To Date", now.date())
        to_time_input = st.time_input("To Time", now.time())

    from_time = timezone.localize(datetime.combine(from_date, from_time_input))
    to_time = timezone.localize(datetime.combine(to_date, to_time_input))

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=True)
if auto_refresh:
    st.sidebar.info("Dashboard auto-refreshes every 30 seconds")

# Refresh button
if st.sidebar.button("🔄 Refresh Now"):
    st.cache_data.clear()

# Fetch data
with st.spinner("Loading sensor data..."):
    df = fetch_sensor_data(from_time, to_time)

if df.empty:
    st.warning("No data available for the selected time range.")
else:
    # Current readings (latest data point)
    latest = df.iloc[-1]

    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="🌡️ Current Temperature",
            value=f"{latest['temperature']:.1f}°C",
            delta=f"{latest['temperature'] - df.iloc[-2]['temperature']:.1f}°C" if len(df) > 1 else None
        )

    with col2:
        st.metric(
            label="💧 Current Humidity",
            value=f"{latest['humidity']:.1f}%",
            delta=f"{latest['humidity'] - df.iloc[-2]['humidity']:.1f}%" if len(df) > 1 else None
        )

    with col3:
        st.metric(
            label="💡 Current Light",
            value=f"{latest['lux']:.0f} lux",
            delta=f"{latest['lux'] - df.iloc[-2]['lux']:.0f}" if len(df) > 1 else None
        )

    with col4:
        st.metric(
            label="📊 Data Points",
            value=len(df)
        )

    with col5:
        st.metric(
            label="🕒 Last Update",
            value=latest['timestamp'].strftime('%H:%M:%S')
        )

    # Charts
    st.markdown("---")

    # Temperature Chart
    st.subheader("🌡️ Temperature Over Time")
    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['temperature'],
        mode='lines+markers',
        name='Temperature',
        line=dict(color='#FF6B6B', width=2),
        marker=dict(size=4),
        fill='tozeroy',
        fillcolor='rgba(255, 107, 107, 0.1)'
    ))

    fig_temp.update_layout(
        xaxis_title="Time",
        yaxis_title="Temperature (°C)",
        hovermode='x unified',
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig_temp, use_container_width=True)

    # Humidity Chart
    st.subheader("💧 Humidity Over Time")
    fig_humid = go.Figure()
    fig_humid.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['humidity'],
        mode='lines+markers',
        name='Humidity',
        line=dict(color='#4ECDC4', width=2),
        marker=dict(size=4),
        fill='tozeroy',
        fillcolor='rgba(78, 205, 196, 0.1)'
    ))

    fig_humid.update_layout(
        xaxis_title="Time",
        yaxis_title="Humidity (%)",
        hovermode='x unified',
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig_humid, use_container_width=True)

    # Light Chart
    st.subheader("💡 Light Over Time")
    fig_light = go.Figure()
    fig_light.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['lux'],
        mode='lines+markers',
        name='Light',
        line=dict(color='#FFD93D', width=2),
        marker=dict(size=4),
        fill='tozeroy',
        fillcolor='rgba(255, 217, 61, 0.1)'
    ))

    fig_light.update_layout(
        xaxis_title="Time",
        yaxis_title="Light (lux)",
        hovermode='x unified',
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig_light, use_container_width=True)

    # Raw Light Chart
    st.subheader("🔆 Raw Light Sensor Values")
    fig_raw_light = go.Figure()
    fig_raw_light.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['raw_light'],
        mode='lines+markers',
        name='Raw Light',
        line=dict(color='#FFA500', width=2),
        marker=dict(size=4),
        fill='tozeroy',
        fillcolor='rgba(255, 165, 0, 0.1)'
    ))

    fig_raw_light.update_layout(
        xaxis_title="Time",
        yaxis_title="Raw Light Value (ADC)",
        hovermode='x unified',
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig_raw_light, use_container_width=True)

    # Combined Chart
    st.subheader("📈 Combined View")
    fig_combined = go.Figure()

    fig_combined.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['temperature'],
        mode='lines',
        name='Temperature (°C)',
        line=dict(color='#FF6B6B', width=2),
        yaxis='y'
    ))

    fig_combined.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['humidity'],
        mode='lines',
        name='Humidity (%)',
        line=dict(color='#4ECDC4', width=2),
        yaxis='y2'
    ))

    fig_combined.update_layout(
        xaxis_title="Time",
        yaxis=dict(title="Temperature (°C)", side='left'),
        yaxis2=dict(title="Humidity (%)", side='right', overlaying='y'),
        hovermode='x unified',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig_combined, use_container_width=True)

    # Statistics
    st.markdown("---")
    st.subheader("📊 Statistics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Temperature**")
        temp_stats = pd.DataFrame({
            'Metric': ['Average', 'Minimum', 'Maximum', 'Std Dev'],
            'Value': [
                f"{df['temperature'].mean():.2f}°C",
                f"{df['temperature'].min():.2f}°C",
                f"{df['temperature'].max():.2f}°C",
                f"{df['temperature'].std():.2f}°C"
            ]
        })
        st.dataframe(temp_stats, hide_index=True, use_container_width=True)

    with col2:
        st.markdown("**Humidity**")
        humid_stats = pd.DataFrame({
            'Metric': ['Average', 'Minimum', 'Maximum', 'Std Dev'],
            'Value': [
                f"{df['humidity'].mean():.2f}%",
                f"{df['humidity'].min():.2f}%",
                f"{df['humidity'].max():.2f}%",
                f"{df['humidity'].std():.2f}%"
            ]
        })
        st.dataframe(humid_stats, hide_index=True, use_container_width=True)

    with col3:
        st.markdown("**Light**")
        light_stats = pd.DataFrame({
            'Metric': ['Average', 'Minimum', 'Maximum', 'Std Dev'],
            'Value': [
                f"{df['lux'].mean():.0f}",
                f"{df['lux'].min():.0f}",
                f"{df['lux'].max():.0f}",
                f"{df['lux'].std():.0f}"
            ]
        })
        st.dataframe(light_stats, hide_index=True, use_container_width=True)

    # Raw data table (expandable)
    with st.expander("📋 View Raw Data"):
        st.dataframe(
            df.sort_values('timestamp', ascending=False),
            use_container_width=True,
            hide_index=True
        )

# Auto-refresh mechanism
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("*Indoor Station Dashboard - Powered by Streamlit*")
