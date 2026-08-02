#!/usr/bin/env python3
"""
Generate a formatted Markdown invoice from a JSON description.

Usage:
    python generate_invoice.py invoice.json
    cat invoice.json | python generate_invoice.py -

Input JSON schema:
{
  "invoice_type": "standard",       # optional: standard|proforma|interim|recurring|credit|debit|timesheet|past_due
  "numbering": {
    "method": "sequential",         # sequential|chronological|customer_id|project_id
    "sequence": 1001,               # required for sequential/chronological
    "date": "2026-08-02",           # required for chronological (defaults to issue_date)
    "customer_id": "CB-014",        # required for customer_id
    "project_id": "PRJ-22"          # required for project_id
  },
  "invoice_number": "CB-014-003",   # optional: overrides "numbering" entirely if given
  "issue_date": "2026-08-02",       # required
  "due_date": "2026-09-01",         # optional if net_days given
  "net_days": 30,                   # optional, used if due_date absent
  "seller": {"name": "...", "address": "...", "email": "..."},
  "buyer":  {"name": "...", "address": "...", "email": "..."},
  "items": [
    {"description": "...", "qty": 1, "unit_price": 100.0, "tax_rate": 0.2}
  ],
  "payment_methods": ["Bank transfer", "Credit card"],
  "notes": "optional free text"
}

tax_rate is a fraction (0.2 = 20%), applied per line item. Omit it (or set to 0)
for tax-exempt lines.
"""
import sys
import json
import datetime


def compute_invoice_number(data):
    if "invoice_number" in data and data["invoice_number"]:
        return str(data["invoice_number"])

    numbering = data.get("numbering") or {}
    method = numbering.get("method", "sequential")

    if method == "sequential":
        seq = numbering.get("sequence")
        if seq is None:
            raise ValueError("numbering.sequence is required for method 'sequential'")
        return str(seq)

    if method == "chronological":
        date_str = numbering.get("date") or data.get("issue_date")
        if not date_str:
            raise ValueError("numbering.date (or issue_date) is required for method 'chronological'")
        seq = numbering.get("sequence")
        if seq is None:
            raise ValueError("numbering.sequence is required for method 'chronological'")
        return f"{date_str}-{int(seq):04d}"

    if method == "customer_id":
        cust = numbering.get("customer_id")
        seq = numbering.get("sequence")
        if not cust or seq is None:
            raise ValueError("numbering.customer_id and numbering.sequence are required for method 'customer_id'")
        return f"{cust}-{int(seq):03d}"

    if method == "project_id":
        proj = numbering.get("project_id")
        seq = numbering.get("sequence")
        if not proj or seq is None:
            raise ValueError("numbering.project_id and numbering.sequence are required for method 'project_id'")
        return f"{proj}-{int(seq):03d}"

    raise ValueError(f"Unknown numbering method: {method!r}")


def compute_due_date(data):
    if data.get("due_date"):
        return data["due_date"]
    issue_date = data.get("issue_date")
    net_days = data.get("net_days")
    if issue_date and net_days is not None:
        d = datetime.date.fromisoformat(issue_date) + datetime.timedelta(days=int(net_days))
        return d.isoformat()
    return None


def compute_line(item):
    qty = float(item["qty"])
    unit_price = float(item["unit_price"])
    tax_rate = float(item.get("tax_rate", 0) or 0)
    line_total = qty * unit_price
    line_tax = line_total * tax_rate
    return {
        **item,
        "line_total": round(line_total, 2),
        "line_tax": round(line_tax, 2),
    }


def render_markdown(data):
    invoice_number = compute_invoice_number(data)
    due_date = compute_due_date(data)
    invoice_type = data.get("invoice_type", "standard")
    seller = data.get("seller", {})
    buyer = data.get("buyer", {})
    items = [compute_line(it) for it in data.get("items", [])]

    subtotal = round(sum(it["line_total"] for it in items), 2)
    tax_total = round(sum(it["line_tax"] for it in items), 2)
    grand_total = round(subtotal + tax_total, 2)

    lines = []
    lines.append(f"# INVOICE {invoice_number}")
    lines.append("")
    if invoice_type != "standard":
        lines.append(f"**Type:** {invoice_type.replace('_', ' ').title()}")
        lines.append("")
    lines.append(f"**Issue date:** {data.get('issue_date', 'N/A')}  ")
    lines.append(f"**Due date:** {due_date or 'N/A'}")
    lines.append("")
    lines.append("## From")
    lines.append(f"{seller.get('name', 'N/A')}  ")
    lines.append(f"{seller.get('address', '')}  ")
    lines.append(f"{seller.get('email', '')}")
    lines.append("")
    lines.append("## Bill to")
    lines.append(f"{buyer.get('name', 'N/A')}  ")
    lines.append(f"{buyer.get('address', '')}  ")
    lines.append(f"{buyer.get('email', '')}")
    lines.append("")
    lines.append("## Items")
    lines.append("")
    lines.append("| Description | Qty | Unit Price | Tax | Line Total |")
    lines.append("|---|---|---|---|---|")
    for it in items:
        tax_pct = f"{float(it.get('tax_rate', 0) or 0) * 100:.1f}%"
        lines.append(
            f"| {it['description']} | {it['qty']} | {float(it['unit_price']):.2f} | "
            f"{tax_pct} | {it['line_total']:.2f} |"
        )
    lines.append("")
    lines.append(f"**Subtotal:** {subtotal:.2f}  ")
    lines.append(f"**Tax:** {tax_total:.2f}  ")
    lines.append(f"**Total due:** {grand_total:.2f}")
    lines.append("")
    lines.append("## Payment methods")
    for m in data.get("payment_methods", []) or ["N/A"]:
        lines.append(f"- {m}")
    if data.get("notes"):
        lines.append("")
        lines.append("## Notes")
        lines.append(data["notes"])

    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    raw = sys.stdin.read() if src == "-" else open(src, "r", encoding="utf-8").read()
    data = json.loads(raw)

    print(render_markdown(data))


if __name__ == "__main__":
    main()
