#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_catalog.py
────────────────
靜態商品目錄產生器（僅使用 Python 標準庫）。

讀取 content/products/<slug>.md（YAML frontmatter + Markdown 內文），產出：

  index.html（網站根目錄）       首頁＝完整商品目錄（資訊列 + 搜尋 + 九大分類 + 聯絡資訊）
  catalog/index.html            轉址頁（舊網址 → 首頁）
  catalog/search-index.json     前端搜尋用輕量索引
  category/<分類名>/index.html   分類頁（九大分類各一頁，含空分類）
  product/<slug>/index.html     商品頁（圖庫、價格、規格表、說明、CTA、麵包屑、相關商品）
  sitemap.xml                   首頁 + 分類 + 品牌 + 商品頁

用法：
  python3 scripts/build_catalog.py        # 在 repo 任意位置執行皆可

frontmatter 欄位契約（與內容編輯流程共用，勿任意更改）：
  name(必填)、category(必填，九選一)、subcategory、price、brand、
  variants(label/price 清單，多規格商品用；有填則 price 由此推導)、
  variant_label(規格表欄名，如「尺寸」)、tags(字串清單)、
  specs(label/value 清單)、images(路徑清單，相對網站根目錄)、published(預設 true)
"""

import hashlib
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

# ── 常數 ────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content" / "products"
BASE_URL = "https://dongguang-medical.github.io"

def _content_hash(paths):
    """依檔案內容算版本號。

    換行字元先正規化成 LF：Windows 的 git checkout 會把文字檔
    轉成 CRLF，CI 的 Linux 則是 LF。直接雜湊原始位元組會讓
    兩邊算出不同的號碼，產生的頁面就會來回跳。
    """
    blob = b"".join(
        (ROOT / f).read_bytes().replace(b"\r\n", b"\n")
        for f in paths if (ROOT / f).is_file()
    )
    return hashlib.md5(blob).hexdigest()[:10]


# CSS 版本號（內容雜湊）：附加於樣式連結的 ?v=，
# 樣式一有變動網址就不同，訪客瀏覽器不會再拿到舊快取
CSS_VERSION = _content_hash(
    "assets/css/" + f
    for f in ("design-system.css", "intro.css", "catalog.css", "subsidy.css")
)
# 補助試算頁的資產版本號（前端程式與 Word 範本）：只影響 /subsidy/，
# 不與全站 CSS 版本綁在一起，範本更新時才不會白白讓所有頁面的樣式失效
SUBSIDY_ASSET_VERSION = _content_hash((
    "assets/js/subsidy.js",
    "assets/templates/certificate-template.json",
))
SITE_NAME = "東光醫療器材"
SITE_NAME_FULL = "台南東光醫療器材"  # 頁首、頁尾顯示用店名
PLACEHOLDER = "assets/images/placeholder.svg"
LOGO = "assets/images/logo.png"

# 洽詢電話（全站統一使用店面實際電話）
PHONE_DISPLAY = "(06) 290-7244"
PHONE_TEL = "062907244"

# 販售藥商（東光自己）的法定資訊。每個商品都一樣，因此存在這裡由程式附在
# 各商品「法定標示」區塊下方，不逐項寫進 frontmatter。
STORE_REGULATORY = """
販售藥商：東光儀器有限公司
藥商地址：台南市東區崇德路 677、679 號
藥商許可執照字號：南市衛藥販字第6221011898號
諮詢專線：0911465368
消費者使用前應詳閱產品說明書。
"""

# 蝦皮總開關。關閉時全站不出現任何蝦皮連結（頁首資訊列、頁尾圖示、商品頁
# 下單按鈕），商品卡片的「線上可購」標記也一併隱藏——沒有可下單的去處時，
# 那個標記等於在騙人。商品的 shopee_url 資料不動，改回 True 就全部回來。
SHOPEE_ENABLED = False
SHOPEE_SHOP_URL = "https://shopee.tw/shop/8642264"

# Google Analytics 4。改追蹤碼只需改這裡，全站頁面與手刻的 about 頁一起生效。
GA_MEASUREMENT_ID = "G-JYEZY3YK74"
GA_TAG = f"""  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA_MEASUREMENT_ID}');
  </script>"""

# 九大分類（固定順序）：名稱、簡介、代表圖
CATEGORIES = [
    ("行動輔具", "輪椅、電動代步車、助行器、拐杖與相關配件"),
    ("臥床照護", "電動照護床、氣墊床、移位輔具、管路與臥床照護用品"),
    ("衛浴與居家安全", "便盆椅、洗澡椅、安全扶手、無障礙改善與沐浴清潔"),
    ("呼吸照護", "氧氣製造機、抽痰機、噴霧器、陽壓呼吸器與洗鼻器"),
    ("健康量測", "血壓計、血糖機、體溫計、血氧濃度計等居家量測儀器"),
    ("復健理療", "熱敷墊、電療機、紅外線治療儀、復健器材與護具"),
    ("照護耗材", "成人紙尿褲、看護墊、敷料人工皮、紗布棉棒等消耗品"),
    ("營養保健", "成人營養補充、特殊配方與血糖管理營養品"),
    ("其他", "診所與醫護設備、急救器材、醫療器械與居家生活用品"),
]
CATEGORY_NAMES = [c[0] for c in CATEGORIES]

# 提供方式與購買方式的合法值（與 admin/config.yml 一致）
OFFERINGS = ["線上選購", "門市洽詢"]
SUBSIDIES = ["長照2.0輔具補助", "身障輔具補助"]

PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
  <rect width="400" height="300" fill="#f0f0f0"/>
  <rect x="150" y="100" width="100" height="80" rx="8" fill="#d0d0d0"/>
  <circle cx="175" cy="125" r="15" fill="#b0b0b0"/>
  <polygon points="150,180 185,140 215,165 240,145 280,180" fill="#c0c0c0"/>
  <text x="200" y="220" font-family="sans-serif" font-size="14" fill="#999" text-anchor="middle">暫無圖片</text>
</svg>
"""


def esc(s):
    return html.escape(str(s), quote=True)


def url_path(path):
    """網站絕對路徑（percent-encode 中文），path 不含開頭斜線。"""
    return "/" + quote(path)


# ── frontmatter 解析（簡易 YAML 子集，不依賴外部套件） ──────────

_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def _strip_comment(val):
    return re.sub(r"\s+#.*$", "", val).strip()


def _scalar(val):
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def parse_frontmatter(text):
    """回傳 (dict, body)。

    支援：純量、字串清單、label/value 物件清單，以及 YAML 的區塊字串（`|`）。
    區塊字串是給整段多行文字用的（如法規標示），後台的多行輸入框存檔時也會
    寫成這個格式，因此必須讀得回來。
    """
    if not text.startswith("---"):
        return {}, text.strip()
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text.strip()

    data = {}
    cur_list = None   # 目前累積中的清單
    cur_dict = None   # 清單中累積中的物件項目
    block_key = None  # 目前累積中的區塊字串
    block_lines = []

    def close_block():
        """把累積的區塊字串收進 data，去掉尾端空行。"""
        while block_lines and not block_lines[-1].strip():
            block_lines.pop()
        data[block_key] = "\n".join(block_lines)

    for raw in lines[1:end]:
        # 區塊字串優先處理：內容裡的空行與 # 都是文字，不能當空行或註解略過
        if block_key is not None:
            if not raw.strip():
                block_lines.append("")
                continue
            if len(raw) - len(raw.lstrip(" ")) >= 2:
                block_lines.append(raw[2:])
                continue
            close_block()
            block_key, block_lines = None, []

        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        m = _KEY_RE.match(line)

        if indent == 0 and m:                       # 頂層 key
            key, val = m.group(1), _strip_comment(m.group(2))
            cur_dict = None
            if val.startswith("|"):                  # 區塊字串，內容在後續縮排行
                block_key, block_lines = key, []
                cur_list = None
                continue
            if val in ("", "[]"):
                data[key] = []                       # 可能接續清單項目
                cur_list = data[key] if val == "" else None
            else:
                data[key] = _scalar(val)
                cur_list = None
        elif line.startswith("- ") or line == "-":   # 清單項目
            if cur_list is None:
                continue
            item = line[1:].strip()
            dm = _KEY_RE.match(item)
            if dm:                                   # 物件項目（如 specs）
                cur_dict = {dm.group(1): _scalar(_strip_comment(dm.group(2)))}
                cur_list.append(cur_dict)
            else:
                cur_dict = None
                if item:
                    cur_list.append(_scalar(_strip_comment(item)))
        elif indent > 0 and m and cur_dict is not None:  # 物件的後續欄位
            cur_dict[m.group(1)] = _scalar(_strip_comment(m.group(2)))

    body = "\n".join(lines[end + 1:]).strip()
    return data, body


# ── Markdown → HTML（段落／粗體／清單／子標題） ─────────────────

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_UL_ITEM_RE = re.compile(r"^[-*]\s+")
_OL_ITEM_RE = re.compile(r"^\d+[.、]\s*")


def _inline(text):
    out = esc(text)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = _LINK_RE.sub(r'<a href="\2">\1</a>', out)
    return out


def md_to_html(md):
    if not md:
        return ""
    blocks = re.split(r"\n\s*\n", md.strip())
    parts = []
    for block in blocks:
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if all(_UL_ITEM_RE.match(ln) for ln in lines):
            items = "".join(
                f"<li>{_inline(_UL_ITEM_RE.sub('', ln))}</li>" for ln in lines)
            parts.append(f"<ul>{items}</ul>")
        elif all(_OL_ITEM_RE.match(ln) for ln in lines):
            items = "".join(
                f"<li>{_inline(_OL_ITEM_RE.sub('', ln))}</li>" for ln in lines)
            parts.append(f"<ol>{items}</ol>")
        elif lines[0].startswith("#"):
            level = min(len(lines[0]) - len(lines[0].lstrip("#")) + 1, 4)
            level = max(level, 3)  # 商品名已是 h1、區塊標題是 h2
            text = lines[0].lstrip("#").strip()
            parts.append(f"<h{level}>{_inline(text)}</h{level}>")
        else:
            parts.append("<p>" + "<br>\n".join(_inline(ln) for ln in lines) + "</p>")
    return "\n".join(parts)


def md_to_text(md, limit=150):
    """給 meta description 用的純文字摘要。"""
    text = re.sub(r"[#*>`\[\]()\-]", "", md or "")
    text = re.sub(r"\s+", "", text)
    return text[:limit]


# ── 讀取商品 ────────────────────────────────────────────

def load_taxonomy():
    """分類階層的唯一真相來源，用來驗證商品沒有用到已被更名／併走的子分類。"""
    pairs = set()
    path = ROOT / "scripts" / "data" / "taxonomy.tsv"
    if not path.is_file():
        return pairs          # 沒有階層檔時只做主分類檢查，不擋建置
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            cat, _, sub = line.partition("\t")
            pairs.add((cat.strip(), sub.strip()))
    return pairs


