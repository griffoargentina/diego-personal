TV_TARGETS = [
    {
        "size_label": '65"',
        "min_inches": 60,
        "max_inches": 65,
        "brands": ["Noblex", "LG", "Samsung", "Sony", "TCL", "Philips"],
        "max_price": 999_999,
        "alert_cuotas": 6,
    },
    {
        "size_label": '70"+',
        "min_inches": 70,
        "max_inches": 999,
        "brands": ["Noblex", "LG", "Samsung", "Sony", "TCL", "Philips"],
        "max_price": 1_200_000,
        "alert_cuotas": 6,
    },
]

SITES = ["mercadolibre", "fravega", "garbarino", "musimundo", "ribeiro"]

ALERT_EMAIL = "griffodiego@gmail.com"

PRICE_HISTORY_FILE = "tv-monitor/price_history.json"
