# ==========================================
# MODULE: MAIN STOREFRONT & PUBLIC APIs
# ==========================================
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from .extensions import db, limiter
from .models import Product, PurchaseLog

# Initialize the Blueprint
main_bp = Blueprint('main', __name__)

# ==========================================
# FRONTEND UI ROUTE
# ==========================================
@main_bp.route('/')
def index():
    """Renders the public Vending Machine interface."""
    return render_template('index.html')

# ==========================================
# PUBLIC API: INVENTORY FETCH & SEARCH
# ==========================================
@main_bp.route('/api/products', methods=['GET'])
def get_products():
    """
    Fetches the inventory. Supports real-time search queries and sorting.
    SECURITY: No rate limiter here to allow fluid 'search-as-you-type' UI.
    """
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    query = Product.query
    
    if search: 
        query = query.filter(Product.name.ilike(f'%{search}%'))
    
    if sort_by == 'likes': 
        query = query.order_by(Product.likes.desc())
    else: 
        query = query.order_by(Product.name.asc())
    
    data = [{'id': p.id, 'name': p.name, 'price': p.price, 'stock': p.stock, 'likes': p.likes} for p in query.all()]
    return jsonify({'products': data})

# ==========================================
# SECURE API: TRANSACTION MECHANICS
# ==========================================
@main_bp.route('/api/products/<int:id>/buy', methods=['POST'])
@login_required
@limiter.limit("10 per minute") # DEFENSE: Throttles automated bot purchases
def buy_product(id):
    """Handles purchases with strict sanitization and atomic concurrency prevention."""
    data = request.get_json() or {}
    
    try:
        qty = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'Stop hacking the payload. Quantity must be an integer.'}), 400

    # DEFENSE: Prevent hackers from buying negative quantities to steal stock
    if qty < 1: 
        return jsonify({'error': 'You must buy at least 1 item!'}), 400

    product = Product.query.get_or_404(id)
    if product.stock < qty:
        return jsonify({'error': f'Insufficient stock. We only have {product.stock} left.'}), 400
    
    # DEFENSE: Atomic SQL update. Prevents Race Conditions if 2 users buy the last item at the exact same millisecond.
    updated = Product.query.filter(Product.id == id, Product.stock >= qty).update({
        Product.stock: Product.stock - qty
    })
    
    if not updated:
        return jsonify({'error': 'Transaction failed. Someone just bought the last one!'}), 409
        
    # Log the financial transaction
    log = PurchaseLog(user_id=current_user.id, product_id=product.id, quantity=qty)
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'message': f'Successfully purchased {qty}x {product.name}'})

@main_bp.route('/api/products/<int:id>/like', methods=['POST'])
@login_required
@limiter.limit("30 per minute") # DEFENSE: Prevents infinite "Like" loop scripts
def like_product(id):
    """Allows users to vote on product popularity."""
    product = Product.query.get_or_404(id)
    product.likes += 1
    db.session.commit()
    return jsonify({'message': 'Product liked'})