def load_brands():
    """{代碼: {…}}。品牌是獨立 collection，商品以代碼指向它。"""
    brands = {}
    brand_dir = ROOT / "content" / "brands"
    if not brand_dir.is_dir():
        return brands
    for md_file in sorted(brand_dir.glob("*.md")):
        fm, body = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        slug = str(fm.get("slug", "")).strip() or md_file.stem
        name = str(fm.get("name", "")).strip()
        if not name:
            print(f"⚠️  brands/{md_file.name}：缺少 name，略過", file=sys.stderr)
            continue
        brands[slug] = {
            "slug": slug,
            "name": name,
            "website": str(fm.get("website", "")).strip(),
            "asset_status": str(fm.get("asset_status", "")).strip(),
            "featured": str(fm.get("featured", "false")).strip().lower()
                        in ("true", "yes", "1"),
            "body": body,
            "url": f"/brand/{quote(slug)}/",
        }
    return brands


def load_products(brands, taxonomy=None):
    taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    products = []
    if not CONTENT_DIR.is_dir():
        print(f"⚠️  找不到 {CONTENT_DIR}", file=sys.stderr)
        return products
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        fm, body = parse_frontmatter(md_file.read_text(encoding="utf-8"))

        def s(key):
            v = fm.get(key, "")
            return v.strip() if isinstance(v, str) else ""

        published = str(fm.get("published", "true")).strip().lower()
        if published in ("false", "no", "0"):
            continue

        name = s("name")
        if not name:
            print(f"⚠️  {md_file.name}：缺少 name，略過", file=sys.stderr)
            continue

        # 分類是單一欄位「主分類/子分類」，在此拆開供頁面使用
        taxonomy_value = s("taxonomy")
        category, _, subcategory = taxonomy_value.partition("/")
        if category not in CATEGORY_NAMES:
            print(f"⚠️  {md_file.name}：分類「{taxonomy_value}」不在九大分類中，略過",
                  file=sys.stderr)
            continue
        # 子分類被更名或併走時，舊值會靜靜地在站上長出一個孤兒分頁，在此攔下
        if taxonomy and (category, subcategory) not in taxonomy:
            print(f"⚠️  {md_file.name}：子分類「{category}/{subcategory}」不在 "
                  f"taxonomy.tsv 中，可能是更名後未更新", file=sys.stderr)

        brand_slug = s("brand")
        brand = brands.get(brand_slug, {}).get("name", "")
        if brand_slug and not brand:
            print(f"⚠️  {md_file.name}：找不到品牌「{brand_slug}」，"
                  f"請確認 content/brands/ 內有對應資料", file=sys.stderr)

        specs = [d for d in fm.get("specs", []) or []
                 if isinstance(d, dict) and d.get("label")]

        # 規格與價格一對一。有 variants 時，商品的價格區間由此推導，
        # 不再另外維護上下限欄位——只有一份資料就不會對不起來。
        variants = [{"label": d["label"], "price": parse_price(d.get("price"))}
                    for d in fm.get("variants", []) or []
                    if isinstance(d, dict) and d.get("label")]
        variant_prices = [v["price"] for v in variants if v["price"] is not None]
        if variant_prices:
            price, price_max = min(variant_prices), max(variant_prices)
        else:
            price = price_max = parse_price(fm.get("price"))
        images = [str(p).lstrip("/") for p in fm.get("images", []) or []
                  if isinstance(p, str) and p.strip()]
        tags = [t for t in fm.get("tags", []) or [] if isinstance(t, str) and t]

        offering = [o for o in fm.get("offering", []) or [] if o in OFFERINGS] \
            or ["門市洽詢"]
        subsidy = [x for x in fm.get("subsidy", []) or [] if x in SUBSIDIES]

        products.append({
            "slug": md_file.stem,
            "name": name,
            "category": category,
            "subcategory": subcategory,
            # price 是數字（供排序與結構化資料），price_text 是顯示用的「NT$3,500」
            "price": price,
            "price_max": price_max,
            "price_text": format_price(price, price_max),
            "variants": variants,
            # 規格表的欄位名稱，如「尺寸」；沒填就用通用的「規格」
            "variant_label": s("variant_label") or "規格",
            # 法定標示（許可證字號、品名、持證藥商、製造廠與地址），整段原文照登。
            # 非管制品（碗盤、保健食品等）留空，前台就不顯示該區塊。
            "regulatory": str(fm.get("regulatory", "") or "").strip(),
            "brand": brand,
            "brand_slug": brand_slug if brand else "",
            "offering": offering,
            "rental_price": s("rental_price"),
            # 只在「提供方式」含網購時才有意義，商品頁據此顯示蝦皮購買按鈕
            "shopee_url": s("shopee_url"),
            # 租賃改成獨立開關，不再混在提供方式裡
            "rentable": str(fm.get("rentable", "false")).strip().lower()
                        in ("true", "yes", "1"),
            "subsidy": subsidy,
            "tags": tags,
            "specs": specs,
            "images": images,
            "featured": str(fm.get("featured", "false")).strip().lower()
                        in ("true", "yes", "1"),
            "body": body,
            "url": f"/product/{quote(md_file.stem)}/",
        })
    return products


# ── 共用頁面外框（與 index.html 形象頁同一設計語彙） ──────────────

MAPS_URL = "https://maps.app.goo.gl/oTmmQYBDbMYAwQVXA"

# 蝦皮連結片段：SHOPEE_ENABLED 為 False 時整段變空字串，版面自動收合
SHOPEE_INFOBAR_LINK = (f"""
        <a class="intro-infobar-shopee" href="{SHOPEE_SHOP_URL}" target="_blank" rel="noopener">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
          蝦皮<span class="intro-infobar-shopee-text"> 咚滋商城</span>
        </a>""" if SHOPEE_ENABLED else "")

SHOPEE_FOOTER_LINK = (f"""
          <a href="{SHOPEE_SHOP_URL}" target="_blank" rel="noopener" aria-label="蝦皮商城" title="蝦皮商城：咚滋商城">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8.2 6.2C8.2 3.9 9.9 2 12 2s3.8 1.9 3.8 4.2"/><path d="M4.5 6.2h15l1 13.6a2.2 2.2 0 0 1-2.2 2.2H5.7a2.2 2.2 0 0 1-2.2-2.2z"/><path d="M14.6 10.9c-.5-.7-1.5-1.2-2.6-1.2-1.4 0-2.6.8-2.6 1.9 0 1.2 1.1 1.6 2.6 2 1.5.4 2.8.9 2.8 2.2 0 1.2-1.3 2-2.8 2-1.2 0-2.3-.5-2.8-1.3"/></svg>
          </a>""" if SHOPEE_ENABLED else "")


def nav_links():
    # 導覽列：九大商品分類＋租賃專區（綠色強調，排在「其他」之後）；
    # 關於我們由頁尾連結（聯絡資訊已由下方橘色資訊列常駐提供）
    return ([("首頁", "/")]
            + [(c, url_path(f"category/{c}/")) for c in CATEGORY_NAMES]
            + [("租賃專區", "/rental/")])


# 主分類 → 有商品的子分類（依 taxonomy.tsv 順序），main() 載入商品後填入，
# 供導覽列下拉選單與分類頁子分類區塊共用
NAV_SUBS = {}


def compute_nav_subs(products):
    have = {(p["category"], p["subcategory"]) for p in products
            if p["subcategory"]}
    subs = {c: [] for c in CATEGORY_NAMES}
    path = ROOT / "scripts" / "data" / "taxonomy.tsv"
    if not path.is_file():
        return subs
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cat, _, sub = line.partition("\t")
        cat, sub = cat.strip(), sub.strip()
        if cat in subs and (cat, sub) in have:
            subs[cat].append(sub)
    return subs


def page_header(active_url=""):
    items = []
    for t, u in nav_links():
        classes = []
        if u == "/rental/":
            classes.append("nav-rental")
        if u == active_url:
            classes.append("active")
        cls = f' class="{" ".join(classes)}"' if classes else ""
        link = f'<a href="{u}"{cls}>{esc(t)}</a>'
        subs = NAV_SUBS.get(t, [])
        if subs:
            drop = "".join(f'<a href="{u}{quote(s)}/">{esc(s)}</a>'
                           for s in subs)
            items.append('<div class="intro-nav-item">'
                         f'{link}<div class="intro-nav-drop">{drop}</div></div>')
        else:
            items.append(f'<div class="intro-nav-item">{link}</div>')
    desktop = "\n        ".join(items)
    # 行動版：導覽列的電話按鈕在 900px 以下會隱藏，因此補一個撥號項目
    mobile = "\n    ".join(
        '<a href="{u}"{cls} onclick="closeMobileNav()">{t}</a>'.format(
            u=u, t=esc(t),
            cls=(' class="mob-home"' if u == "/"
                 else ' class="nav-rental"' if u == "/rental/" else ""))
        for t, u in nav_links())
    return f"""  <header class="intro-header">
    <div class="intro-header-inner">
      <a href="/" class="intro-logo" aria-label="{SITE_NAME_FULL} 首頁">
        <img src="/{LOGO}" alt="{SITE_NAME_FULL}" width="40" height="40">
        <div class="intro-logo-name">{SITE_NAME_FULL}</div>
      </a>
      <nav class="intro-nav" aria-label="主要導覽">
        {desktop}
      </nav>
      <button class="intro-hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    </div>
    <div class="intro-infobar">
      <div class="intro-infobar-inner">
        <a class="intro-infobar-loc" href="{MAPS_URL}" target="_blank" rel="noopener">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          崇德路677號<span class="intro-infobar-addr">（台南市立醫院對面）</span>
        </a>
        <a class="intro-infobar-tel" href="tel:{PHONE_TEL}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91A16 16 0 0 0 16 17l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 23.73 18z"/></svg>
          {PHONE_DISPLAY}
        </a>
        <a class="intro-infobar-line" href="https://line.me/ti/p/~{PHONE_TEL}" target="_blank" rel="noopener">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
          LINE<span class="intro-infobar-line-text"> {PHONE_TEL}</span>
        </a>
{SHOPEE_INFOBAR_LINK}
        <span class="intro-infobar-hours">營業 9:30–22:00（週日 10:00–17:00）</span>
      </div>
    </div>
  </header>

  <nav class="intro-nav-mobile" id="mobile-nav" aria-label="行動版導覽">
    {mobile}
  </nav>
"""


