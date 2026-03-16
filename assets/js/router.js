/* =====================================================
   ROUTER — Path-based routing with history.pushState
   ===================================================== */
var DG = DG || {};

DG.router = (function () {

  /**
   * Auto-detect base path.
   * GitHub Pages subdirectory:  /website/  → basePath = '/website'
   * Custom domain (root):       /           → basePath = ''
   */
  var basePath = (function () {
    var segs = window.location.pathname.split('/').filter(Boolean);
    var routeRoots = { category: 1, product: 1, search: 1 };
    if (segs.length > 0 && !routeRoots[segs[0]]) {
      return '/' + segs[0];
    }
    return '';
  })();

  var currentRoute = null;

  /** Parse current URL into { type, segments, query } */
  function parseRoute() {
    var path = window.location.pathname.slice(basePath.length).replace(/^\//, '');
    var segs = path.split('/').filter(Boolean).map(decodeURIComponent);
    var type = segs[0] || 'home';
    var rest = segs.slice(1);

    var query = {};
    (window.location.search || '').slice(1).split('&').forEach(function (pair) {
      if (!pair) return;
      var eq = pair.indexOf('=');
      if (eq >= 0) query[decodeURIComponent(pair.slice(0, eq))] = decodeURIComponent(pair.slice(eq + 1));
    });

    return { type: type, segments: rest, query: query };
  }

  /** Handle route change — dispatches to the right render function */
  function handleRoute() {
    var route = parseRoute();
    currentRoute = route;

    var bc = document.getElementById('breadcrumb');
    if (bc) bc.hidden = true;

    switch (route.type) {
      case 'home':
      case '':
        DG.catalog.showHome();
        break;
      case 'category':
        DG.catalog.showCategory(route.segments);
        break;
      case 'product':
        DG.product.show(route.segments);
        break;
      case 'search':
        DG.search.run(route.query.q || '');
        break;
      default:
        DG.catalog.showHome();
    }

    DG.utils.scrollTop();
    window.dispatchEvent(new Event('routechange'));
  }

  /** Navigate programmatically (pushState + render) */
  function navigate(url) {
    history.pushState(null, null, url);
    handleRoute();
  }

  /** Get current route */
  function getCurrent() {
    return currentRoute;
  }

  /** Initialize router */
  function init() {
    // Handle GitHub Pages 404 redirect (?p=category/行動輔具&q=...)
    var params = new URLSearchParams(window.location.search);
    var redirected = params.get('p');
    if (redirected) {
      params.delete('p');
      var qs = params.toString();
      history.replaceState(null, null, basePath + '/' + redirected + (qs ? '?' + qs : ''));
    }

    // Intercept internal link clicks — intercept by resolved a.href
    document.addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (!a || !a.href) return;
      // Skip non-http(s) links (tel:, mailto:, javascript:, etc.)
      if (!/^https?:/.test(a.href)) return;
      var url = new URL(a.href);
      // Only intercept same-origin links within the base path
      if (url.origin !== window.location.origin) return;
      var path = url.pathname;
      var isHome = path === basePath + '/' || path === basePath;
      var isAppRoute = path.startsWith(basePath + '/category/') ||
                       path.startsWith(basePath + '/product/') ||
                       path.startsWith(basePath + '/search');
      if (isHome || isAppRoute) {
        e.preventDefault();
        navigate(path + url.search);
      }
    });

    window.addEventListener('popstate', handleRoute);
    handleRoute();
  }

  return {
    init: init,
    navigate: navigate,
    parseRoute: parseRoute,
    getCurrent: getCurrent,
    basePath: basePath
  };
})();
