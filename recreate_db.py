from app import app
from extensions import db
from models import User, Car, Contract, Ride, RideStop
from datetime import datetime, time, timedelta

def create_sample_data():
    # Create admin user
    admin = User(
        email='admin@example.com',
        username='admin',
        user_type='admin'
    )
    admin.set_password('admin123')
    db.session.add(admin)
    
    # Create test rider
    rider = User(
        email='rider@example.com',
        username='testrider',
        user_type='rider'
    )
    rider.set_password('rider123')
    db.session.add(rider)
    
    # Create test driver
    driver = User(
        email='driver@example.com',
        username='testdriver',
        user_type='driver'
    )
    driver.set_password('driver123')
    db.session.add(driver)
    
    # Create cars
    car1 = Car(
        model='Toyota Camry',
        license_plate='ABC123'
    )
    car2 = Car(
        model='Honda Civic',
        license_plate='XYZ789'
    )
    db.session.add_all([car1, car2])
    db.session.commit()
    
    # Create contract for test driver
    contract = Contract(
        user_id=driver.id,
        car_id=car1.id,
        monthly_km_limit=1000.0,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=365),
        daily_start_time=time(8, 0),  # 8:00 AM
        daily_end_time=time(18, 0),   # 6:00 PM
        working_days='1,2,3,4,5'      # Monday to Friday
    )
    db.session.add(contract)
    db.session.commit()

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()
    create_sample_data()
    print("Database tables recreated successfully!")
