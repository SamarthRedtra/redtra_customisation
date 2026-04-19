# Copyright (c) 2026, Redtra Customisation and contributors

import frappe
from frappe.utils import flt, today


def _empty_totals():
	return {
		"sales_person_commission_total": 0.0,
		"sales_partner_commission_total": 0.0,
	}


def _get_boq_commission_accounts(company):
	if not company or not frappe.db.exists("DocType", "BOQ Settings"):
		return {}
	return frappe.db.get_value(
		"BOQ Settings",
		company,
		["sales_person_commission_account", "sales_partner_commission_account"],
		as_dict=True,
	) or {}


def _get_gl_commission_total(project, company, account, from_date=None, to_date=None):
	if not (project and company and account):
		return 0

	conditions = [
		"gle.project = %(project)s",
		"gle.company = %(company)s",
		"gle.account = %(account)s",
		"gle.is_cancelled = 0",
		"gle.voucher_type = 'Journal Entry'",
	]
	args = {"project": project, "company": company, "account": account}
	if from_date:
		conditions.append("gle.posting_date >= %(from_date)s")
		args["from_date"] = from_date
	if to_date:
		conditions.append("gle.posting_date <= %(to_date)s")
		args["to_date"] = to_date

	return flt(
		frappe.db.sql(
			f"""
			SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
			FROM `tabGL Entry` gle
			WHERE {' AND '.join(conditions)}
			""",
			args,
		)[0][0]
	)


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

	commission_accounts = _get_boq_commission_accounts(company)
	sales_person_total += _get_gl_commission_total(
		project,
		company,
		commission_accounts.get("sales_person_commission_account"),
		from_date,
		to_date,
	)
	sales_partner_total += _get_gl_commission_total(
		project,
		company,
		commission_accounts.get("sales_partner_commission_account"),
		from_date,
		to_date,
	)

	return {
		"sales_person_commission_total": flt(sales_person_total),
		"sales_partner_commission_total": flt(sales_partner_total),
	}
