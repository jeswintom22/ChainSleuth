# Goods Receipt and Delivery Specification DS-210 (Synthetic)

Document ID: DS-210. Version 1.4. Owner: Warehouse Operations. Synthetic document for the ChainSleuth demonstration.

## Valid Delivery Evidence

Only shipment lines from shipments with status delivered count as goods-receipt evidence. Shipments with status cancelled provide no delivery evidence. Shipments that are in transit are not yet receipted and cannot support payment of an invoice line.

## Units of Measure

Quantities must be compared in the same unit of measure. If an invoice line is expressed in a different unit from the purchase-order line or the receipted shipment line, for example box against each, the line must be referred for unit confirmation before any quantity comparison is relied upon. No automatic conversion between packaging units is permitted unless a conversion factor is recorded on the product master.

## Partial Deliveries

A purchase order may be fulfilled by several shipments. The delivered quantity for a product line is the sum of all delivered shipment lines for that product on that purchase order. Outstanding quantities that have not yet been delivered are not an exception unless they have already been invoiced.

## Missing Receipt Evidence

When an invoice line bills a product for which no delivered shipment line exists on the linked purchase order, the receiving warehouse must confirm whether goods were received. The invoice line remains on hold until receipt is confirmed or the invoice is credited.
