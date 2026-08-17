/**
 * Renders the shared retailer chrome (topbar + store switcher + tab nav)
 * into the page. Kept as one module rather than duplicated markup across
 * dashboard/inventory/sessions/alerts.html, so the store-switching
 * behavior only needs to be correct in one place.
 */
import { api, clearSession } from './api-client.js';
import { getCurrentStoreId, setCurrentStoreId } from './retailer-context.js';
import { initTheme } from './ui.js';

const TABS = [
  { href: './dashboard.html', label: 'Dashboard' },
  { href: './inventory.html', label: 'Inventory' },
  { href: './sessions.html', label: 'Live Sessions' },
  { href: './alerts.html', label: 'AI Alerts' },
];

export function renderRetailerShell({ activeTab, store, allStores }) {
  const topbarRoot = document.getElementById('retailerTopbar');
  const tabRoot = document.getElementById('retailerTabs');

  topbarRoot.innerHTML = `
    <a href="./dashboard.html" class="logo"><span class="logo-mark" aria-hidden="true"></span>QuickCart</a>
    <div style="display:flex; align-items:center; gap:12px;">
      <div class="store-switcher">
        <button class="store-switcher-btn" id="storeSwitcherBtn">
          &#127978; ${escapeHtml(store?.name || 'Select store')} <span style="font-size:10px;">&#9662;</span>
        </button>
        <div class="store-switcher-menu" id="storeSwitcherMenu">
          ${allStores.map(s => `<button data-store-id="${s.id}">${escapeHtml(s.name)}</button>`).join('')}
          <button data-action="new-store" style="border-top:1px solid var(--line); color:var(--green); font-weight:600;">+ Add another store</button>
        </div>
      </div>
      <button class="theme-toggle" aria-label="Toggle dark mode"></button>
      <button class="icon-btn" id="retailerLogoutBtn" aria-label="Sign out" title="Sign out">&#8594;</button>
    </div>
  `;

  tabRoot.innerHTML = `
    <nav class="tab-nav">
      ${TABS.map(t => `<a href="${t.href}" class="${t.href.includes(activeTab) ? 'active' : ''}">${t.label}</a>`).join('')}
    </nav>
  `;

  initTheme();

  document.getElementById('retailerLogoutBtn').addEventListener('click', () => {
    clearSession();
    window.location.href = '../app/login.html';
  });

  const switcherBtn = document.getElementById('storeSwitcherBtn');
  const switcherMenu = document.getElementById('storeSwitcherMenu');
  switcherBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    switcherMenu.classList.toggle('show');
  });
  document.addEventListener('click', () => switcherMenu.classList.remove('show'));

  switcherMenu.querySelectorAll('button[data-store-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      setCurrentStoreId(btn.dataset.storeId);
      window.location.reload();
    });
  });
  switcherMenu.querySelector('[data-action="new-store"]').addEventListener('click', () => {
    window.location.href = './store-setup.html';
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
