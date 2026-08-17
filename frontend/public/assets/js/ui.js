/**
 * Small shared UI helpers used across every app page: toast notifications
 * and theme persistence. Kept separate from api-client.js since this file
 * has zero backend knowledge — it's pure UI plumbing, importable on pages
 * (like login) that don't need the API client's auth-token logic yet.
 */

export function initTheme() {
  const root = document.documentElement;
  const saved = localStorage.getItem('quickcart-theme');
  if (saved) root.setAttribute('data-theme', saved);

  const toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      localStorage.setItem('quickcart-theme', next);
    });
  }
}

let toastContainer = null;
export function showToast(message, variant = 'default') {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
  }
  const toast = document.createElement('div');
  toast.className = 'toast';
  if (variant === 'error') toast.style.background = 'var(--red)';
  if (variant === 'success') toast.style.background = 'var(--green)';
  toast.textContent = message;
  toastContainer.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

/** Sets a button into/out of a loading state, swapping its label for a spinner. */
export function setButtonLoading(button, loading, loadingLabel = '') {
  if (loading) {
    button.dataset.originalLabel = button.innerHTML;
    button.innerHTML = `<span class="spinner"></span>${loadingLabel}`;
    button.disabled = true;
  } else {
    button.innerHTML = button.dataset.originalLabel || button.innerHTML;
    button.disabled = false;
  }
}

export function formatMoney(paise) {
  return `\u20B9${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
