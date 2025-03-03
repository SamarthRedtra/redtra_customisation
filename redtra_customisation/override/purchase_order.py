import frappe
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
from redtra_customisation.override.itemwisestock import execute_report

class CustomPurchaseOrder(PurchaseOrder):

    def on_update(self):
        is_rorder_enable = frappe.db.get_single_value("Redtra Custom Setting", "enble_purchase_reorder")
        
        if is_rorder_enable and self.items:
            report_result = execute_report()  # Ensure execute_report returns a valid dictionary
            
            if isinstance(report_result, dict):  # Validate that report_result is a dictionary
                for item in self.items:
                    item_data = report_result.get(item.item_code, {})  # Avoid KeyErrors
                    if item_data:
                        item.custom_reorder_level = item_data.get("reorder_level", 0)
                        item.custom_safety_stock = item_data.get("safety_stock", 0)
                        item.custom_lead_time_days = item_data.get("lead_time_days", 0)
                        item.custom_consumed = item_data.get("consumed", 0)
                        item.custom_delivered = item_data.get("delivered", 0)
                        item.custom_total_outgoing = item_data.get("total_outgoing", 0)
                        item.custom_avg_daily_outgoing = item_data.get("avg_daily_outgoing", 0)
                
                # Save the document to persist changes


def on_update_po(doc,method):
        print('on_update_po')
        self = doc
        is_rorder_enable = frappe.db.get_single_value("Redtra Custom Setting", "enble_purchase_reorder")
        
        if is_rorder_enable and self.items:
            report_result = execute_report()  # Ensure execute_report returns a valid dictionary
            
            if isinstance(report_result, dict):  # Validate that report_result is a dictionary
                for item in self.items:
                    item_data = report_result.get(item.item_code, {})  # Avoid KeyErrors
                    if item_data:
                        item.custom_reorder_level = item_data.get("reorder_level", 0)
                        item.custom_safety_stock = item_data.get("safety_stock", 0)
                        item.custom_lead_time_days = item_data.get("lead_time_days", 0)
                        item.custom_consumed = item_data.get("consumed", 0)
                        item.custom_delivered = item_data.get("delivered", 0)
                        item.custom_total_outgoing = item_data.get("total_outgoing", 0)
                        item.custom_avg_daily_outgoing = item_data.get("avg_daily_outgoing", 0)              