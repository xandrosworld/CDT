# Customer usability requirements

The user prioritizes convenience and clear Vietnamese wording for customers.

- Use the same field names in labels, instructions, and validation messages.
- Explain what is missing or incorrect and exactly how to fix it; avoid technical terms and repeated per-row errors for a shared field.
- Where an error can be corrected on screen, provide a button that opens or scrolls to the relevant form, row, or field and focuses it.
- Preserve entered data while correcting errors. Do not make customers restart the workflow or re-upload unchanged files.
- Verify the actual customer interaction in a browser when changing these flows. Do not equate a successful API response with a usable interface.
- Convenience does not authorize changing purchase dates, accounting data, or bypassing confirmations for posting stock or issuing invoices.

## Customer-approved printing workflow

- Preserve the delivery-print screen's date range, kitchen selection list, and selected view/print/download actions. The customer explicitly approved this layout; do not redesign it as part of unrelated fixes.
- Preserve source references (including TDP-BATCH-* and TDP-BK-HD-DAU-RA-*) in the printed Ghi chú column. The customer explicitly wants these references visible for logical source reconciliation; do not hide them as technical clutter.

- On printed summaries, label legacy TDP-BATCH-<id> as TDP-BK-DON-HANG-<id> to identify the order source explicitly. Preserve every source reference on merged lines and keep original stored keys unchanged; never label an order ID as an invoice number.
