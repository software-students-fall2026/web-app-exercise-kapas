from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os
from auth import auth_bp
from db import ensure_indexes
from models import User

load_dotenv()

from profiles import profiles_bp
from albums import albums_bp

app = Flask(__name__)
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    raise RuntimeError('SECRET_KEY is not set. Add it to your .env file (see env.example).')
app.config['SECRET_KEY'] = secret_key

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for flask-login"""
    return User.find_by_id(user_id)


try: # creates the indexes so uniqueness can be checked
    ensure_indexes()
except Exception as e: # could not create indexes
    print(f"Error: could not create database indexes: {e}")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profiles_bp)
app.register_blueprint(albums_bp)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)