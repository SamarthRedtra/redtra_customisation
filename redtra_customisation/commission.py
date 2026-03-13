# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def apply_project_wise_commission(doc, method=None):
	preview = _build_sales_order_commission_preview(doc)
	commission_rate = preview.get("commission_rate")
	if commission_rate is None:
		return

	doc.amount_eligible_for_commission = preview.get("amount_eligible_for_commission")
	doc.commission_rate = commission_rate
	doc.total_commission = preview.get("total_commission")

	row_by_name = {row.get("name"): row for row in preview.get("rows", []) if row.get("name")}
	for sales_person in doc.get("sales_team") or []:
		updated_row = row_by_name.get(sales_person.name)
		if not updated_row:
			continue
		sales_person.commission_rate = updated_row.get("commission_rate")
		sales_person.incentives = updated_row.get("incentives")

	if hasattr(doc, "calculate_contribution"):
		doc.calculate_contribution()


def get_project_commission_rate(project, settings=None):
	if not project:
		return None

	settings = settings or frappe.get_cached_doc("Redtra Custom Setting")
	if not settings.get("enable_project_wise_commission"):
		return None

	project_value = get_project_boq_value(project)
	if project_value is None:
		return None

	return get_commission_rate(settings.get("project_commission_slabs"), project_value)


@frappe.whitelist()
def get_project_commission_details(project=None):
	project = project or frappe.form_dict.get("project")
	settings = frappe.get_cached_doc("Redtra Custom Setting")

	return {
		"enabled": bool(settings.get("enable_project_wise_commission")),
		"project_value": get_project_boq_value(project) if project else None,
		"commission_rate": get_project_commission_rate(project, settings=settings),
	}


def _normalize_commission_doc(doc):
	as_dict_method = getattr(doc, "as_dict", None)
	if callable(as_dict_method):
		doc = as_dict_method()

	doc = frappe._dict(doc or {})
	doc.sales_team = [frappe._dict(row) for row in (doc.get("sales_team") or [])]
	return doc


def _get_sales_order_commission_base_amount(doc, row=None):
	order_total = flt(doc.get("base_total"))

	if row and flt(row.get("allocated_percentage")) > 0:
		return order_total * (flt(row.get("allocated_percentage")) / 100.0)

	if row and flt(row.get("allocated_amount")) > 0:
		return flt(row.get("allocated_amount"))

	return order_total


def _build_sales_order_commission_preview(doc):
	doc = _normalize_commission_doc(doc)
	commission_rate = get_project_commission_rate(doc.get("project"))

	if commission_rate is None:
		return {
			"commission_rate": None,
			"amount_eligible_for_commission": flt(doc.get("amount_eligible_for_commission")),
			"total_commission": flt(doc.get("total_commission")),
			"rows": [
				{
					"name": row.get("name"),
					"sales_person": row.get("sales_person"),
					"commission_rate": flt(row.get("commission_rate")),
					"incentives": flt(row.get("incentives")),
				}
				for row in doc.sales_team
			],
		}

	rows = []
	for row in doc.sales_team:
		base_amount = _get_sales_order_commission_base_amount(doc, row)
		rows.append(
			{
				"name": row.get("name"),
				"sales_person": row.get("sales_person"),
				"commission_rate": commission_rate,
				"incentives": base_amount * (commission_rate / 100.0),
			}
		)

	amount_eligible_for_commission = _get_sales_order_commission_base_amount(doc)
	return {
		"commission_rate": commission_rate,
		"amount_eligible_for_commission": amount_eligible_for_commission,
		"total_commission": amount_eligible_for_commission * (commission_rate / 100.0),
		"rows": rows,
	}


@frappe.whitelist()
def get_sales_order_commission_preview(doc):
	doc = frappe.parse_json(doc) if isinstance(doc, str) else doc
	return _build_sales_order_commission_preview(doc)


def get_project_boq_value(project):
	project_boq = frappe.db.get_value(
		"Project BOQ",
		{"project": project},
		["total_estimated_boq_value", "total_boq_value"],
		as_dict=True,
	)
	if not project_boq:
		return None

	return flt(project_boq.total_estimated_boq_value or project_boq.total_boq_value or 0)


def get_commission_rate(slabs, project_value):
	if not slabs:
		return None

	project_value = flt(project_value)

	for slab in sorted(slabs, key=lambda row: flt(row.minimum_value)):
		minimum_value = flt(slab.minimum_value)
		maximum_value = (
			flt(slab.maximum_value) if slab.maximum_value not in (None, "") else None
		)

		if project_value < minimum_value:
			continue

		if maximum_value is not None and project_value >= maximum_value:
			continue

		return flt(slab.commission_percentage)

	return None
