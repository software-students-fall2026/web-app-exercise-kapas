from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login
    GET: Display login page
    POST: Process login form
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password', 'error')
            return render_template('login.html')

        user = User.find_by_username(username)

        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            return render_template('login.html')

    return render_template('login.html')

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    Handle user logout
    """
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('home'))

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Handle user registration (API endpoint only, no template)
    Expects JSON: {"username": "...", "email": "...", "password": "..."}
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "Missing required fields: username, email, password"}), 400

    # Check if user already exists
    if User.find_by_username(username):
        return jsonify({"error": "Username already exists"}), 400

    if User.find_by_email(email):
        return jsonify({"error": "Email already exists"}), 400

    # Create new user
    user = User(username=username, email=email)
    user.set_password(password)
    user.save()

    return jsonify({
        "message": "User created successfully",
        "user": {
            "id": str(user._id),
            "username": user.username,
            "email": user.email
        }
    }), 201

@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """
    Get current authenticated user info
    """
    return jsonify({
        "user": {
            "id": str(current_user._id),
            "username": current_user.username,
            "email": current_user.email
        }
    }), 200
