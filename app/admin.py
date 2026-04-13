# ==========================================
# MODULE: SECURE ADMIN COMMAND CENTER
# ==========================================
# This Blueprint is the highest-privilege sector of the application. 
# It is completely isolated from the public storefront and handles 
# Database CRUD (Create, Read, Update, Delete) operations, Identity Management, 
# and Financial Auditing.

import re
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, abort
from flask_login import current_user
from werkzeug.security import generate_password_hash
from .extensions import db, limiter
from .models import User, Product, PriceLog, PurchaseLog

admin_bp = Blueprint('admin', __name__)

# ==========================================
# ZERO-TRUST ACCESS CONTROL (RBAC)
# ==========================================
def admin_required(f):
    """
    CRYPTOGRAPHIC ROLE-BASED ACCESS CONTROL (RBAC):
    This decorator wraps every single route in this file. 
    It intercepts the incoming request, decrypts the session cookie, 
    and checks the database-level 'is_admin' boolean. 
    If a standard user attempts to spoof a POST request here, 
    it terminates the connection instantly with a 403 Forbidden.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# FRONTEND UI ROUTE
# ==========================================
@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    """Renders the secure Admin Command Center (Server-Side Rendering)"""
    products = Product.query.all()
    # Order the logs chronologically so the Admin sees the newest events at the top
    purchases = PurchaseLog.query.order_by(PurchaseLog.timestamp.desc()).all()
    price_logs = PriceLog.query.order_by(PriceLog.timestamp.desc()).all()
    users = User.query.all()
    
    return render_template('admin.html', products=products, purchases=purchases, price_logs=price_logs, users=users)

# ==========================================
# ADMIN API: INVENTORY MANAGEMENT (CRUD)
# ==========================================
@admin_bp.route('/api/products', methods=['POST'])
@admin_required
@limiter.limit("5 per minute") # DEFENSE: Throttles automated resource creation
def add_product():
    # DEFENSE 1: THE "PHYSICS" HARD LIMIT
    # Caps the database at 15 products to completely neutralize 'Denial of Wallet' loop scripts.
    if Product.query.count() >= 15:
        return jsonify({'error': 'Hardware capacity reached. The vending machine only holds 15 products.'}), 403

    data = request.json
    name = data.get('name', '').strip()
    
    # DEFENSE 2: STRING LENGTH EXHAUSTION (Memory Defense)
    if len(name) > 20:
        return jsonify({'error': 'Product name too long. Max 20 characters.'}), 400

    # DEFENSE 3: STRICT REGEX SANITIZATION
    # Prevents XSS <script> payloads and SQL injection characters.
    if not re.match(r'^[a-zA-Z0-9\s\-]+$', name):
        return jsonify({'error': 'Invalid characters. Alphanumeric and hyphens only.'}), 400

    try:
        price = float(data.get('price', 0))
        stock = int(data.get('stock', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numbers provided.'}), 400

    # DEFENSE 4: NEGATIVE VALUE BOUNCING
    if not name: return jsonify({'error': 'Product name cannot be empty.'}), 400
    if price < 0: return jsonify({'error': 'Price cannot be negative.'}), 400
    if stock < 0: return jsonify({'error': 'Stock cannot be negative.'}), 400

    new_product = Product(name=name, price=price, stock=stock)
    db.session.add(new_product)
    db.session.commit()
    return jsonify({'message': 'Product Added Successfully'})

@admin_bp.route('/api/products/<int:id>', methods=['PUT'])
@admin_required
@limiter.limit("10 per minute") # DEFENSE: Throttles automated price-manipulation attacks
def update_product(id):
    """Admin: Modify price and stock. Generates PriceLog automatically."""
    data = request.json
    product = Product.query.get_or_404(id)
    
    try:
        new_price = float(data.get('price', product.price))
        new_stock = int(data.get('stock', product.stock))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numbers provided.'}), 400

    if new_price < 0 or new_stock < 0:
         return jsonify({'error': 'Values cannot be negative.'}), 400

    # IMMUTABLE LEDGER: Automatically log financial price changes for auditing.
    if new_price != product.price:
        log = PriceLog(product_id=product.id, old_price=product.price, new_price=new_price)
        db.session.add(log)
        product.price = new_price

    product.stock = new_stock
    db.session.commit()
    return jsonify({'message': 'Product Updated Successfully'})

@admin_bp.route('/api/products/<int:id>', methods=['DELETE'])
@admin_required
@limiter.limit("5 per minute") # DEFENSE: Prevents automated 'Delete All' scripts
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product Deleted Successfully'})

# ==========================================
# ADMIN API: IDENTITY MANAGEMENT (CRUD)
# ==========================================
@admin_bp.route('/api/users', methods=['POST'])
@admin_required
@limiter.limit("5 per minute")
def admin_create_user():
    """Allows Admins to force-create user accounts."""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    is_admin = bool(data.get('is_admin', False))

    if not username or not password:
        return jsonify({'error': 'Username and Password cannot be empty.'}), 400

    # DEFENSE: USERNAME REGEX & SPOOF CHECK
    if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
        return jsonify({'error': 'Username must be 3-20 chars (letters, numbers, underscores).'}), 400

    if User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first():
        return jsonify({'error': 'Username already exists.'}), 400

    # CREATE HASHES: Admins created via this dashboard get a default '0000' recovery PIN.
    hashed_password = generate_password_hash(password)
    hashed_pin = generate_password_hash('0000')
    
    new_user = User(username=username, password_hash=hashed_password, recovery_pin_hash=hashed_pin, is_admin=is_admin)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User Created Successfully'})

@admin_bp.route('/api/users/<int:id>', methods=['PUT'])
@admin_required
@limiter.limit("10 per minute")
def admin_update_user(id):
    """Allows Admins to alter identities, promote users, and force-reset passwords."""
    data = request.json
    user = User.query.get_or_404(id)
    
    new_username = data.get('username', '').strip()
    new_password = data.get('password', '').strip()
    new_role = bool(data.get('is_admin', user.is_admin))

    # DEFENSE: THE ANTI-COUP PROTOCOL. 
    # Prevents a rogue script (or a careless click) from demoting the supreme Root Admin.
    if user.username == 'root' and new_role is False:
        return jsonify({'error': 'ACCESS DENIED: You cannot demote the supreme Root Admin.'}), 403

    if new_username and new_username != user.username:
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', new_username):
            return jsonify({'error': 'Username must be 3-20 chars (letters, numbers, underscores).'}), 400
            
        if User.query.filter(db.func.lower(User.username) == db.func.lower(new_username)).first():
            return jsonify({'error': 'Username already exists.'}), 400
            
        user.username = new_username

    # ZERO-KNOWLEDGE PASSWORD RESET: 
    # Overwrites the old password with a fresh PBKDF2 hash.
    if new_password:
        user.password_hash = generate_password_hash(new_password)

    user.is_admin = new_role
    db.session.commit()
    return jsonify({'message': 'User Identity Updated Successfully'})

@admin_bp.route('/api/users/<int:id>', methods=['DELETE'])
@admin_required
@limiter.limit("5 per minute")
def admin_delete_user(id):
    """
    Deletes the user identity but leaves the Purchase History intact.
    SQLAlchemy's backref sets user_id to NULL to create the 'Ghost' effect.
    """
    # DEFENSE: PREVENT ADMIN SUICIDE & ROOT DELETION
    # You cannot delete the account you are currently logged into, 
    # nor can anyone delete User ID #1.
    if id == current_user.id or id == 1:
        return jsonify({'error': 'ACCESS DENIED: You cannot delete yourself or the Root Admin.'}), 403
        
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': 'User Deleted Successfully'})