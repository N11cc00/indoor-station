"""
Script to populate the sensor database with realistic test data
"""
import random
from datetime import datetime, timedelta
import pytz
from main import app, db, SensorData

# Configuration
timezone = pytz.timezone('Europe/Berlin')
DAYS_OF_DATA = 7  # Generate 7 days of data
INTERVAL_MINUTES = 5  # Data point every 5 minutes

# Realistic temperature and humidity ranges (indoor station)
BASE_TEMP = 21.0  # Base temperature in °C
TEMP_VARIATION = 3.0  # Daily variation
TEMP_NOISE = 0.5  # Random noise

BASE_HUMIDITY = 50.0  # Base humidity in %
HUMIDITY_VARIATION = 15.0  # Daily variation
HUMIDITY_NOISE = 2.0  # Random noise

BASE_LIGHT = 30000  # Base light value (16-bit ADC)
LIGHT_VARIATION = 50000  # Day/night variation
LIGHT_NOISE = 2000  # Random noise

def generate_realistic_data():
    """Generate realistic temperature, humidity, and light patterns"""
    data_points = []
    
    end_time = datetime.now(timezone)
    start_time = end_time - timedelta(days=DAYS_OF_DATA)
    
    current_time = start_time
    
    print(f"Generating data from {start_time} to {end_time}")
    print(f"Interval: {INTERVAL_MINUTES} minutes")
    
    while current_time <= end_time:
        # Time of day factor (cooler at night, warmer during day)
        hour = current_time.hour
        time_factor = (hour - 6) / 12  # Peak at ~18:00
        if time_factor < 0:
            time_factor = 0
        elif time_factor > 1:
            time_factor = 1
        
        # Generate temperature with daily pattern
        temp = (BASE_TEMP + 
                (time_factor * TEMP_VARIATION) + 
                random.uniform(-TEMP_NOISE, TEMP_NOISE))
        
        # Generate humidity (inverse relationship with temperature)
        humidity = (BASE_HUMIDITY - 
                   (time_factor * HUMIDITY_VARIATION / 2) + 
                   random.uniform(-HUMIDITY_NOISE, HUMIDITY_NOISE))
        
        # Generate light (peaks during day, very low at night)
        # Create a smoother day/night cycle
        if 6 <= hour <= 20:  # Daytime
            day_factor = 1 - abs(hour - 13) / 7  # Peak at 13:00
            light = (BASE_LIGHT + 
                    (day_factor * LIGHT_VARIATION) + 
                    random.uniform(-LIGHT_NOISE, LIGHT_NOISE))
        else:  # Nighttime
            light = random.uniform(0, 5000)  # Very low light at night
        
        # Keep within realistic bounds
        temp = max(15.0, min(30.0, temp))
        humidity = max(20.0, min(80.0, humidity))
        light = max(0, min(65535, light))  # 16-bit ADC range
        
        data_points.append({
            'timestamp': current_time,
            'temperature': round(temp, 2),
            'humidity': round(humidity, 2),
            'light': round(light, 0)
        })
        
        current_time += timedelta(minutes=INTERVAL_MINUTES)
    
    return data_points

def populate_database():
    """Populate database with test data"""
    with app.app_context():
        # Check if database already has data
        existing_count = SensorData.query.count()
        
        if existing_count > 0:
            print(f"\nDatabase already has {existing_count} entries.")
            response = input("Do you want to delete existing data? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                db.session.query(SensorData).delete()
                db.session.commit()
                print("Existing data deleted.")
            else:
                print("Keeping existing data and adding new data.")
        
        # Generate and insert data
        print("\nGenerating test data...")
        data_points = generate_realistic_data()
        
        print(f"Inserting {len(data_points)} data points...")
        
        for i, point in enumerate(data_points):
            entry = SensorData(
                timestamp=point['timestamp'],
                temperature=point['temperature'],
                humidity=point['humidity'],
                light=point['light']
            )
            db.session.add(entry)
            
            # Commit in batches of 100 for efficiency
            if (i + 1) % 100 == 0:
                db.session.commit()
                print(f"  Inserted {i + 1}/{len(data_points)} entries...")
        
        # Commit remaining entries
        db.session.commit()
        
        print(f"\n✅ Successfully inserted {len(data_points)} data points!")
        
        # Show summary
        total = SensorData.query.count()
        first = SensorData.query.order_by(SensorData.timestamp.asc()).first()
        last = SensorData.query.order_by(SensorData.timestamp.desc()).first()
        
        print(f"\nDatabase Summary:")
        print(f"  Total entries: {total}")
        print(f"  First entry: {first.timestamp}")
        print(f"  Last entry: {last.timestamp}")
        print(f"  Temperature range: {first.temperature}°C - {last.temperature}°C")
        print(f"  Humidity range: {first.humidity}% - {last.humidity}%")
        print(f"  Light range: {first.light} - {last.light}")

if __name__ == "__main__":
    print("=" * 60)
    print("Sensor Database Test Data Generator")
    print("=" * 60)
    populate_database()
    print("\nYou can now run the Streamlit dashboard to view the data!")
