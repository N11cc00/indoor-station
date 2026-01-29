import json
from flask import Flask, request, jsonify
from functools import wraps
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
from flask_sqlalchemy import SQLAlchemy

# Define the timezone (e.g., 'US/Pacific', 'Europe/London', 'Asia/Kolkata')
timezone = pytz.timezone('Europe/Berlin')

load_dotenv()
VALID_API_TOKEN = os.environ.get("API_TOKEN")

app = Flask("sensor_endpoint")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sensor_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the SensorData model
class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    light = db.Column(db.Float, nullable=True)  # Optional for backward compatibility

    def to_dict(self):
        return {
            "timestamp": self.timestamp.strftime('%Y-%m-%d %H:%M:%S %z %Z'),
            "temperature": self.temperature,
            "humidity": self.humidity,
            "light": self.light
        }

with app.app_context():
    db.create_all()

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

# def get_last_n_rows_from_csv(file_path, n):
#     """Helper function to get the last n rows from a CSV file."""
#     with open(file_path, 'r', newline='') as csv_file:
#         reader = csv.reader(csv_file)
#         rows = list(reader)
#         return rows[-n:] if len(rows) >= n else rows
    
# def get_rows_between_timestamps(file_path, from_timestamp, to_timestamp):
#     """Helper function to get rows between two timestamps."""
#     with open(file_path, 'r', newline='') as csv_file:
#         reader = csv.reader(csv_file)
#         rows = [row for row in reader if from_timestamp <= row[0] <= to_timestamp]
#         return rows

@app.route('/sensor', methods=["GET"])
@require_api_token
def get_sensor_data():
    try:
        from_timestamp = request.args.get('from', default=None, type=str)
        to_timestamp = request.args.get('to', default=None, type=str)

        try:
            from_timestamp = datetime.strptime(from_timestamp, '%Y-%m-%d %H:%M:%S %z')
            to_timestamp = datetime.strptime(to_timestamp, '%Y-%m-%d %H:%M:%S %z')
        except ValueError:
            return jsonify({"error": "Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS +ZZZZ"}), 400

        rows = SensorData.query.filter(
            SensorData.timestamp >= from_timestamp,
            SensorData.timestamp <= to_timestamp
        ).order_by(SensorData.timestamp.desc()).all()

        if rows:
            data = [row.to_dict() for row in rows]
            return jsonify(data), 200
        else:
            return jsonify({"error": "No data found in the specified time range"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sensor", methods=["POST"])
@require_api_token
def add_sensor_data():
    try:
        sensor_data = json.loads(request.data)

        if "temperature" not in sensor_data or "humidity" not in sensor_data:
            return jsonify({"error": "Key missing in data"}), 400

        current_time = datetime.now(timezone)
        new_entry = SensorData(
            timestamp=current_time,
            temperature=float(sensor_data["temperature"]),
            humidity=float(sensor_data["humidity"]),
            light=float(sensor_data.get("light")) if sensor_data.get("light") is not None else None
        )

        db.session.add(new_entry)
        db.session.commit()

        return jsonify(new_entry.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0')
