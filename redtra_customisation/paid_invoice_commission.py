# Copyright (c) 2026, Redtra Customisation and contributors
# For license information, please see license.txt

"""Record project-wise commission on Sales Invoice when fully paid."""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate
from frappe.utils.nestedset import get_root_of

from redtra_customisation.commission import (
	apply_sales_partner_commission_from_team,
	get_project_commission_rate,
	get_sales_invoice_commission_base_amount,
)


def should_defer_commission_to_payment(doc) -> bool:
	"""Project-wise commission is finalized only when the invoice is paid."""
	if not doc.get("project"):
		return False
	if flt(doc.get("custom_enable_sales_based")):
		return False

	settings = frappe.get_cached_doc("Redtra Custom Setting")
	return bool(settings.get("enable_project_wise_commission"))


def get_project_sales_manager_employee(project: str) -> str | None:
	if not project:
		return None

	for role in ("Sales Manager", "Salesman"):
		rows = frappe.get_all(
			"Project Team Member",
			filters={"parent": project, "parenttype": "Project", "role": role},
			fields=["employee"],
			order_by="idx asc",
			limit=1,
		)
		if rows and rows[0].employee:
			return rows[0].employee

	return frappe.db.get_value("Project", project, "custom_sales_engineer")


def get_or_create_sales_person_from_employee(employee: str) -> str | None:
	if not employee:
		return None

	existing = frappe.db.get_value("Sales Person", {"employee": employee}, "name")
	if existing:
		return existing

	employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee
	by_name = frappe.db.get_value("Sales Person", {"sales_person_name": employee_name}, "name")
	if by_name:
		linked_employee = frappe.db.get_value("Sales Person", by_name, "employee")
		if not linked_employee:
			frappe.db.set_value(
				"Sales Person", by_name, "employee", employee, update_modified=False
			)
			return by_name
		if linked_employee == employee:
			return by_name

	sales_person_name = employee_name
	if frappe.db.exists("Sales Person", sales_person_name):
		sales_person_name = f"{employee_name} ({employee})"

	doc = frappe.get_doc(
		{
			"doctype": "Sales Person",
			"sales_person_name": sales_person_name,
			"employee": employee,
			"enabled": 1,
			"parent_sales_person": get_root_of("Sales Person"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def get_invoice_paid_date(si_name: str):
	paid_date = frappe.db.sql(
		"""
		SELECT MAX(pe.posting_date)
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE pe.docstatus = 1
		  AND per.reference_doctype = 'Sales Invoice'
		  AND per.reference_name = %s
		""",
		si_name,
	)
	if paid_date and paid_date[0][0]:
		return getdate(paid_date[0][0])

	posting_date = frappe.db.get_value("Sales Invoice", si_name, "posting_date")
	return getdate(posting_date) if posting_date else None


def get_paid_project_invoices(project: str) -> list[frappe._dict]:
	rows = frappe.db.sql(
		"""
		SELECT name, posting_date, base_total, base_net_total,
		       amount_eligible_for_commission, custom_commission_recorded
		FROM `tabSales Invoice`
		WHERE project = %s
		  AND docstatus = 1
		  AND IFNULL(outstanding_amount, 0) <= 0
		  AND IFNULL(is_return, 0) = 0
		""",
		project,
		as_dict=True,
	)
	for row in rows:
		row.paid_date = get_invoice_paid_date(row.name) or getdate(row.posting_date)
	rows.sort(key=lambda r: (r.paid_date, r.name))
	return rows


def _invoice_has_sales_order_items(si_name: str) -> bool:
	return bool(
		frappe.db.sql(
			"""
			SELECT 1
			FROM `tabSales Invoice Item`
			WHERE parent = %s
			  AND parenttype = 'Sales Invoice'
			  AND IFNULL(sales_order, '') != ''
			LIMIT 1
			""",
			si_name,
		)
	)


def _get_si_base_amount(si_row: frappe._dict) -> float:
	from_so = _invoice_has_sales_order_items(si_row.name)
	doc = frappe._dict(
		{
			"name": si_row.name,
			"base_total": si_row.base_total,
			"base_net_total": si_row.base_net_total,
			"amount_eligible_for_commission": si_row.amount_eligible_for_commission,
			"items": [{"sales_order": "x"}] if from_so else [],
		}
	)
	return get_sales_invoice_commission_base_amount(
		doc,
		force_total=from_so,
		force_net_total=not from_so,
	)


def _get_recorded_incentives(si_name: str) -> float:
	return flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(incentives), 0)
			FROM `tabSales Team`
			WHERE parent = %s AND parenttype = 'Sales Invoice'
			""",
			si_name,
		)[0][0]
	)


def compute_true_up_incentives(project: str, si_name: str, current_rate: float) -> tuple[float, float]:
	"""Return (incentives, amount_eligible) for si_name using cumulative slab true-up."""
	paid = get_paid_project_invoices(project)
	bases_total = 0.0
	already = 0.0
	current_base = 0.0
	seen_current = False

	for row in paid:
		base = _get_si_base_amount(row)
		if row.name == si_name:
			current_base = base
			seen_current = True
			bases_total += base
			break

		bases_total += base
		if cint_flag(row.custom_commission_recorded):
			already += _get_recorded_incentives(row.name)

	if not seen_current:
		si = frappe.db.get_value(
			"Sales Invoice",
			si_name,
			[
				"name",
				"posting_date",
				"base_total",
				"base_net_total",
				"amount_eligible_for_commission",
				"custom_commission_recorded",
			],
			as_dict=True,
		)
		if si:
			current_base = _get_si_base_amount(si)
			bases_total += current_base

	target_total = bases_total * (flt(current_rate) / 100.0)
	return flt(target_total - already), flt(current_base)


def cint_flag(value) -> bool:
	return bool(flt(value))


def _ensure_commission_recorded_field():
	if not frappe.get_meta("Sales Invoice").has_field("custom_commission_recorded"):
		frappe.throw(
			"Sales Invoice field custom_commission_recorded is missing. Run migrate / install custom fields."
		)


def _write_sales_team(
	si_name: str,
	sales_person: str,
	commission_rate: float,
	incentives: float,
	allocated_amount: float = 0,
):
	existing = frappe.get_all(
		"Sales Team",
		filters={"parent": si_name, "parenttype": "Sales Invoice"},
		fields=["name"],
		order_by="idx asc",
	)
	values = {
		"sales_person": sales_person,
		"commission_rate": flt(commission_rate),
		"incentives": flt(incentives),
		"allocated_percentage": 100,
		"allocated_amount": flt(allocated_amount),
	}

	if existing:
		frappe.db.set_value("Sales Team", existing[0].name, values, update_modified=False)
		for extra in existing[1:]:
			frappe.db.delete("Sales Team", {"name": extra.name})
		return

	row = frappe.get_doc(
		{
			"doctype": "Sales Team",
			"parent": si_name,
			"parenttype": "Sales Invoice",
			"parentfield": "sales_team",
			"idx": 1,
			**values,
		}
	)
	row.db_insert()


def _clear_sales_team_commission(si_name: str):
	rows = frappe.get_all(
		"Sales Team",
		filters={"parent": si_name, "parenttype": "Sales Invoice"},
		pluck="name",
	)
	for name in rows:
		frappe.db.set_value(
			"Sales Team",
			name,
			{"commission_rate": 0, "incentives": 0},
			update_modified=False,
		)


def _write_header_commission(si_name: str, preview: dict):
	values = {
		"amount_eligible_for_commission": flt(preview.get("amount_eligible_for_commission")),
		"commission_rate": flt(preview.get("commission_rate")),
		"total_commission": flt(preview.get("total_commission")),
		"custom_commission_recorded": 1,
	}
	if frappe.get_meta("Sales Invoice").has_field("custom_sales_partner_commission_percentage"):
		values["custom_sales_partner_commission_percentage"] = flt(
			preview.get("sales_partner_commission_percentage")
		)
		values["custom_sales_partner_commission_amount"] = flt(
			preview.get("sales_partner_commission_amount")
		)
	frappe.db.set_value("Sales Invoice", si_name, values, update_modified=False)


def _clear_header_commission(si_name: str):
	values = {
		"amount_eligible_for_commission": 0,
		"commission_rate": 0,
		"total_commission": 0,
		"custom_commission_recorded": 0,
	}
	if frappe.get_meta("Sales Invoice").has_field("custom_sales_partner_commission_percentage"):
		values["custom_sales_partner_commission_percentage"] = 0
		values["custom_sales_partner_commission_amount"] = 0
	frappe.db.set_value("Sales Invoice", si_name, values, update_modified=False)


def record_paid_invoice_commission(si_name: str, force: bool = False) -> bool:
	"""Write sales person + partner commission for a fully paid project SI. Returns True if written."""
	_ensure_commission_recorded_field()

	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		[
			"name",
			"project",
			"docstatus",
			"outstanding_amount",
			"sales_partner",
			"custom_enable_sales_based",
			"custom_commission_recorded",
			"is_return",
		],
		as_dict=True,
	)
	if not si or si.docstatus != 1 or flt(si.is_return):
		return False
	if flt(si.outstanding_amount) > 0:
		return False
	if not should_defer_commission_to_payment(si):
		return False
	if cint_flag(si.custom_commission_recorded) and not force:
		return False

	settings = frappe.get_cached_doc("Redtra Custom Setting")
	rate = get_project_commission_rate(si.project, settings=settings)
	if rate is None:
		frappe.logger("paid_invoice_commission").info(
			f"Skip {si_name}: no project commission rate for {si.project}"
		)
		return False

	employee = get_project_sales_manager_employee(si.project)
	if not employee:
		frappe.logger("paid_invoice_commission").info(
			f"Skip {si_name}: no Sales Manager employee on project {si.project}"
		)
		return False

	sales_person = get_or_create_sales_person_from_employee(employee)
	if not sales_person:
		return False

	incentives, amount_eligible = compute_true_up_incentives(si.project, si_name, rate)
	preview = {
		"commission_rate": rate,
		"amount_eligible_for_commission": amount_eligible,
		"total_commission": incentives,
		"sales_partner_commission_applied": False,
		"rows": [
			{
				"sales_person": sales_person,
				"commission_rate": rate,
				"incentives": incentives,
			}
		],
	}
	doc = frappe._dict({"sales_partner": si.sales_partner})
	preview = apply_sales_partner_commission_from_team(doc, preview, settings=settings)

	_write_sales_team(si_name, sales_person, rate, incentives, amount_eligible)
	_write_header_commission(si_name, preview)
	_book_commission_accrual_gl(si_name, incentives, si.project)
	return True


def _book_commission_accrual_gl(si_name: str, incentives: float, project: str | None):
	"""Create Dr Commission / Cr Payable JV for sales-person incentives."""
	try:
		from construction_management.api.sales_commission_gl import (
			create_or_update_commission_accrual_jv,
		)
	except ImportError:
		return

	create_or_update_commission_accrual_jv(
		si_name=si_name,
		amount=flt(incentives),
		project=project,
	)


def _clear_commission_accrual_gl(si_name: str):
	try:
		from construction_management.api.sales_commission_gl import cancel_commission_accrual_jv
	except ImportError:
		return
	cancel_commission_accrual_jv(si_name)


def clear_paid_invoice_commission(si_name: str) -> bool:
	_ensure_commission_recorded_field()
	if not frappe.db.get_value("Sales Invoice", si_name, "custom_commission_recorded"):
		return False

	_clear_commission_accrual_gl(si_name)
	_clear_sales_team_commission(si_name)
	_clear_header_commission(si_name)
	return True


def maybe_record_or_clear_paid_commission(doc, method=None):
	"""Sales Invoice on_update hook."""
	if getattr(doc, "doctype", None) != "Sales Invoice" or doc.docstatus != 1:
		return
	_sync_si_commission(doc.name)


def maybe_record_or_clear_paid_commission_by_name(si_name: str):
	_sync_si_commission(si_name)


def _sync_si_commission(si_name: str):
	if not si_name or not frappe.db.exists("Sales Invoice", si_name):
		return
	if not frappe.db.has_column("Sales Invoice", "custom_commission_recorded"):
		# Do not block invoice saves on a site that has not yet run the field migration.
		frappe.logger("paid_invoice_commission").warning(
			"Skipping paid-invoice commission sync because Sales Invoice.custom_commission_recorded is missing"
		)
		return

	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		[
			"name",
			"project",
			"docstatus",
			"outstanding_amount",
			"custom_enable_sales_based",
			"custom_commission_recorded",
			"is_return",
		],
		as_dict=True,
	)
	if not si or si.docstatus != 1 or flt(si.is_return):
		return
	if not should_defer_commission_to_payment(si):
		return

	if flt(si.outstanding_amount) <= 0:
		record_paid_invoice_commission(si_name)
	elif cint_flag(si.custom_commission_recorded):
		clear_paid_invoice_commission(si_name)


def sync_commission_from_payment_entry(doc, method=None):
	"""Payment Entry on_submit / on_cancel — SI outstanding is updated via db_set."""
	seen = set()
	for ref in doc.get("references") or []:
		if ref.reference_doctype != "Sales Invoice" or not ref.reference_name:
			continue
		if ref.reference_name in seen:
			continue
		seen.add(ref.reference_name)
		maybe_record_or_clear_paid_commission_by_name(ref.reference_name)


def backfill_project_paid_commissions(project: str | None = None, force: bool = True) -> dict:
	"""
	Recompute paid-invoice commissions per project in paid-date order.
	When force=True (default for patch), clear recorded flags for selected projects first.
	"""
	filters = {
		"docstatus": 1,
		"project": ["is", "set"],
		"outstanding_amount": ["<=", 0],
		"is_return": 0,
	}
	if project:
		filters["project"] = project

	projects = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		pluck="project",
		distinct=True,
	)

	stats = {"projects": 0, "recorded": 0, "skipped": 0}
	for project_name in projects:
		if not project_name:
			continue
		if not should_defer_commission_to_payment(frappe._dict({"project": project_name})):
			continue

		stats["projects"] += 1
		paid = get_paid_project_invoices(project_name)
		if force:
			for row in paid:
				if cint_flag(row.custom_commission_recorded):
					clear_paid_invoice_commission(row.name)

		for row in paid:
			if record_paid_invoice_commission(row.name, force=False):
				stats["recorded"] += 1
			else:
				stats["skipped"] += 1

	return stats
