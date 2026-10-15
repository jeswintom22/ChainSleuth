# Incident Review IR-2025-Q4-07 (Synthetic)

Document ID: IR-2025-Q4-07. Classification: internal lessons learned. Synthetic document for the ChainSleuth demonstration; all names and events are fictional.

## Summary

During a quarterly review, auditors identified two supplier records that used the same payout account and the same controlling owner. One record submitted an invoice that repeated the invoice number, amount and line items of an invoice already submitted by the other record. The second invoice had no purchase order reference.

## Contributing Factors

The duplicate invoice was not detected because the duplicate check compared invoices only within a single supplier record. The shared payout account had been flagged at onboarding but the secondary review had not been completed. Goods-receipt evidence for the original invoice covered only part of the billed quantity.

## Lessons Learned

Duplicate checks must compare invoices across supplier records. Shared payout accounts should be reviewed together with the invoices submitted by every linked supplier record. Quantity reconciliation should be performed per product line using only delivered shipments. Investigations should record the evidence used and the reviewer's decision so that later reviews can build on earlier work.
