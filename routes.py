from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, Ride, RideStop, Car, Contract
from sqlalchemy import func
import requests
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
    
    # Get all user's rides
    rides = Ride.query.filter_by(rider_id=current_user.id).order_by(Ride.created_at.desc()).all()
    
    # Get all user's contracts
    contracts = Contract.query.filter_by(user_id=current_user.id).all()
    
    # Calculate monthly usage for each contract
    monthly_usage = {}
    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    
    for contract in contracts:
        usage = db.session.query(func.sum(Ride.distance)).filter(
            Ride.contract_id == contract.id,
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
    
    # Get all user's active contracts
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
            
            # Find a suitable contract for this ride
            valid_contract = None
            for contract in contracts:
                # Check if pickup time is within contract hours
                pickup_time = pickup_datetime.time()
                if pickup_time < contract.daily_start_time or pickup_time > contract.daily_end_time:
                    continue
                
                # Check if pickup day is a working day
                working_days = [int(d) for d in contract.working_days.split(',')]
                if pickup_datetime.weekday() + 1 not in working_days:
                    continue
                
                # Calculate this month's total distance
                month_start = datetime(pickup_datetime.year, pickup_datetime.month, 1)
                month_end = (month_start + timedelta(days=32)).replace(day=1)
                month_distance = db.session.query(func.sum(Ride.distance)).filter(
                    Ride.contract_id == contract.id,
                    Ride.created_at.between(month_start, month_end)
                ).scalar() or 0
                
                # Check if new ride would exceed monthly limit
                new_distance = float(request.form.get('distance') or 0)
                if month_distance + new_distance <= contract.monthly_km_limit:
                    valid_contract = contract
                    break
            
            if not valid_contract:
                flash('No suitable contract found for this ride (check working hours, days, and monthly limits)')
                return redirect(url_for('main.book_ride'))
            
            # Create ride with the valid contract
            ride = Ride(
                rider_id=current_user.id,
                car_id=valid_contract.car_id,
                contract_id=valid_contract.id,
                pickup_lat=float(request.form.get('pickup_lat')),
                pickup_lng=float(request.form.get('pickup_lng')),
                dropoff_lat=float(request.form.get('dropoff_lat')),
                dropoff_lng=float(request.form.get('dropoff_lng')),
                distance=new_distance,
                fare=(new_distance * 2) + 5,  # $2 per km + $5 base fare
                route_data=request.form.get('route_data'),
                pickup_datetime=pickup_datetime,
                status='pending'
            )
            
            db.session.add(ride)
            db.session.flush()  # Get ride.id without committing
            
            # Add pickup stop
            pickup_stop = RideStop(
                ride_id=ride.id,
                sequence=0,
                lat=float(request.form.get('pickup_lat')),
                lng=float(request.form.get('pickup_lng')),
                stop_type='pickup'
            )
            db.session.add(pickup_stop)
            
            # Add intermediate stops
            stop_lats = request.form.getlist('stop_lat[]')
            stop_lngs = request.form.getlist('stop_lng[]')
            stop_addresses = request.form.getlist('stop_address[]')
            
            for i, (lat, lng, address) in enumerate(zip(stop_lats, stop_lngs, stop_addresses), 1):
                if lat and lng:  # Only add if coordinates are present
                    stop = RideStop(
                        ride_id=ride.id,
                        sequence=i,
                        lat=float(lat),
                        lng=float(lng),
                        address=address,
                        stop_type='stop'
                    )
                    db.session.add(stop)
            
            # Add dropoff stop
            dropoff_stop = RideStop(
                ride_id=ride.id,
                sequence=len(stop_lats) + 1,
                lat=float(request.form.get('dropoff_lat')),
                lng=float(request.form.get('dropoff_lng')),
                stop_type='dropoff'
            )
            db.session.add(dropoff_stop)
            
            db.session.commit()
            flash('Ride booked successfully!')
            return redirect(url_for('main.rider_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking ride: {str(e)}')
            return redirect(url_for('main.book_ride'))
    
    return render_template('book_ride.html', now=datetime.now(), contracts=contracts)

# ... rest of the routes.py file remains the same ...
