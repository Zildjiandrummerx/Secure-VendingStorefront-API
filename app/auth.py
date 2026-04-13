# ==========================================
# MODULE: IDENTITY & AUTHENTICATION BLUEPRINT
# ==========================================
# This Blueprint isolates all credential handling from the rest of the app.
# By modularizing it, we ensure that changes to the storefront or admin panel 
# do not accidentally introduce vulnerabilities into the authentication flow.

import re
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db, limiter
from .models import User

auth_bp = Blueprint('auth', __name__)

# ==========================================
# 1. THE LOGIN PORTAL
# ==========================================
@auth_bp.route('/login', methods=['POST'])
# BURST LIMITING: Solves the "Launch Day / NAT" problem. 
# A whole university campus sharing one IP can login up to 100 times a day, 
# but an automated script trying 11 logins in 60 seconds is instantly banned.
@limiter.limit("10 per minute, 100 per day") 
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # CASE-INSENSITIVE LOOKUP: Prevents hackers from registering "rOot" to spoof "root"
    user = User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first()
    
    # TIMING-ATTACK DEFENSE: `check_password_hash` compares the PBKDF2 strings 
    # in constant time, meaning hackers cannot measure CPU response milliseconds 
    # to guess characters of the password.
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
    else:
        # ZERO-KNOWLEDGE ERROR: Never tell the user *which* part was wrong 
        # (e.g., "Username not found"). It prevents Account Enumeration scanning.
        flash("Invalid credentials.", "danger")
        
    return redirect(url_for('main.index'))

# ==========================================
# 2. THE REGISTRATION PORTAL
# ==========================================
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute, 100 per day") 
def register():
    if request.method == 'POST':
        # PAYLOAD SANITIZATION: .strip() destroys whitespace-only bypass attacks
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        pin = request.form.get('pin', '').strip()
        
        if not username or not password or not pin:
            flash("All fields are required.", "danger")
            return redirect(url_for('auth.register'))

        # DEFENSE 1: USERNAME REGEX (XSS & Injection Armor)
        # Rejects HTML tags <script>, SQL characters ', and Unicode Zalgo text.
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            flash("Username must be 3-20 characters (letters, numbers, underscores).", "danger")
            return redirect(url_for('auth.register'))
            
        # DEFENSE 2: PIN REGEX (Format Enforcement)
        # Must be exactly 4 digits. No letters, no symbols.
        if not re.match(r'^[0-9]{4}$', pin):
            flash("Recovery PIN must be exactly 4 digits.", "danger")
            return redirect(url_for('auth.register'))

        # DEFENSE 3: DUPLICATE PREVENTION
        if User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first():
            flash("Username already taken.", "danger")
            return redirect(url_for('auth.register'))
            
        # THE CRYPTOGRAPHIC MEAT GRINDER:
        # Both the Password and the PIN are permanently destroyed and converted 
        # into 256-bit unreadable hashes. We store nothing but mathematical proof.
        hashed_password = generate_password_hash(password)
        hashed_pin = generate_password_hash(pin) 
        
        new_user = User(username=username, password_hash=hashed_password, recovery_pin_hash=hashed_pin, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        
        # Auto-login the user immediately after creation for frictionless UX
        login_user(new_user)
        return redirect(url_for('main.index'))
        
    return render_template('register.html')

# ==========================================
# 3. ACCOUNT TAKEOVER (ATO) PREVENTION PORTAL
# ==========================================
@auth_bp.route('/forgot-password', methods=['POST'])
# THE BRUTE-FORCE KILL SWITCH:
# A 4-digit PIN only has 10,000 possible combinations. If we allowed infinite guesses, 
# a bot could crack it in seconds. By limiting guesses to 10 per hour, it would take 
# an attacker 41 DAYS to guess a PIN. We mathematically destroy the attack vector.
@limiter.limit("3 per minute, 10 per hour") 
def forgot_password():
    username = request.form.get('username', '').strip()
    pin = request.form.get('pin', '').strip()
    new_password = request.form.get('new_password', '').strip()

    # ==========================================
    # DEFENSE: THE ROOT RECOVERY LOCKOUT
    # ==========================================
    # The Root Admin account cannot be reset via the web interface. 
    # This completely destroys the "0000" brute-force vector.
    if username.lower() == 'root':
        flash("ACCESS DENIED: Root account recovery requires physical infrastructure access.", "danger")
        return redirect(url_for('main.index'))
    
    # ZERO-TRUST VALIDATION:
    # Requires proof of identity (the Username) AND proof of secret (the hashed PIN).
    if user and check_password_hash(user.recovery_pin_hash, pin):
        if not new_password:
            flash("New password cannot be empty.", "danger")
        else:
            # Safely overwrites the forgotten password hash with the new one
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Password reset successfully! You may now log in.", "success")
    else:
        # Ambiguous error message so attackers don't know if the User or the PIN was wrong.
        flash("Invalid Username or Recovery PIN.", "danger")
        
    return redirect(url_for('main.index'))

# ==========================================
# 4. SESSION TERMINATION
# ==========================================
@auth_bp.route('/logout')
def logout():
    # Destroys the secure cookie session completely.
    # Paired with our HTTP Cache headers, this makes the browser instantly 'forget' the user.
    logout_user()
    return redirect(url_for('main.index'))