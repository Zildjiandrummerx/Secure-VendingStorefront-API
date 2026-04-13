# ==========================================
# MODULE: DATABASE SCHEMAS & RELATIONSHIPS
# ==========================================
# This file utilizes SQLAlchemy (an Object-Relational Mapper). 
# It translates these Python classes into secure, optimized SQL tables,
# preventing SQL Injection (SQLi) attacks by automatically sanitizing inputs.

from datetime import datetime
from flask_login import UserMixin
from .extensions import db

# ==========================================
# IDENTITY & ACCESS MANAGEMENT (IAM)
# ==========================================
class User(UserMixin, db.Model):
    """
    Represents a registered identity. 
    Inherits from UserMixin to seamlessly integrate with Flask-Login's session manager.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    
    # ZERO-KNOWLEDGE ARCHITECTURE:
    # We never store plain text. These columns strictly hold 256-bit PBKDF2 hashes.
    # If the database is ever stolen, the blast radius is neutralized.
    password_hash = db.Column(db.String(256), nullable=False)
    
    # THE ATO (Account Takeover) DEFENSE:
    # Allows self-service password resets without email, mathematically protected 
    # against brute-force guessing via our rate limiters.
    recovery_pin_hash = db.Column(db.String(256), nullable=False) 
    
    is_admin = db.Column(db.Boolean, default=False)
    
    # QUERY OPTIMIZATION: lazy=True ensures that when we load a User, we don't 
    # automatically load their entire purchase history into server RAM until we explicitly ask for it.
    purchases = db.relationship('PurchaseLog', backref='user', lazy=True)


# ==========================================
# INVENTORY MANAGEMENT
# ==========================================
class Product(db.Model):
    """
    The core Vending Machine inventory item.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    
    # DATABASE INTEGRITY (CASCADING DELETES):
    # If the Admin permanently deletes a Soda from the catalog, the database 
    # will automatically hunt down and destroy its associated logs to prevent 
    # "Orphaned Foreign Keys" and database corruption.
    purchases = db.relationship('PurchaseLog', backref='product', cascade='all, delete-orphan')
    price_logs = db.relationship('PriceLog', backref='product', cascade='all, delete-orphan')


# ==========================================
# FINANCIAL AUDIT TRAILS (IMMUTABLE LEDGERS)
# ==========================================
class PriceLog(db.Model):
    """
    Tracks historical price fluctuations for inventory items.
    Crucial for financial auditing and tracing admin actions over time.
    """
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    old_price = db.Column(db.Float, nullable=False)
    new_price = db.Column(db.Float, nullable=False)
    
    # Automatically stamps the exact UTC server time upon creation
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PurchaseLog(db.Model):
    """
    The ledger of all transactions. Maps Users to Products.
    """
    id = db.Column(db.Integer, primary_key=True)
    
    # THE GHOST PROTOCOL (FINANCIAL ACCURACY):
    # nullable=True is an industry-standard accounting mechanism. 
    # If an Admin deletes a User, we DO NOT delete the purchase (which would alter total sales).
    # Instead, SQLAlchemy severs the tie, setting user_id to NULL. 
    # The UI gracefully reads this as a "Deleted User".
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)