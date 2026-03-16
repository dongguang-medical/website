/* =====================================================
   SEARCH — Client-side search over flat products array
   ===================================================== */
var DG = DG || {};

DG.search = (function () {

  /** Run search query and render results */
  function run(query) {
    query = (query || '').trim();

    var titleEl = document.getElementById('search-title');
    var countEl = document.getElementById('search-count');
    var grid = document.getElementById('search-grid');
    var empty = document.getElementById('search-empty');

    DG.utils.showView('view-search');
    DG.utils.setTitle(['搜尋：' + query]);
    DG.catalog.updateSidebarActive(null);

    var bc = document.getElementById('breadcrumb');
    if (bc) {
      bc.hidden = false;
      bc.innerHTML = '<a href="' + DG.router.basePath + '/">首頁</a>' +
        '<span class="breadcrumb-sep">›</span>' +
        '<span class="breadcrumb-current">搜尋「' + DG.utils.escHtml(query) + '」</span>';
    }

    if (!query) {
      DG.router.navigate(DG.router.basePath + '/');
      return;
    }

    var results = query ? filter(query) : [];

    if (titleEl) titleEl.textContent = '搜尋結果：「' + query + '」';
    if (countEl) countEl.textContent = '共 ' + results.length + ' 項商品';

    if (!results.length) {
      if (grid) grid.innerHTML = '';
      if (empty) empty.hidden = false;
    } else {
      if (empty) empty.hidden = true;
      if (grid) grid.innerHTML = results.map(DG.catalog.productCardHtml).join('');
    }
  }

  /** Filter products array by query string */
  function filter(query) {
    if (!DG.app.index || !DG.app.index.products) return [];
    return DG.app.index.products.filter(function (p) {
      return matches(p, query);
    });
  }

  /** Check if a product matches the query */
  function matches(product, query) {
    return contains(product.name, query) ||
           contains(product.brand, query) ||
           (product.tags || []).some(function (t) { return contains(t, query); }) ||
           (product.path || []).some(function (seg) { return contains(seg, query); });
  }

  function contains(str, query) {
    if (!str) return false;
    return str.toLowerCase().indexOf(query.toLowerCase()) >= 0;
  }

  return {
    run: run,
    filter: filter
  };
})();
