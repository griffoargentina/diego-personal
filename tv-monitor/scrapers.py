"""
Scrapers for each Argentine retail site.
Each scraper returns a list of dicts:
  {
    "site": str,
    "name": str,
    "price": int,           # ARS, sin decimales
    "cuotas": int | None,   # cuotas sin interés detectadas
    "url": str,
  }
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


def _session():
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "es-AR,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return s


def _get(session, url, **kwargs):
    """GET with retry and polite delay."""
    time.sleep(random.uniform(1.5, 3.5))
    try:
        r = session.get(url, timeout=20, **kwargs)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        logger.warning("GET %s failed: %s", url, e)
        return None


def _parse_price(text: str) -> int | None:
    """Extract integer ARS price from messy strings like '$  1.299.999'."""
    clean = re.sub(r"[^\d]", "", text)
    return int(clean) if clean else None


def _parse_cuotas(text: str) -> int | None:
    """Return number of installments from strings like '12 cuotas sin interés'."""
    m = re.search(r"(\d+)\s*cuotas?\s*sin\s*inter", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# MercadoLibre
# ---------------------------------------------------------------------------

def scrape_mercadolibre(brands: list[str], min_inches: int, max_inches: int) -> list[dict]:
    results = []
    session = _session()
    for brand in brands:
        query = f"smart tv {brand} {min_inches} pulgadas"
        url = (
            f"https://listado.mercadolibre.com.ar/{requests.utils.quote(query)}"
            f"_Desde_1_NoIndex_True"
        )
        r = _get(session, url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("li.ui-search-layout__item")
        for item in items[:20]:
            try:
                name_el = item.select_one(".poly-component__title")
                price_el = item.select_one(".andes-money-amount__fraction")
                link_el = item.select_one("a.poly-component__title")
                if not (name_el and price_el and link_el):
                    continue
                name = name_el.get_text(strip=True)
                # Only process items that look like TVs within size range
                if not _tv_size_match(name, min_inches, max_inches):
                    continue
                price = _parse_price(price_el.get_text())
                if not price:
                    continue
                # Cuotas: look for installments text in the card
                cuotas_el = item.select_one(".poly-price__installments")
                cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
                results.append(
                    {
                        "site": "MercadoLibre",
                        "name": name,
                        "price": price,
                        "cuotas": cuotas,
                        "url": link_el["href"].split("?")[0],
                    }
                )
            except Exception as e:
                logger.debug("ML item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Fravega
# ---------------------------------------------------------------------------

def scrape_fravega(brands: list[str], min_inches: int, max_inches: int) -> list[dict]:
    results = []
    session = _session()
    for brand in brands:
        url = (
            f"https://www.fravega.com/l/?keyword=smart+tv+{brand}"
            f"&facets=categoria%3Atelevisores"
        )
        r = _get(session, url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article[data-test-id='product-card']")
        for item in items[:20]:
            try:
                name_el = item.select_one("[data-test-id='product-title']")
                price_el = item.select_one("[data-test-id='product-price']")
                link_el = item.select_one("a")
                if not (name_el and price_el and link_el):
                    continue
                name = name_el.get_text(strip=True)
                if not _tv_size_match(name, min_inches, max_inches):
                    continue
                price = _parse_price(price_el.get_text())
                if not price:
                    continue
                cuotas_el = item.select_one("[data-test-id='installment']")
                cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
                href = link_el["href"]
                full_url = href if href.startswith("http") else f"https://www.fravega.com{href}"
                results.append(
                    {"site": "Fravega", "name": name, "price": price, "cuotas": cuotas, "url": full_url}
                )
            except Exception as e:
                logger.debug("Fravega item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Garbarino
# ---------------------------------------------------------------------------

def scrape_garbarino(brands: list[str], min_inches: int, max_inches: int) -> list[dict]:
    results = []
    session = _session()
    for brand in brands:
        url = f"https://www.garbarino.com/search?q=smart+tv+{brand}&category=televisores"
        r = _get(session, url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".product-card, [class*='ProductCard']")
        for item in items[:20]:
            try:
                name_el = item.select_one("[class*='product-title'], [class*='ProductTitle'], h2, h3")
                price_el = item.select_one("[class*='price']:not([class*='old'])")
                link_el = item.select_one("a[href]")
                if not (name_el and price_el and link_el):
                    continue
                name = name_el.get_text(strip=True)
                if not _tv_size_match(name, min_inches, max_inches):
                    continue
                price = _parse_price(price_el.get_text())
                if not price:
                    continue
                cuotas_el = item.select_one("[class*='installment'], [class*='cuota']")
                cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
                href = link_el["href"]
                full_url = href if href.startswith("http") else f"https://www.garbarino.com{href}"
                results.append(
                    {"site": "Garbarino", "name": name, "price": price, "cuotas": cuotas, "url": full_url}
                )
            except Exception as e:
                logger.debug("Garbarino item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Musimundo
# ---------------------------------------------------------------------------

def scrape_musimundo(brands: list[str], min_inches: int, max_inches: int) -> list[dict]:
    results = []
    session = _session()
    for brand in brands:
        url = f"https://www.musimundo.com/search?q=smart+tv+{brand}&category=televisores"
        r = _get(session, url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".product-item, [class*='product-card']")
        for item in items[:20]:
            try:
                name_el = item.select_one(".product-name, [class*='title']")
                price_el = item.select_one(".price, [class*='price']:not([class*='old'])")
                link_el = item.select_one("a[href]")
                if not (name_el and price_el and link_el):
                    continue
                name = name_el.get_text(strip=True)
                if not _tv_size_match(name, min_inches, max_inches):
                    continue
                price = _parse_price(price_el.get_text())
                if not price:
                    continue
                cuotas_el = item.select_one("[class*='installment'], [class*='cuota'], [class*='quota']")
                cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
                href = link_el["href"]
                full_url = href if href.startswith("http") else f"https://www.musimundo.com{href}"
                results.append(
                    {"site": "Musimundo", "name": name, "price": price, "cuotas": cuotas, "url": full_url}
                )
            except Exception as e:
                logger.debug("Musimundo item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Ribeiro
# ---------------------------------------------------------------------------

def scrape_ribeiro(brands: list[str], min_inches: int, max_inches: int) -> list[dict]:
    results = []
    session = _session()
    for brand in brands:
        url = f"https://www.ribeiro.com.ar/search?q=smart+tv+{brand}&category=televisores"
        r = _get(session, url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".product-item, [class*='product']")
        for item in items[:20]:
            try:
                name_el = item.select_one(".product-name, [class*='title'], h2, h3")
                price_el = item.select_one(".price, [class*='price']:not([class*='old'])")
                link_el = item.select_one("a[href]")
                if not (name_el and price_el and link_el):
                    continue
                name = name_el.get_text(strip=True)
                if not _tv_size_match(name, min_inches, max_inches):
                    continue
                price = _parse_price(price_el.get_text())
                if not price:
                    continue
                cuotas_el = item.select_one("[class*='installment'], [class*='cuota']")
                cuotas = _parse_cuotas(cuotas_el.get_text()) if cuotas_el else None
                href = link_el["href"]
                full_url = href if href.startswith("http") else f"https://www.ribeiro.com.ar{href}"
                results.append(
                    {"site": "Ribeiro", "name": name, "price": price, "cuotas": cuotas, "url": full_url}
                )
            except Exception as e:
                logger.debug("Ribeiro item parse error: %s", e)
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tv_size_match(name: str, min_inches: int, max_inches: int) -> bool:
    """Return True if the product name mentions a size within [min_inches, max_inches]."""
    matches = re.findall(r'(\d{2})"?(?:\s*pulgadas?)?', name, re.IGNORECASE)
    for m in matches:
        size = int(m)
        if min_inches <= size <= max_inches:
            return True
    return False


SCRAPER_MAP = {
    "mercadolibre": scrape_mercadolibre,
    "fravega": scrape_fravega,
    "garbarino": scrape_garbarino,
    "musimundo": scrape_musimundo,
    "ribeiro": scrape_ribeiro,
}
