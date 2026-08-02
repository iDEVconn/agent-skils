#!/usr/bin/env python3
"""
Validate an invoice draft against the required-components checklist and
check its arithmetic. Uses the same JSON schema as generate_invoice.py
(see that script's docstring) — pass in whatever fields could be extracted
from the draft; anything genuinely absent from the source draft should
simply be omitted rather than guessed, so this script can flag it as missing.

Usage:
    python validate_invoice.py invoice.json
    cat invoice.json | python validate_invoice.py -

Prints a JSON report:
{
  "ok": bool,
  "missing_components": [str, ...],
  "math_errors": [str, ...]
}
Exit code is 0 if ok, 1 otherwise.
"""
import sys
import json


def check_missing_components(data):
    missing = []
    invoice_type = data.get("invoice_type", "standard")

    if not data.get("invoice_number") and not (data.get("numbering") or {}).get("method"):
        missing.append("invoice identification number")

    seller = data.get("seller") or {}
    if not seller.get("name"):
        missing.append("vendor (seller) name")
    if not (seller.get("email") or seller.get("address")):
        missing.append("vendor (seller) contact details")

    buyer = data.get("buyer") or {}
    if not buyer.get("name"):
        missing.append("customer (buyer) name")
    if not (buyer.get("email") or buyer.get("address")):
        missing.append("customer (buyer) contact details")

    items = data.get("items") or []
    if not items:
        missing.append("itemized products/services")
    else:
        for i, item in enumerate(items, start=1):
            if not item.get("description"):
                missing.append(f"item {i}: description")
            if item.get("qty") is None:
                missing.append(f"item {i}: quantity")
            if item.get("unit_price") is None:
                missing.append(f"item {i}: unit price")

    # Proforma invoices are estimates sent before delivery — a firm due date
    # is not a hard requirement the way it is for a standard invoice.
    if invoice_type != "proforma":
        has_due_date = bool(data.get("due_date"))
        has_net_terms = data.get("issue_date") and data.get("net_days") is not None
        if not (has_due_date or has_net_terms):
            missing.append("payment terms / due date")

    if not data.get("payment_methods"):
        missing.append("accepted payment methods")

    if items and all(not item.get("tax_rate") for item in items) and "tax_exempt" not in data:
        missing.append(
            "tax information (no item has a tax_rate — if genuinely tax-exempt, "
            "set top-level \"tax_exempt\": true to silence this)"
        )

    return missing


def check_math(data):
    errors = []
    items = data.get("items") or []

    computed_subtotal = 0.0
    computed_tax = 0.0

    for i, item in enumerate(items, start=1):
        qty = item.get("qty")
        unit_price = item.get("unit_price")
        if qty is None or unit_price is None:
            continue  # already reported as missing
        expected_line_total = round(float(qty) * float(unit_price), 2)
        computed_subtotal += expected_line_total
        tax_rate = float(item.get("tax_rate", 0) or 0)
        computed_tax += round(expected_line_total * tax_rate, 2)

        if "line_total" in item:
            given = round(float(item["line_total"]), 2)
            if abs(given - expected_line_total) > 0.01:
                errors.append(
                    f"item {i} ({item.get('description', '?')}): line_total is {given}, "
                    f"expected {expected_line_total} (qty * unit_price)"
                )

    computed_subtotal = round(computed_subtotal, 2)
    computed_tax = round(computed_tax, 2)
    computed_grand_total = round(computed_subtotal + computed_tax, 2)

    if "subtotal" in data:
        given = round(float(data["subtotal"]), 2)
        if abs(given - computed_subtotal) > 0.01:
            errors.append(f"subtotal is {given}, expected {computed_subtotal}")

    if "tax_total" in data:
        given = round(float(data["tax_total"]), 2)
        if abs(given - computed_tax) > 0.01:
            errors.append(f"tax_total is {given}, expected {computed_tax}")

    if "grand_total" in data:
        given = round(float(data["grand_total"]), 2)
        if abs(given - computed_grand_total) > 0.01:
            errors.append(f"grand_total is {given}, expected {computed_grand_total}")

    return errors


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    raw = sys.stdin.read() if src == "-" else open(src, "r", encoding="utf-8").read()
    data = json.loads(raw)

    missing = check_missing_components(data)
    math_errors = check_math(data)
    ok = not missing and not math_errors

    print(json.dumps({
        "ok": ok,
        "missing_components": missing,
        "math_errors": math_errors,
    }, indent=2))

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
