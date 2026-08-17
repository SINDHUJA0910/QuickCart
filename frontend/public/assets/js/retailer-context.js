/**
 * Resolves which store a retailer is currently managing.
 *
 * A retailer can own multiple stores (the schema supports it — one
 * `retailers` row, many `stores` rows), but every dashboard/inventory/
 * alerts endpoint is scoped to one store_id at a time. This module is the
 * single place that decides which one: the last one explicitly selected
 * (persisted in localStorage), falling back to the retailer's first store,
 * falling back to "you need to create one" if they have none yet.
 */
import { api, isLoggedIn } from './api-client.js';

const STORE_KEY = 'quickcart_current_store_id';

export function getCurrentStoreId() {
  return localStorage.getItem(STORE_KEY);
}

export function setCurrentStoreId(storeId) {
  localStorage.setItem(STORE_KEY, storeId);
}

/**
 * Ensures a valid current store is set, returning { store, allStores }.
 * If the retailer has no stores at all, returns { store: null, allStores: [] }
 * so the caller can render a "create your first store" prompt instead of
 * a broken dashboard.
 */
export async function resolveCurrentStore() {
  if (!isLoggedIn()) {
    window.location.href = './login.html';
    throw new Error('redirecting to login');
  }

  const allStores = await api.listMyStores();
  if (allStores.length === 0) {
    return { store: null, allStores: [] };
  }

  const savedId = getCurrentStoreId();
  let store = allStores.find(s => s.id === savedId);
  if (!store) {
    store = allStores[0];
    setCurrentStoreId(store.id);
  }
  return { store, allStores };
}
