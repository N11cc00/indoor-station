import json
from flask import Flask, request, jsonify
from functools import wraps
import csv
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os

# In correct order
CSV_HEADER = ["timestamp", "temperature", "humidity"]

# Define the timezone (e.g., 'US/Pacific', 'Europe/London', 'Asia/Kolkata')
timezone = pytz.timezone('Europe/Berlin')

csv_file = open('data.csv', 'a+',  newline='')
csv_writer = csv.writer(csv_file)
csv_reader = csv.reader(csv_file)

load_dotenv()
VALID_API_TOKEN = os.environ.get("API_TOKEN")

app = Flask("sensor_endpoint")

def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for token in Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401

        # Expecting "Bearer <token>" format
        try:
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
        except IndexError:
            return jsonify({"error": "Invalid Authorization header format"}), 401

        # Validate token
        if token != VALID_API_TOKEN:
            return jsonify({"error": "Invalid or unauthorized token"}), 401

        return f(*args, **kwargs)
    return decorated_function

@app.route('/sensor', methods=["GET"])
def get_sensor_data():
    try:
        with open('data.csv', 'r', newline='') as f:
            reader = csv.reader(f)
            last_row = None
            for row in reader:
                if row:
                    last_row = row
            if last_row:
                data = {"timestamp": last_row[0], "temperature": last_row[1], "humidity": last_row[2]}
                return jsonify(data), 200
            else:
                return jsonify({"error": "No data found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sensor", methods=["POST"])
@require_api_token
def add_sensor_data():
    try:
        with open('data.csv', 'a', newline=''):
            # Get current time in the specified timezone
            current_time = datetime.now(timezone)

            # Format the timestamp as a string (e.g., YYYY-MM-DD HH:MM:SS TZOFFSET TZNAME)
            timestamp_string = current_time.strftime('%Y-%m-%d %H:%M:%S %z %Z')
            sensor_data = json.loads(request.data)

            if not "temperature" in sensor_data or not "humidity" in sensor_data:
                return jsonify({"error": "Key missing in data"}), 400
            
            sensor_data.update({"timestamp": timestamp_string})

            csv_writer.writerow([sensor_data["timestamp"], sensor_data["temperature"], sensor_data["humidity"]])

            return jsonify(sensor_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

app.run()