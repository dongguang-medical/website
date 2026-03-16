#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_index.py
─────────────────
掃描 products/ 目錄，產生 products-index.json。

規則：
  - 最多 3 層：products/大類/小類/商品/
  - 包含 images/ 或 info.txt 的資料夾 = 商品
  - info.txt 解析欄位：名稱、售價、品牌、說明、規格、標籤
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PRODUCTS_DIR = Path("products")
OUTPUT_FILE  = Path("products-index.json")
IMG_EXTS     = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'}


def is_product(folder: Path) -> bool:
    """A folder is a product if it contains images/ or info.txt."""
    return (folder / 'images').is_dir() or (folder / 'info.txt').is_file()


def get_images(product_path: Path):
    img_dir = product_path / 'images'
    if not img_dir.is_dir():
        return []
    imgs = sorted(
        [f.name for f in img_dir.iterdir() if f.suffix.lower() in IMG_EXTS],
        key=lambda x: (not x.startswith('1'), x)
    )
    return imgs


def parse_info(product_path: Path) -> dict:
    info_file = product_path / 'info.txt'
    result = {'name': '', 'price': '', 'brand': '', 'description': '', 'specs': [], 'tags': []}
    if not info_file.is_file():
        return result
    try:
        text = info_file.read_text(encoding='utf-8')
    except Exception:
        return result

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        colon = line.find(':')
        if colon < 0:
            continue
        key = line[:colon].strip()
        val = line[colon + 1:].strip()
        if key == '名稱':
            result['name'] = val
        elif key == '售價':
            result['price'] = val
        elif key == '品牌':
            result['brand'] = val
        elif key == '說明':
            result['description'] = val
        elif key == '規格':
            pipe = val.find('|')
            if pipe >= 0:
                result['specs'].append({
                    'label': val[:pipe].strip(),
                    'value': val[pipe + 1:].strip()
                })
        elif key == '標籤':
            if val:
                result['tags'].append(val)
    return result


def build_product_entry(path_arr: list, product_dir: Path) -> dict:
    info   = parse_info(product_dir)
    images = get_images(product_dir)
    name   = info['name'] or product_dir.name
    cover  = 'products/' + '/'.join(path_arr) + '/images/' + images[0] if images else ''

    return {
        'id':         '/'.join(path_arr),
        'path':       path_arr[:],
        'name':       name,
        'price':      info['price'],
        'brand':      info['brand'],
        'description': info['description'],
        'specs':      info['specs'],
        'tags':       info['tags'],
        'cover':      cover,
        'imageCount': len(images)
    }


def collect_tree(base_dir: Path):
    """
    Recursively collect categories and products.
    Returns (categories_tree, flat_products_list).
    """
    categories = []
    flat_products = []

    if not base_dir.is_dir():
        print(f"⚠️  products/ directory not found at: {base_dir.resolve()}", file=sys.stderr)
        return categories, flat_products

    for cat_dir in sorted(base_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith('.'):
            continue

        cat_name = cat_dir.name
        cat_entry = {'name': cat_name, 'subcategories': []}

        # Check if top-level IS a product (1-level depth)
        if is_product(cat_dir):
            product = build_product_entry([cat_name], cat_dir)
            # No subcategory — product is directly under a fake subcategory with same name
            sub_entry = {'name': cat_name, 'products': [product]}
            cat_entry['subcategories'].append(sub_entry)
            flat_products.append(product)
            categories.append(cat_entry)
            continue

        for sub_dir in sorted(cat_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith('.'):
                continue

            sub_name = sub_dir.name
            sub_entry = {'name': sub_name, 'products': []}

            # Check if sub IS a product (2-level depth)
            if is_product(sub_dir):
                product = build_product_entry([cat_name, sub_name], sub_dir)
                sub_entry['products'].append(product)
                flat_products.append(product)
                cat_entry['subcategories'].append(sub_entry)
                continue

            # 3-level depth: iterate products
            for prod_dir in sorted(sub_dir.iterdir()):
                if not prod_dir.is_dir() or prod_dir.name.startswith('.'):
                    continue
                if is_product(prod_dir):
                    product = build_product_entry([cat_name, sub_name, prod_dir.name], prod_dir)
                    sub_entry['products'].append(product)
                    flat_products.append(product)

            if sub_entry['products']:
                cat_entry['subcategories'].append(sub_entry)

        if cat_entry['subcategories']:
            categories.append(cat_entry)

    return categories, flat_products


def main():
    print('掃描 products/ 目錄...')
    categories, flat_products = collect_tree(PRODUCTS_DIR)

    output = {
        'generated':    datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'totalProducts': len(flat_products),
        'categories':   categories,
        'products':     flat_products
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    print(f'✅ 產生完成：{len(categories)} 個大類，{len(flat_products)} 項商品')
    print(f'   輸出：{OUTPUT_FILE.resolve()}')


if __name__ == '__main__':
    main()
