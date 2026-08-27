## Redtra Customisation

Redtra Customisation

## Stock item dismantling / conversion

Use **Item Conversion / Dismantling** in Stock Entry. It is a Redtra-specific
label that uses the standard Stock Entry ledger without ERPNext's Finished Good
requirement.

1. Add one or more source items with their **Source Warehouse**, then enter
   their **Basic Rate**.
2. Add one or more output items with their **Target Warehouse**, including new
   items created for the conversion, then enter their **Basic Rate**.
3. The type enables manual Basic Rate on every row. The **Is Finished Item**
   checkbox is not used or shown.
4. The combined output valuation must equal the combined source valuation.

This creates normal Stock Ledger and accounting entries; it does not introduce
a separate inventory ledger.

#### License

mit# redtra_customisation
