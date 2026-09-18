/* Kerala Cafe shared client-side helpers */

const KeralaCafe = (() => {
  const CART_KEY = 'keralacafe_cart';

  function getCart() {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY)) || JSON.parse(localStorage.getItem('tastehub_cart')) || {};
    } catch (e) {
      return {};
    }
  }

  function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    window.dispatchEvent(new Event('keralacafe:cartchange'));
    window.dispatchEvent(new Event('tastehub:cartchange'));
  }

  function addToCart(item) {
    const cart = getCart();
    if (cart[item.id]) {
      cart[item.id].qty += 1;
    } else {
      cart[item.id] = { id: item.id, name: item.name, price: item.price, qty: 1 };
    }
    saveCart(cart);
  }

  function changeQty(id, delta) {
    const cart = getCart();
    if (!cart[id]) return;
    cart[id].qty += delta;
    if (cart[id].qty <= 0) delete cart[id];
    saveCart(cart);
  }

  function clearCart() {
    localStorage.removeItem(CART_KEY);
    localStorage.removeItem('tastehub_cart');
    window.dispatchEvent(new Event('keralacafe:cartchange'));
    window.dispatchEvent(new Event('tastehub:cartchange'));
  }

  let toastTimer;
  function toast(message) {
    let el = document.getElementById('th-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'th-toast';
      el.className = 'th-toast';
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
  }

  // ---- Reusable "+ Add to Cart" <-> "- qty +" control ----
  // Any element with class="cart-action" and data-id/data-name/data-price
  // attributes automatically becomes a live add-to-cart / quantity stepper,
  // no per-page JS required.

  function escapeAttr(str) {
    return String(str).replace(/"/g, '&quot;');
  }

  function cartControlHtml(item) {
    const cart = getCart();
    const entry = cart[item.id];
    if (entry && entry.qty > 0) {
      return `
        <div class="th-qty-control th-qty-control-block">
          <button type="button" class="th-qty-btn" data-cart-action="dec" data-id="${item.id}">-</button>
          <span>${entry.qty}</span>
          <button type="button" class="th-qty-btn" data-cart-action="inc" data-id="${item.id}">+</button>
        </div>`;
    }
    return `<button type="button" class="btn btn-primary btn-sm btn-block cart-add-btn" data-id="${item.id}" data-name="${escapeAttr(item.name)}" data-price="${item.price}">+ Add to Cart</button>`;
  }

  function refreshCartActions() {
    document.querySelectorAll('.cart-action').forEach(el => {
      const item = { id: el.dataset.id, name: el.dataset.name, price: parseFloat(el.dataset.price) };
      el.innerHTML = cartControlHtml(item);
    });
  }

  return { getCart, saveCart, addToCart, changeQty, clearCart, toast, cartControlHtml, refreshCartActions };
})();

// Alias TasteHub to KeralaCafe for backwards compatibility
const TasteHub = KeralaCafe;

// mobile nav toggle + global cart-action wiring
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');
  if (toggle && links) {
    toggle.addEventListener('click', () => links.classList.toggle('open'));
  }

  TasteHub.refreshCartActions();
  window.addEventListener('tastehub:cartchange', TasteHub.refreshCartActions);

  document.addEventListener('click', (e) => {
    const addBtn = e.target.closest('.cart-add-btn');
    if (addBtn) {
      TasteHub.addToCart({ id: addBtn.dataset.id, name: addBtn.dataset.name, price: parseFloat(addBtn.dataset.price) });
      TasteHub.toast(`${addBtn.dataset.name} added to cart`);
      return;
    }
    const qtyBtn = e.target.closest('[data-cart-action]');
    if (qtyBtn) {
      const delta = qtyBtn.dataset.cartAction === 'inc' ? 1 : -1;
      TasteHub.changeQty(qtyBtn.dataset.id, delta);
    }
  });
});
