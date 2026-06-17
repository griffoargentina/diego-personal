"""
Verifica que _parse_price, _parse_cuotas y _matches funcionan correctamente.
Sin necesitar red.
"""
from scrapers import _parse_price, _parse_cuotas, _matches

cases_price = [
    ('$ 999.999', 999999),
    ('$1.200.000', 1200000),
    ('1.050.000', 1050000),
    ('$ 849,999', 849999),
]
cases_cuotas = [
    ('12 cuotas sin interés', 12),
    ('6 Cuotas Sin Interés', 6),
    ('3 cuotas sin interés', 3),
    ('Hasta 18 cuotas sin intereses', 18),
    ('Precio contado', None),
]
cases_matches = [
    # TVs — filtro por pulgadas
    ('Samsung Smart TV 65" 4K QLED', [], (60, 65), True),
    ('LG OLED 55 pulgadas', [], (55, 65), True),
    ('Sony Bravia 75" 8K', [], (70, 999), True),
    ('Noblex 32" HD', [], (60, 65), False),
    ('TCL Smart TV 4K 70 pulgadas', [], (70, 999), True),
    ('Samsung Smart TV 70" 4K', [], (60, 65), False),
    # Aspiradoras — filtro por keywords
    ('Aspiradora Robot Gadnic AC701 Negro', ['gadnic', 'ac701'], None, True),
    ('Aspiradora Robot Gadnic AC501', ['gadnic', 'ac701'], None, False),
    ('Robot Limpia Vidrios Automatic', ['vidrio'], None, True),
    ('Aspiradora Robot Xiaomi S10', ['gadnic', 'ac701'], None, False),
]

ok = True
for text, expected in cases_price:
    result = _parse_price(text)
    status = "✓" if result == expected else "✗"
    if result != expected:
        ok = False
    print(f"  {status} _parse_price({text!r}) = {result}  (esperado {expected})")

for text, expected in cases_cuotas:
    result = _parse_cuotas(text)
    status = "✓" if result == expected else "✗"
    if result != expected:
        ok = False
    print(f"  {status} _parse_cuotas({text!r}) = {result}  (esperado {expected})")

for name, kws, sr, expected in cases_matches:
    result = _matches(name, kws, sr)
    status = "✓" if result == expected else "✗"
    if result != expected:
        ok = False
    print(f"  {status} _matches({name!r}, kws={kws}, size={sr}) = {result}")

print()
print("RESULTADO:", "TODOS OK" if ok else "HAY FALLAS")