PAGE_FOOTER = f"""  <footer class="intro-footer">
    <div class="intro-footer-inner">
      <div class="intro-footer-col intro-footer-brand-col">
        <div class="intro-footer-brand">
          <img src="/{LOGO}" alt="{SITE_NAME_FULL}" loading="lazy" width="36" height="36">
          <span class="intro-footer-brand-name">{SITE_NAME_FULL}</span>
        </div>
        <div class="intro-footer-social" aria-label="社群與購物連結">
          <a href="https://line.me/ti/p/~{PHONE_TEL}" target="_blank" rel="noopener" aria-label="LINE" title="LINE：{PHONE_TEL}">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63h2.386c.346 0 .627.285.627.63 0 .349-.281.63-.63.63H17.61v1.125h1.755zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63v4.771zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63.346 0 .628.285.628.63v4.771zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.348 0 .63.285.63.63v4.141h1.756c.348 0 .629.283.629.63 0 .344-.282.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314"/></svg>
          </a>
{SHOPEE_FOOTER_LINK}
          <a class="intro-footer-social-desktop" href="https://www.facebook.com/p/%E6%9D%B1%E5%85%89%E9%86%AB%E7%99%82%E5%99%A8%E6%9D%90-100063838362289/" target="_blank" rel="noopener" aria-label="Facebook" title="Facebook：{SITE_NAME}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
          </a>
          <a class="intro-footer-social-desktop" href="mailto:t2907244@seed.net.tw" aria-label="電子信箱" title="電子信箱：t2907244@seed.net.tw">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          </a>
          <a class="intro-footer-social-mobile" href="tel:{PHONE_TEL}" aria-label="電話 {PHONE_DISPLAY}" title="電話：{PHONE_DISPLAY}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91A16 16 0 0 0 16 17l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 23.73 18z"/></svg>
          </a>
          <a class="intro-footer-social-mobile" href="{MAPS_URL}" target="_blank" rel="noopener" aria-label="門市位置" title="701 台南市東區崇德路 677 &amp; 679 號（台南市立醫院對面）">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          </a>
        </div>
        <a class="intro-footer-about intro-footer-about-desktop" href="/subsidy/">長照輔具補助試算</a>
        <a class="intro-footer-about intro-footer-about-desktop" href="/about/">關於我們</a>
      </div>
      <div class="intro-footer-col">
        <h4 class="intro-footer-contact-h4">聯絡資訊</h4>
        <div class="intro-footer-contact-row">
        <ul>
          <li class="intro-footer-phone-li">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91A16 16 0 0 0 16 17l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 23.73 18z"/></svg>
            <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a>
          </li>
          <li>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span>週一–週六 9:30–22:00</span>
          </li>
          <li>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="visibility:hidden"><circle cx="12" cy="12" r="10"/></svg>
            <span>週日 10:00–17:00</span>
          </li>
        </ul>
        </div>
      </div>
      <div class="intro-footer-col intro-footer-loc-col">
        <h4>門市位置</h4>
        <ul>
          <li>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <a href="{MAPS_URL}" target="_blank" rel="noopener">701 台南市東區崇德路 677 &amp; 679 號</a>
          </li>
          <li>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="visibility:hidden"><circle cx="12" cy="12" r="10"/></svg>
            <span>台南市立醫院對面</span>
          </li>
        </ul>
      </div>
      <div class="intro-footer-col intro-footer-map-col">
        <div class="intro-footer-map">
          <iframe
            src="https://maps.google.com/maps?q=%E6%9D%B1%E5%85%89%E5%84%80%E5%99%A8%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8&t=&z=16&ie=UTF8&iwloc=&output=embed"
            title="{SITE_NAME}門市位置地圖"
            loading="lazy"
            referrerpolicy="no-referrer-when-downgrade"></iframe>
        </div>
      </div>
    </div>
    <div class="intro-footer-bottom">
      <span>© 台南東光醫療器材醫療輔具租賃. All Rights Reserved.</span>
    </div>
  </footer>
"""

NAV_JS = """  <script>
    var hamburger = document.getElementById('hamburger');
    var mobileNav = document.getElementById('mobile-nav');
    hamburger.addEventListener('click', function () {
      var isOpen = mobileNav.classList.toggle('open');
      hamburger.setAttribute('aria-expanded', isOpen);
    });
    function closeMobileNav() {
      mobileNav.classList.remove('open');
      hamburger.setAttribute('aria-expanded', 'false');
    }
    document.addEventListener('click', function (e) {
      if (!hamburger.contains(e.target) && !mobileNav.contains(e.target)) closeMobileNav();
    });
    mobileNav.addEventListener('click', function (e) {
      if (e.target === mobileNav) closeMobileNav();
    });

    /* 向下捲動收起頁首、向上捲動顯示 */
    var siteHeader = document.querySelector('.intro-header');
    var lastScrollY = window.scrollY;
    window.addEventListener('scroll', function () {
      var y = window.scrollY;
      if (mobileNav.classList.contains('open')) { lastScrollY = y; return; }
      if (y > lastScrollY && y > 140) {
        siteHeader.classList.add('header-hidden');
      } else if (y < lastScrollY - 2 || y <= 140) {
        siteHeader.classList.remove('header-hidden');
      }
      lastScrollY = y;
    }, { passive: true });
  </script>
"""


GA_EVENTS_JS = """  <script>
    // GA4 的加強型評估會自動記錄外部連結點擊，但 tel: 不算外部連結、不會被
    // 記錄——而撥電話正是本站最主要的成交動作，所以在這裡自己送。
    (function () {
      var PATTERNS = [
        [/^tel:/i, 'phone_call'],
        [/(line\\.me|lin\\.ee)/i, 'line_click'],
        [/shopee\\./i, 'shopee_click'],
        [/(maps\\.app\\.goo\\.gl|google\\.[a-z.]+\\/maps)/i, 'map_click']
      ];
      var h1 = document.querySelector('h1');
      var pageName = (h1 ? h1.textContent : document.title).trim();
      document.addEventListener('click', function (e) {
        var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
        if (!a || typeof gtag !== 'function') return;
        var href = a.getAttribute('href') || '';
        for (var i = 0; i < PATTERNS.length; i++) {
          if (PATTERNS[i][0].test(href)) {
            gtag('event', PATTERNS[i][1], { page_name: pageName });
            return;
          }
        }
      }, { passive: true });
    })();
  </script>
"""


def render_page(*, title, description, path, og_type, og_image, jsonld,
                main_html, extra_js="", active_url="", extra_head=""):
    """組出完整 HTML 頁面。path 為不含開頭斜線的網站路徑（用於 canonical）。"""
    canonical = BASE_URL + url_path(path)
    jsonld_tag = ""
    if jsonld:
        jsonld_tag = ('<script type="application/ld+json">\n'
                      + json.dumps(jsonld, ensure_ascii=False, indent=2)
                      + "\n  </script>")
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
{GA_TAG}
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{canonical}">{extra_head}

  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="台南東光儀器有限公司">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:url" content="{canonical}">

  <link rel="icon" href="/favicon.ico">
  {jsonld_tag}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/design-system.css?v={CSS_VERSION}">
  <link rel="stylesheet" href="/assets/css/intro.css?v={CSS_VERSION}">
  <link rel="stylesheet" href="/assets/css/catalog.css?v={CSS_VERSION}">
</head>
<body>

{page_header(active_url)}
  <main class="cat-main">
{main_html}
  </main>

{PAGE_FOOTER}
{NAV_JS}{GA_EVENTS_JS}{extra_js}
</body>
</html>
"""


# ── 片段：麵包屑、商品卡片 ─────────────────────────────────

def breadcrumb(items):
    """items: [(text, url|None)]，最後一項為目前頁。"""
    parts = []
    for i, (text, url) in enumerate(items):
        if i:
            parts.append('<span class="cat-bc-sep">›</span>')
        if url:
            parts.append(f'<a href="{url}">{esc(text)}</a>')
        else:
            parts.append(f'<span class="cat-bc-current">{esc(text)}</span>')
    return ('<nav class="cat-breadcrumb" aria-label="麵包屑">'
            + "".join(parts) + "</nav>")


def breadcrumb_jsonld(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": text,
                **({"item": BASE_URL + url} if url else {}),
            }
            for i, (text, url) in enumerate(items)
        ],
    }


def cover_of(product):
    return product["images"][0] if product["images"] else PLACEHOLDER


def parse_price(raw):
    """把 frontmatter 的售價轉成整數。

    後台現在填純數字，但舊資料是「NT$3,500」這種字串，兩種都要吃得下。
    取不到數字回傳 None（網站顯示「歡迎洽詢」）。
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def format_price(value, value_max=None):
    """數字轉成網站上顯示的樣子；幣別固定台幣，由這裡統一加上。

    多規格商品（不同尺寸／型號不同價）傳入 value_max 即顯示為區間，
    上限沒填或不大於下限時退回單一價格。
    """
    if value is None:
        return ""
    if value_max is not None and value_max > value:
        return f"NT${value:,}～{value_max:,}"
    return f"NT${value:,}"


def price_html(product, big=False):
    cls = "cat-product-price" if big else "cat-card-price"
    if product["price_text"]:
        return f'<div class="{cls}">{esc(product["price_text"])}</div>'
    return f'<div class="{cls} cat-price-ask">歡迎洽詢</div>'


def badge_spans(product):
    """租賃／補助等關鍵標記。與一般標籤同列同尺寸，僅「可租賃」以實心橘突出。"""
    marks = []
    if product["rentable"]:
        marks.append('<span class="cat-badge cat-badge-rent">可租賃</span>')
    # 蝦皮關閉時站上沒有任何可下單的去處，再標「線上可購」等於誤導
    if SHOPEE_ENABLED and "線上選購" in product["offering"]:
        marks.append('<span class="cat-badge cat-badge-online">線上可購</span>')
    if product["subsidy"]:
        marks.append('<span class="cat-badge cat-badge-subsidy">可申請補助</span>')
    return marks


def product_card(product):
    # 標記與行銷標籤合併為同一列 pill，行銷標籤最多兩個避免過長
    pills = badge_spans(product)
    plain = [t for t in product["tags"] if t not in ("可租賃", "可申請補助")]
    pills += [f'<span class="cat-tag">{esc(t)}</span>' for t in plain[:2]]
    tags = f'<div class="cat-tags">{"".join(pills)}</div>' if pills else ""
    brand = (f'<div class="cat-card-brand">{esc(product["brand"])}</div>'
             if product["brand"] else "")
    return f"""<a class="cat-card" href="{product['url']}">
  <div class="cat-card-photo">
    <img src="{url_path(cover_of(product))}" alt="{esc(product['name'])}" loading="lazy" width="400" height="300">
  </div>
  <div class="cat-card-body">
    <h3>{esc(product['name'])}</h3>
    {brand}
    {tags}
    {price_html(product)}
  </div>
</a>"""


# ── 各頁面產生 ──────────────────────────────────────────

