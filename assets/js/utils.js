/* =====================================================
   UTILS — Shared helpers
   ===================================================== */
var DG = DG || {};

DG.utils = (function () {

  /** Encode a path array to a hash segment string */
  function encodePath(segments) {
    return segments.map(encodeURIComponent).join('/');
  }

  /** Decode a slash-separated hash segment string to array */
  function decodePath(str) {
    return str.split('/').map(decodeURIComponent).filter(Boolean);
  }

  /** Build image URL from path array and filename */
  function buildImageUrl(pathArr, filename) {
    var base = 'products/' + pathArr.map(encodeURIComponent).join('/') + '/images/';
    return base + encodeURIComponent(filename);
  }

  /** Build category URL */
  function categoryHash(pathArr) {
    var base = DG.router ? DG.router.basePath : '';
    return base + '/category/' + encodePath(pathArr);
  }

  /** Build product URL */
  function productHash(pathArr) {
    var base = DG.router ? DG.router.basePath : '';
    return base + '/product/' + encodePath(pathArr);
  }

  /** Fetch JSON with error handling */
  function fetchJSON(url) {
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status + ': ' + url);
      return res.json();
    });
  }

  /** Fetch text with error handling */
  function fetchText(url) {
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status + ': ' + url);
      return res.text();
    });
  }

  /** Parse info.txt content into a product info object */
  function parseInfoTxt(text) {
    var info = { name: '', price: '', brand: '', description: '', specs: [], tags: [] };
    var lines = text.split('\n');
    lines.forEach(function (line) {
      line = line.trim();
      if (!line) return;
      var colon = line.indexOf(':');
      if (colon < 0) return;
      var key = line.slice(0, colon).trim();
      var val = line.slice(colon + 1).trim();
      switch (key) {
        case '名稱': info.name = val; break;
        case '售價': info.price = val; break;
        case '品牌': info.brand = val; break;
        case '說明': info.description = val; break;
        case '規格': {
          var pipe = val.indexOf('|');
          if (pipe >= 0) {
            info.specs.push({ label: val.slice(0, pipe).trim(), value: val.slice(pipe + 1).trim() });
          }
          break;
        }
        case '標籤': if (val) info.tags.push(val); break;
      }
    });
    return info;
  }

  /**
   * Assign tag CSS class based on tag text
   * Subsidy keywords → green, warranty keywords → blue, else → default
   */
  function tagClass(text) {
    var t = text.toLowerCase();
    if (t.includes('補助')) return 'tag--subsidy';
    if (t.includes('保固')) return 'tag--warranty';
    if (t.includes('新品') || t.includes('促銷')) return 'tag--orange';
    return 'tag--default';
  }

  /** Render tag pill HTML */
  function renderTag(text) {
    return '<span class="tag ' + tagClass(text) + '">' + escHtml(text) + '</span>';
  }

  /** Escape HTML special characters */
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /** Set document title */
  function setTitle(parts) {
    document.title = parts.concat(['東光醫療器材']).join(' — ');
  }

  /** Show a specific view, hide others */
  function showView(id) {
    var views = document.querySelectorAll('.view');
    views.forEach(function (v) { v.classList.remove('active'); v.hidden = true; });
    var target = document.getElementById(id);
    if (target) { target.classList.add('active'); target.hidden = false; }
  }

  /** Scroll to top of page */
  function scrollTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return {
    encodePath: encodePath,
    decodePath: decodePath,
    buildImageUrl: buildImageUrl,
    categoryHash: categoryHash,
    productHash: productHash,
    fetchJSON: fetchJSON,
    fetchText: fetchText,
    parseInfoTxt: parseInfoTxt,
    tagClass: tagClass,
    renderTag: renderTag,
    escHtml: escHtml,
    setTitle: setTitle,
    showView: showView,
    scrollTop: scrollTop
  };
})();
