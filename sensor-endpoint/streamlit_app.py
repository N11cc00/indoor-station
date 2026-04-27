import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
import extra_streamlit_components as stx
from itsdangerous import URLSafeSerializer, BadSignature

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

# Password Configuration
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")  # Default password

# Cookie/session configuration
AUTH_COOKIE_NAME = "indoor_station_dashboard_auth"
AUTH_COOKIE_DAYS = int(os.environ.get("DASHBOARD_AUTH_DAYS", "30"))
AUTH_SECRET = os.environ.get("DASHBOARD_AUTH_SECRET") or API_TOKEN or DASHBOARD_PASSWORD


def _auth_serializer():
    """Create serializer used to sign/verify the auth cookie value."""
    return URLSafeSerializer(AUTH_SECRET or "dev-fallback-secret", salt="indoor-station-auth")


def _build_auth_cookie_value():
    return _auth_serializer().dumps({"authenticated": True})


def _is_valid_auth_cookie(cookie_value):
    if not cookie_value:
        return False

    try:
        payload = _auth_serializer().loads(cookie_value)
    except BadSignature:
        return False

    return payload.get("authenticated") is True

def check_password():
    """Returns True if the user has entered the correct password."""

    cookie_manager = stx.CookieManager(key="dashboard_auth_cookie_manager")

    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # Restore auth from cookie after refresh/new session
    cookie_value = cookie_manager.get(cookie=AUTH_COOKIE_NAME)
    if not st.session_state.authenticated and _is_valid_auth_cookie(cookie_value):
        st.session_state.authenticated = True

    # If already authenticated, return True
    if st.session_state.authenticated:
        return True

    # Show login form
    st.title("🔐 Indoor Station Dashboard Login")
    st.markdown("Please enter the dashboard password to continue.")

    # Create a form that submits on Enter
    with st.form(key="login_form"):
        password = st.text_input("Password", type="password", key="password_input")
        submit = st.form_submit_button("Login", type="primary")

        if submit:
            if password == DASHBOARD_PASSWORD:
                st.session_state.authenticated = True
                cookie_manager.set(
                    cookie=AUTH_COOKIE_NAME,
                    val=_build_auth_cookie_value(),
                    expires_at=datetime.utcnow() + timedelta(days=AUTH_COOKIE_DAYS)
                )
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Incorrect password")

    # Instructions
    # st.markdown("---")
    # st.info("💡 Set custom password via `.env` file: `DASHBOARD_PASSWORD=your_password`")

    return False

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

# Check authentication first
if not check_password():
    st.stop()  # Stop execution if not authenticated

# Title and header
st.title("🏠 Indoor Station Dashboard")
st.markdown("Real-time temperature and humidity monitoring")

if st.sidebar.button("🚪 Logout"):
    cookie_manager = stx.CookieManager(key="dashboard_auth_cookie_manager")
    cookie_manager.delete(AUTH_COOKIE_NAME)
    st.session_state.authenticated = False
    st.rerun()

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
