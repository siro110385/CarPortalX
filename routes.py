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
    rides = Ride.query.filter_by(driver_id=current_user.id).order_by(Ride.created_at.desc()).all()
    return render_template('driver/dashboard.html', rides=rides)

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
