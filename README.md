## Redtra Customisation

Redtra Customisation

## Stock item dismantling / conversion

Use standard ERPNext **Stock Entry** with Purpose set to **Repack**. Do not
create a custom Stock Entry type.

1. Add the source item as an outgoing row and select its **Source Warehouse**.
2. Add one row for each resulting item, select each **Target Warehouse**, and
   mark those rows as finished items.
3. Save, then check the Stock Entry's total outgoing and incoming values before
   submitting. ERPNext allocates the source valuation across the outputs, so
   the incoming total equals the consumed value unless you deliberately enter
   an additional cost.

Validate the resulting stock ledger rows after submission: the source item's
quantity decreases, each output item increases, and the total inventory value
is conserved (apart from any explicit additional cost).

#### License

mit# redtra_customisation
