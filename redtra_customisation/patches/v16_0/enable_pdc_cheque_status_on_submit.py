# Copyright (c) 2024, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe


def execute():
    """Enable allow_on_submit for pdc_cheque_status custom field in Payment Entry"""

    # Find the Custom Field
    custom_field_name = frappe.db.get_value(
        "Custom Field",
        {
            "dt": "Payment Entry",
            "fieldname": "pdc_cheque_status"
        },
        "name"
    )

    if custom_field_name:
        # Update allow_on_submit to 1
        frappe.db.set_value("Custom Field", custom_field_name, "allow_on_submit", 1)
        frappe.db.commit()
        print(f"Updated pdc_cheque_status field to allow changes after submit")
        
        frappe.msgprint(f"Updated pdc_cheque_status field to allow changes after submit")
    else:
        frappe.log_error("Custom Field pdc_cheque_status not found in Payment Entry", "PDC Patch")

