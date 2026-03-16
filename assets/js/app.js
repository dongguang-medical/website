/* =====================================================
   APP — Bootstrap: fetch index, init modules, wire events
   ===================================================== */
var DG = DG || {};

DG.app = (function () {

  var index = null;

  function init() {
    DG.utils.fetchJSON('products-index.json')
      .then(function (data) {
        DG.app.index = data;

        // Build sidebar and footer nav from data
        DG.catalog.buildSidebar(data);

        // Start router (handles initial hash)
        DG.router.init();
      })
      .catch(function (err) {
        console.error('Failed to load products-index.json:', err);
        document.getElementById('category-tree').innerHTML =
          '<p style="padding:16px;color:#c00;font-size:13px">商品資料載入失敗，請稍後再試。</p>';
        DG.utils.showView('view-home');
      });

    wireSearchUI();
    wireHamburger();
  }

  /** Search input + button wiring */
  function wireSearchUI() {
    var input = document.getElementById('search-input');
    var btn = document.getElementById('search-btn');

    function doSearch() {
      var q = (input && input.value || '').trim();
      if (q) DG.router.navigate(DG.router.basePath + '/search?q=' + encodeURIComponent(q));
    }

    if (btn) btn.addEventListener('click', doSearch);

    if (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') doSearch();
      });

      // Sync input value when navigating back to a search
      window.addEventListener('routechange', function () {
        var route = DG.router.parseRoute();
        if (route.type === 'search' && route.query.q) {
          input.value = route.query.q;
        } else if (route.type !== 'search') {
          input.value = '';
        }
      });
    }
  }

  /** Mobile hamburger sidebar toggle */
  function wireHamburger() {
    var btn = document.getElementById('hamburger-btn');
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebar-overlay');

    function openSidebar() {
      sidebar.classList.add('open');
      overlay.hidden = false;
      btn.classList.add('open');
      btn.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
      sidebar.classList.remove('open');
      overlay.hidden = true;
      btn.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    }

    if (btn) {
      btn.addEventListener('click', function () {
        if (sidebar.classList.contains('open')) closeSidebar();
        else openSidebar();
      });
    }

    if (overlay) overlay.addEventListener('click', closeSidebar);

    // Close on any navigation (mobile)
    window.addEventListener('routechange', function () {
      if (window.innerWidth < 1024) closeSidebar();
    });
  }

  return {
    init: init,
    get index() { return index; },
    set index(v) { index = v; }
  };
})();

// Bootstrap on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', DG.app.init);
} else {
  DG.app.init();
}
