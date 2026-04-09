# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub
from erpnext.selling.report.sales_analytics.sales_analytics import Analytics
from frappe.utils import flt

def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.doc_type = "Sales Invoice"
	filters.tree_type = "Customer"
	return SalesInvoiceAnalytics(filters).run()

class SalesInvoiceAnalytics(Analytics):
	def get_sales_transactions_based_on_customers_or_suppliers(self):
		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total as value_field"
		else:
			value_field = "total_qty as value_field"

		entity = "customer as entity"
		entity_name = "customer_name as entity_name"

		filters = {
			"docstatus": 1,
			"company": ["in", self.filters.company],
			self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
			"is_opening": "No"
		}

		self.entries = frappe.get_all(
			"Sales Invoice", fields=[entity, entity_name, value_field, self.date_field, "name as invoice_no"], filters=filters
		)

		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_periodic_data(self):
		self.entity_periodic_data = frappe._dict()

		for d in self.entries:
			period = self.get_period(d.get(self.date_field))
			self.entity_periodic_data.setdefault(d.entity, frappe._dict()).setdefault(period, 0.0)
			self.entity_periodic_data[d.entity][period] += flt(d.value_field)
			
			self.entity_periodic_data[d.entity].setdefault("invoices", frappe._dict())
			self.entity_periodic_data[d.entity]["invoices"].setdefault(d.invoice_no, frappe._dict())
			self.entity_periodic_data[d.entity]["invoices"][d.invoice_no].setdefault(period, 0.0)
			self.entity_periodic_data[d.entity]["invoices"][d.invoice_no][period] += flt(d.value_field)

	def get_rows(self):
		self.data = []
		self.get_periodic_data()

		for entity, period_data in self.entity_periodic_data.items():
			row = {
				"entity": entity,
				"entity_name": self.entity_names.get(entity) if hasattr(self, "entity_names") else None,
				"indent": 0,
			}
			total = 0
			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				amount = flt(period_data.get(period, 0.0))
				row[scrub(period)] = amount
				total += amount

			row["total"] = total
			self.data.append(row)

			invoices = period_data.get("invoices", {})
			for inv_no, inv_data in invoices.items():
				inv_row = {
					"entity": inv_no,
					"entity_name": "",
					"indent": 1,
				}
				inv_total = 0
				for end_date in self.periodic_daterange:
					period = self.get_period(end_date)
					amount = flt(inv_data.get(period, 0.0))
					inv_row[scrub(period)] = amount
					inv_total += amount
					
				inv_row["total"] = inv_total
				self.data.append(inv_row)
