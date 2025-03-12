import streamlit as st
import requests
import pandas as pd
import folium
import sqlite3
import time
import smtplib
from twilio.rest import Client
from streamlit_folium import folium_static

# OpenSky API URL
API_URL = "https://opensky-network.org/api/states/all"

# Nigeria's approximate latitude and longitude boundaries
NIGERIA_BOUNDS = {
    "min_lat": 4.0,
    "max_lat": 14.0,
    "min_lon": 2.7,
    "max_lon": 14.6
}

# Initialize SQLite database
conn = sqlite3.connect("flights.db", check_same_thread=False)
cursor = conn.cursor()

# Create flight tracking table if not exists
cursor.execute("""
    CREATE TABLE IF NOT EXISTS flights (
        icao24 TEXT PRIMARY KEY,
        callsign TEXT,
        latitude REAL,
        longitude REAL,
        altitude REAL,
        velocity REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# Twilio SMS Configuration (replace with your credentials)
TWILIO_SID = "your_twilio_sid"
TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
TWILIO_PHONE_NUMBER = "your_twilio_phone"
ALERT_PHONE_NUMBER = "your_phone_number"

# Email Configuration
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_PASSWORD = "your_email_password"
ALERT_EMAIL = "recipient_email@gmail.com"

def send_sms_alert(flight):
    """Send SMS alert using Twilio when a specific flight is detected"""
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"ALERT! Flight {flight['callsign']} (ICAO24: {flight['icao24']}) detected over Nigeria at {flight['altitude']}m altitude.",
            from_=TWILIO_PHONE_NUMBER,
            to=ALERT_PHONE_NUMBER
        )
        print("SMS Alert Sent!")
    except Exception as e:
        print("SMS Error:", e)

def send_email_alert(flight):
    """Send Email alert when a specific flight is detected"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            subject = f"Flight Alert: {flight['callsign']} Detected"
            body = f"Flight {flight['callsign']} (ICAO24: {flight['icao24']}) detected over Nigeria at altitude {flight['altitude']}m."
            message = f"Subject: {subject}\n\n{body}"
            server.sendmail(EMAIL_ADDRESS, ALERT_EMAIL, message)
            print("Email Alert Sent!")
    except Exception as e:
        print("Email Error:", e)

def fetch_flight_data():
    """Fetch live flight data from OpenSky Network API"""
    response = requests.get(API_URL)
    if response.status_code == 200:
        data = response.json()
        return data.get("states", [])
    else:
        st.error("Failed to fetch flight data. Try again later.")
        return []

def filter_nigerian_flights(flights):
    """Filter flights currently over Nigeria"""
    nigerian_flights = []
    for flight in flights:
        if flight[5] and flight[6]:  # Ensure latitude & longitude exist
            lat, lon = flight[6], flight[5]
            if (NIGERIA_BOUNDS["min_lat"] <= lat <= NIGERIA_BOUNDS["max_lat"] and
                NIGERIA_BOUNDS["min_lon"] <= lon <= NIGERIA_BOUNDS["max_lon"]):
                flight_data = {
                    "icao24": flight[0],
                    "callsign": flight[1].strip() if flight[1] else "Unknown",
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": flight[7],
                    "velocity": flight[9]
                }
                nigerian_flights.append(flight_data)
                
                # Send alert if the flight matches the watchlist
                if flight_data["callsign"] in watchlist:
                    send_sms_alert(flight_data)
                    send_email_alert(flight_data)

    return nigerian_flights

def save_to_db(flights):
    """Save flight data to SQLite database"""
    for flight in flights:
        cursor.execute("""
            INSERT OR REPLACE INTO flights (icao24, callsign, latitude, longitude, altitude, velocity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (flight["icao24"], flight["callsign"], flight["latitude"], flight["longitude"], flight["altitude"], flight["velocity"]))
    conn.commit()

def load_past_flights():
    """Load historical flight data"""
    cursor.execute("SELECT * FROM flights ORDER BY timestamp DESC LIMIT 50")
    return cursor.fetchall()

# Streamlit App
st.title("✈️ Nigeria Flight Tracker")
st.write("Live flight tracking over Nigeria using OpenSky Network API.")

# User input for tracking specific flights
watchlist = st.text_input("Enter flight callsign(s) to watch (comma-separated)", "").upper().split(",")

# Fetch and display flight data
flights = fetch_flight_data()
nigerian_flights = filter_nigerian_flights(flights)

if nigerian_flights:
    save_to_db(nigerian_flights)

    # **Search Functionality**
    search_query = st.text_input("🔍 Search by ICAO24 or Callsign").upper()
    if search_query:
        nigerian_flights = [f for f in nigerian_flights if search_query in f["callsign"] or search_query in f["icao24"]]

    # Display flight table
    st.subheader("🛫 Active Flights Over Nigeria")
    df = pd.DataFrame(nigerian_flights)
    st.dataframe(df)

    # Display map
    m = folium.Map(location=[9.08, 8.68], zoom_start=6)
    for flight in nigerian_flights:
        folium.Marker(
            location=[flight["latitude"], flight["longitude"]],
            popup=f'Callsign: {flight["callsign"]}\nAltitude: {flight["altitude"]}m',
            icon=folium.Icon(color="blue", icon="plane", prefix="fa")
        ).add_to(m)
    folium_static(m)

else:
    st.warning("No active flights detected over Nigeria at the moment.")

# **Flight History Tracking**
st.subheader("📜 Flight History (Last 50 Records)")
past_flights = load_past_flights()
if past_flights:
    df_history = pd.DataFrame(past_flights, columns=["ICAO24", "Callsign", "Latitude", "Longitude", "Altitude", "Velocity", "Timestamp"])
    st.dataframe(df_history)
else:
    st.write("No past flight records found.")

# Refresh every 60 seconds
time.sleep(60)
st.rerun()

