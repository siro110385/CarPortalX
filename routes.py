from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, Ride, RideStop, Car, Contract
from sqlalchemy import func
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
    
    # Get user's active contracts
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
            
            # Find available cars from user's contracts
            available_cars = []
            overtime_contracts = []
            
            for contract in contracts:
                # Check if car is already booked
                existing_bookings = Ride.query.filter(
                    Ride.car_id == contract.car_id,
                    Ride.status.in_(['pending', 'accepted', 'in_progress']),
                    Ride.pickup_datetime <= pickup_datetime + timedelta(hours=2),  # Buffer time
                    Ride.pickup_datetime >= pickup_datetime - timedelta(hours=2)
                ).first()
                
                if existing_bookings:
                    continue  # Car is already booked
                
                # Check if pickup time is within contract hours
                pickup_time = pickup_datetime.time()
                working_days = [int(d) for d in contract.working_days.split(',')]
                is_working_day = pickup_datetime.weekday() + 1 in working_days
                is_working_hours = (contract.daily_start_time <= pickup_time <= contract.daily_end_time)
                
                if is_working_day and is_working_hours:
                    available_cars.append((contract, False))  # (contract, is_overtime)
                elif is_working_day:  # Outside working hours but on working day
                    overtime_contracts.append((contract, True))
            
            # Combine regular and overtime options
            available_options = available_cars + overtime_contracts
            
            if not available_options:
                flash('No cars available at the selected time.')
                return redirect(url_for('main.book_ride'))
            
            # Use the first available contract (prefer non-overtime)
            selected_contract, is_overtime = available_options[0]
            
            # Check for overtime confirmation if needed
            if is_overtime and not request.form.get('confirmed_overtime'):
                return jsonify({
                    'needsConfirmation': True,
                    'message': 'This booking is outside contract hours. Overtime charges will apply. Do you want to continue?',
                    'contract_id': selected_contract.id
                })
            
            # Create ride
            ride = Ride(
                rider_id=current_user.id,
                car_id=selected_contract.car_id,
                contract_id=selected_contract.id,
                pickup_datetime=pickup_datetime,
                pickup_lat=float(request.form.get('pickup_lat')),
                pickup_lng=float(request.form.get('pickup_lng')),
                dropoff_lat=float(request.form.get('dropoff_lat')),
                dropoff_lng=float(request.form.get('dropoff_lng')),
                distance=float(request.form.get('distance')),
                fare=float(request.form.get('distance')) * 2 + 5,  # $2 per km + $5 base fare
                route_data=request.form.get('route_data'),
                status='pending'
            )
            
            db.session.add(ride)
            db.session.flush()
            
            # Add pickup stop
            pickup_stop = RideStop(
                ride_id=ride.id,
                sequence=0,
                lat=float(request.form.get('pickup_lat')),
                lng=float(request.form.get('pickup_lng')),
                address=request.form.get('pickup'),
                stop_type='pickup'
            )
            db.session.add(pickup_stop)
            
            # Add intermediate stops
            stop_lats = request.form.getlist('stop_lat[]')
            stop_lngs = request.form.getlist('stop_lng[]')
            stop_addresses = request.form.getlist('stop_address[]')
            
            for i, (lat, lng, addr) in enumerate(zip(stop_lats, stop_lngs, stop_addresses), 1):
                if lat and lng:
                    stop = RideStop(
                        ride_id=ride.id,
                        sequence=i,
                        lat=float(lat),
                        lng=float(lng),
                        address=addr,
                        stop_type='stop'
                    )
                    db.session.add(stop)
            
            # Add dropoff stop
            dropoff_stop = RideStop(
                ride_id=ride.id,
                sequence=len(stop_lats) + 1,
                lat=float(request.form.get('dropoff_lat')),
                lng=float(request.form.get('dropoff_lng')),
                address=request.form.get('dropoff'),
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
    
    return render_template('book_ride.html', 
                         now=datetime.now(), 
                         contracts=contracts)

@main_bp.route('/ride/<int:ride_id>/cancel', methods=['POST'])
@login_required
def cancel_ride(ride_id):
    if current_user.user_type != 'rider':
        return redirect(url_for('main.index'))
    
    ride = Ride.query.get_or_404(ride_id)
    if ride.rider_id != current_user.id:
        flash('Unauthorized action.')
        return redirect(url_for('main.rider_dashboard'))
    
    if ride.status != 'pending':
        flash('Cannot cancel ride that is not pending.')
        return redirect(url_for('main.rider_dashboard'))
    
    ride.status = 'cancelled'
    db.session.commit()
    flash('Ride cancelled successfully.')
    return redirect(url_for('main.rider_dashboard'))

@main_bp.route('/ride/<int:ride_id>/edit', methods=['GET'])
@login_required
def edit_ride(ride_id):
    if current_user.user_type != 'rider':
        return redirect(url_for('main.index'))
        
    ride = Ride.query.get_or_404(ride_id)
    if ride.rider_id != current_user.id:
        flash('Unauthorized action.')
        return redirect(url_for('main.rider_dashboard'))
        
    if ride.status != 'pending':
        flash('Cannot edit ride that is not pending.')
        return redirect(url_for('main.rider_dashboard'))
        
    return render_template('edit_ride.html', 
                         ride=ride,
                         now=datetime.now(),
                         contracts=Contract.query.filter_by(user_id=current_user.id).all())
