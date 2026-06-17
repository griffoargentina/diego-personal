"""
Scrapers for each Argentine retail site.

Each scraper has the signature:
    scraper(query: str, keywords: list[str], size_range: tuple|None) -> list[dict]

  query      — search string to send to the site
  keywords   — all words must appear (case-insensitive) in the product name
  size_range — (min_inches, max_inches) for TVs; None = skip size filter

Returns list of dicts:
  { site, name, price, cuotas, url }

MercadoLibre, Fravega            → requests + BeautifulSoup (SSR)
Garbarino, Musimundo, Ribeiro    → Playwright (React SPA)
Gadnic, Bidcom                   → requests + BeautifulSoup (SSR / light JS)
"""

import logging
import random
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

_PW_FALLBACK_PATHS = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "es-AR,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s


def _get(session, url, **kwargs):
    time.sleep(random.uniform(1.5, 3.5))
    try:
        r = session.get(url, timeout=20, **kwargs)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        logger.warning("GET %s failed: %s", url, e)
        return None


def _parse_price(text: str) -> int | None:
    clean = re.sub(r"[^\d]", "", text)
    return int(clean) if clean else None


def _parse_cuotas(text: str) -> int | None:
    m = re.search(r"(\d+)\s*cuotas?\s*sin\s*inter", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _matches(name: str, keywords: list[str], size_range: tuple | None) -> bool:
    """Return True if name passes keyword filter AND optional size filter."""
    name_lower = name.lower()
    if keywords and not all(kw.lower() in name_lower for kw in keywords):
        return False
    if size_range:
        hits = re.findall(r'(\d{2})"?(?:\s*pulgadas?)?', name, re.IGNORECASE)
        if not any(size_range[0] <= int(h) <= size_range[1] for h in hits):
            return False
    return True


def _pw_executable() -> str | None:
    import os
    for path in _PW_FALLBACK_PATHS:
        if os.path.isfile(path):
            return path
    return None


def _pw_get_html(url: str, wait_selector: str, timeout_ms: int = 20_000) -> str | None:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("playwright not installed")
        return None

    launch_kwargs: dict = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    exe = _pw_executable()
    if exe:
        launch_kwargs["executable_path"] = exe

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            ctx = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="es-AR",
                extra_http_headers={"Accept-Language": "es-AR,es;q=0.9"},
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except PWTimeout:
                logger.warning("Selector '%s' never appeared on %s", wait_selector, url)
            time.sleep(random.uniform(1.0, 2.5))
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.warning("Playwright failed for %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# MercadoLibre  (requests)
# ---------------------------------------------------------------------------

def scrape_mercadolibre(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    session = _session()
    slug = re.sub(r"\s+", "-", query.strip().lower())
    url = f"https://listado.mercadolibre.com.ar/{slug}_Desde_1_NoIndex_True"
    r = _get(session, url)
    if not r:
        return results
    soup = BeautifulSoup(r.text, "html.parser")
    for item in soup.select("li.ui-search-layout__item")[:20]:
        try:
            name_el = item.select_one(".poly-component__title")
            price_el = item.select_one(".andes-money-amount__fraction")
            link_el = item.select_one("a.poly-component__title")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one(".poly-price__installments")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            results.append({
                "site": "MercadoLibre",
                "name": name,
                "price": price,
                "cuotas": cuotas,
                "url": link_el["href"].split("?")[0],
            })
        except Exception as e:
            logger.debug("ML item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Fravega  (requests)
# ---------------------------------------------------------------------------

def scrape_fravega(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    session = _session()
    session.headers.update({
        "Referer": "https://www.fravega.com/",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
    })
    encoded = requests.utils.quote(query)
    url = f"https://www.fravega.com/l/?keyword={encoded}"
    r = _get(session, url)
    if not r:
        return results
    soup = BeautifulSoup(r.text, "html.parser")
    for item in soup.select("article[data-test-id='product-card']")[:20]:
        try:
            name_el = item.select_one("[data-test-id='product-title']")
            price_el = item.select_one("[data-test-id='product-price']")
            link_el = item.select_one("a")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one("[data-test-id='installment']")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://www.fravega.com{href}"
            results.append({"site": "Fravega", "name": name, "price": price, "cuotas": cuotas, "url": full_url})
        except Exception as e:
            logger.debug("Fravega item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Garbarino  (Playwright)
# ---------------------------------------------------------------------------

def scrape_garbarino(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    encoded = requests.utils.quote(query)
    url = f"https://www.garbarino.com/search?q={encoded}"
    html = _pw_get_html(url, wait_selector="[class*='ProductCard'],[class*='product-card']")
    if not html:
        return results
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select("[class*='ProductCard'],[class*='product-card']")[:20]:
        try:
            name_el = item.select_one(
                "[class*='ProductTitle'],[class*='product-title'],[class*='ProductName'],h2,h3"
            )
            price_el = item.select_one(
                "[class*='CurrentPrice'],[class*='current-price'],[class*='PriceCurrent']"
            ) or item.select_one("[class*='Price']:not([class*='Old']):not([class*='old'])")
            link_el = item.select_one("a[href]")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one("[class*='Installment'],[class*='installment'],[class*='cuota']")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://www.garbarino.com{href}"
            results.append({"site": "Garbarino", "name": name, "price": price, "cuotas": cuotas, "url": full_url})
        except Exception as e:
            logger.debug("Garbarino item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Musimundo  (Playwright)
# ---------------------------------------------------------------------------

def scrape_musimundo(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    encoded = requests.utils.quote(query)
    url = f"https://www.musimundo.com/search?q={encoded}"
    html = _pw_get_html(url, wait_selector=".product-item,[class*='ProductItem'],[class*='product-card']")
    if not html:
        return results
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select(".product-item,[class*='ProductItem'],[class*='product-card']")[:20]:
        try:
            name_el = item.select_one(
                ".product-name,[class*='ProductName'],[class*='product-name'],[class*='Title'],h2,h3"
            )
            price_el = item.select_one(
                "[class*='CurrentPrice'],[class*='current-price'],"
                ".price,[class*='Price']:not([class*='Old']):not([class*='old'])"
            )
            link_el = item.select_one("a[href]")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one("[class*='installment'],[class*='Installment'],[class*='cuota']")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://www.musimundo.com{href}"
            results.append({"site": "Musimundo", "name": name, "price": price, "cuotas": cuotas, "url": full_url})
        except Exception as e:
            logger.debug("Musimundo item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Ribeiro  (Playwright)
# ---------------------------------------------------------------------------

def scrape_ribeiro(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    encoded = requests.utils.quote(query)
    url = f"https://www.ribeiro.com.ar/search?q={encoded}"
    html = _pw_get_html(url, wait_selector=".product-item,[class*='ProductItem'],[class*='product-card']")
    if not html:
        return results
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select(".product-item,[class*='ProductItem'],[class*='product-card']")[:20]:
        try:
            name_el = item.select_one(
                ".product-name,[class*='ProductName'],[class*='product-name'],h2,h3"
            )
            price_el = item.select_one(
                "[class*='CurrentPrice'],[class*='current-price'],"
                ".price,[class*='Price']:not([class*='Old']):not([class*='old'])"
            )
            link_el = item.select_one("a[href]")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one("[class*='installment'],[class*='Installment'],[class*='cuota']")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://www.ribeiro.com.ar{href}"
            results.append({"site": "Ribeiro", "name": name, "price": price, "cuotas": cuotas, "url": full_url})
        except Exception as e:
            logger.debug("Ribeiro item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Gadnic  (requests — tienda oficial)
# ---------------------------------------------------------------------------

def scrape_gadnic(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    session = _session()
    encoded = requests.utils.quote(query)
    url = f"https://gadnic.com.ar/search?q={encoded}&type=product"
    r = _get(session, url)
    if not r:
        return results
    soup = BeautifulSoup(r.text, "html.parser")
    # Gadnic usa Shopify — estructura estándar
    for item in soup.select(".product-item, .grid__item, [class*='product-card']")[:20]:
        try:
            name_el = item.select_one(
                ".product-item__title, .card__heading, h2, h3, [class*='title']"
            )
            price_el = item.select_one(
                ".price__regular .price-item, .price .money, [class*='price']:not([class*='compare'])"
            )
            link_el = item.select_one("a[href]")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one("[class*='installment'],[class*='cuota']")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://gadnic.com.ar{href}"
            results.append({"site": "Gadnic", "name": name, "price": price, "cuotas": cuotas, "url": full_url})
        except Exception as e:
            logger.debug("Gadnic item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Bidcom  (requests)
# ---------------------------------------------------------------------------

def scrape_bidcom(query: str, keywords: list[str], size_range: tuple | None) -> list[dict]:
    results = []
    session = _session()
    encoded = requests.utils.quote(query)
    url = f"https://www.bidcom.com.ar/buscar?q={encoded}"
    r = _get(session, url)
    if not r:
        return results
    soup = BeautifulSoup(r.text, "html.parser")
    for item in soup.select(".product-item, [class*='product-card'], [class*='ProductCard']")[:20]:
        try:
            name_el = item.select_one(
                ".product-item__title, [class*='product-name'], [class*='ProductName'], h2, h3"
            )
            price_el = item.select_one(
                "[class*='current-price'], [class*='CurrentPrice'], "
                ".price:not([class*='old']):not([class*='compare'])"
            )
            link_el = item.select_one("a[href]")
            if not (name_el and price_el and link_el):
                continue
            name = name_el.get_text(strip=True)
            if not _matches(name, keywords, size_range):
                continue
            price = _parse_price(price_el.get_text())
            if not price:
                continue
            cuotas_el = item.select_one("[class*='installment'],[class*='cuota'],[class*='quota']")
            cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
            href = link_el["href"]
            full_url = href if href.startswith("http") else f"https://www.bidcom.com.ar{href}"
            results.append({"site": "Bidcom", "name": name, "price": price, "cuotas": cuotas, "url": full_url})
        except Exception as e:
            logger.debug("Bidcom item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SCRAPER_MAP = {
    "mercadolibre": scrape_mercadolibre,
    "fravega":      scrape_fravega,
    "garbarino":    scrape_garbarino,
    "musimundo":    scrape_musimundo,
    "ribeiro":      scrape_ribeiro,
    "gadnic":       scrape_gadnic,
    "bidcom":       scrape_bidcom,
}
