/* =====================================================
   PRODUCT — Detail view: gallery, specs, tags
   ===================================================== */
var DG = DG || {};

DG.product = (function () {

  var PLACEHOLDER = 'assets/images/placeholder.svg';

  /* ── Show product detail ──────────────────────────── */

  function show(pathSegments) {
    if (!pathSegments || !pathSegments.length) {
      DG.router.navigate(DG.router.basePath + '/');
      return;
    }

    DG.utils.showView('view-product');
    DG.catalog.renderBreadcrumb(pathSegments, 'product');
    DG.catalog.updateSidebarActive(pathSegments.slice(0, -1).join('/'));

    var container = document.getElementById('product-detail-container');
    if (!container) return;

    // Show loading skeleton
    container.innerHTML = '<div class="product-detail-loading">' +
      '<div class="skeleton" style="height:300px;border-radius:10px;margin-bottom:16px"></div>' +
      '<div class="skeleton" style="height:20px;width:60%;margin-bottom:8px"></div>' +
      '<div class="skeleton" style="height:16px;width:40%"></div>' +
    '</div>';

    // Find product in index for basic info
    var indexProduct = null;
    if (DG.app.index && DG.app.index.products) {
      var idStr = pathSegments.join('/');
      DG.app.index.products.forEach(function (p) {
        if (p.id === idStr || (p.path && p.path.join('/') === idStr)) indexProduct = p;
      });
    }

    // Build info.txt URL
    var infoUrl = 'products/' + pathSegments.map(encodeURIComponent).join('/') + '/info.txt';

    DG.utils.fetchText(infoUrl)
      .then(function (text) {
        var info = DG.utils.parseInfoTxt(text);
        // Merge with index data (index has cover + imageCount)
        render(pathSegments, info, indexProduct);
      })
      .catch(function () {
        // Fallback: render with only index data
        var fallback = indexProduct ? {
          name: indexProduct.name,
          price: indexProduct.price || '',
          brand: indexProduct.brand || '',
          description: '',
          specs: [],
          tags: indexProduct.tags || []
        } : { name: pathSegments[pathSegments.length - 1], price: '', brand: '', description: '', specs: [], tags: [] };
        render(pathSegments, fallback, indexProduct);
      });
  }

  /* ── Render detail HTML ───────────────────────────── */

  function render(pathSegments, info, indexProduct) {
    var container = document.getElementById('product-detail-container');
    if (!container) return;

    var productName = info.name || (indexProduct && indexProduct.name) || pathSegments[pathSegments.length - 1];
    var price = info.price || (indexProduct && indexProduct.price) || '';
    var brand = info.brand || (indexProduct && indexProduct.brand) || '';
    var tags = info.tags.length ? info.tags : (indexProduct && indexProduct.tags) || [];
    var imageCount = indexProduct ? (indexProduct.imageCount || 1) : 1;

    DG.utils.setTitle([productName]);

    // Build image list from imageCount
    var images = [];
    for (var i = 1; i <= imageCount; i++) {
      images.push(DG.utils.buildImageUrl(pathSegments, i + '.jpg'));
    }
    if (!images.length) images.push(PLACEHOLDER);

    // Gallery HTML
    var galleryHtml = '<div class="product-gallery">' +
      '<div class="gallery-main">' +
        '<img id="gallery-main-img" src="' + DG.utils.escHtml(images[0]) + '"' +
        ' alt="' + DG.utils.escHtml(productName) + '"' +
        ' onerror="this.src=\'' + PLACEHOLDER + '\'">' +
      '</div>';

    if (images.length > 1) {
      galleryHtml += '<div class="gallery-thumbs" id="gallery-thumbs">';
      images.forEach(function (src, idx) {
        galleryHtml += '<div class="gallery-thumb' + (idx === 0 ? ' active' : '') + '"' +
          ' data-full="' + DG.utils.escHtml(src) + '"' +
          ' role="button" tabindex="0" aria-label="圖片 ' + (idx + 1) + '">' +
          '<img src="' + DG.utils.escHtml(src) + '" alt="圖片 ' + (idx + 1) + '"' +
          ' onerror="this.src=\'' + PLACEHOLDER + '\'">' +
          '</div>';
      });
      galleryHtml += '</div>';
    }
    galleryHtml += '</div>';

    // Price HTML
    var priceHtml = price
      ? '<p class="product-price">' + DG.utils.escHtml(price) + '</p>'
      : '<p class="product-price price-inquiry">歡迎洽詢</p>';

    // Tags HTML
    var tagsHtml = tags.map(DG.utils.renderTag).join('');

    // Description section
    var descHtml = '';
    if (info.description) {
      descHtml = '<div class="product-section">' +
        '<h3 class="product-section-title">商品說明</h3>' +
        '<p class="product-description">' + DG.utils.escHtml(info.description) + '</p>' +
        '</div>';
    }

    // Specs section
    var specsHtml = '';
    if (info.specs && info.specs.length) {
      var rows = info.specs.map(function (s) {
        return '<tr><th>' + DG.utils.escHtml(s.label) + '</th><td>' + DG.utils.escHtml(s.value) + '</td></tr>';
      }).join('');
      specsHtml = '<div class="product-section">' +
        '<h3 class="product-section-title">規格</h3>' +
        '<table class="specs-table"><tbody>' + rows + '</tbody></table>' +
        '</div>';
    }

    // Contact CTA
    var contactHtml = '<div class="product-contact">' +
      '<p>如需詢價、更多資訊或申請補助，歡迎直接聯絡我們</p>' +
      '<a href="tel:042405066" class="btn-primary">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91A16 16 0 0 0 16 17l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 23.73 18z"/></svg>' +
        '電話洽詢' +
      '</a>' +
    '</div>';

    // Info panel
    var infoHtml = '<div class="product-info">' +
      '<h1 class="product-name">' + DG.utils.escHtml(productName) + '</h1>' +
      (brand ? '<p class="product-brand">品牌：' + DG.utils.escHtml(brand) + '</p>' : '') +
      priceHtml +
      (tagsHtml ? '<div class="product-tags">' + tagsHtml + '</div>' : '') +
      '<hr class="product-divider">' +
      descHtml +
      specsHtml +
      contactHtml +
    '</div>';

    container.innerHTML = '<div class="product-detail">' + galleryHtml + infoHtml + '</div>';

    // Bind thumbnail clicks
    var thumbs = container.querySelectorAll('.gallery-thumb');
    var mainImg = container.querySelector('#gallery-main-img');
    thumbs.forEach(function (thumb) {
      function activate() {
        if (mainImg) {
          mainImg.style.opacity = '0.6';
          mainImg.src = thumb.dataset.full;
          mainImg.onload = function () { mainImg.style.opacity = '1'; };
        }
        thumbs.forEach(function (t) { t.classList.remove('active'); });
        thumb.classList.add('active');
      }
      thumb.addEventListener('click', activate);
      thumb.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
      });
    });

    // Render related products
    renderRelated(pathSegments, productName);
  }

  /* ── Related products ─────────────────────────────── */

  function renderRelated(pathSegments, currentName) {
    if (!DG.app.index) return;
    var container = document.getElementById('product-detail-container');
    if (!container) return;

    // Same subcategory or same top category
    var catPath = pathSegments.slice(0, -1);
    var related = (DG.app.index.products || []).filter(function (p) {
      if (!p.path) return false;
      if (p.name === currentName) return false;
      // same subcategory first
      var shareSub = catPath.length >= 2 && p.path[0] === catPath[0] && p.path[1] === catPath[1];
      var shareCat = !shareSub && p.path[0] === catPath[0];
      return shareSub || shareCat;
    }).slice(0, 4);

    if (!related.length) return;

    var html = '<div class="related-section">' +
      '<h3>相關商品</h3>' +
      '<div class="product-grid">' +
      related.map(DG.catalog.productCardHtml).join('') +
      '</div></div>';

    container.insertAdjacentHTML('beforeend', html);
  }

  return {
    show: show
  };
})();
