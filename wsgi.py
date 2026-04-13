# ==========================================
# MODULE: WEB SERVER GATEWAY INTERFACE (WSGI)
# ==========================================
# This file is the absolute entry point for the production Gunicorn server.
# It imports the Application Factory from our 'app' package and executes it 
# to generate the living Flask application object.

from app import create_app

# Instantiate the Flask application
app = create_app()

if __name__ == '__main__':
    # Fallback for local debugging (Gunicorn ignores this block)
    app.run(host='0.0.0.0', port=8080)