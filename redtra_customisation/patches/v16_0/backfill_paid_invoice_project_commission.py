# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from redtra_customisation.paid_invoice_commission import backfill_project_paid_commissions
from redtra_customisation.setup import get_sales_partner_commission_custom_fields


def execute():
	create_custom_fields(get_sales_partner_commission_custom_fields(), ignore_validate=True)
	frappe.clear_cache(doctype="Sales Invoice")

	stats = backfill_project_paid_commissions(force=True)
	frappe.logger("paid_invoice_commission").info(
		"Backfill paid invoice project commission: {0}".format(stats)
	)
