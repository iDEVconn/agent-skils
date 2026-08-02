# Invoice Concepts Reference

## What is an invoice?

An invoice is a detailed business document that lists the goods or services a customer purchased, the amount owed, and the accepted payment methods. It serves as official proof of a transaction between a business and a client, and it records the payment terms and deadline for that transaction.

Invoices serve several purposes at once:

- Recording the sale and the client's details for the seller's own books
- Requesting timely payment by a specified due date
- Creating compliance documentation for tax reporting
- Feeding inventory tracking and financial/cash-flow projections

## Invoice types

Which type applies depends on *when* in the delivery/payment cycle the document is sent and *why* — picking the wrong type is the most common conceptual mistake (e.g. sending a standard invoice before goods have shipped, when a proforma invoice is what's actually needed).

| Type | When to use it |
|---|---|
| **Proforma invoice** | Sent *before* delivery, so the customer can plan for the payment. Not a demand for payment yet — more a preview/estimate. |
| **Interim invoice** | Used on large, long-running projects to bill for partial completion rather than waiting until the whole project is done. |
| **Recurring invoice** | For ongoing, consistent work billed on a repeating schedule (e.g. monthly retainer). |
| **Credit invoice** (credit note) | Issued to refund or credit a customer — reduces what they owe or owed. |
| **Debit invoice** (debit note) | Issued when a customer underpaid, to bill the difference. |
| **Time sheet invoice** | Bills labor costs for a client based on hours/time logged. |
| **Past due invoice** | Sent for a balance that wasn't paid by the original due date — a follow-up, not a first request. |

If a request doesn't map cleanly onto one of these (e.g. "bill for work not yet delivered"), that's the signal it's a proforma invoice, not a standard one — flag that distinction rather than defaulting to "standard."

## Required components

A complete invoice needs all of the following. When validating a draft, treat any of these as a hard miss unless the invoice type genuinely doesn't require it (e.g. a proforma invoice's "due date" is more of an estimate):

1. **Invoice identification number** — a unique ID, never reused (see Numbering methods below)
2. **Customer and vendor details** — names, addresses, contact info for both sides of the transaction
3. **Itemized products/services with pricing** — line-by-line, not a single lump sum
4. **Payment terms and due date** — when payment is expected, and any late-payment terms
5. **Accepted payment methods** — how the customer can actually pay
6. **Tax information** — applicable tax rate(s) and amount, per relevant jurisdiction

## Invoice vs. related documents

These get confused because they all appear around the same transaction — the distinguishing factor is *when* each is issued and *what* it obligates:

- **Bill** — Functionally similar to an invoice, but implies a faster, often immediate expected payment (e.g. a restaurant bill), whereas an invoice usually carries longer payment terms.
- **Receipt** — Proof that payment was *already made*. Issued after the transaction completes, not before. An invoice requests payment; a receipt confirms it happened.
- **Purchase order (PO)** — Issued by the *buyer* to request goods/services, before the sale happens. It precedes the invoice; the invoice is the seller's response once the order is fulfilled (or ready to be).

Sequence in a typical transaction: Purchase Order (buyer requests) → Invoice (seller bills) → Receipt (proof of payment).

## Numbering methods

Pick one method and stay consistent — mixing schemes across invoices to the same client is what usually causes their bookkeeping to break, since duplicate or out-of-order numbers make reconciliation ambiguous.

- **Sequential** — Increment by one each invoice (`1001`, `1002`, `1003`, ...). Simplest, works for most small-to-medium volumes.
- **Chronological** — Encode the date into the number (e.g. `2026-08-0001` for the first invoice issued on a given day). Makes it obvious when an invoice was issued just from its ID.
- **Customer-ID-based** — Prefix or embed a customer identifier (e.g. `CB-014-003` for the 3rd invoice to customer `CB-014`). Useful when invoice history needs to be grouped by client at a glance.
- **Project-ID-based** — Same idea, but keyed to a project rather than a customer — useful for interim/recurring invoices tied to one long-running engagement.

## Best practices

1. **Offer multiple delivery options** — email, a client portal, or mail — so the invoice actually reaches the right person promptly.
2. **Bundle supporting documentation** — attach the relevant purchase order, timesheet, or contract reference so the client doesn't have to hunt for context.
3. **Use electronic/cloud-based invoicing** rather than one-off documents — it reduces errors, speeds up payment, and keeps a searchable history.

Automation (e.g. auto-generated recurring invoices, integrated payment links) generally reduces processing cost, cuts manual-entry errors, and improves how fast invoices get paid — worth suggesting when a user describes a recurring or high-volume invoicing situation.
