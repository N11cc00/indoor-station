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

def get_last_n_rows_from_csv(file_path, n):
    """Helper function to get the last n rows from a CSV file."""
    with open(file_path, 'r', newline='') as csv_file:
        reader = csv.reader(csv_file)
        rows = list(reader)
        return rows[-n:] if len(rows) >= n else rows
    
def get_rows_between_timestamps(file_path, from_timestamp, to_timestamp):
    """Helper function to get rows between two timestamps."""
    with open(file_path, 'r', newline='') as csv_file:
        reader = csv.reader(csv_file)
        rows = [row for row in reader if from_timestamp <= row[0] <= to_timestamp]
        return rows

@app.route('/sensor', methods=["GET"])
def get_sensor_data():
    try:
        number_of_rows = Flask.request.args.get('rows', default=1, type=int) # counts from the end

        from_timestamp = Flask.request.args.get('from', default=None, type=str)
        to_timestamp = Flask.request.args.get('to', default=None, type=str)

        if from_timestamp and to_timestamp:
            from_timestamp = datetime.strptime(from_timestamp, '%Y-%m-%d %H:%M:%S %z')
            to_timestamp = datetime.strptime(to_timestamp, '%Y-%m-%d %H:%M:%S %z')
            # TODO: Implement filtering by timestamp range
            rows_in_timespan = get_rows_between_timestamps('data.csv', from_timestamp, to_timestamp)
            if rows_in_timespan:
                data = [{"timestamp": row[0], "temperature": row[1], "humidity": row[2]} for row in rows_in_timespan]
                return jsonify(data), 200
            else:
                return jsonify({"error": "No data found in the specified time range"}), 404
        else:
            if number_of_rows < 1:
                return jsonify({"error": "Invalid number of rows requested"}), 400
            
            last_n_rows = get_last_n_rows_from_csv('data.csv', number_of_rows)
            
            if last_n_rows:
                data = [{"timestamp": row[0], "temperature": row[1], "humidity": row[2]} for row in last_n_rows] 
                return jsonify(data), 200
            else:
                return jsonify({"error": "No data found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sensor", methods=["POST"])
@require_api_token
def add_sensor_data():
    try:
        with open('data.csv', 'a', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
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