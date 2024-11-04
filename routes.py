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
    rides = Ride.query.filter_by(rider_id=current_user.id).order_by(Ride.created_at.desc()).all()
    return render_template('rider/dashboard.html', rides=rides)

@main_bp.route('/driver/dashboard')
@login_required
def driver_dashboard():
    if current_user.user_type != 'driver':
        return redirect(url_for('main.index'))
    # Get driver's own rides
    my_rides = Ride.query.filter_by(driver_id=current_user.id).order_by(Ride.created_at.desc()).all()
    # Get all pending rides that haven't been assigned to a driver
    pending_rides = Ride.query.filter_by(driver_id=None, status='pending').order_by(Ride.created_at.desc()).all()
    return render_template('driver/dashboard.html', my_rides=my_rides, pending_rides=pending_rides)

@main_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.user_type != 'admin':
        return redirect(url_for('main.index'))
    users = User.query.all()
    rides = Ride.query.order_by(Ride.created_at.desc()).all()
    cars = Car.query.all()
    contracts = Contract.query.all()
    return render_template('admin/dashboard.html', 
                         users=users, 
                         rides=rides,
                         cars=cars,
                         contracts=contracts)

@main_bp.route('/book-ride', methods=['GET', 'POST'])
@login_required
def book_ride():
    if current_user.user_type != 'rider':
        return redirect(url_for('main.index'))
    
    # Get user's active contract
    contract = Contract.query.filter_by(user_id=current_user.id).first()
    if not contract:
        flash('No active contract found. Please contact administrator.')
        return redirect(url_for('main.rider_dashboard'))
    
    if request.method == 'POST':
        try:
            pickup_datetime_str = request.form.get('pickup_datetime')
            if not pickup_datetime_str:
                raise ValueError("Pickup datetime is required")
                
            pickup_datetime = datetime.strptime(pickup_datetime_str, '%Y-%m-%dT%H:%M')
            
            # Check if pickup time is within contract hours
            pickup_time = pickup_datetime.time()
            if pickup_time < contract.daily_start_time or pickup_time > contract.daily_end_time:
                flash('Pickup time must be within contracted hours')
                return redirect(url_for('main.book_ride'))
            
            # Check if pickup day is a working day
            working_days = [int(d) for d in contract.working_days.split(',')]
            if pickup_datetime.weekday() + 1 not in working_days:
                flash('Rides can only be booked on contracted working days')
                return redirect(url_for('main.book_ride'))
            
            # Calculate this month's total distance
            month_start = datetime(pickup_datetime.year, pickup_datetime.month, 1)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            month_distance = db.session.query(func.sum(Ride.distance)).filter(
                Ride.contract_id == contract.id,
                Ride.created_at.between(month_start, month_end)
            ).scalar() or 0
            
            # Check if new ride would exceed monthly limit
            new_distance = float(request.form.get('distance') or 0)
            if month_distance + new_distance > contract.monthly_km_limit:
                flash('This ride would exceed your monthly kilometer limit')
                return redirect(url_for('main.book_ride'))
            
            # Create ride with contract and car
            ride = Ride(
                rider_id=current_user.id,
                car_id=contract.car_id,
                contract_id=contract.id,
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
    
    return render_template('book_ride.html', now=datetime.now(), contract=contract)

@main_bp.route('/ride/<int:ride_id>/cancel', methods=['POST'])
@login_required
def cancel_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    if ride.rider_id != current_user.id:
        flash('Unauthorized action')
        return redirect(url_for('main.rider_dashboard'))
    
    if ride.status == 'pending':
        ride.status = 'cancelled'
        db.session.commit()
        flash('Ride cancelled successfully')
    else:
        flash('Cannot cancel ride in current status')
    return redirect(url_for('main.rider_dashboard'))

@main_bp.route('/ride/<int:ride_id>/accept', methods=['POST'])
@login_required
def accept_ride(ride_id):
    if current_user.user_type != 'driver':
        return jsonify({'error': 'Unauthorized'}), 403
        
    ride = Ride.query.get_or_404(ride_id)
    if ride.status != 'pending':
        return jsonify({'error': 'Ride already accepted'}), 400
        
    ride.driver_id = current_user.id
    ride.status = 'accepted'
    db.session.commit()
    
    return jsonify({'message': 'Ride accepted successfully'})

@main_bp.route('/ride/<int:ride_id>/start', methods=['POST'])
@login_required
def start_ride(ride_id):
    if current_user.user_type != 'driver':
        return jsonify({'error': 'Unauthorized'}), 403
        
    ride = Ride.query.get_or_404(ride_id)
    if ride.driver_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if ride.status != 'accepted':
        return jsonify({'error': 'Cannot start ride in current status'}), 400
        
    ride.status = 'in_progress'
    db.session.commit()
    
    return jsonify({'message': 'Ride started successfully'})

@main_bp.route('/ride/<int:ride_id>/complete', methods=['POST'])
@login_required
def complete_ride(ride_id):
    if current_user.user_type != 'driver':
        return jsonify({'error': 'Unauthorized'}), 403
        
    ride = Ride.query.get_or_404(ride_id)
    if ride.driver_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if ride.status != 'in_progress':
        return jsonify({'error': 'Cannot complete ride in current status'}), 400
        
    ride.status = 'completed'
    db.session.commit()
    
    return jsonify({'message': 'Ride completed successfully'})

@main_bp.route('/admin/car/add', methods=['POST'])
@login_required
def add_car():
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    model = request.form.get('model')
    license_plate = request.form.get('license_plate')
    
    car = Car(model=model, license_plate=license_plate)
    db.session.add(car)
    db.session.commit()
    
    flash('Car added successfully')
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/car/<int:car_id>/toggle', methods=['POST'])
@login_required
def toggle_car(car_id):
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    car = Car.query.get_or_404(car_id)
    car.is_active = not car.is_active
    db.session.commit()
    
    return jsonify({'message': 'Car status updated successfully'})

@main_bp.route('/admin/contract/add', methods=['POST'])
@login_required
def add_contract():
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        user_id = request.form.get('user_id')
        car_id = request.form.get('car_id')
        monthly_km_limit = float(request.form.get('monthly_km_limit'))
        working_days = ','.join(request.form.getlist('working_days'))
        daily_start_time = datetime.strptime(request.form.get('daily_start_time'), '%H:%M').time()
        daily_end_time = datetime.strptime(request.form.get('daily_end_time'), '%H:%M').time()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
        
        contract = Contract(
            user_id=user_id,
            car_id=car_id,
            monthly_km_limit=monthly_km_limit,
            working_days=working_days,
            daily_start_time=daily_start_time,
            daily_end_time=daily_end_time,
            start_date=datetime.now(),
            end_date=end_date
        )
        
        db.session.add(contract)
        db.session.commit()
        
        flash('Contract added successfully')
    except Exception as e:
        flash(f'Error adding contract: {str(e)}')
    
    return redirect(url_for('main.admin_dashboard'))
