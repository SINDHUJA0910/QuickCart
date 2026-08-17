/**
 * QuickCart API client.
 *
 * Single source of truth for talking to the backend, matching the Pydantic
 * schemas in backend/app/schemas/*.py exactly (field names, required vs
 * optional) — this file should never invent a field the backend doesn't
 * actually accept or return.
 *
 * Config: API_BASE_URL is read from a <meta name="quickcart-api-base">
 * tag so the same file works in local dev (pointed at localhost:8000) and
 * production (pointed at the deployed Railway URL) without a build step —
 * this is a plain script, not a bundled app, per the spec's HTML5/CSS3/ES6
 * stack.
 */

const API_BASE_URL = (
  document.querySelector('meta[name="quickcart-api-base"]')?.content
  || 'http://localhost:8000/api/v1'
);

const TOKEN_KEY = 'quickcart_access_token';
const ROLE_KEY = 'quickcart_role';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function setSession(accessToken, role) {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function isLoggedIn() {
  return Boolean(getToken());
}

/**
 * Thrown on any non-2xx response. `detail` mirrors FastAPI's error body
 * shape ({"detail": "..."}), which is what every QuickCart error handler
 * returns (see backend/app/core/exceptions.py + main.py's exception
 * handler) — callers can show `error.detail` directly to the user.
 */
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, { body, auth = true, query } = {}) {
  let url = `${API_BASE_URL}${path}`;
  if (query) {
    const params = new URLSearchParams(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    );
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch {
    // non-JSON response (e.g. a CSV download) — caller handles response directly via requestRaw
  }

  if (!response.ok) {
    const detail = data?.detail || (Array.isArray(data) ? data.map(d => d.msg).join(', ') : null);
    throw new ApiError(response.status, detail);
  }

  return data;
}

export const api = {
  // ---- Auth ----
  customerSignup: (payload) => request('POST', '/auth/customer/signup', { body: payload, auth: false }),
  customerLogin: (payload) => request('POST', '/auth/customer/login', { body: payload, auth: false }),
  customerMe: () => request('GET', '/auth/customer/me'),
  customerForgotPassword: (payload) => request('POST', '/auth/customer/forgot-password', { body: payload, auth: false }),
  retailerSignup: (payload) => request('POST', '/auth/retailer/signup', { body: payload, auth: false }),
  retailerLogin: (payload) => request('POST', '/auth/retailer/login', { body: payload, auth: false }),
  retailerMe: () => request('GET', '/auth/retailer/me'),
  retailerForgotPassword: (payload) => request('POST', '/auth/retailer/forgot-password', { body: payload, auth: false }),

  // ---- Stores (customer) ----
  searchStores: (query) => request('GET', '/stores/search', { query }),

  // ---- Sessions ----
  createSession: (storeId) => request('POST', '/sessions', { body: { store_id: storeId } }),
  getActiveSession: () => request('GET', '/sessions/active'),

  // ---- Products / cart ----
  getProductByBarcode: (storeId, barcode) => request('GET', `/stores/${storeId}/products/barcode/${encodeURIComponent(barcode)}`),
  getCart: (sessionId) => request('GET', `/sessions/${sessionId}/cart`),
  addCartItem: (sessionId, productId, quantity) => request('POST', `/sessions/${sessionId}/cart/items`, { body: { product_id: productId, quantity } }),
  updateCartItem: (sessionId, itemId, quantity) => request('PATCH', `/sessions/${sessionId}/cart/items/${itemId}`, { body: { quantity } }),
  removeCartItem: (sessionId, itemId) => request('DELETE', `/sessions/${sessionId}/cart/items/${itemId}`),

  // ---- Checkout ----
  startCheckout: (sessionId) => request('POST', `/sessions/${sessionId}/checkout`),
  confirmCheckout: (sessionId, payload) => request('POST', `/sessions/${sessionId}/checkout/confirm`, { body: payload }),

  // ---- Notifications ----
  listNotifications: (unreadOnly) => request('GET', '/notifications', { query: { unread_only: unreadOnly || undefined } }),
  markNotificationRead: (id) => request('POST', `/notifications/${id}/read`),

  // ---- Retailer: stores ----
  listMyStores: () => request('GET', '/retailer/stores'),
  createStore: (payload) => request('POST', '/retailer/stores', { body: payload }),
  updateStore: (storeId, payload) => request('PATCH', `/retailer/stores/${storeId}`, { body: payload }),

  // ---- Retailer: dashboard ----
  getDashboardStats: (storeId) => request('GET', `/retailer/stores/${storeId}/dashboard/stats`),
  getLiveSessions: (storeId) => request('GET', `/retailer/stores/${storeId}/dashboard/live-sessions`),
  getRecentTransactions: (storeId) => request('GET', `/retailer/stores/${storeId}/dashboard/transactions`),

  // ---- Retailer: inventory ----
  listProducts: (storeId, params) => request('GET', `/retailer/stores/${storeId}/products`, { query: params }),
  createProduct: (storeId, payload) => request('POST', `/retailer/stores/${storeId}/products`, { body: payload }),
  updateProduct: (storeId, productId, payload) => request('PATCH', `/retailer/stores/${storeId}/products/${productId}`, { body: payload }),
  deleteProduct: (storeId, productId) => request('DELETE', `/retailer/stores/${storeId}/products/${productId}`),
  listCategories: (storeId) => request('GET', `/retailer/stores/${storeId}/categories`),
  createCategory: (storeId, payload) => request('POST', `/retailer/stores/${storeId}/categories`, { body: payload }),

  // ---- Retailer: cameras ----
  listCameras: (storeId) => request('GET', `/retailer/stores/${storeId}/cameras`),
  createCamera: (storeId, payload) => request('POST', `/retailer/stores/${storeId}/cameras`, { body: payload }),

  // ---- Retailer: AI alerts ----
  listAlerts: (storeId, status) => request('GET', `/retailer/stores/${storeId}/ai-alerts`, { query: { status } }),
  resolveAlert: (storeId, alertId, status) => request('POST', `/retailer/stores/${storeId}/ai-alerts/${alertId}/resolve`, { body: { status } }),

  // ---- Retailer: reports ----
  getTopProducts: (storeId) => request('GET', `/retailer/stores/${storeId}/reports/top-products`),
  getPeakHours: (storeId) => request('GET', `/retailer/stores/${storeId}/reports/peak-hours`),

  // ---- Admin (separate X-Admin-Key auth, not a bearer token) ----
  adminStats: (adminKey) => fetch(`${API_BASE_URL}/admin/stats`, { headers: { 'X-Admin-Key': adminKey } }).then(handleAdminResponse),
  adminStores: (adminKey) => fetch(`${API_BASE_URL}/admin/stores`, { headers: { 'X-Admin-Key': adminKey } }).then(handleAdminResponse),
  adminHealth: (adminKey) => fetch(`${API_BASE_URL}/admin/health`, { headers: { 'X-Admin-Key': adminKey } }).then(handleAdminResponse),
};

async function handleAdminResponse(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data?.detail || 'Admin request failed');
  return data;
}

/** CSV export requires the auth header, so it can't be a plain <a href> link
 * (the browser wouldn't attach the token) — fetch as a blob and trigger a
 * client-side download instead. */
export async function downloadTransactionsCsv(storeId) {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}/retailer/stores/${storeId}/reports/transactions.csv`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new ApiError(response.status, 'Could not download the report.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `quickcart_transactions_${storeId}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
