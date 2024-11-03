from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, Ride
import requests

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
    return render_template('admin/dashboard.html', users=users, rides=rides)

@main_bp.route('/book-ride', methods=['GET', 'POST'])
@login_required
def book_ride():
    if current_user.user_type != 'rider':
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        pickup_lat = float(request.form.get('pickup_lat'))
        pickup_lng = float(request.form.get('pickup_lng'))
        dropoff_lat = float(request.form.get('dropoff_lat'))
        dropoff_lng = float(request.form.get('dropoff_lng'))
        distance = float(request.form.get('distance', 0))
        route_data = request.form.get('route_data')
        
        # Calculate fare (example: $2 per km + base fare of $5)
        fare = (distance * 2) + 5
        
        ride = Ride(
            rider_id=current_user.id,
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            dropoff_lat=dropoff_lat,
            dropoff_lng=dropoff_lng,
            distance=distance,
            fare=fare,
            route_data=route_data
        )
        
        db.session.add(ride)
        db.session.commit()
        
        flash('Ride booked successfully!')
        return redirect(url_for('main.rider_dashboard'))
        
    return render_template('book_ride.html')

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

@main_bp.route('/ride/<int:ride_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    if ride.rider_id != current_user.id:
        flash('Unauthorized action')
        return redirect(url_for('main.rider_dashboard'))
    
    if request.method == 'POST':
        if ride.status != 'pending':
            flash('Cannot edit ride in current status')
            return redirect(url_for('main.rider_dashboard'))
            
        ride.pickup_lat = float(request.form.get('pickup_lat'))
        ride.pickup_lng = float(request.form.get('pickup_lng'))
        ride.dropoff_lat = float(request.form.get('dropoff_lat'))
        ride.dropoff_lng = float(request.form.get('dropoff_lng'))
        ride.distance = float(request.form.get('distance', 0))
        ride.route_data = request.form.get('route_data')
        ride.fare = (float(request.form.get('distance', 0)) * 2) + 5
        
        db.session.commit()
        flash('Ride updated successfully')
        return redirect(url_for('main.rider_dashboard'))
        
    return render_template('edit_ride.html', ride=ride)

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
