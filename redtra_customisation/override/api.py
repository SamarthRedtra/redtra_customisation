import frappe
import json
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def check_has_permission(doctype,name,ptype='write'):
    if frappe.has_permission(doctype, ptype):
        return True,frappe.get_doc(doctype,name).as_dict()
    
    else:
        return False

from frappe.utils import cint,flt

@frappe.whitelist()
def get_leaf_accounts(parent_account):
    if not parent_account:
        frappe.throw("Parent Account is required")

    leaf_accounts = []
    get_leaf_nodes(parent_account, leaf_accounts)
    
    return leaf_accounts

def get_leaf_nodes(account, leaf_accounts):
    accounts = frappe.get_all("Account", filters={"parent_account": account}, fields=["name", "is_group"])
    
    for acc in accounts:
        if cint(acc.get("is_group")):
            get_leaf_nodes(acc.get("name"), leaf_accounts)
        else:
            leaf_accounts.append(acc.get("name"))



@frappe.whitelist()
def get_all_leaf_nodes(parent_account=None):
    if not parent_account:
        return frappe.get_all('Account',filters={'is_group':0},fields=['name'],pluck='name')
    else:
        return get_leaf_accounts(parent_account)
    

def set_missing_values(source, target):
	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
     
@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):
    def update_item(obj, target, source_parent):
        target.qty = flt(obj.qty) - flt(obj.received_qty)
        target.stock_qty = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.conversion_factor)
        target.amount = (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate)
        target.base_amount = (
            (flt(obj.qty) - flt(obj.received_qty)) * flt(obj.rate) * flt(source_parent.conversion_rate)
        )

    def update_accounting_item(obj, target, source_parent):
        if(obj.debit >0):
            target.credit = obj.debit
            target.account = obj.account
            target.debit = 0   
        else:
            target.credit = 0
            target.account = None
            target.debit = 0   
        
        
    doc = get_mapped_doc(
        "Purchase Order",
        source_name,
        {
            "Purchase Order": {
                "doctype": "Purchase Receipt",
                "field_map": {"supplier_warehouse": "supplier_warehouse"},
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Purchase Order Item": {
                "doctype": "Purchase Receipt Item",
                "field_map": {
                    "name": "purchase_order_item",
                    "parent": "purchase_order",
                    "bom": "bom",
                    "material_request": "material_request",
                    "material_request_item": "material_request_item",
                    "sales_order": "sales_order",
                    "sales_order_item": "sales_order_item",
                    "wip_composite_asset": "wip_composite_asset",
                },
                "postprocess": update_item,
                "condition": lambda doc: abs(doc.received_qty) < abs(doc.qty)
                and doc.delivered_by_supplier != 1,
            },
            "Accounting Entries":{
                "doctype":"Accounting Entries",
                "field_map":{
                    'account':'account',
                    "debit": "debit",
                    "credit":"credit"
                },
                "postprocess": update_accounting_item
            

            },
            "Purchase Taxes and Charges": {"doctype": "Purchase Taxes and Charges", "add_if_empty": True},
        },
        target_doc,
        set_missing_values,
    )

    return doc



@frappe.whitelist()
def get_children(doctype, parent=None,label=None, company=None, warehouse=None, is_root=False, include_disabled=False):
    if is_root:
        parent = ""

    if isinstance(include_disabled, str):
        include_disabled = json.loads(include_disabled)

    fields = ["name as value", "is_group as expandable"]
    filters = [
        ["company", "in", (company, None, "")],
    ]
   

    if warehouse and is_root:
        filters.append(["parent_warehouse", "=", warehouse])
    elif parent and not is_root:
        filters.append(["parent_warehouse", "=", parent])
    else:
        filters.append(["ifnull(`parent_warehouse`, '')", "=", parent])
        # via expand child
        
    if frappe.db.has_column(doctype, "disabled") and not include_disabled:
        filters.append(["disabled", "=", False])
    print(filters,"--")
    return frappe.get_list(doctype, fields=fields, filters=filters, order_by="name", ignore_permissions=True)    