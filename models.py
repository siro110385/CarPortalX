from datetime import datetime, time, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    user_type = db.Column(db.String(20), nullable=False)  # 'rider', 'driver', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Driver specific fields
    is_active = db.Column(db.Boolean, default=True)
    current_location_lat = db.Column(db.Float)
    current_location_lng = db.Column(db.Float)
    vehicle_type = db.Column(db.String(50))
    license_plate = db.Column(db.String(20))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Add new association table
contract_cars = db.Table('contract_cars',
    db.Column('contract_id', db.Integer, db.ForeignKey('contract.id'), primary_key=True),
    db.Column('car_id', db.Integer, db.ForeignKey('car.id'), primary_key=True)
)

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    monthly_km_limit = db.Column(db.Float, nullable=False)  # Monthly kilometer budget
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    daily_start_time = db.Column(db.Time, nullable=False)  # Available from time
    daily_end_time = db.Column(db.Time, nullable=False)    # Available until time
    working_days = db.Column(db.String(50), nullable=False)  # e.g., "1,2,3,4,5" for Mon-Fri
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add relationships
    user = db.relationship('User', backref='contracts')
    cars = db.relationship('Car', secondary='contract_cars', backref='contracts')

class Passenger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ride = db.relationship('Ride', backref='passengers')
    
class Ride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    pickup_lat = db.Column(db.Float, nullable=False)
    pickup_lng = db.Column(db.Float, nullable=False)
    dropoff_lat = db.Column(db.Float, nullable=False)
    dropoff_lng = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pickup_datetime = db.Column(db.DateTime, nullable=False)
    distance = db.Column(db.Float)  # in kilometers
    fare = db.Column(db.Float)
    route_data = db.Column(db.JSON)  # Store route coordinates
    pickup_address = db.Column(db.String(256))  # Added for email notifications
    dropoff_address = db.Column(db.String(256))  # Added for email notifications
    
    # Add relationships
    rider = db.relationship('User', foreign_keys=[rider_id], backref='rides_as_rider')
    driver = db.relationship('User', foreign_keys=[driver_id], backref='rides_as_driver')
    car = db.relationship('Car', backref='rides')
    contract = db.relationship('Contract', backref='rides')
    stops = db.relationship('RideStop', backref='ride', order_by='RideStop.sequence')

class RideStop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)  # Order of stops
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(256))
    stop_type = db.Column(db.String(20))  # 'pickup', 'stop', 'dropoff'
