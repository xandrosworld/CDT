"""Unit-aware presentation totals shared by screens and Excel documents."""
from decimal import Decimal


def quantity_totals(rows, field, unit_field="unit"):
    totals = {}
    for row in rows:
        unit = str(row.get(unit_field) or "Chưa rõ ĐVT").strip()
        key = unit.casefold()
        item = totals.setdefault(key, {"unit": unit, "value": Decimal(0)})
        item["value"] += Decimal(str(row.get(field) or 0))
    return [{"unit": v["unit"], "quantity": float(v["value"])}
            for _, v in sorted(totals.items())]


def quantity_text(totals):
    return " · ".join(f"{item['quantity']:,.6f}".rstrip("0").rstrip(".") + " " + item["unit"]
                      for item in totals) or "0"


def quantity_cell(rows, field):
    """Keep numeric cells for one unit; never add kilograms to pieces."""
    totals = quantity_totals(rows, field)
    if not totals:
        return 0
    return totals[0]["quantity"] if len(totals) == 1 else quantity_text(totals)
