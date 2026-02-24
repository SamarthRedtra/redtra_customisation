import frappe
from frappe.utils import getdate, date_diff

def update_customer_commissions():
    """
    Daily cron job to dynamically set customer commission percentage 
    based on the time since their last submitted Sales Invoice.
    """
    settings = frappe.get_doc("Redtra Custom Setting")
    # if no settings or table empty, do nothing
    if not settings.get("commission_settings"):
        return
        
    commission_slabs = settings.get("commission_settings")
    current_date = getdate()

    # Fetch all active customers
    customers = frappe.get_all("Customer", filters={"disabled": 0}, fields=["name", "custom_comission"])

    for customer in customers:
        # Get the latest submitted Sales Invoice for the customer
        latest_invoice = frappe.get_all(
            "Sales Invoice",
            filters={"customer": customer.name, "docstatus": 1},
            fields=["posting_date"],
            order_by="posting_date desc",
            limit=1
        )
        
        if not latest_invoice:
            continue
            
        latest_date = latest_invoice[0].posting_date
        
        # Calculate float months elapsed (average month = 30.416 days)
        days_diff = date_diff(current_date, latest_date)
        if days_diff < 0:
            days_diff = 0
            
        months_elapsed = days_diff / 30.416667
        
        # Determine applicable commission percentage
        matched_percentage = None
        for slab in commission_slabs:
            min_m = float(slab.min_months or 0)
            max_m = float(slab.max_months or 0)
            
            # Handle max_months = 0 as infinity
            if max_m == 0.0:
                max_m = float('inf')
            
            if min_m <= months_elapsed < max_m:
                matched_percentage = slab.commission_percentage
                break
                
            # If months_elapsed exactly equals max_m and it is not infinity (e.g., exactly 12.0)
            # The next slab might start at 12. 
            # We treat max_m as exclusive if they chain min_m == max_m of prev slab, but let's do inclusive 
            # if user entered 11 and 12-24, so it's safer to just do standard numeric comparison.
            # but standard is: min_m <= months_elapsed <= max_m if we want inclusive.
            if min_m <= months_elapsed <= max_m and max_m != float('inf'):
                # small chance of overlap if user sets 0-12, 12-24. We use `< max_m` for standard.
                pass
                
        # Re-evaluating standard logic for overlapping slabs
        # E.g. 0-12, 12-24, >24
        # We'll use: `min_m <= months_elapsed <= max_m` if user configures exact integer bounds
        # Let's refine the matching logic
        # We want the first slab where min_m <= months_elapsed and (months_elapsed <= max_m or max_m == float('inf'))
        for slab in commission_slabs:
            min_m = float(slab.min_months or 0)
            max_m = float(slab.max_months or 0)
            if max_m == 0.0:
                max_m = float('inf')
                
            if min_m <= months_elapsed <= max_m:
                matched_percentage = slab.commission_percentage
                # If we matched exactly max_m without infinity, it might overlap next slab's min_m.
                # However, since they are ordered, we can just break on first match.
                break

        if matched_percentage is not None and customer.custom_comission != matched_percentage:
            frappe.db.set_value("Customer", customer.name, "custom_comission", matched_percentage)
            
    # Commit changes made by set_value
    frappe.db.commit()