CATALOG_SEARCH_JS = """  <script>
    (function () {
      var input = document.getElementById('cat-search-input');
      if (!input) return;
      var browse = document.getElementById('cat-browse');
      var extras = document.querySelectorAll('.search-hide');
      var resultsWrap = document.getElementById('cat-search-results');
      var grid = document.getElementById('cat-results-grid');
      var empty = document.getElementById('cat-no-results');
      var index = null;

      function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
          return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
      }

      function card(p) {
        var tags = (p.tags || []).filter(function (t) {
          return t !== '可租賃' && t !== '可申請補助';
        }).slice(0, 2).map(function (t) {
          return '<span class="cat-tag">' + esc(t) + '</span>';
        }).join('');
        var badges = '';
        if (p.rentable) {
          badges += '<span class="cat-badge cat-badge-rent">可租賃</span>';
        }
        if (SHOPEE_ENABLED && (p.offering || []).indexOf('線上選購') !== -1) {
          badges += '<span class="cat-badge cat-badge-online">線上可購</span>';
        }
        if ((p.subsidy || []).length) {
          badges += '<span class="cat-badge cat-badge-subsidy">可申請補助</span>';
        }
        return '<a class="cat-card" href="' + esc(p.url) + '">'
          + '<div class="cat-card-photo"><img src="' + esc(p.image) + '" alt="' + esc(p.name) + '" loading="lazy" width="400" height="300"></div>'
          + '<div class="cat-card-body"><h3>' + esc(p.name) + '</h3>'
          + (p.brand ? '<div class="cat-card-brand">' + esc(p.brand) + '</div>' : '')
          + ((badges || tags) ? '<div class="cat-tags">' + badges + tags + '</div>' : '')
          + (p.price_text ? '<div class="cat-card-price">' + esc(p.price_text) + '</div>'
                     : '<div class="cat-card-price cat-price-ask">歡迎洽詢</div>')
          + '</div></a>';
      }

      function run() {
        var q = input.value.trim().toLowerCase();
        if (!q) {
          resultsWrap.hidden = true;
          browse.hidden = false;
          extras.forEach(function (el) { el.hidden = false; });
          return;
        }
        if (!index) return;
        var hits = index.filter(function (p) {
          var hay = [p.name, p.brand, p.category, p.subcategory]
            .concat(p.tags || []).join(' ').toLowerCase();
          return q.split(/\\s+/).every(function (w) { return hay.indexOf(w) !== -1; });
        });
        grid.innerHTML = hits.map(card).join('');
        empty.hidden = hits.length > 0;
        grid.hidden = hits.length === 0;
        resultsWrap.hidden = false;
        browse.hidden = true;
        extras.forEach(function (el) { el.hidden = true; });
        reportSearch(q, hits.length);
      }

      // 搜尋是純前端的，GA4 內建的站內搜尋追蹤（看網址參數）抓不到，得自己送。
      // run() 每敲一個字就跑一次，等停手再送，否則「輪椅」會拆成兩三筆。
      // results_count 為 0 的關鍵字最有價值：那是客人想買而店裡沒有的東西。
      var searchTimer;
      function reportSearch(term, count) {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          if (typeof gtag === 'function') {
            gtag('event', 'search', { search_term: term, results_count: count });
          }
        }, 1200);
      }

      input.addEventListener('input', function () {
        if (index) { run(); return; }
        fetch('/catalog/search-index.json')
          .then(function (r) { return r.json(); })
          .then(function (d) { index = d.products || []; run(); })
          .catch(function () {});
      });
    })();
  </script>
""".replace("SHOPEE_ENABLED", "true" if SHOPEE_ENABLED else "false")
# ↑ 這段是普通字串不是 f-string（內含大量 JS 大括號），故以字面替換注入開關值


# 目前未使用：首頁聯絡資訊區塊已移除（資訊整合至頁尾）。
# 若要復原，把 {HOME_CONTACT_HTML} 插回 build_home_page 的頁面組裝字串即可。
HOME_CONTACT_HTML = f"""    <section class="intro-section home-screen3" id="contact">
      <div class="intro-container">
        <div class="intro-heading">
          <h2>歡迎來電或親自到訪</h2>
          <p>位於台南市立醫院對面，交通便利，歡迎您攜帶家人前來了解適合的器材方案</p>
        </div>
        <div class="intro-contact-grid">

          <div class="intro-contact-cards">

            <a href="tel:{PHONE_TEL}" class="intro-cc-card intro-cc-card-link">
              <div class="intro-cc-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91A16 16 0 0 0 16 17l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 23.73 18z"/></svg>
              </div>
              <div class="intro-cc-body">
                <h4>洽詢電話</h4>
                <p class="intro-cc-main">{PHONE_DISPLAY}</p>
              </div>
            </a>

            <div class="intro-cc-card intro-cc-hours">
              <div class="intro-cc-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              </div>
              <div class="intro-cc-body">
                <h4>營業時間</h4>
                <div class="intro-hours-rows">
                  <div class="intro-hours-row">
                    <span class="intro-hours-day">週一 – 週六</span>
                    <span class="intro-hours-time">9:30 – 22:00</span>
                  </div>
                  <div class="intro-hours-row">
                    <span class="intro-hours-day">週日</span>
                    <span class="intro-hours-time">10:00 – 17:00</span>
                  </div>
                </div>
              </div>
            </div>

            <a href="https://line.me/ti/p/~{PHONE_TEL}" target="_blank" rel="noopener" class="intro-cc-card intro-cc-card-link">
              <div class="intro-cc-icon intro-cc-icon-line">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M22 10.2C22 5.4 17.5 1.5 12 1.5S2 5.4 2 10.2c0 4.3 3.8 8 9.1 8.6.4.1.9.3 1 .6.1.3.1.7 0 1l-.2.9c-.1.3-.3 1.3 1.1.7 1.4-.6 7.6-4.5 10.4-7.6 1.9-2.1 2.6-4.2 2.6-4.2z"/></svg>
              </div>
              <div class="intro-cc-body">
                <h4>LINE</h4>
                <p class="intro-cc-main">ID: {PHONE_TEL}</p>
              </div>
            </a>

            <a href="https://shopee.tw/shop/8642264" target="_blank" rel="noopener" class="intro-cc-card intro-cc-card-link">
              <div class="intro-cc-icon intro-cc-icon-shopee">
                <img src="/assets/images/shopee-icon.png" alt="" width="22" height="22" style="object-fit:contain;">
              </div>
              <div class="intro-cc-body">
                <h4>蝦皮商城</h4>
                <p class="intro-cc-main">咚滋商城</p>
              </div>
            </a>

            <a href="https://www.facebook.com/p/%E6%9D%B1%E5%85%89%E9%86%AB%E7%99%82%E5%99%A8%E6%9D%90-100063838362289/" target="_blank" rel="noopener" class="intro-cc-card intro-cc-card-link">
              <div class="intro-cc-icon intro-cc-icon-fb">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
              </div>
              <div class="intro-cc-body">
                <h4>Facebook</h4>
                <p class="intro-cc-main">{SITE_NAME}</p>
              </div>
            </a>

            <a href="mailto:t2907244@seed.net.tw" class="intro-cc-card intro-cc-card-link">
              <div class="intro-cc-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
              </div>
              <div class="intro-cc-body">
                <h4>電子信箱</h4>
                <p class="intro-cc-main">t2907244@seed.net.tw</p>
              </div>
            </a>

          </div>

          <div class="intro-contact-right">
            <a href="{MAPS_URL}" target="_blank" rel="noopener" class="intro-map-address intro-map-address-link">
              <div class="intro-cc-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              </div>
              <div>
                <h4>地址</h4>
                <p>701 台南市東區崇德路 677 &amp; 679 號</p>
                <span class="intro-cc-landmark">📍 台南市立醫院對面</span>
              </div>
            </a>
            <div class="intro-map">
              <iframe
                src="https://maps.google.com/maps?q=%E6%9D%B1%E5%85%89%E5%84%80%E5%99%A8%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8&t=&z=17&ie=UTF8&iwloc=&output=embed"
                title="東光醫療器材地址地圖"
                loading="lazy"
                referrerpolicy="no-referrer-when-downgrade"
                allowfullscreen>
              </iframe>
            </div>
          </div>

        </div>
      </div>
    </section>
"""

HOME_JSONLD_STORE = {
    "@type": "MedicalSupplyStore",
    "name": "台南東光儀器有限公司",
    "alternateName": SITE_NAME,
    "url": BASE_URL + "/",
    "logo": f"{BASE_URL}/{LOGO}",
    "image": f"{BASE_URL}/{LOGO}",
    "description": "東光醫療器材醫療輔具租賃，秉持認真、負責、專業的態度超過二十年",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "崇德路677號",
        "addressLocality": "東區",
        "addressRegion": "台南市",
        "postalCode": "701",
        "addressCountry": "TW",
    },
    "telephone": "+886-6-290-7244",
    "email": "t2907244@seed.net.tw",
    "openingHoursSpecification": [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday",
                          "Friday", "Saturday"],
            "opens": "09:30",
            "closes": "22:00",
        },
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": "Sunday",
            "opens": "10:00",
            "closes": "17:00",
        },
    ],
}


FEATURED_FALLBACK_COUNT = 8

CAROUSEL_JS = """  <script>
    (function () {
      document.querySelectorAll('.carousel-wrap').forEach(function (wrap) {
        var track = wrap.querySelector('.home-carousel');
        var prev = wrap.querySelector('.car-prev');
        var next = wrap.querySelector('.car-next');
        if (!track || !prev || !next) return;
        if (track.scrollWidth <= track.clientWidth + 4) {
          prev.style.display = 'none';
          next.style.display = 'none';
          return;
        }
        function step() {
          var card = track.querySelector('.cat-card');
          return (card ? card.offsetWidth + 14 : 254) * 2;
        }
        prev.addEventListener('click', function () {
          track.scrollBy({ left: -step(), behavior: 'smooth' });
        });
        next.addEventListener('click', function () {
          track.scrollBy({ left: step(), behavior: 'smooth' });
        });
      });
    })();
  </script>
"""

def pick_featured(products):
    """frontmatter featured: true 的商品；不足時以「可租賃且有標價」遞補。

    首頁輪播只放有圖的商品——擺一整排 placeholder 沒有意義，
    標了 featured 但還沒補圖的商品會自動略過，補上圖之後就會回到輪播。
    """
    feats = [p for p in products if p["featured"] and p["images"]]
    if len(feats) < FEATURED_FALLBACK_COUNT:
        # 多層備援：可租賃且有標價 → 有標價 → 只要有圖。
        # 資料尚在補建時（如 rentable 全空）輪播才不會整個開天窗。
        with_img = [p for p in products if p not in feats and p["images"]]
        # 優先序：可租賃且有標價 → 有標價 → 只要有圖。三層相接後去重，
        # 而不是取第一個非空的清單——否則高優先層只有一兩項時輪播會塌掉。
        seen, pool = set(), []
        for p in ([p for p in with_img if p["rentable"] and p["price"]]
                  + [p for p in with_img if p["price"]]
                  + with_img):
            if p["slug"] not in seen:
                seen.add(p["slug"])
                pool.append(p)
        # 依主分類輪流取，避免整排都是同一類商品——照檔名順序直接取前 N 筆
        # 會讓輪播全是 bedcare-*，首頁看起來像只賣臥床用品。
        buckets = {}
        for p in pool:
            buckets.setdefault(p["category"], []).append(p)
        order = [c for c in CATEGORY_NAMES if c in buckets]
        need = FEATURED_FALLBACK_COUNT - len(feats)
        while need > 0 and order:
            for cat in list(order):
                if not buckets[cat]:
                    order.remove(cat)
                    continue
                feats.append(buckets[cat].pop(0))
                need -= 1
                if need == 0:
                    break
    return feats


