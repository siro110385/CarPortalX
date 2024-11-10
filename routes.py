from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, Ride, RideStop, Car, Contract, Passenger
from sqlalchemy import func, extract, and_, or_
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/rider/dashboard')
@login_required
def rider_dashboard():
    if current_user.user_type != 'rider':
        return redirect(url_for('main.index'))
    
    rides = Ride.query.filter_by(rider_id=current_user.id).order_by(Ride.created_at.desc()).all()
    contracts = Contract.query.filter_by(user_id=current_user.id).all()
    
    monthly_usage = {}
    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    
    for contract in contracts:
        usage = db.session.query(func.sum(Ride.distance)).filter(
            Ride.contract_id == contract.id,
            Ride.status == 'completed',
            Ride.created_at >= current_month,
            Ride.created_at < next_month
        ).scalar() or 0
        monthly_usage[contract.id] = usage
    
    return render_template('rider/dashboard.html', 
                         rides=rides, 
                         contracts=contracts,
                         monthly_usage=monthly_usage)

@main_bp.route('/book-ride', methods=['GET', 'POST'])
@login_required
def book_ride():
    if current_user.user_type != 'rider':
        return redirect(url_for('main.index'))
    
    # Get user's contracts
    contracts = Contract.query.filter_by(user_id=current_user.id).all()
    if not contracts:
        flash('No active contracts found. Please contact administrator.')
        return redirect(url_for('main.rider_dashboard'))
    
    if request.method == 'POST':
        try:
            pickup_datetime_str = request.form.get('pickup_datetime')
            if not pickup_datetime_str:
                raise ValueError("Pickup datetime is required")
            
            pickup_datetime = datetime.strptime(pickup_datetime_str, '%Y-%m-%dT%H:%M')
            
            contract_id = request.form.get('contract_id')
            if not contract_id:
                raise ValueError("Please select a car")
            
            contract = Contract.query.get(contract_id)
            if not contract or contract.user_id != current_user.id:
                raise ValueError("Invalid contract selected")
            
            ride = Ride(
                rider_id=current_user.id,
                car_id=contract.car_id,
                contract_id=contract.id,
                pickup_datetime=pickup_datetime,
                pickup_lat=float(request.form.get('pickup_lat')),
                pickup_lng=float(request.form.get('pickup_lng')),
                dropoff_lat=float(request.form.get('dropoff_lat')),
                dropoff_lng=float(request.form.get('dropoff_lng')),
                distance=float(request.form.get('distance')),
                fare=float(request.form.get('distance')) * 2 + 5,
                route_data=request.form.get('route_data'),
                pickup_address=request.form.get('pickup'),
                dropoff_address=request.form.get('dropoff'),
                status='pending'
            )
            
            db.session.add(ride)
            db.session.flush()
            
            # Add passengers
            passenger_names = request.form.getlist('passenger_name[]')
            passenger_emails = request.form.getlist('passenger_email[]')
            passenger_phones = request.form.getlist('passenger_phone[]')
            
            for name, email, phone in zip(passenger_names, passenger_emails, passenger_phones):
                passenger = Passenger(
                    ride_id=ride.id,
                    name=name,
                    email=email,
                    phone=phone
                )
                db.session.add(passenger)
            
            db.session.commit()
            flash('Ride booked successfully!')
            return redirect(url_for('main.rider_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking ride: {str(e)}')
            return redirect(url_for('main.book_ride'))
    
    # For GET request, check availability of all cars
    pickup_datetime = request.args.get('pickup_datetime')
    if pickup_datetime:
        pickup_datetime = datetime.strptime(pickup_datetime, '%Y-%m-%dT%H:%M')
    else:
        pickup_datetime = datetime.now()

    available_cars = []
    
    for contract in contracts:
        # Calculate monthly usage from completed rides only
        monthly_usage = db.session.query(func.sum(Ride.distance)).filter(
            Ride.contract_id == contract.id,
            Ride.status == 'completed',
            extract('year', Ride.created_at) == pickup_datetime.year,
            extract('month', Ride.created_at) == pickup_datetime.month
        ).scalar() or 0

        # Check for overlapping bookings
        existing_bookings = Ride.query.filter(
            Ride.car_id == contract.car_id,
            Ride.status.in_(['pending', 'accepted', 'in_progress']),
            or_(
                # New booking starts during existing booking
                and_(
                    Ride.pickup_datetime <= pickup_datetime,
                    Ride.pickup_datetime + timedelta(hours=2) >= pickup_datetime
                ),
                # New booking ends during existing booking
                and_(
                    Ride.pickup_datetime <= pickup_datetime + timedelta(hours=2),
                    Ride.pickup_datetime + timedelta(hours=2) >= pickup_datetime + timedelta(hours=2)
                )
            )
        ).first()

        # Check timing
        pickup_time = pickup_datetime.time()
        working_days = [int(d) for d in contract.working_days.split(',')]
        is_working_day = pickup_datetime.weekday() + 1 in working_days
        is_working_hours = contract.daily_start_time <= pickup_time <= contract.daily_end_time

        car_status = {
            'monthly_usage': monthly_usage,
            'available': True,
            'selectable': not bool(existing_bookings),
            'warning': None,
            'overtime': False
        }

        if existing_bookings:
            car_status['warning'] = 'Car is already booked for this time'
        elif monthly_usage >= contract.monthly_km_limit:
            car_status['warning'] = f'Monthly limit exceeded ({monthly_usage:.1f}/{contract.monthly_km_limit} km)'
        elif not is_working_day:
            car_status['warning'] = 'Not a working day for this contract'
            car_status['overtime'] = True
        elif not is_working_hours:
            car_status['warning'] = 'Outside contract hours - Overtime charges apply'
            car_status['overtime'] = True

        available_cars.append((contract, car_status))

    return render_template('book_ride.html',
                         datetime=datetime,
                         now=datetime.now(),
                         contracts=contracts,
                         available_cars=available_cars)