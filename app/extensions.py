# ==========================================
# MODULE: GLOBAL SECURITY PLUGINS (THE KEYSTONE)
# ==========================================
# ENTERPRISE ARCHITECTURE NOTE:
# Why do these plugins live in their own file? 
# In a monolithic app, everything is in app.py. But in an Application Factory,
# models.py needs the database, auth.py needs the database, and __init__.py needs both.
# If they all import each other, Python throws a fatal "Circular Import" crash.
# By isolating uninitialized plugins here, we create a clean, central hub that 
# any file can import from without looping the compiler.

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ==========================================
# 1. DATABASE & ORM ENGINE
# ==========================================
# SQLAlchemy acts as our cryptographic barrier against SQL Injection (SQLi).
# It parameterizes all queries automatically, meaning malicious inputs 
# like " ' OR 1=1 -- " are treated as harmless text, not executable code.
db = SQLAlchemy()

# ==========================================
# 2. SESSION & STATE MANAGEMENT
# ==========================================
# Handles the secure cookie parsing, user loading, and the impenetrable 
# @login_required decorator.
login_manager = LoginManager()

# ==========================================
# 3. CROSS-SITE REQUEST FORGERY (CSRF) ARMOR
# ==========================================
# Automatically intercepts all POST, PUT, and DELETE requests.
# If the request does not contain a cryptographically valid token matching 
# the user's current session, it instantly drops the connection with a 400 Bad Request.
csrf = CSRFProtect()


# ==========================================
# 4. LAYER 7 DDoS & BRUTE-FORCE DEFENSE (RATE LIMITER)
# ==========================================
def get_user_id_or_ip():
    """
    IDENTITY-AWARE THROTTLING (The NAT Bypass):
    If we only rate-limit by IP address, a university campus sharing a single 
    public IP router (NAT) would trigger false-positive bans for legitimate users.
    This genius function checks:
    1. Are they logged in? Track their exact Database User ID.
    2. Are they an anonymous guest? Track their real Home IP Address.
    """
    if current_user and current_user.is_authenticated:
        return str(current_user.id)
    return get_remote_address()

# We initialize the global Limiter here, but deliberately leave `default_limits` EMPTY.
# By removing the global blanket limit, we allow our front-end "Search-as-you-type" 
# JavaScript to fire dozens of rapid GET requests without banning the user.
# We then rely on surgical @limiter.limit() decorators to armor the vulnerable POST/PUT routes.
limiter = Limiter(key_func=get_user_id_or_ip)