def build_home_page(products):
    """首頁：資訊列（醫院對面）→ 搜尋 → 熱銷輪播 → 分類卡 → 聯絡資訊。"""
    featured = pick_featured(products)
    carousel = "\n".join(product_card(p) for p in featured)
    feat_section = ""
    if featured:
        feat_section = f"""        <section class="home-feat" id="featured">
          <div class="cat-cat-head">
            <h2>熱銷精選</h2>
          </div>
          <div class="carousel-wrap">
            <button class="car-prev" aria-label="上一批">‹</button>
            <div class="home-carousel" id="feat-carousel">
{carousel}
            </div>
            <button class="car-next" aria-label="下一批">›</button>
          </div>
        </section>"""

    cat_counts = {c: sum(1 for p in products if p["category"] == c)
                  for c in CATEGORY_NAMES}

    CAT_ICONS = {
        "行動輔具": '<circle cx="7" cy="17" r="4"/><circle cx="17" cy="19" r="2"/><path d="M7 13V5h2l5 6h3l2 4"/>',
        "臥床照護": '<path d="M2 17V7"/><path d="M2 13h20v4"/><path d="M2 11h7a3 3 0 0 1 3 3"/><circle cx="6" cy="9" r="1.6"/>',
        "衛浴與居家安全": '<path d="M4 12h16v2a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6z"/><path d="M6 12V6a3 3 0 0 1 6 0"/><path d="M15 8l1.5-1.5M17 11l2-.5M16 5l.5-2"/>',
        "呼吸照護": '<path d="M9 4v8a4 4 0 0 1-8 0"/><path d="M15 4v8a4 4 0 0 0 8 0"/><path d="M12 3v12"/><circle cx="12" cy="18" r="2.4"/>',
        "健康量測": '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
        "復健理療": '<path d="M6 3v18M18 3v18"/><path d="M6 8h12M6 16h12"/>',
        "照護耗材": '<path d="M4 8l8-5 8 5v8l-8 5-8-5z"/><path d="M4 8l8 5 8-5M12 13v8"/>',
        "營養保健": '<rect x="7" y="8" width="10" height="13" rx="3"/><path d="M9 8V5h6v3M9 13h6"/>',
        "其他": '<circle cx="5" cy="5" r="2"/><circle cx="12" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="12" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>',
    }

    def cat_icon_sm(name):
        """分類名稱左側的小圖示。"""
        path = CAT_ICONS.get(name, "")
        return (f'<span class="intro-cat-ic-sm"><svg width="17" height="17" viewBox="0 0 24 24" '
                f'fill="none" stroke="currentColor" stroke-width="1.9" '
                f'stroke-linecap="round" stroke-linejoin="round">{path}</svg></span>')

    def cat_chips(name):
        """子分類標籤：清楚示意每類實際有哪些品項（最多五個，其餘 +N）。"""
        subs = NAV_SUBS.get(name, [])
        if not subs:
            return ""
        shown = subs[:5]
        more = (f'<span class="intro-cat-chip intro-cat-chip-more">+{len(subs)-5}</span>'
                if len(subs) > 5 else "")
        return ('<span class="intro-cat-chips">'
                + "".join(f'<span class="intro-cat-chip">{esc(s)}</span>' for s in shown)
                + more + "</span>")

    cat_cards = "\n".join(f"""          <a class="intro-cat-card" href="{url_path(f"category/{name}/")}">
            <h3>{cat_icon_sm(name)}{esc(name)}<span class="intro-cat-count">{cat_counts[name]} 項</span></h3>
            {cat_chips(name)}
            <span class="intro-cat-more">瀏覽商品 →</span>
          </a>""" for name, desc in CATEGORIES)

    main = f"""    <div class="cat-section home-screen1">
      <div class="cat-container">
        <div class="cat-page-head home-hero-head">
          <img src="/{LOGO}" alt="" class="home-hero-logo" width="84" height="84">
          <h1>台南東光醫療器材</h1>
          <p class="home-hero-tag">醫療輔具租賃及販售｜超過二十年在地服務</p>
        </div>
        <div class="cat-search">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="search" id="cat-search-input" placeholder="搜尋商品名稱、品牌或標籤…" aria-label="搜尋商品">
        </div>
        <div id="cat-search-results" hidden>
          <div class="cat-grid" id="cat-results-grid"></div>
          <div class="cat-empty" id="cat-no-results" hidden>找不到符合的商品，歡迎來電 <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a> 詢問，門市品項更齊全。</div>
        </div>
        <div id="cat-browse">
{feat_section}
        </div>
      </div>
    </div>

    <div class="cat-section home-screen2 search-hide" id="categories">
      <div class="cat-container">
        <section class="home-cats">
          <div class="cat-cat-head">
            <h2>商品分類</h2>
          </div>
          <div class="intro-cat-grid">
{cat_cards}
          </div>
        </section>
      </div>
    </div>
"""
    desc = ("東光醫療器材（台南市立醫院對面）醫療輔具租賃及販售：輪椅、電動床、"
            "氣墊床、製氧機、安全扶手等九大類商品含價格，超過二十年在地服務，"
            f"電話 {PHONE_DISPLAY}。")
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            HOME_JSONLD_STORE,
            {
                "@type": "WebSite",
                "name": "台南東光儀器有限公司",
                "url": BASE_URL + "/",
            },
        ],
    }
    html_out = render_page(
        title=f"{SITE_NAME} — 醫療輔具租賃及販售｜台南市立醫院對面",
        description=desc,
        path="",
        og_type="website",
        og_image=f"{BASE_URL}/{LOGO}",
        jsonld=jsonld,
        main_html=main,
        extra_js=CATALOG_SEARCH_JS + CAROUSEL_JS,
        extra_head='\n  <meta name="google-site-verification" '
                   'content="c2vod6zryQNa5_kj1qKnbEpmSReGXSjPSgtubfUTuUw">',
    )
    (ROOT / "index.html").write_text(html_out, encoding="utf-8")


def build_catalog_redirect():
    """/catalog/ 併入首頁後保留轉址，避免外部舊連結 404。
    search-index.json 仍放在 /catalog/ 下，由 build_search_index 產生。"""
    html_out = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <title>商品目錄 — {SITE_NAME}</title>
  <meta http-equiv="refresh" content="0; url=/">
  <link rel="canonical" href="{BASE_URL}/">
</head>
<body>
  <p>商品目錄已併入首頁，<a href="/">點此前往</a>。</p>
</body>
</html>
"""
    out = ROOT / "catalog" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")


def build_category_pages(products):
    for cat_name, cat_desc in CATEGORIES:
        items = [p for p in products if p["category"] == cat_name]
        cat_url = url_path(f"category/{cat_name}/")
        subs = NAV_SUBS.get(cat_name, [])
        if items and subs:
            # 依子分類分區（taxonomy 順序），提供 #錨點 給導覽下拉選單
            blocks = []
            grouped = set()
            for sub in subs:
                sub_items = [p for p in items if p["subcategory"] == sub]
                grouped.update(p["slug"] for p in sub_items)
                sub_url = url_path(f"category/{cat_name}/{sub}/")
                blocks.append(f"""<section class="cat-cat-block" id="{esc(sub)}">
  <div class="cat-cat-head">
    <h2><a href="{sub_url}">{esc(sub)}</a><span class="cat-cat-sub">{len(sub_items)} 項</span></h2>
    <a class="cat-cat-more" href="{sub_url}">查看全部 →</a>
  </div>
  <div class="carousel-wrap">
    <button class="car-prev" aria-label="上一批">‹</button>
    <div class="home-carousel cat-sub-carousel">
{chr(10).join(product_card(p) for p in sub_items)}
    </div>
    <button class="car-next" aria-label="下一批">›</button>
  </div>
</section>""")
            rest = [p for p in items if p["slug"] not in grouped]
            if rest:
                blocks.append(f"""<section class="cat-cat-block">
  <div class="cat-cat-head">
    <h2>其他品項<span class="cat-cat-sub">{len(rest)} 項</span></h2>
  </div>
  <div class="carousel-wrap">
    <button class="car-prev" aria-label="上一批">‹</button>
    <div class="home-carousel cat-sub-carousel">
{chr(10).join(product_card(p) for p in rest)}
    </div>
    <button class="car-next" aria-label="下一批">›</button>
  </div>
</section>""")
            content = "\n".join(blocks)
        elif items:
            content = ('<div class="cat-grid">'
                       + "\n".join(product_card(p) for p in items)
                       + "</div>")
        else:
            content = (f'<div class="cat-empty">此分類商品陸續上架中，門市備有多款現貨。<br>'
                       f'歡迎來電 <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a> 洽詢庫存與租賃方案。</div>')

        bc = [("商品分類", "/#categories"), (cat_name, None)]
        main = f"""    <div class="cat-section">
      <div class="cat-container">
        {breadcrumb(bc)}
        {content}
      </div>
    </div>
"""
        desc = (f"東光醫療器材{cat_name}商品目錄：{cat_desc}。"
                f"台南醫療輔具租賃與販售，歡迎來電 {PHONE_DISPLAY} 洽詢。")
        jsonld = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": f"{cat_name} — {SITE_NAME}",
                    "url": BASE_URL + cat_url,
                    "description": desc,
                },
                breadcrumb_jsonld(bc),
            ],
        }
        html_out = render_page(
            title=f"{cat_name} — {SITE_NAME}",
            description=desc,
            path=f"category/{cat_name}/",
            og_type="website",
            og_image=f"{BASE_URL}/{LOGO}",
            jsonld=jsonld,
            main_html=main,
            extra_js=CAROUSEL_JS,
            active_url=cat_url,
        )
        out = ROOT / "category" / cat_name / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_out, encoding="utf-8")


def build_subcategory_pages(products):
    """子分類獨立頁（導覽下拉選單的落點）：category/<主分類>/<子分類>/"""
    for cat_name in CATEGORY_NAMES:
        cat_url = url_path(f"category/{cat_name}/")
        for sub in NAV_SUBS.get(cat_name, []):
            items = [p for p in products
                     if p["category"] == cat_name and p["subcategory"] == sub]
            sub_url = url_path(f"category/{cat_name}/{sub}/")
            content = ('<div class="cat-grid">'
                       + "\n".join(product_card(p) for p in items)
                       + "</div>")
            bc = [("商品分類", "/#categories"), (cat_name, cat_url), (sub, None)]
            main = f"""    <div class="cat-section">
      <div class="cat-container">
        {breadcrumb(bc)}
        {content}
      </div>
    </div>
"""
            desc = (f"東光醫療器材{cat_name}／{sub}商品目錄，共 {len(items)} 項。"
                    f"台南醫療輔具租賃與販售，歡迎來電 {PHONE_DISPLAY} 洽詢。")
            jsonld = {
                "@context": "https://schema.org",
                "@graph": [
                    {
                        "@type": "CollectionPage",
                        "name": f"{sub}（{cat_name}）— {SITE_NAME}",
                        "url": BASE_URL + sub_url,
                        "description": desc,
                    },
                    breadcrumb_jsonld(bc),
                ],
            }
            html_out = render_page(
                title=f"{sub}（{cat_name}）— {SITE_NAME}",
                description=desc,
                path=f"category/{cat_name}/{sub}/",
                og_type="website",
                og_image=f"{BASE_URL}/{LOGO}",
                jsonld=jsonld,
                main_html=main,
                active_url=cat_url,
            )
            out = ROOT / "category" / cat_name / sub / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html_out, encoding="utf-8")


def build_rental_page(products):
    """租賃專區：跨分類集中所有可租賃品項（首頁租賃入口的落點）。"""
    items = [p for p in products if p["rentable"]]
    by_cat = [(c, [p for p in items if p["category"] == c])
              for c in CATEGORY_NAMES]
    blocks = []
    for cat_name, cat_items in by_cat:
        if not cat_items:
            continue
        blocks.append(f"""<section class="cat-cat-block">
  <div class="cat-cat-head">
    <h2>{esc(cat_name)}</h2>
  </div>
  <div class="cat-grid">
{chr(10).join(product_card(p) for p in cat_items)}
  </div>
