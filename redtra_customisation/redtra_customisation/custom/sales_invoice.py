import frappe
from frappe.utils import flt

def calculate_profit_and_commission(doc, method):
    """
    Calculate Profit Percentage and Commission for Sales Person on Sales Invoice Validate.
    """
    calculate_profit_percentage(doc)
    calculate_commission(doc)

def calculate_profit_percentage(doc):
    """
    Calculates Profit Percentage based on (Sales - Cost) / Sales.
    Cost is derived from item.incoming_rate (valuation rate).
    Handles cases where Invoice is created from Delivery Note (update_stock=0).
    """
    total_buying_amount = 0.0
    total_sales_amount = flt(doc.base_net_total)

    for item in doc.items:
        # Standard ERPNext logic for Valuation Rate:
        # 1. If update_stock=1, item.incoming_rate is used (snapshot of valuation).
        # 2. If from Delivery Note, item.incoming_rate might be 0 in Invoice Item,
        #    so we must fetch from Delivery Note Item.
        
        valuation_rate = 0.0
        
        if flt(item.incoming_rate) > 0:
            valuation_rate = flt(item.incoming_rate)
        elif item.delivery_note and item.dn_detail:
             # Fetch from linked Delivery Note Item
             valuation_rate = frappe.db.get_value("Delivery Note Item", item.dn_detail, "incoming_rate") or 0.0
        elif item.sales_order and item.so_detail:
             # Try to find if there are Delivery Notes linked to this SO Detail
             # and get average incoming rate. 
             # For simplicity and performance, we will take the latest DN Item's rate or fallback to Item Master.
             
             # Check if any DN Item exists for this SO Detail
             dn_rates = frappe.get_all("Delivery Note Item", 
                                       filters={"so_detail": item.so_detail, "docstatus": 1}, 
                                       fields=["incoming_rate"])
             if dn_rates:
                 # Average it? or max? ERPNext averages.
                 total_rate = sum([flt(d.incoming_rate) for d in dn_rates])
                 valuation_rate = total_rate / len(dn_rates)
        
        # Fallback to Item Master Valuation Rate if still 0
        if not valuation_rate:
             valuation_rate = frappe.db.get_value("Item", item.item_code, "valuation_rate") or 0.0

        buying_amount = flt(item.stock_qty) * flt(valuation_rate)
        total_buying_amount += buying_amount

    profit_amount = total_sales_amount - total_buying_amount

    if total_sales_amount > 0:
        doc.custom_profit_percentage = (profit_amount / total_sales_amount) * 100.0
    else:
        doc.custom_profit_percentage = 0.0

def calculate_commission(doc):
    """
    Calculate commission for Sales Persons based on slabs.
    """
    if not doc.sales_team:
        return

    profit_percentage = flt(doc.custom_profit_percentage)

    for row in doc.sales_team:
        sales_person_doc = frappe.get_doc("Sales Person", row.sales_person)
        
        if sales_person_doc.custom_enable_slab and sales_person_doc.custom_slabs:
            # Find matching slab
            commission_rate = 0.0
            for slab in sales_person_doc.custom_slabs:
                # Check if profit_percentage falls within slab range
                # Assuming from and to are inclusive, or standard slab logic
                print("slab",flt(slab.get("from")), profit_percentage , flt(slab.get("to")))
                if flt(slab.get("from")) <= profit_percentage <= flt(slab.get("to")):
                    commission_rate = flt(slab.get("value"))
                    break
            
            print("commission_rate",commission_rate)
            # Set commission rate on the row to prevent client-side override/mismatch
            row.commission_rate = commission_rate

            # Calculate commission amount
            # If allocated_amount is used (multiple sales persons), calculate on that.
            # Else calculate on base_net_total.
            
            # allocated_amount is 'Contribution to Net Total'
            base_amount = flt(row.allocated_amount) if flt(row.allocated_amount) > 0 else flt(doc.base_net_total)
            
            incentive_amount = base_amount * (commission_rate / 100.0)
            
            # Set the incentive amount
            row.incentives = incentive_amount
            print(incentive_amount,"00")
