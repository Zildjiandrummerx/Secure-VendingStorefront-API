# Enterprise Vending API (Cloud-Native & Zero-Trust)

## The Origin Story: An 8-Year Evolution
This project began 8 years ago as a standard backend code challenge. At the time, I was just starting my engineering journey. 
I saved the original requirements as a guiding star to master full-stack development, database architecture, and cloud deployments. 

Today, this repository represents the culmination of that journey. I didn't just fulfill the original requirements; I proactively engineered a **Multi-Cloud, Zero-Trust, Enterprise-Grade Application** designed to withstand real-world vulnerabilities, automated botnets, and data-integrity conflicts.

---

## The Original Challenge Requirements
*   **Inventory:** Add/Remove products and set stock quantities.
*   **Pricing:** Modify prices and save an immutable log of price updates.
*   **Transactions:** Buy a product (reducing stock) and keep an audit log of purchases (who, what, when).
*   **Social:** Like a product.
*   **Data Fetching:** Obtain a list of available products, sortable by name or popularity, with pagination.
*   **Search:** Search products by name.
*   **RBAC (Role-Based Access Control):** 
    *   Only Admins can add/remove products and modify prices.
    *   Only logged-in users can buy/like products.
    *   Everyone (guests included) can view and search products.
*   **Extra Credit:** Build a frontend application that connects to the API.

---

## The Enterprise Evolution (Proactive Architecture)
To elevate this from a coding challenge to a production-ready application, I engineered defenses against the **OWASP Top 10** and sophisticated automated attacks.

### 1. Application Factory & Blueprint Architecture
Transitioned from a monolithic script to a modular `Flask Blueprint` architecture (Auth, Main, Admin) to ensure infinite scalability and separation of concerns.

### 2. Zero-Trust Security & Identity Access Management (IAM)
*   **PBKDF2 Cryptography:** Passwords and Recovery PINs are mathematically ground into 256-bit hashes. Zero plain-text storage prevents blast-radius damage from data leaks.
*   **Anti-Account Takeover (ATO):** Self-service password recovery utilizes a Zero-Trust 4-Digit PIN. The recovery endpoint is strictly throttled (3 requests/minute) to mathematically neutralize brute-force dictionary attacks.
*   **The Anti-Coup Protocol:** Hardcoded logic prevents malicious actors or compromised accounts from demoting, altering, or deleting the supreme Root Administrator.

### 3. Layer 7 DDoS & Botnet Armor
*   **Surgical Rate Limiting:** Applied Token-Bucket rate limiting (e.g., `5 per minute, 100 per day`). This prevents "Denial of Wallet" loop scripts while avoiding false-positive bans on corporate NAT networks.
*   **The "Physics" Hard-Limit (Mass Assignment Defense):** The database caps inventory at 15 slots, completely destroying automated resource-creation botnets at the database layer.
*   **Proxy IP Extraction:** Utilizes `ProxyFix` middleware to strip Google Cloud Load Balancer disguises, revealing and throttling the attacker's true home IP address.
*   **The Fat Payload Kill-Switch:** Flask is configured to instantly drop any request payload larger than 1MB, preventing Out-Of-Memory (OOM) crashes.

### 4. Military-Grade Session Hygiene
*   **Cookie Lockdown:** Enforces `HttpOnly`, `Secure`, and `SameSite='Strict'` to neutralize XSS, CSRF, and MITM attacks.
*   **The "Ghost Tab" Destroyer:** Strict `Cache-Control` headers force the browser to never save authenticated HTML, destroying cloned-cookie replay attacks.
*   **Session Time-Bombs:** Sessions mathematically self-destruct after 30 minutes of inactivity.

### 5. Financial Audit Integrity (The Ghost Protocol)
In enterprise accounting, deleting a user must never delete their financial history. Using advanced SQLAlchemy relationships, deleted users trigger a `nullable=True` cascade. The purchase remains in the immutable ledger, gracefully tied to an anonymized "Deleted User" to preserve total sales accuracy.

