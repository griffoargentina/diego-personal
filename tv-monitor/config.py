TV_BRANDS = ["Noblex", "LG", "Samsung", "Sony", "TCL", "Philips"]

TARGETS = [
    # ── Televisores ────────────────────────────────────────────────────────
    {
        "label": 'Smart TV 65"',
        "queries": [f"smart tv {b} 65 pulgadas" for b in TV_BRANDS],
        "keywords": [],          # filtrado por size_range es suficiente
        "size_range": (60, 65),  # solo para TVs
        "max_price": 999_999,
        "alert_cuotas": 6,
        "sites": ["mercadolibre", "fravega", "garbarino", "musimundo", "ribeiro"],
    },
    {
        "label": 'Smart TV 70"+',
        "queries": [f"smart tv {b} 70 pulgadas" for b in TV_BRANDS],
        "keywords": [],
        "size_range": (70, 999),
        "max_price": 1_200_000,
        "alert_cuotas": 6,
        "sites": ["mercadolibre", "fravega", "garbarino", "musimundo", "ribeiro"],
    },
    # ── Aspiradoras robot ──────────────────────────────────────────────────
    {
        "label": "Aspiradora Robot Gadnic AC701",
        "queries": ["aspiradora robot gadnic ac701", "gadnic ac701"],
        "keywords": ["gadnic", "ac701"],   # ambas palabras deben aparecer en el nombre
        "size_range": None,
        "max_price": 546_000,
        "alert_cuotas": 6,
        "sites": ["mercadolibre", "gadnic", "bidcom"],
    },
    {
        "label": "Aspiradora Robot para Vidrios",
        "queries": ["aspiradora robot vidrios", "robot limpia vidrios"],
        "keywords": ["vidrio"],            # al menos una de estas palabras
        "size_range": None,
        "max_price": 211_000,
        "alert_cuotas": 6,
        "sites": ["mercadolibre", "gadnic", "bidcom"],
    },
]

ALERT_EMAIL = "griffodiego@gmail.com"

PRICE_HISTORY_FILE = "tv-monitor/price_history.json"
