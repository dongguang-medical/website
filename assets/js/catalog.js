/* =====================================================
   CATALOG — Sidebar, Product Grid, Homepage
   ===================================================== */
var DG = DG || {};

DG.catalog = (function () {

  var PLACEHOLDER = 'assets/images/placeholder.svg';

  /* ── Sidebar ──────────────────────────────────────── */

  function buildSidebar(index) {
    var tree = document.getElementById('category-tree');
    var footerNav = document.getElementById('footer-nav');
    if (!tree) return;

    var html = '';
    var footerHtml = '';

    (index.categories || []).forEach(function (cat) {
      var catPath = [cat.name];
      var catHash = DG.utils.categoryHash(catPath);
      var totalCount = (cat.subcategories || []).reduce(function (sum, sub) {
        return sum + (sub.products || []).length;
      }, 0);

      html += '<div class="sidebar-cat-group">';
      html += '<div class="sidebar-cat-top">';
      html += '<a href="' + catHash + '" data-path="' + DG.utils.escHtml(catPath.join('/')) + '">';
      html += DG.utils.escHtml(cat.name);
      html += '<span class="cat-count">' + totalCount + '</span>';
      html += '</a>';
      html += '</div>';

      if (cat.subcategories && cat.subcategories.length) {
        html += '<div class="sidebar-subcat">';
        cat.subcategories.forEach(function (sub) {
          var subPath = [cat.name, sub.name];
          var subHash = DG.utils.categoryHash(subPath);
          html += '<a href="' + subHash + '" data-path="' + DG.utils.escHtml(subPath.join('/')) + '">';
          html += DG.utils.escHtml(sub.name);
          html += '<span class="cat-count">' + (sub.products || []).length + '</span>';
          html += '</a>';
        });
        html += '</div>';
      }
      html += '</div>';

      // Footer nav
      footerHtml += '<a href="' + catHash + '">' + DG.utils.escHtml(cat.name) + '</a>';
    });

    tree.innerHTML = html;
    if (footerNav) footerNav.innerHTML = footerHtml;
  }

  function updateSidebarActive(pathStr) {
    document.querySelectorAll('#category-tree a').forEach(function (a) {
      a.classList.remove('active');
    });
    if (!pathStr) return;
    var match = document.querySelector('#category-tree a[data-path="' + CSS.escape(pathStr) + '"]');
    if (match) match.classList.add('active');
  }

  /* ── Product Card HTML ────────────────────────────── */

  function productCardHtml(product) {
    var hash = DG.utils.productHash(product.path);
    var imgSrc = product.cover || PLACEHOLDER;
    var priceHtml = product.price
      ? '<p class="card-price">' + DG.utils.escHtml(product.price) + '</p>'
      : '<p class="card-price price-inquiry">歡迎洽詢</p>';
    var brandHtml = product.brand
      ? '<p class="card-brand">' + DG.utils.escHtml(product.brand) + '</p>'
      : '';
    var tagsHtml = (product.tags || []).slice(0, 3).map(DG.utils.renderTag).join('');

    return '<a class="product-card" href="' + hash + '">' +
      '<div class="card-image">' +
        '<img src="' + DG.utils.escHtml(imgSrc) + '" alt="' + DG.utils.escHtml(product.name) + '"' +
        ' loading="lazy" onerror="this.src=\'' + PLACEHOLDER + '\'">' +
      '</div>' +
      '<div class="card-body">' +
        '<h3 class="card-name">' + DG.utils.escHtml(product.name) + '</h3>' +
        brandHtml +
        priceHtml +
        (tagsHtml ? '<div class="card-tags">' + tagsHtml + '</div>' : '') +
      '</div>' +
    '</a>';
  }

  /* ── Homepage ─────────────────────────────────────── */

  function showHome() {
    DG.utils.setTitle([]);
    DG.utils.showView('view-home');
    updateSidebarActive(null);

    var showcase = document.getElementById('category-showcase');
    if (!showcase || !DG.app.index) return;

    var html = '';
    (DG.app.index.categories || []).forEach(function (cat) {
      var catHash = DG.utils.categoryHash([cat.name]);
      var totalCount = (cat.subcategories || []).reduce(function (s, sub) {
        return s + (sub.products || []).length;
      }, 0);

      html += '<div class="showcase-card">';
      html += '<div class="showcase-card-header">';
      html += '<h3>' + DG.utils.escHtml(cat.name) + '</h3>';
      html += '<p>' + totalCount + ' 項商品</p>';
      html += '</div>';
      html += '<div class="showcase-card-products">';

      // Show up to 5 products from this category
      var allProds = [];
      (cat.subcategories || []).forEach(function (sub) {
        (sub.products || []).forEach(function (p) { allProds.push(p); });
      });
      allProds.slice(0, 5).forEach(function (p) {
        html += '<a class="showcase-product-link" href="' + DG.utils.productHash(p.path) + '">';
        html += DG.utils.escHtml(p.name);
        html += '</a>';
      });

      html += '</div>';
      html += '<a class="showcase-view-all" href="' + catHash + '">查看全部 ' + cat.name + ' →</a>';
      html += '</div>';
    });

    showcase.innerHTML = html;
  }

  /* ── Category view ────────────────────────────────── */

  function showCategory(pathSegments) {
    if (!DG.app.index) return;

    var grid = document.getElementById('product-grid');
    var titleEl = document.getElementById('catalog-title');
    var countEl = document.getElementById('catalog-count');

    DG.utils.showView('view-catalog');

    // Filter products by path prefix
    var products = (DG.app.index.products || []).filter(function (p) {
      if (!p.path || p.path.length < pathSegments.length) return false;
      for (var i = 0; i < pathSegments.length; i++) {
        if (p.path[i] !== pathSegments[i]) return false;
      }
      return true;
    });

    var catLabel = pathSegments[pathSegments.length - 1] || '全部商品';
    DG.utils.setTitle([catLabel]);

    if (titleEl) titleEl.textContent = catLabel;
    if (countEl) countEl.textContent = '共 ' + products.length + ' 項商品';
    if (grid) grid.innerHTML = products.map(productCardHtml).join('');

    updateSidebarActive(pathSegments.join('/'));
    renderBreadcrumb(pathSegments, 'category');
  }

  /* ── Breadcrumb ───────────────────────────────────── */

  function renderBreadcrumb(pathSegments, type) {
    var bc = document.getElementById('breadcrumb');
    if (!bc) return;
    bc.hidden = false;

    var parts = ['<a href="' + DG.router.basePath + '/">首頁</a>'];

    if (type === 'category') {
      pathSegments.forEach(function (seg, i) {
        parts.push('<span class="breadcrumb-sep">›</span>');
        if (i < pathSegments.length - 1) {
          parts.push('<a href="' + DG.utils.categoryHash(pathSegments.slice(0, i + 1)) + '">' + DG.utils.escHtml(seg) + '</a>');
        } else {
          parts.push('<span class="breadcrumb-current">' + DG.utils.escHtml(seg) + '</span>');
        }
      });
    } else if (type === 'product') {
      // Category levels
      var catPath = pathSegments.slice(0, -1);
      catPath.forEach(function (seg, i) {
        parts.push('<span class="breadcrumb-sep">›</span>');
        parts.push('<a href="' + DG.utils.categoryHash(catPath.slice(0, i + 1)) + '">' + DG.utils.escHtml(seg) + '</a>');
      });
      // Product name
      parts.push('<span class="breadcrumb-sep">›</span>');
      parts.push('<span class="breadcrumb-current">' + DG.utils.escHtml(pathSegments[pathSegments.length - 1]) + '</span>');
    }

    bc.innerHTML = parts.join('');
  }

  return {
    buildSidebar: buildSidebar,
    updateSidebarActive: updateSidebarActive,
    productCardHtml: productCardHtml,
    showHome: showHome,
    showCategory: showCategory,
    renderBreadcrumb: renderBreadcrumb
  };
})();
