# Copyright (c) 2026, Redtra Customisation and contributors

import frappe
from frappe.utils import flt, today


def _empty_totals():
	return {
		"sales_person_commission_total": 0.0,
		"sales_partner_commission_total": 0.0,
	}


@frappe.whitelist()
def get_project_commission_totals(project=None) -> dict:
	"""
	Sum commission amounts from the two payout summary reports for a project.
	Uses Sales Invoice, current fiscal year to date, and project's company.
	"""
	if not project or not frappe.db.exists("Project", project):
		return _empty_totals()

	company = frappe.db.get_value("Project", project, "company") or frappe.defaults.get_user_default(
		"Company"
	)
	if not company:
		return _empty_totals()

	today_d = today()
	from_date = None
	to_date = today_d

	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy = get_fiscal_year(date=today_d, company=company, raise_on_missing=False)
		if fy:
			from_date, fy_end = fy[1], fy[2]
			to_date = today_d if str(today_d) <= str(fy_end) else fy_end
	except Exception:
		pass

	base_filters = {
		"company": company,
		"project": project,
		"from_date": from_date,
		"to_date": to_date,
	}

	try:
		from redtra_customisation.redtra_customisation.report.sales_person_commission_payment_summary.sales_person_commission_payment_summary import (
			execute as execute_sales_person_report,
		)
		from redtra_customisation.redtra_customisation.report.sales_partner_commission_payment_summary.sales_partner_commission_payment_summary import (
			execute as execute_sales_partner_report,
		)
	except ImportError:
		return _empty_totals()

	sp_filters = {**base_filters, "doc_type": "Sales Invoice"}
	partner_filters = {**base_filters, "doctype": "Sales Invoice"}

	try:
		_cols1, sp_rows = execute_sales_person_report(sp_filters)
		sales_person_total = sum(flt(r.get("commission_amount")) for r in (sp_rows or []))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Sales Person commission KPI")
		sales_person_total = 0.0

	try:
		_cols2, pt_rows = execute_sales_partner_report(partner_filters)
		sales_partner_total = sum(flt(r.get("commission_amount")) for r in (pt_rows or []))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Sales Partner commission KPI")
		sales_partner_total = 0.0

	return {
		"sales_person_commission_total": flt(sales_person_total),
		"sales_partner_commission_total": flt(sales_partner_total),
	}
