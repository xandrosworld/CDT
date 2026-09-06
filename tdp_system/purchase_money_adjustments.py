"""Explicit money deductions, independent of purchased or sold quantities."""
import unicodedata

DEDUCTION_KIND = "replacement_deduction"
DEDUCTION_LABEL = "Trừ tiền mua hộ do hàng hỏng"


def key(value):
    text = unicodedata.normalize("NFD", str(value or "").lower().replace("đ", "d"))
    return "".join(c for c in text if c.isalnum())


def approved_phong_source(work_date, supplier, kitchen, code, name, unit, numbers):
    """Only the two source facts explicitly settled by the owner on 06/09.

    Row positions are deliberately excluded so sorting the same workbook does
    not lose the decision. Changed amounts/identities need an explicit type.
    """
    approved = {
        ("mnlinhtrang2", "j000017", "quaduahau", 117000),
        ("mnlinhtrang3", "", "quanhan", 90000),
    }
    return (
        work_date == "2026-09-03" and key(supplier) == "phong"
        and key(unit) == "kg" and numbers["base_qty"] == -1
        and all(numbers[f] == 0 for f in ("damaged_qty", "added_qty", "reduced_qty", "missing_qty"))
        and (key(kitchen), key(code), key(name), numbers["buy_price"]) in approved
    )
