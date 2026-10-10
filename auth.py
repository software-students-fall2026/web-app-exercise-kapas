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
            # only allow redirects to paths on this site
            if not next_page or not next_page.startswith('/') or next_page.startswith('//'):
                next_page = url_for('home')
            return redirect(next_page)
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

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handle user registration
    GET: Display registration page
    POST: Process registration form
    """
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not username or not email or not password:
        flash('Please fill in all fields', 'error')
        return render_template('register.html')

    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return render_template('register.html')

    if User.find_by_username(username):
        flash('Username already exists', 'error')
        return render_template('register.html')

    if User.find_by_email(email):
        flash('Email already exists', 'error')
        return render_template('register.html')

    user = User(username=username, email=email)
    user.set_password(password)
    user.save()

    login_user(user)
    flash('Account created!', 'success')
    return redirect(url_for('home'))

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
