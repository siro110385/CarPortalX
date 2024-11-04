from app import app
from extensions import db
from models import User, Car, Contract
from datetime import datetime, time, timedelta

def create_sample_data():
    # Create cars
    car1 = Car(model='Toyota Camry', license_plate='ABC123')
    car2 = Car(model='Honda Civic', license_plate='XYZ789')
    db.session.add_all([car1, car2])
    db.session.commit()
    
    # Create contract for specific user
    user = User.query.filter_by(email='siro110385@gmail.com').first()
    if user:
        contract = Contract(
            user_id=user.id,
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
    db.drop_all()
    db.create_all()
    create_sample_data()
    print("Database tables recreated successfully!")
