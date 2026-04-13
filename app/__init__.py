# ==========================================
# MODULE: THE APPLICATION FACTORY (HEART OF THE APP)
# ==========================================
# ENTERPRISE ARCHITECTURE NOTE:
# Instead of declaring a global 'app' variable (which causes scaling and testing issues),
# we wrap the application creation inside a function: create_app().
# This allows us to instantiate multiple versions of the app dynamically, 
# preventing circular imports and making the codebase infinitely scalable.

import os
from datetime import timedelta
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

# Import the uninitialized plugins from our isolated extensions file
from .extensions import db, csrf, login_manager, limiter
from .models import User, Product

def create_app():
    app = Flask(__name__)
    
    # ==========================================
    # LAYER 5 SECURITY: REVEAL TRUE CLIENT IP
    # ==========================================
    # Google Cloud Run sits behind a massive Load Balancer proxy. 
    # Without this middleware, Flask thinks every request comes from "127.0.0.1".
    # ProxyFix strips the proxy disguise so Flask-Limiter can see the attacker's real home IP.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # ==========================================
    # CRYPTOGRAPHIC KEYS & DATABASE ROUTING
    # ==========================================
    # SECRET_KEY signs the session cookies. Our deploy.sh script injects a randomized 
    # 256-bit hex string here dynamically, ensuring the key is never hardcoded in GitHub.
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secure-dev-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vending.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # ==========================================
    # LAYER 2 SECURITY: MILITARY-GRADE SESSION HYGIENE
    # ==========================================
    # 1. HttpOnly = True: Completely hides the cookie from JavaScript (XSS immune).
    # 2. Secure = True: Forces the cookie to ONLY be sent over encrypted HTTPS (MITM immune).
    # 3. SameSite = 'Strict': Prevents the browser from sending the cookie with cross-site requests (CSRF immune).
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    
    # THE TIME-BOMB: Destroys cloned/stolen cookies after 30 minutes of inactivity.
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
    
    # THE FAT PAYLOAD KILL-SWITCH:
    # If an attacker sends a JSON payload larger than 1 Megabyte to cause an Out-Of-Memory (OOM) 
    # crash, Flask instantly terminates the connection with a 413 Payload Too Large error.
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 

    # ==========================================
    # INITIALIZE EXTENSIONS
    # ==========================================
    # Bind the isolated plugins to this specific app instance
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = None # Suppress default ghost messages

    # ==========================================
    # HTTP CACHE CONTROL (The "Ghost Tab" Fix) & FRAME ARMOR
    # ==========================================
    @app.after_request
    def add_security_headers(response):
        """
        Forces the browser to NEVER cache authenticated pages.
        If a user logs out in Tab A, Tab B's cached HTML becomes instantly invalid.
        """
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        
        # ANTI-MIME-SNIFFING: Forces the browser to strictly follow declared content types.
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # ANTI-CLICKJACKING: Prevents hackers from embedding our app inside an invisible 
        # <iframe> on a malicious website to steal clicks.
        response.headers['X-Frame-Options'] = 'DENY'
        
        return response

    # ==========================================
    # DATABASE LEDGER LOCALIZATION (TIMEZONE SYNC)
    # ==========================================
    @app.template_filter('cst_time')
    def cst_time_filter(dt):
        """Converts UTC server time to El Salvador CST Timezone (UTC-6) for audit logs."""
        if not dt: return ""
        return (dt - timedelta(hours=6)).strftime('%Y-%m-%d %I:%M %p')

    # ==========================================
    # GRACEFUL RATE-LIMIT HANDLING
    # ==========================================
    # Catches the ugly 429 white page and formats it beautifully.
    @app.errorhandler(429)
    def ratelimit_handler(e):
        # If the attacker was hitting an /api/ route, return a JSON error
        if request.path.startswith('/api/'):
            return {"error": f"Rate limit exceeded. Step away from the keyboard. ({e.description})"}, 429
        # If they were spamming a web page (like /register), return formatted HTML
        return f"""
            <div style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #d9534f;">🚫 429 Too Many Requests</h1>
                <p>You have triggered the automated defense systems. {e.description}</p>
                <button onclick="window.history.back()" style="padding: 10px 20px; cursor: pointer;">Go Back</button>
            </div>
        """, 429

    # ==========================================
    # REGISTER BLUEPRINTS (The Modular Routing Engine)
    # ==========================================
    # We import these locally inside create_app() to prevent Circular Imports.
    from .auth import auth_bp
    from .main import main_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # ==========================================
    # DATABASE BOOTSTRAPPER (The Self-Healing Sandbox)
    # ==========================================
    with app.app_context():
        db.create_all()
        
        # If the Cloud Run container wakes up from sleep and the DB is empty, 
        # it magically restores the Root Admin and the default inventory.
        if not User.query.first():
            # Root user gets a default recovery PIN of '0000'
            admin = User(
                username='root', 
                password_hash=generate_password_hash('DuMmYP4$5W0rD_'), 
                recovery_pin_hash=generate_password_hash('0000'), 
                is_admin=True
            )
            db.session.add(admin)
            db.session.add_all([
                Product(name='Coca-Cola', price=0.65, stock=10),
                Product(name='Fresca', price=0.60, stock=10),
                Product(name='Dr Pepper', price=0.75, stock=10)
            ])
            db.session.commit()

    return app

# ==========================================
# FLASK-LOGIN USER LOADER
# ==========================================
# This callback is required by the LoginManager to mathematically tie 
# the secure session cookie string back to a real User object in the database.
@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))