</section>""")

    body = "\n".join(blocks) if blocks else (
        f'<div class="cat-empty">租賃品項調整中，歡迎來電 '
        f'<a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a> 洽詢。</div>')

    bc = [("首頁", "/"), ("租賃專區", None)]
    main = f"""    <div class="cat-section">
      <div class="cat-container">
        {breadcrumb(bc)}
        <h1 class="visually-hidden">租賃專區</h1>
        <div class="cat-rental-note">
          <p><strong>租賃流程</strong>：來電說明需求 → 專人評估機型 →
             送貨到府並教學操作 → 租期結束回收消毒。台南市區可到府服務。</p>
        </div>
        {body}
      </div>
    </div>
"""
    desc = ("東光醫療器材租賃專區：電動照護床、氣墊床、輪椅、氧氣製造機、抽痰機等"
            "醫療輔具租賃，台南在地服務、到府送貨教學，可協助申請長照補助。")
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "name": f"租賃專區 — {SITE_NAME}",
                "url": BASE_URL + "/rental/",
                "description": desc,
            },
            breadcrumb_jsonld(bc),
        ],
    }
    html_out = render_page(
        title=f"醫療輔具租賃 — {SITE_NAME}",
        description=desc,
        path="rental/",
        og_type="website",
        og_image=f"{BASE_URL}/{LOGO}",
        jsonld=jsonld,
        main_html=main,
        active_url="/rental/",
    )
    out = ROOT / "rental" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")


GALLERY_JS = """  <script>
    (function () {
      var main = document.getElementById('cat-gallery-img');
      var thumbs = document.querySelectorAll('.cat-gallery-thumbs button');
      thumbs.forEach(function (btn) {
        btn.addEventListener('click', function () {
          main.src = btn.dataset.src;
          thumbs.forEach(function (b) { b.classList.remove('active'); });
          btn.classList.add('active');
        });
      });
    })();
  </script>
"""


LIGHTBOX_JS = """  <script>
    (function () {
      var main = document.getElementById('cat-gallery-img');
      if (!main) return;
      var wrap = main.closest('.cat-gallery-main');

      /* ── 圖片清單（多圖時取縮圖列，否則只有主圖） ── */
      var imgs = Array.prototype.map.call(
        document.querySelectorAll('.cat-gallery-thumbs button'),
        function (b) { return b.dataset.src; });
      if (!imgs.length) imgs = [main.getAttribute('src')];
      var idx = 0;

      /* ── Lightbox ── */
      var overlay = document.createElement('div');
      overlay.className = 'cat-lightbox';
      overlay.innerHTML =
        '<button class="cat-lightbox-close" aria-label="關閉">×</button>'
        + (imgs.length > 1
           ? '<button class="cat-lightbox-nav cat-lightbox-prev" aria-label="上一張">‹</button>'
             + '<button class="cat-lightbox-nav cat-lightbox-next" aria-label="下一張">›</button>'
           : '')
        + '<img alt="">';
      document.body.appendChild(overlay);
      var big = overlay.querySelector('img');

      function show(i) {
        idx = (i + imgs.length) % imgs.length;
        big.src = imgs[idx];
      }
      function close() {
        overlay.classList.remove('open');
        document.body.style.overflow = '';
      }
      main.style.cursor = 'zoom-in';
      main.addEventListener('click', function () {
        var cur = imgs.indexOf(main.getAttribute('src'));
        show(cur < 0 ? 0 : cur);
        big.alt = main.alt;
        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
      });
      overlay.addEventListener('click', close);
      big.addEventListener('click', function (e) { e.stopPropagation(); });
      var prev = overlay.querySelector('.cat-lightbox-prev');
      var next = overlay.querySelector('.cat-lightbox-next');
      if (prev) {
        prev.addEventListener('click', function (e) { e.stopPropagation(); show(idx - 1); });
        next.addEventListener('click', function (e) { e.stopPropagation(); show(idx + 1); });
      }
      document.addEventListener('keydown', function (e) {
        if (!overlay.classList.contains('open')) return;
        if (e.key === 'Escape') close();
        if (prev && e.key === 'ArrowLeft') show(idx - 1);
        if (prev && e.key === 'ArrowRight') show(idx + 1);
      });

      /* ── 方形放大鏡（滑鼠跟隨，桌機限定） ── */
      if (wrap && window.matchMedia('(hover: hover)').matches) {
        var Z = 2, LS = 190;
        var lens = document.createElement('div');
        lens.className = 'cat-zoom-lens';
        wrap.appendChild(lens);
        wrap.addEventListener('mousemove', function (e) {
          var r = main.getBoundingClientRect();
          var x = e.clientX - r.left, y = e.clientY - r.top;
          if (x < 0 || y < 0 || x > r.width || y > r.height) {
            lens.style.display = 'none';
            return;
          }
          var wr = wrap.getBoundingClientRect();
          lens.style.display = 'block';
          lens.style.left = (e.clientX - wr.left - LS / 2) + 'px';
          lens.style.top = (e.clientY - wr.top - LS / 2) + 'px';
          lens.style.backgroundImage = 'url("' + main.getAttribute('src') + '")';
          lens.style.backgroundSize = (r.width * Z) + 'px ' + (r.height * Z) + 'px';
          lens.style.backgroundPosition =
            (-(x * Z - LS / 2)) + 'px ' + (-(y * Z - LS / 2)) + 'px';
        });
        wrap.addEventListener('mouseleave', function () {
          lens.style.display = 'none';
        });
      }
    })();
  </script>
"""

def product_jsonld(product, bc):
    cover = cover_of(product)
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Product",
                "name": product["name"],
                "url": BASE_URL + product["url"],
                "image": [BASE_URL + url_path(img) for img in product["images"]]
                         or [BASE_URL + url_path(cover)],
                "description": md_to_text(product["body"], 200) or product["name"],
                "category": product["category"],
            },
            breadcrumb_jsonld(bc),
        ],
    }
    prod = data["@graph"][0]
    if product["brand"]:
        prod["brand"] = {"@type": "Brand", "name": product["brand"]}
    if product["price"] is not None:
        price_max = product["price_max"]
        if price_max is not None and price_max > product["price"]:
            # 多規格商品用 AggregateOffer，搜尋結果才會顯示成價格區間；
            # 底下再逐一列出每個規格的報價，讓搜尋引擎拿得到明細
            prod["offers"] = {
                "@type": "AggregateOffer",
                "lowPrice": str(product["price"]),
                "highPrice": str(price_max),
                "priceCurrency": "TWD",
                "offerCount": len(product["variants"]) or None,
                "availability": "https://schema.org/InStock",
                "url": BASE_URL + product["url"],
                "offers": [
                    {
                        "@type": "Offer",
                        "name": v["label"],
                        "price": str(v["price"]),
                        "priceCurrency": "TWD",
                        "availability": "https://schema.org/InStock",
                        "url": BASE_URL + product["url"],
                    }
                    for v in product["variants"] if v["price"] is not None
                ] or None,
            }
            prod["offers"] = {k: v for k, v in prod["offers"].items()
                              if v is not None}
        else:
            prod["offers"] = {
                "@type": "Offer",
                "price": str(product["price"]),
                "priceCurrency": "TWD",
                "availability": "https://schema.org/InStock",
                "url": BASE_URL + product["url"],
            }
    return data


def build_product_pages(products):
    for product in products:
        images = product["images"] or [PLACEHOLDER]
        main_img = images[0]
        thumbs = ""
        if len(images) > 1:
            btns = "".join(
                '<button type="button" data-src="{src}"{cls} aria-label="檢視圖片 {n}">'
                '<img src="{src}" alt="{name} 圖片 {n}" loading="lazy" '
                'width="120" height="120"></button>'.format(
                    src=url_path(img), n=i + 1, name=esc(product["name"]),
                    cls=' class="active"' if i == 0 else "")
                for i, img in enumerate(images))
            thumbs = f'<div class="cat-gallery-thumbs">{btns}</div>'

        # 商品規格：可選規格與固定屬性合成同一張卡，全頁只出現一次「規格」。
        # 兩張分開的卡都叫規格，會讓人以為是不同的東西。
        variant_part = specs_part = ""
        variants = product["variants"]
        if variants:
            prices = [v["price"] for v in variants if v["price"] is not None]
            if prices and len(set(prices)) > 1:
                # 價格有差異才值得兩欄表；排在固定屬性之前，那是購買決策
                rows = "".join(
                    f'<tr><th scope="row">{esc(v["label"])}</th>'
                    f'<td>{esc(format_price(v["price"])) or "洽詢"}</td></tr>'
                    for v in variants)
                variant_part = (
                    '            <table class="cat-spec-table cat-variant-table">\n'
                    f'              <thead><tr><th scope="col">{esc(product["variant_label"])}</th>'
                    '<th scope="col">價格</th></tr></thead>\n'
                    f'              <tbody>{rows}</tbody>\n'
                    '            </table>\n')
            else:
                # 全部同價：價格上方已經寫過，這裡只需列出有哪些選項
                specs_part += (
                    f'<tr><th scope="row">{esc(product["variant_label"])}</th>'
                    f'<td>{esc("、".join(v["label"] for v in variants))}</td></tr>')

        specs_part += "".join(
            f'<tr><th scope="row">{esc(d.get("label", ""))}</th>'
            f'<td>{esc(d.get("value", ""))}</td></tr>'
            for d in product["specs"])

        specs_html = ""
        if variant_part or specs_part:
            attr_table = (f'            <table class="cat-spec-table">{specs_part}</table>\n'
                          if specs_part else "")
            specs_html = f"""        <section class="cat-block">
          <h2>商品規格</h2>
          <div style="overflow-x:auto;">
{variant_part}{attr_table}          </div>
        </section>
"""

        # 法定標示：查證用資訊，不是賣點，用小字低對比。商品自己的標示在上，
        # 店家藥商資訊由 STORE_REGULATORY 統一附在下方，不必逐項寫進 frontmatter。
        legal_html = ""
        if product["regulatory"]:
            legal_html = ('        <section class="cat-block cat-legal">\n'
                          '          <h2>法定標示</h2>\n'
                          '          <div class="cat-legal-body">'
                          + "<br>\n".join(esc(ln) for ln
                                          in product["regulatory"].split("\n")
                                          if ln.strip())
                          + '<p class="cat-legal-store">'
                          + "<br>\n".join(esc(ln) for ln
                                          in STORE_REGULATORY.strip().split("\n"))
                          + "</p></div>\n        </section>\n")

        desc_html = ""
        body_html = md_to_html(product["body"])
        if body_html:
            desc_html = f"""        <section class="cat-block">
          <h2>商品說明</h2>
          <div class="cat-desc">
{body_html}
          </div>
        </section>
