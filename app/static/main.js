// ==========================================
// STATE MANAGEMENT & SECURITY
// ==========================================
// Automatically extract the CSRF token from the secure meta tag injected by Flask
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

// Local memory tracking
let quantities = {}; 
let currentSort = 'name'; 

// DEFENSE: The AbortController destroys network race conditions.
// If a user types "Co" and then rapidly types "ca", it aborts the first fetch 
// so the UI doesn't render overlapping/duplicate data.
let fetchController = new AbortController();

// ==========================================
// SEARCH & RENDER LOGIC
// ==========================================
function triggerSearch(sortOverride = null) {
    if (sortOverride) currentSort = sortOverride; 
    
    // .trim() prevents users from searching blank spaces and breaking the query
    const searchQuery = document.getElementById('searchInput').value.trim(); 
    loadProducts(currentSort, searchQuery);
}

async function loadProducts(sort = 'name', search = '') {
    // Abort previous pending fetch requests
    fetchController.abort();
    fetchController = new AbortController();

    try {
        const res = await fetch(`/api/products?sort=${sort}&search=${search}`, {
            signal: fetchController.signal 
        });
        const data = await res.json();
        
        const container = document.getElementById('product-container');
        container.innerHTML = '';

        // Empty state handler
        if (data.products.length === 0) {
            container.innerHTML = `<div class="text-center text-muted mt-5">
                <i class="fas fa-box-open fa-3x mb-3"></i>
                <h5>No products found matching "${search}"</h5>
            </div>`;
            return;
        }

        // Render Product Blocks Dynamically
        data.products.forEach(p => {
            if (!quantities[p.id]) quantities[p.id] = 1;

            const disabled = p.stock < 1 ? 'disabled' : '';
            const stockStatus = p.stock > 0 ? `<span class="text-success fw-bold">Stock: ${p.stock}</span>` : `<span class="text-danger fw-bold">Out of Stock</span>`;

            const block = `
            <div class="card stacked-product shadow-3-strong transition mb-3">
                <div class="card-body d-flex justify-content-between align-items-center p-4">
                    <div class="d-flex align-items-center">
                        <i class="fas fa-beer fa-3x text-danger me-4"></i>
                        <div>
                            <h4 class="card-title fw-bold mb-1">${p.name}</h4>
                            <h5 class="text-success mb-0">$${p.price.toFixed(2)}</h5>
                        </div>
                    </div>
                    <div class="text-center d-none d-md-block">
                        <p class="mb-1">${stockStatus}</p>
                        <p class="text-info mb-0 small"><i class="fas fa-heart"></i> ${p.likes} Likes</p>
                    </div>
                    <div class="action-panel text-end" style="min-width: 250px;">
                        <div class="default-state text-muted">Hover to Interact <i class="fas fa-arrow-right ms-2"></i></div>
                        <div class="hover-controls align-items-center justify-content-end gap-2">
                            <!-- Quantity Controls -->
                            <button class="btn btn-outline-secondary btn-sm px-2" onclick="changeQty(${p.id}, -1)">-</button>
                            <span id="qty-${p.id}" class="fw-bold fs-5 px-2">${quantities[p.id]}</span>
                            <button class="btn btn-outline-secondary btn-sm px-2" onclick="changeQty(${p.id}, 1)">+</button>
                            
                            <!-- Action Buttons -->
                            <button class="btn btn-primary btn-sm ms-2" onclick="buyProduct(${p.id})" ${disabled}><i class="fas fa-shopping-cart"></i> Buy</button>
                            <button class="btn btn-info btn-sm ms-1 text-white" onclick="likeProduct(${p.id})"><i class="fas fa-thumbs-up"></i></button>
                        </div>
                    </div>
                </div>
            </div>`;
            container.innerHTML += block;
        });
    } catch (err) {
        // Gracefully ignore fetch errors if we intentionally aborted them
        if (err.name === 'AbortError') return;
        console.error("API Error:", err);
    }
}

// ==========================================
// CLIENT-SIDE DEFENSE LOGIC
// ==========================================
function changeQty(id, delta) {
    let newVal = quantities[id] + delta;
    
    // UI DEFENSE: Restrict UI controls from showing negative numbers
    if (newVal < 1) newVal = 1; 
    
    quantities[id] = newVal;
    document.getElementById(`qty-${id}`).innerText = newVal;
}

async function apiCall(endpoint, method, payload = null) {
    try {
        const options = {
            method: method,
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        };
        
        // PAYLOAD DEFENSE: Catch users who edit Javascript in Chrome DevTools
        // If they try to force a negative purchase, stop it before it even hits the server
        if (payload && payload.quantity !== undefined) {
            if (isNaN(payload.quantity) || payload.quantity < 1) {
                alert("Nice try modifying the JS variables! Stop hacking and just buy a soda.");
                return;
            }
        }

        if (payload) options.body = JSON.stringify(payload);

        // Execute API Call
        const res = await fetch(endpoint, options);
        
        // ==========================================
        // UNAUTHENTICATED REDIRECT DEFENSE
        // ==========================================
        // If Flask-Login catches an unauthenticated user, it redirects them to the /login HTML page.
        // We catch that silent redirect here before JS tries to parse HTML as JSON.
        if (res.redirected && res.url.includes('login')) {
            alert("🔒 Hold up! You need to Login or Register before you can interact with the vending machine.");
            return;
        }

        // RBAC Check (For true 401/403 responses)
        if (res.status === 401 || res.status === 403) {
            alert("🔒 Access Denied. Nice try, but you need admin/user privileges for this.");
            return;
        }
        
        const data = await res.json();
        
        // SERVER-SIDE DEFENSE UI: If the server caught them cheating, show the server's error
        if (!res.ok || data.error) {
            alert(`🚫 BUSTED: ${data.error || "Invalid Action"}`);
        } else {
            // Success handler (Silent UX update)
            if (method === 'POST' && endpoint.includes('buy')) {
                quantities = {}; // Reset local quantity tracker on success
            }
            triggerSearch(); // Refresh UI smoothly
        }
    } catch(err) {
        console.error("API Error:", err);
        alert("An unexpected error occurred. Stop breaking my app!");
    }
}

// ==========================================
// ACTION TRIGGERS
// ==========================================
function buyProduct(id) { 
    apiCall(`/api/products/${id}/buy`, 'POST', { quantity: quantities[id] }); 
}

function likeProduct(id) { 
    apiCall(`/api/products/${id}/like`, 'POST'); 
}

// Initial UI render on load
document.addEventListener("DOMContentLoaded", () => triggerSearch());