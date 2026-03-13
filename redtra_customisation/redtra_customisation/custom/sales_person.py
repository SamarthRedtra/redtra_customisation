import frappe
from frappe import _
from frappe.utils import flt

def validate_slabs(doc, method):
    """
    Validate Percentage Slabs on Sales Person.
    Ensures:
    1. 'From' is less than 'To'.
    2. Slabs do not overlap.
    """
    if not doc.custom_enable_slab or not doc.custom_slabs:
        return

    # Sort slabs by 'from' percentage
    sorted_slabs = sorted(doc.custom_slabs, key=lambda k: flt(k.get('from')))

    last_to = -1.0
    
    for slab in sorted_slabs:
        from_perp = flt(slab.get('from'))
        to_perp = flt(slab.get('to'))

        # Check 1: From < To
        if from_perp >= to_perp:
            frappe.throw(_("Row #{0}: 'From' percentage ({1}%) must be less than 'To' percentage ({2}%).").format(slab.idx, from_perp, to_perp))

        # Check 2: Overlap
        # Since matches are inclusive (<= profit <=), we should strictly check for overlap?
        # Usually slabs are like 0-50, 51-100.
        # So next slab's 'from' must be > last slab's 'to'.
        # However, if slabs are continuous (0-50, 50-100), then 50 is in both?
        # Standard practice: inclusive start, exclusive end? Or both inclusive?
        # My commission logic uses: from <= profit <= to (Both Inclusive).
        # So 0-50 and 50-100 would overlap at 50.
        # Thus, next slab's 'from' must be strictly greater than last slab's 'to'.
        
        if last_to >= 0 and from_perp <= last_to:
             frappe.throw(_("Row #{0}: Slab range ({1}-{2}%) overlaps with previous slab ending at {3}%.").format(slab.idx, from_perp, to_perp, last_to))
        
        last_to = to_perp