"""

        # 商品頁不放租賃／補助標記：下方的資訊列講得更精確（租金怎麼算、
        # 是哪一種補助），標記只會讓同一件事在一個畫面出現兩次。
        # 標記留在商品卡片上——那裡沒有空間放資訊列，才需要它來快速掃視。
        plain_tags = [t for t in product["tags"]
                      if t not in ("可租賃", "可申請補助")]
        tags_html = ""
        if plain_tags:
            tags_html = ('<div class="cat-tags">'
                         + "".join(f'<span class="cat-tag">{esc(t)}</span>'
                                   for t in plain_tags)
                         + "</div>")

        # 提供方式：只留資訊列講不完的細節。「購買方式」本身已由下方的
        # 電話按鈕與蝦皮按鈕表達，不再重複一行。
        offer_rows = []
        if product["rental_price"]:
            offer_rows.append(("租金", product["rental_price"]))
        elif product["rentable"]:
            offer_rows.append(("租金", "依租期而定，歡迎來電詢價"))
        if product["subsidy"]:
            offer_rows.append(("補助", "、".join(product["subsidy"])))
        offer_html = ""
        if offer_rows:
            offer_html = ('<div class="cat-offer-rows">'
                          + "".join(f'<div class="cat-offer-row">'
                                    f'<span class="cat-offer-label">{esc(k)}</span>'
                                    f'<span>{esc(v)}</span></div>'
                                    for k, v in offer_rows)
                          + "</div>")

        # 可網購且填了連結時，在電話按鈕下方補一個蝦皮下單的次要按鈕
        shopee_cta = ""
        if SHOPEE_ENABLED and "線上選購" in product["offering"] and product["shopee_url"]:
            shopee_cta = (
                f'              <a href="{esc(product["shopee_url"])}" class="cat-cta-shopee"'
                f' target="_blank" rel="noopener noreferrer">\n'
                f'                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"'
                f' stroke="currentColor" stroke-width="2"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2'
                f' 0 0 0 2-2V6l-3-4z"/><path d="M3 6h18"/>'
                f'<path d="M16 10a4 4 0 0 1-8 0"/></svg>\n'
                f'                蝦皮下單\n'
                f'              </a>\n')

        brand_html = ""
        if product["brand"]:
            label = f'<strong>{esc(product["brand"])}</strong>'
            if product["brand_slug"]:
                label = (f'<a href="/brand/{quote(product["brand_slug"])}/">'
                         f'{label}</a>')
            brand_html = f'<p class="cat-product-brand">品牌：{label}</p>'

        price_note = ('<p class="cat-price-note">價格如有異動，以門市標示為準。</p>'
                      if product["price"] else
                      '<p class="cat-price-note">此商品採詢價報價，歡迎來電或親臨門市。</p>')

        related = [p for p in products
                   if p["category"] == product["category"] and p["slug"] != product["slug"]][:4]
        related_html = ""
        if related:
            related_html = f"""        <section class="cat-related">
          <h2>{esc(product['category'])}・其他商品</h2>
          <div class="cat-grid">
{chr(10).join(product_card(p) for p in related)}
          </div>
        </section>
"""

        cat_url = url_path(f"category/{product['category']}/")
        bc = [("商品分類", "/#categories"),
              (product["category"], cat_url), (product["name"], None)]

        main = f"""    <div class="cat-section">
      <div class="cat-container">
        {breadcrumb(bc)}
        <div class="cat-product-layout">
          <div class="cat-gallery">
            <div class="cat-gallery-main">
              <img id="cat-gallery-img" src="{url_path(main_img)}" alt="{esc(product['name'])}" width="800" height="600">
            </div>
            {thumbs}
            <p class="cat-photo-note">圖片僅供參考，實品請依門市現場為主</p>
          </div>
          <div class="cat-product-info">
            <h1>{esc(product['name'])}</h1>
            {brand_html}
            {price_html(product, big=True)}
            {price_note}
            {tags_html}
            {offer_html}
            <div class="cat-cta">
              <div class="cat-cta-actions">
                <a href="tel:{PHONE_TEL}" class="cat-cta-call">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91A16 16 0 0 0 16 17l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 23.73 18z"/></svg>
                  電話洽詢
                </a>
{shopee_cta}              </div>
              <p class="cat-cta-sub">門市：崇德路 677 號（台南市立醫院對面）・營業 9:30–22:00</p>
            </div>
          </div>
        </div>
{specs_html}{desc_html}{legal_html}{related_html}
      </div>
    </div>
"""
        summary = md_to_text(product["body"], 90)
        desc_parts = [f"{product['name']}"]
        if product["brand"]:
            desc_parts.append(f"品牌 {product['brand']}")
        desc_parts.append(f"售價 {product['price_text']}" if product["price"] else "歡迎洽詢")
        meta_desc = "，".join(desc_parts) + f"。{summary}｜台南東光醫療器材，電話 {PHONE_DISPLAY}。"

        cover = cover_of(product)
        og_image = (BASE_URL + url_path(cover) if product["images"]
                    else f"{BASE_URL}/{LOGO}")
        html_out = render_page(
            title=f"{product['name']} — {SITE_NAME}",
            description=meta_desc,
            path=f"product/{product['slug']}/",
            og_type="product",
            og_image=og_image,
            jsonld=product_jsonld(product, bc),
            main_html=main,
            extra_js=(GALLERY_JS if len(images) > 1 else "")
                     + (LIGHTBOX_JS if images else ""),
            active_url=cat_url,
        )
        out = ROOT / "product" / product["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_out, encoding="utf-8")


def build_brand_pages(products, brands):
    """每個品牌一頁，列出該品牌全部商品。客人常直接搜「台南 康揚輪椅」。"""
    made = []
    for slug, brand in brands.items():
        items = [p for p in products if p["brand_slug"] == slug]
        if not items:
            continue                      # 沒有商品的品牌不產生空頁面
        made.append(slug)

        by_cat = [(c, [p for p in items if p["category"] == c])
                  for c in CATEGORY_NAMES]
        blocks = []
        for cat_name, cat_items in by_cat:
            if not cat_items:
                continue
            blocks.append(f"""<section class="cat-cat-block">
  <div class="cat-cat-head">
    <h2><a href="{url_path(f"category/{cat_name}/")}">{esc(cat_name)}</a></h2>
  </div>
  <div class="cat-grid">
{chr(10).join(product_card(p) for p in cat_items)}
  </div>
</section>""")

        site_link = ""
        if brand["website"]:
            site_link = (f'<p class="cat-brand-site">原廠網站：'
                         f'<a href="{esc(brand["website"])}" target="_blank"'
                         f' rel="noopener noreferrer">{esc(brand["website"])}</a></p>')
        note = md_to_html(brand["body"])

        bc = [("商品分類", "/#categories"), (brand["name"], None)]
        main = f"""    <div class="cat-section">
      <div class="cat-container">
        {breadcrumb(bc)}
        <div class="cat-page-head">
          <h1>{esc(brand['name'])}</h1>
          <p>共 {len(items)} 項商品</p>
          {site_link}
        </div>
        {note}
{chr(10).join(blocks)}
      </div>
    </div>
