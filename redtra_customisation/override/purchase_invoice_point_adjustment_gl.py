# Copyright (c) 2026, redtra_customisation contributors

import frappe
from frappe import _
from frappe.utils import flt

from redtra_customisation.override.purchase_invoice_point_adjustment_settings import (
	get_pi_point_adjustment_account,
	is_pi_point_adjustment_gl_split_enabled,
)


def build_point_adjustment_gl_entries(doc) -> list:
	if not is_pi_point_adjustment_gl_split_enabled() or not doc.get("point_adjustments"):
		return []

	adjustment_account = get_pi_point_adjustment_account()
	if not adjustment_account:
		frappe.throw(
			_("Set Purchase Invoice Point Adjustment Account in Redtra Custom Setting")
		)

	gl_entries = []
	conversion_rate = flt(doc.conversion_rate) or 1.0

	for item in doc.get("items") or []:
		adjustment = flt(item.get("custom_point_adjustment_total"))
		if not adjustment:
			continue

		base_adjustment = flt(
			adjustment * conversion_rate, item.precision("base_net_amount")
		)
		against = item.expense_account or doc.against_expense_account or doc.supplier

		gl_entries.append(
			doc.get_gl_dict(
				{
					"account": adjustment_account,
					"against": against,
					"debit": base_adjustment,
					"debit_in_account_currency": adjustment,
					"cost_center": item.cost_center or doc.cost_center,
					"project": item.project,
					"remarks": _("Purchase Invoice Point Adjustment"),
				},
				item=item,
			)
		)

	return gl_entries