### 6. Cloud-Native Infrastructure
*   **Containerization:** Hardened `python:3.11-slim` Docker image running a production Gunicorn WSGI server as an unprivileged non-root user.
*   **Ephemeral Sandbox vs. Persistent DB:** Designed to run statelessly on **Google Cloud Run** (auto-wiping the SQLite DB upon sleep for QA testing), but dynamically accepts Postgres Cloud SQL URIs via environment variables for permanent production deployment.

## Tech Stack
*   **Backend:** Python 3.11, Flask, SQLAlchemy, Flask-Limiter, Flask-Login, Werkzeug Security
*   **Frontend:** Vanilla JavaScript (ES6+), HTML5, MDBootstrap 5 (Material Design)
*   **Infrastructure:** Docker, Google Cloud Build, Google Cloud Run, Artifact Registry

---

## How It Works (The Architecture Flow)

1. **The Entry Point (WSGI):** The Gunicorn server boots the application via `wsgi.py`, which triggers the Application Factory (`__init__.py`) to load all isolated security plugins and register the URL Blueprints.
2. **The Stateless Sandbox:** Upon boot, the application automatically detects if a database exists. If not, it self-heals by creating a local SQLite vault and injecting the default `root` identity and inventory.
3. **Frontend-Backend Sync (CSRF):** The server generates a unique cryptographic CSRF token and hides it in a `<meta>` HTML tag. The Vanilla JavaScript engine extracts this token and automatically attaches it to the headers of every `fetch()` POST/PUT/DELETE request.
4. **Real-Time Search:** The public storefront utilizes an `AbortController` in JavaScript. As the user types in the search bar, previous network requests are instantly aborted to prevent race conditions, ensuring the UI remains buttery smooth without reloading the page.
5. **Server-Side Rendering (SSR) Admin:** Unlike the public storefront, the Admin Command Center is fully Server-Side Rendered. This ensures the Administrator is always viewing a synchronous, cryptographically verified snapshot of the database ledger.

---

## How to Use It (Deployment & Testing)

### 1. Run Locally (Docker)
You do not need Python installed on your local machine. The entire environment is containerized.
```bash
# Build the hardened image
docker build -t enterprise-vending-api .

# Run the container locally on port 8080
docker run -p 8080:8080 enterprise-vending-api

Navigate to http://localhost:8080 in your web browser.


### 2. Default Administrator Credentials
The system automatically bootstraps a supreme Root Administrator on initial boot:

Username: root
Password: DuMmYP4$5W0rD_
Recovery PIN: 0000 (Note: The Root account is explicitly blocked from using the web-based password recovery portal to prevent ATO exploits).


### 3. Deploy to Google Cloud Platform (GCP)
The repository includes an idempotent Infrastructure-as-Code (IaC) Bash script (deploy.sh). To test this in your own GCP environment, follow these exact steps:

Ensure you have the gcloud CLI installed and authenticated to your Google account.
Open the deploy.sh file and modify the Global Configuration block at the top:

PROJECT_ID="your-gcp-project-id" # Change this to your actual GCP Project ID
SERVICE_NAME="vending-api"       # Optional: Name of your Cloud Run service
REGION="us-central1"             # Optional: Change to your preferred GCP region
REPOSITORY="vending-repo"        # Optional: Name of the Artifact Registry repo

Make the script executable and run it:
chmod +x deploy.sh
./deploy.sh

The script will automatically provision Artifact Registry, submit the build to Cloud Build, deploy to Cloud Run, securely inject a randomized 256-bit Hex SECRET_KEY, apply the Domain Restricted Sharing bypass if needed, and output your live HTTPS URL.


### 4. Red Team / QA Testing
I encourage you to try and break it.

Try to intercept the session cookie in Chrome DevTools. (You will find it is HttpOnly and Secure).
Try to brute-force the password reset endpoint. (You will be throttled after 3 attempts).
Try to inject <script> tags into the registration form. (The Backend Regex engine will bounce you).
Try to write a JavaScript fetch() loop to create 100 products. (The "Physics" limit will lock the database at 15 products, and the Layer 7 rate limiter will temporarily ban your IP with a 429 Too Many Requests).