"""
        desc = (f"東光醫療器材 {brand['name']} 商品一覽，共 {len(items)} 項。"
                f"台南醫療輔具租賃與販售，歡迎來電 {PHONE_DISPLAY} 洽詢。")
        jsonld = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": f"{brand['name']} — {SITE_NAME}",
                    "url": BASE_URL + brand["url"],
                    "description": desc,
                },
                breadcrumb_jsonld(bc),
            ],
        }
        html_out = render_page(
            title=f"{brand['name']} — {SITE_NAME}",
            description=desc,
            path=f"brand/{slug}/",
            og_type="website",
            og_image=f"{BASE_URL}/{LOGO}",
            jsonld=jsonld,
            main_html=main,
            active_url="/",
        )
        out = ROOT / "brand" / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_out, encoding="utf-8")
    return made


# ── 長照輔具補助試算（/subsidy/） ────────────────────────────────────
#
# 給付項目、購置價格上限、最低使用年限：
#   長期照顧服務申請及給付辦法「附表四 照顧組合表」第一組（E、F 碼）
# 部分負擔比率：
#   同辦法「附表五」— E、F 碼 第一類 0%、第二類 10%、第三類 30%
#
# 品項資料與計算邏輯都在 assets/js/subsidy.js，不在本檔；
# 法規修正時請一併更新 SUBSIDY_BASIS 的版本日期，讓頁面標示與資料一致。

SUBSIDY_BASIS = "115.07.01 施行版本"
SUBSIDY_UPDATED = "115.08.30"


def build_subsidy_page():
    """長照輔具補助試算頁：試算金額並產生台南市格式之給付證明暨契約書。廠商資料（名稱／地址／代表人）刻意不預設帶入，由使用者輸入後存於自己瀏覽器的 localStorage；本站原始碼為公開 repo，不放公司資料。
    """
    bc = [("首頁", "/"), ("長照輔具補助試算", None)]

    main = f"""    <div class="cat-section">
      <div class="cat-container">
        {breadcrumb(bc)}
        <div class="sub-wrap">

          <header class="sub-intro">
            <h1>台南長照輔具補助試算</h1>
            <p>依中央「長期照顧服務申請及給付辦法」試算長照輔具及居家無障礙環境改善服務（第一組 E、F 碼）的購買與修繕補助金額，並可產生台南市格式的「長照輔具服務給付證明暨契約書」列印或下載。</p>
            <div class="sub-basis">
              <span>第一組 E、F 碼</span>
              <span>每 3 年 4 萬元額度</span>
              <span>依據 {SUBSIDY_BASIS}</span>
              <span>資料更新 {SUBSIDY_UPDATED}</span>
            </div>
          </header>

          <section class="sub-card">
            <h2>申請資料</h2>
            <div class="sub-grid sub-g3">
              <div>
                <label for="sbName">申請人姓名</label>
                <input id="sbName" placeholder="請輸入申請人姓名">
              </div>
              <div>
                <label for="sbId">身分證字號（選填）</label>
                <input id="sbId" placeholder="未填則印空白欄">
              </div>
              <div>
                <label for="sbTel">聯絡電話（選填）</label>
                <input id="sbTel" placeholder="未填則印空白欄">
              </div>
              <div>
                <label for="sbCopay">部分負擔類別</label>
                <select id="sbCopay">
                  <option value="0">第一類　低收入戶（部分負擔 0%）</option>
                  <option value="0.1">第二類　中低收入戶（部分負擔 10%）</option>
                  <option value="0.3" selected>第三類　一般戶（部分負擔 30%）</option>
                </select>
              </div>
              <div>
                <label for="sbQuota">本次可用給付額度（元）</label>
                <input id="sbQuota" type="number" min="0" step="1" value="40000">
              </div>
              <div>
                <label for="sbY">證明書日期（民國）</label>
                <div class="sub-grid sub-g3" style="gap:6px">
                  <input id="sbY" type="number" aria-label="年" placeholder="年">
                  <input id="sbM" type="number" aria-label="月" placeholder="月">
                  <input id="sbD" type="number" aria-label="日" placeholder="日">
                </div>
              </div>
            </div>
          </section>

          <section class="sub-card">
            <h2>
              <span>廠商資料（乙方）</span>
              <button type="button" class="sub-btn-link" id="sbVendorClear">清除已儲存的廠商資料</button>
            </h2>
            <div class="sub-grid sub-g3">
              <div>
                <label for="sbVendorName">廠商名稱</label>
                <input id="sbVendorName" placeholder="販售或修繕之單位名稱">
              </div>
              <div>
                <label for="sbVendorAddr">地址</label>
                <input id="sbVendorAddr" placeholder="廠商地址">
              </div>
              <div>
                <label for="sbVendorRep">代表人</label>
                <input id="sbVendorRep" placeholder="代表人姓名">
              </div>
            </div>
          </section>

          <section class="sub-card">
            <h2>購買／修繕明細</h2>
            <div id="sbRows"></div>
            <button type="button" class="sub-btn-add" id="sbAdd">＋ 新增明細</button>
          </section>

          <section class="sub-card">
            <h2>試算結果</h2>
            <div class="sub-stats">
              <div class="sub-stat"><div class="k">購買總金額</div><div class="v" id="sbSumPrice">0 元</div></div>
              <div class="sub-stat sub-stat-gov"><div class="k">申請給付金額（政府）</div><div class="v" id="sbSumGov">0 元</div></div>
              <div class="sub-stat sub-stat-self"><div class="k">民眾部分負擔（含超額）</div><div class="v" id="sbSumSelf">0 元</div></div>
              <div class="sub-stat sub-stat-over"><div class="k">其中超額自費</div><div class="v" id="sbSumOver">0 元</div></div>
            </div>
            <div class="sub-stats" style="margin-top:12px">
              <div class="sub-stat"><div class="k">本次扣除長照額度</div><div class="v" id="sbSumUse">0 元</div></div>
              <div class="sub-stat"><div class="k">剩餘給付額度</div><div class="v" id="sbSumLeft">0 元</div></div>
            </div>
            <div class="sub-note" id="sbWarn" hidden></div>

            <div class="sub-actions">
              <button type="button" class="sub-btn-main" id="sbPrint">產生正式給付證明並列印</button>
              <button type="button" class="sub-btn-ghost" id="sbWord"
                      data-template="/assets/templates/certificate-template.json?v={SUBSIDY_ASSET_VERSION}">下載 Word 版給付證明</button>
            </div>
            <div class="sub-note" id="sbMsg" hidden></div>
          </section>

          <p class="sub-disclaimer">
            <strong>計算依據</strong>：給付項目、購置價格上限與最低使用年限依「長期照顧服務申請及給付辦法」附表四；部分負擔比率依同辦法附表五，E、F 碼為第一類 0%、第二類 10%、第三類 30%，金額小數點後無條件捨去。長照額度以給付價格（含部分負擔）扣除。<br>
            本試算工具由{SITE_NAME_FULL}自行製作，<strong>非中央機關或台南市政府提供之系統</strong>，僅供初步試算與作業參考。實際給付金額以主管機關核定為準；送件前請以衛生局最新公告之表單格式為準。<br>
            填寫內容僅在您的瀏覽器中計算，不會上傳。試算有疑問歡迎來電
            <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a> 洽詢。
          </p>

        </div>
      </div>
    </div>

    <div class="sub-print" id="sbPrintArea" aria-hidden="true"></div>
"""

    desc = ("台南長照輔具補助試算：依長期照顧服務申請及給付辦法附表四、附表五，"
            "試算輔具購置與居家無障礙環境改善的給付金額、民眾部分負擔與超額自費，"
            "並可產生台南市格式的長照輔具服務給付證明暨契約書。")
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebApplication",
                "name": "台南長照輔具補助試算",
                "url": BASE_URL + "/subsidy/",
                "applicationCategory": "FinanceApplication",
                "operatingSystem": "Web",
                "description": desc,
                "offers": {"@type": "Offer", "price": "0",
                           "priceCurrency": "TWD"},
            },
            breadcrumb_jsonld(bc),
        ],
    }
    html_out = render_page(
        title=f"台南長照輔具補助試算 — {SITE_NAME}",
        description=desc,
        path="subsidy/",
        og_type="website",
        og_image=f"{BASE_URL}/{LOGO}",
        jsonld=jsonld,
        main_html=main,
        extra_head=(f'\n  <link rel="stylesheet" '
                    f'href="/assets/css/subsidy.css?v={CSS_VERSION}">'),
        extra_js=f'  <script src="/assets/js/subsidy.js?v={SUBSIDY_ASSET_VERSION}"></script>\n',
    )
    out = ROOT / "subsidy" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")


def build_sitemap(products, brand_slugs=()):
    today = date.today().isoformat()
    paths = ["", "rental/", "about/", "subsidy/"]
    paths += [f"category/{c}/" for c in CATEGORY_NAMES]
    paths += [f"category/{c}/{sub}/"
              for c in CATEGORY_NAMES for sub in NAV_SUBS.get(c, [])]
    paths += [f"brand/{s}/" for s in brand_slugs]
    paths += [f"product/{p['slug']}/" for p in products]
    entries = "\n".join(
        f"  <url>\n    <loc>{BASE_URL}{url_path(p) if p else '/'}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n  </url>"
        for p in paths)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{entries}\n</urlset>\n")
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")


def build_robots():
    """robots.txt：全站開放，並指出 sitemap 位置讓搜尋引擎自己找得到。"""
    txt = ("User-agent: *\n"
           "Allow: /\n\n"
           f"Sitemap: {BASE_URL}/sitemap.xml\n")
    (ROOT / "robots.txt").write_text(txt, encoding="utf-8")


def build_search_index(products):
    index = {
        "products": [
            {
                "name": p["name"],
                "brand": p["brand"],
                "tags": p["tags"],
                "category": p["category"],
                "subcategory": p["subcategory"],
                "offering": p["offering"],
                "rentable": p["rentable"],
                "subsidy": p["subsidy"],
                "price": p["price"],
                "price_text": p["price_text"],
                "url": p["url"],
                "image": url_path(cover_of(p)),
            }
            for p in products
        ]
    }
    out = ROOT / "catalog" / "search-index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                   encoding="utf-8")


# ── 主流程 ──────────────────────────────────────────────

def sync_about_chrome():
    """about/index.html 為手刻頁面，頁首/頁尾會隨模板演進而過期；
    每次建置時把該頁的 header（含行動版選單）與 footer 換成共用模板，
    內文（main 區塊）維持手刻內容不動。"""
    path = ROOT / "about" / "index.html"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")

    # 頁首：<header class="intro-header"> 起，到行動版選單的 </nav> 止
    h_start = text.find('<header class="intro-header">')
    mob = text.find('intro-nav-mobile', h_start)
    h_end = text.find("</nav>", mob)
    if h_start == -1 or mob == -1 or h_end == -1:
        print("⚠️  about/index.html 頁首錨點未找到，略過同步", file=sys.stderr)
        return
    h_end += len("</nav>")
    text = text[:h_start] + page_header("/about/").strip() + text[h_end:]

    # 頁尾：<footer class="intro-footer"> 到 </footer>
    f_start = text.find('<footer class="intro-footer">')
    f_end = text.find("</footer>", f_start)
    if f_start == -1 or f_end == -1:
        print("⚠️  about/index.html 頁尾錨點未找到，略過同步", file=sys.stderr)
        return
    f_end += len("</footer>")
    text = text[:f_start] + PAGE_FOOTER.strip() + text[f_end:]

    # 導覽 JS：以 'var hamburger' 所在的 <script> 區塊為錨點，換成 NAV_JS
    j_anchor = text.find("var hamburger = document.getElementById")
    if j_anchor != -1:
        j_start = text.rfind("<script>", 0, j_anchor)
        j_end = text.find("</script>", j_anchor)
        if j_start != -1 and j_end != -1:
            j_end += len("</script>")
            text = text[:j_start] + NAV_JS.strip() + text[j_end:]

    # GA4：手刻頁不經 render_page，追蹤碼與事件 JS 得在這裡補上，否則會漏掉
    # 這一頁的流量。已存在就整段換掉，維持與模板同步。
    ga_start = text.find("<!-- Google tag (gtag.js) -->")
    if ga_start != -1:
        ga_end = text.find("</script>", text.find("gtag('config'", ga_start))
        text = text[:ga_start] + GA_TAG.strip() + text[ga_end + len("</script>"):]
    else:
        text = text.replace("<title>", GA_TAG.strip() + "\n  <title>", 1)

    if "PATTERNS[i][0].test(href)" not in text:
        text = text.replace("</body>", GA_EVENTS_JS.rstrip() + "\n</body>", 1)

    # CSS 版本號同步（避免 about 頁拿到舊快取樣式）
    text = re.sub(r'(href="/assets/css/[\w-]+\.css)(\?v=\w+)?"',
                  rf'\1?v={CSS_VERSION}"', text)

    path.write_text(text, encoding="utf-8")
    print("   about/index.html 頁首頁尾與導覽 JS 已同步為共用模板")


def main():
    # Windows 主控台預設 cp950，直接印中文／emoji 會 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    # 確保無圖商品的預設圖存在
    placeholder = ROOT / PLACEHOLDER
    if not placeholder.is_file():
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        placeholder.write_text(PLACEHOLDER_SVG, encoding="utf-8")

    brands = load_brands()
    products = load_products(brands)
    print(f"讀取 {len(products)} 項已發布商品、{len(brands)} 個品牌")

    NAV_SUBS.update(compute_nav_subs(products))

    # 重建產出目錄（皆為純產生內容，可安全清除）
    for d in ("catalog", "category", "product", "rental", "brand", "subsidy"):
        shutil.rmtree(ROOT / d, ignore_errors=True)

    build_home_page(products)
    build_catalog_redirect()
    build_category_pages(products)
    build_subcategory_pages(products)
    build_rental_page(products)
    build_subsidy_page()
    brand_slugs = build_brand_pages(products, brands)
    build_product_pages(products)
    build_search_index(products)
    build_sitemap(products, brand_slugs)
    build_robots()
    sync_about_chrome()

    rentable = sum(1 for p in products if p["rentable"])
    pages = 3 + len(CATEGORIES) + len(brand_slugs) + len(products)
    print(f"✅ 產生完成：{pages} 個頁面（首頁目錄 + 1 租賃專區 + 1 補助試算 + {len(CATEGORIES)} 分類 + "
          f"{len(brand_slugs)} 品牌 + {len(products)} 商品）、sitemap.xml、search-index.json")
    print(f"   其中可租賃 {rentable} 項")


if __name__ == "__main__":
    main()
