---
name: invoice-toolkit
description: Everything about invoices — explaining what they are, generating a new invoice document with correct fields and numbering, and validating a draft invoice against required components. Use this skill whenever the user asks what an invoice is, asks about invoice types (proforma, interim, recurring, credit, debit, time sheet, past due), asks how an invoice differs from a bill, receipt, or purchase order, wants an invoice numbering scheme, wants to create/draft/generate an invoice for a client or project, or wants to check whether an invoice or invoice template is missing required fields before sending it. Trigger even if the user just says "make me an invoice" or "is this invoice ready to send" without using the word "toolkit."
---

# Invoice Toolkit

Invoices are simple in concept but easy to get subtly wrong: a missing due date confuses a client about when payment is expected, a reused invoice number breaks a customer's bookkeeping, an invoice sent for work that hasn't shipped yet should actually be a proforma invoice. This skill covers three related jobs — explain, generate, validate — so pick the one that matches what's being asked and lean on the reference material rather than guessing from general invoicing knowledge.

## 1. Explaining invoice concepts

For questions about definitions, invoice types, required components, how an invoice differs from a bill/receipt/purchase order, numbering methods, or best practices, read `references/invoice-concepts.md` and answer from it directly. It's short enough to read in full — don't summarize from memory, since the exact distinctions (e.g. proforma vs. interim, invoice vs. bill) are easy to blur together and the reference spells out the differences precisely.

## 2. Generating an invoice

When asked to create, draft, or generate an invoice, don't hand-format the numbers yourself — line totals, tax, and grand totals need to be exactly right, and `scripts/generate_invoice.py` computes them deterministically instead of leaving arithmetic to chance.

Steps:

1. Gather what's needed: seller info, buyer info, line items (description, quantity, unit price, tax rate per item or one overall rate), payment terms (a due date, or net-N days from issue date), accepted payment methods, and which invoice type applies (standard, proforma, interim, recurring, credit, debit, time sheet, or past due — see `references/invoice-concepts.md` for what distinguishes each). If the user hasn't specified some of these, ask rather than inventing business details like tax rates or payment terms.
2. Decide the numbering scheme if the user hasn't picked one — sequential, chronological, customer-ID-based, or project-ID-based (see reference doc). If they're generating one invoice in isolation with no stated numbering history, sequential starting from a sensible seed (e.g. `1001`) is a reasonable default — say so explicitly rather than silently picking a number.
3. Build the JSON input `scripts/generate_invoice.py` expects (see the script's `--help` / docstring for the schema) and run it. It prints a formatted Markdown invoice with the invoice number, itemized table, and computed totals.
4. Hand the result to the user as the invoice document. If they want a different output format (HTML, PDF, a specific template), convert the generated Markdown rather than re-deriving totals by hand.

## 3. Validating an invoice draft

When asked to check whether an invoice is complete or ready to send, don't just eyeball it — run it through `scripts/validate_invoice.py`, which checks presence of the required components and verifies the arithmetic (line totals, tax, grand total) instead of relying on a visual scan that can miss a small mismatch.

Steps:

1. Extract the invoice's fields from whatever the user gave you (pasted text, a file, a description) into the same JSON structure `generate_invoice.py` consumes. This extraction step needs judgment — do it yourself rather than trying to regex it.
2. Run `scripts/validate_invoice.py` on that JSON. It reports which required components are missing (invoice ID, seller/buyer details, itemized items, payment terms/due date, payment method, tax info — per `references/invoice-concepts.md`) and flags any arithmetic that doesn't add up.
3. Report the findings back in plain terms — what's missing, what's wrong, and why it matters (e.g. "no due date — the client won't know when payment is expected"). Don't just dump the raw script output.

## Reference

- `references/invoice-concepts.md` — definitions, the 7 invoice types, required components, invoice vs. bill/receipt/purchase order, numbering methods, best practices. Read this for any conceptual question and before generating or validating, since it defines what "complete" and "correct type" mean.
