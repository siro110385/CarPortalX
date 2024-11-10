from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, Ride, RideStop, Car, Contract
from sqlalchemy import func, extract, and_, or_
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

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

@main_bp.route('/admin/car/add', methods=['POST'])
@login_required
def add_car():
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        model = request.form.get('model')
        license_plate = request.form.get('license_plate')
        
        if not model or not license_plate:
            raise ValueError("Model and license plate are required")
        
        car = Car()
        car.model = model
        car.license_plate = license_plate
        
        db.session.add(car)
        db.session.commit()
        flash('Car added successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding car: {str(e)}')
    
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/car/<int:car_id>/edit', methods=['POST'])
@login_required
def edit_car(car_id):
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        car = Car.query.get_or_404(car_id)
        model = request.form.get('model')
        license_plate = request.form.get('license_plate')
        
        if not model or not license_plate:
            raise ValueError("Model and license plate are required")
            
        car.model = model
        car.license_plate = license_plate
        db.session.commit()
        flash('Car updated successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating car: {str(e)}')
    
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/contract/add', methods=['POST'])
@login_required
def add_contract():
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        user_id = request.form.get('user_id')
        car_ids = request.form.getlist('car_ids[]')
        monthly_km_limit_str = request.form.get('monthly_km_limit')
        working_days = request.form.getlist('working_days')
        daily_start_time_str = request.form.get('daily_start_time')
        daily_end_time_str = request.form.get('daily_end_time')
        end_date_str = request.form.get('end_date')
        
        if not all([user_id, car_ids, monthly_km_limit_str, working_days, 
                   daily_start_time_str, daily_end_time_str, end_date_str]):
            raise ValueError("All fields are required")
        
        monthly_km_limit = float(monthly_km_limit_str)
        daily_start_time = datetime.strptime(daily_start_time_str, '%H:%M').time()
        daily_end_time = datetime.strptime(daily_end_time_str, '%H:%M').time()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        contract = Contract()
        contract.user_id = int(user_id)
        contract.monthly_km_limit = monthly_km_limit
        contract.working_days = ','.join(working_days)
        contract.daily_start_time = daily_start_time
        contract.daily_end_time = daily_end_time
        contract.start_date = datetime.now()
        contract.end_date = end_date
        
        # Add selected cars
        for car_id in car_ids:
            car = Car.query.get(car_id)
            if car:
                contract.cars.append(car)
        
        db.session.add(contract)
        db.session.commit()
        flash('Contract added successfully')
    except ValueError as e:
        flash(f'Validation error: {str(e)}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding contract: {str(e)}')
    
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/contract/<int:contract_id>/edit', methods=['POST'])
@login_required
def edit_contract(contract_id):
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        contract = Contract.query.get_or_404(contract_id)
        monthly_km_limit_str = request.form.get('monthly_km_limit')
        working_days = request.form.getlist('working_days')
        daily_start_time_str = request.form.get('daily_start_time')
        daily_end_time_str = request.form.get('daily_end_time')
        end_date_str = request.form.get('end_date')
        car_ids = request.form.getlist('car_ids[]')
        
        if not all([monthly_km_limit_str, working_days, daily_start_time_str, 
                   daily_end_time_str, end_date_str, car_ids]):
            raise ValueError("All fields are required")
        
        contract.monthly_km_limit = float(monthly_km_limit_str)
        contract.working_days = ','.join(working_days)
        contract.daily_start_time = datetime.strptime(daily_start_time_str, '%H:%M').time()
        contract.daily_end_time = datetime.strptime(daily_end_time_str, '%H:%M').time()
        contract.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Update cars
        contract.cars = []
        for car_id in car_ids:
            car = Car.query.get(car_id)
            if car:
                contract.cars.append(car)
        
        db.session.commit()
        flash('Contract updated successfully')
    except ValueError as e:
        flash(f'Validation error: {str(e)}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating contract: {str(e)}')
    
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        user.is_active = not user.is_active
        db.session.commit()
        return jsonify({'message': 'User status updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main_bp.route('/admin/car/<int:car_id>/toggle', methods=['POST']) 
@login_required
def toggle_car(car_id):
    if current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        car = Car.query.get_or_404(car_id)
        car.is_active = not car.is_active
        db.session.commit()
        return jsonify({'message': 'Car status updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
