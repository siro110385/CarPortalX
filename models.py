from datetime import datetime
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

class Ride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    pickup_lat = db.Column(db.Float, nullable=False)
    pickup_lng = db.Column(db.Float, nullable=False)
    dropoff_lat = db.Column(db.Float, nullable=False)
    dropoff_lng = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    distance = db.Column(db.Float)  # in kilometers
    fare = db.Column(db.Float)
    route_data = db.Column(db.JSON)  # Store route coordinates
    pickup_datetime = db.Column(db.DateTime, nullable=False)  # Added new field

    rider = db.relationship('User', foreign_keys=[rider_id], backref='rides_as_rider')
    driver = db.relationship('User', foreign_keys=[driver_id], backref='rides_as_driver')
