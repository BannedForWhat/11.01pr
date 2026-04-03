(function () {
  const isEditable = (el) =>
    el && (
      el.tagName === "INPUT" ||
      el.tagName === "TEXTAREA" ||
      el.isContentEditable ||
      (el.tagName === "SELECT")
    );

  const $body = document.body;
  const urls = {
    home: $body.dataset.urlHome,
    catalog: $body.dataset.urlCatalog,
    cart: $body.dataset.urlCart,
    checkout: $body.dataset.urlCheckout,
    filters: $body.dataset.urlFilters,
    next: $body.dataset.urlNext,
    prev: $body.dataset.urlPrev,
    adminOrders: $body.dataset.urlAdminOrders,
    toggleTheme: $body.dataset.urlToggleTheme
  };
  const role = $body.dataset.role || "guest";

  const go = (url) => { if (url) location.assign(url); };
  const focusSearch = () => {
    const search = document.querySelector('#searchInput, [name="q"], [type="search"]');
    if (search) { search.focus(); search.select?.(); }
  };
  const openFilters = () => {
    const offcanvas = document.querySelector('.offcanvas#filters, [data-filters-panel="1"]');
    if (offcanvas) {
      if (window.bootstrap?.Offcanvas) {
        const instance = bootstrap.Offcanvas.getOrCreateInstance(offcanvas);
        instance.show();
      } else {
        offcanvas.classList.add('show');
        offcanvas.style.display = 'block';
      }
      return;
    }
    const btn = document.querySelector('[data-action="open-filters"], button#openFilters');
    btn?.click();
  };
  const toggleTheme = async () => {
    document.documentElement.classList.toggle('theme-dark');
    if (urls.toggleTheme) {
      try { await fetch(urls.toggleTheme, { method: 'POST', headers: {'X-Requested-With':'XMLHttpRequest','X-CSRFToken':getCSRF()} }); } catch {}
    }
    announce('Тема переключена');
  };
  const announceRegion = (() => {
    let node = document.getElementById('hotkeys-live');
    if (!node) {
      node = document.createElement('div');
      node.id = 'hotkeys-live';
      node.setAttribute('aria-live', 'polite');
      node.className = 'visually-hidden';
      document.body.appendChild(node);
    }
    return node;
  })();
  const announce = (msg) => { announceRegion.textContent = msg; };

  const getCSRF = () => {
    const name = 'csrftoken';
    const m = document.cookie.match(new RegExp('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'));
    return m ? decodeURIComponent(m.pop()) : '';
  };

  const openHelp = () => {
    const modal = document.getElementById('hotkeysModal');
    if (!modal) return;
    if (window.bootstrap?.Modal) {
      bootstrap.Modal.getOrCreateInstance(modal).show();
    } else {
      modal.classList.add('show');
      modal.style.display = 'block';
    }
  };

  // Основные хоткеи:
  // g — каталог
  // / — фокус на поиск
  // c — корзина
  // o — оформить заказ
  // f — фильтры
  // n/p — следующая/предыдущая страница
  // t — тема (светлая/тёмная)
  // ? — помощь (шпаргалка)
  // h — домой
  // r — обновить (без кеша при Shift+R)
  // a — заказы (только менеджер/админ)

  window.addEventListener('keydown', (e) => {
    const typing = isEditable(e.target);

    const key = e.key;
    const code = e.code;
    const shift = e.shiftKey;

    if (key === '?' || (shift && key === '/')) {
      e.preventDefault();
      openHelp();
      return;
    }

    if (typing) {
      if (key === 'Escape') {
        const opened = document.querySelector('.offcanvas.show, .modal.show');
        if (opened) opened.querySelector('[data-bs-dismiss="offcanvas"], [data-bs-dismiss="modal"], .btn-close')?.click();
      }
      return;
    }

    switch (key) {
      case 'g':      e.preventDefault(); go(urls.catalog); break;
      case '/':      e.preventDefault(); focusSearch(); break;
      case 'c':      e.preventDefault(); go(urls.cart); break;
      case 'o':      e.preventDefault(); go(urls.checkout); break;
      case 'f':
        e.preventDefault();
        const panel = document.querySelector('#filters.offcanvas, .offcanvas#filters, [data-filters-panel="1"]');
        if (panel) {
            if (window.bootstrap?.Offcanvas) {
            bootstrap.Offcanvas.getOrCreateInstance(panel).show();
            } else {
            panel.classList.add('show');
            panel.style.display = 'block';
            panel.removeAttribute('aria-hidden');
            document.body.classList.add('offcanvas-backdrop', 'show');
            }
        } else {
            go(urls.filters);
        }
        break;
      case 'n':      e.preventDefault(); go(urls.next); break;
      case 'p':      e.preventDefault(); go(urls.prev); break;
      case 't':      e.preventDefault(); toggleTheme(); break;
      case 'h':      e.preventDefault(); go(urls.home); break;
      case 'r':      e.preventDefault(); shift ? location.reload(true) : location.reload(); break;
      case 'a':
        if (role === 'manager' || role === 'admin' || role === 'staff' || role === 'superuser') {
          e.preventDefault(); go(urls.adminOrders);
        }
        break;
      default:
        break;
    }
  });
})();
