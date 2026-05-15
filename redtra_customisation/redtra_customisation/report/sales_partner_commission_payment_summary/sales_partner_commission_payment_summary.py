# Copyright (c) 2026, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, qb
from frappe.query_builder import Criterion, Order
from pypika.terms import ValueWrapper


ALLOWED_DOCTYPES = {
	"Sales Order": "transaction_date",
	"Delivery Note": "posting_date",
	"Sales Invoice": "posting_date",
	"POS Invoice": "posting_date",
	"Journal Entry": "posting_date",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})

	validate_filters(filters)

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data


def validate_filters(filters):
	if filters.get("doctype") not in ALLOWED_DOCTYPES:
		msgprint(_("Please select a valid document type first"), raise_exception=1)


def get_columns(filters):
	return [
		{
			"label": _(filters["doctype"]),
			"options": filters["doctype"],
			"fieldname": "source_name",
			"fieldtype": "Link",
			"width": 140,
		},
		{
			"label": _("Customer"),
			"options": "Customer",
			"fieldname": "customer",
			"fieldtype": "Link",
			"width": 140,
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Territory"),
			"options": "Territory",
			"fieldname": "territory",
			"fieldtype": "Link",
			"width": 100,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 140,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 140,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Sales Partner"),
			"options": "Sales Partner",
			"fieldname": "sales_partner",
			"fieldtype": "Link",
			"width": 140,
		},
		{
			# Optional link on Sales Partner; Payment Entry from report may omit party when empty.
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("User Remarks"),
			"fieldname": "user_remark",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Commission Rate %"),
			"fieldname": "commission_rate",
			"fieldtype": "Percent",
			"width": 120,
		},
		{
			"label": _("Commission Amount"),
			"fieldname": "commission_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"label": _("Create Payment Entry"),
			"fieldname": "create_payment_entry",
			"fieldtype": "Data",
			"width": 170,
		},
	]


def get_entries(filters):
	if filters["doctype"] == "Journal Entry":
		return get_journal_entries(filters)

	# Employee comes from Sales Partner only when that custom field exists and is set; it is not required for commission rows.
	dt = qb.DocType(filters["doctype"])
	sp = qb.DocType("Sales Partner")
	emp = qb.DocType("Employee")
	date_field = dt[ALLOWED_DOCTYPES[filters["doctype"]]]
	company_currency = frappe.db.get_value("Company", filters.get("company"), "default_currency")
	has_employee_field = frappe.db.has_column("Sales Partner", "employee")

	employee = sp.employee if has_employee_field else ValueWrapper("")
	employee_name = emp.employee_name if has_employee_field else ValueWrapper("")

	query = (
		qb.from_(dt)
		.left_join(sp)
		.on(sp.name.eq(dt.sales_partner))
		.select(
			dt.name.as_("source_name"),
			dt.customer,
			dt.territory,
			date_field.as_("posting_date"),
			dt.company,
			dt.project,
			dt.base_net_total.as_("amount"),
			dt.sales_partner,
			employee.as_("employee"),
			employee_name.as_("employee_name"),
			dt.commission_rate,
			dt.total_commission.as_("commission_amount"),
			ValueWrapper(company_currency).as_("currency"),
		)
		.where(Criterion.all(get_conditions(dt, filters, date_field)))
		.orderby(dt.name, order=Order.desc)
		.orderby(dt.sales_partner)
	)

	if has_employee_field:
		query = query.left_join(emp).on(emp.name.eq(sp.employee))

	entries = query.run(as_dict=True)

	for entry in entries:
		entry.source_doctype = filters["doctype"]
		entry.create_payment_entry = ""

	return entries


def get_journal_entries(filters):
	company = filters.get("company")
	if not company:
		return []

	commission_accounts = _get_commission_accounts(company)
	print(f"Commission Accounts: {commission_accounts}")
	if not commission_accounts:
		return []

	conditions = [
		"gle.docstatus = 1",
		"gle.is_cancelled = 0",
		"gle.company = %(company)s",
		"gle.voucher_type = 'Journal Entry'",
		"gle.account IN %(accounts)s",
	]
	args = {"company": company, "accounts": commission_accounts}

	for field in ("from_date", "to_date", "project"):
		value = filters.get(field)
		if not value:
			continue
		if field == "from_date":
			conditions.append("gle.posting_date >= %(from_date)s")
		elif field == "to_date":
			conditions.append("gle.posting_date <= %(to_date)s")
		else:
			conditions.append("gle.project = %(project)s")
		args[field] = value

	currency = frappe.db.get_value("Company", company, "default_currency")
	rows = frappe.db.sql(
		f"""
		SELECT
			gle.voucher_no AS source_name,
			gle.posting_date,
			gle.company,
			gle.project,
			gle.party AS sales_partner,
			je.user_remark,
			(gle.debit - gle.credit) AS commission_amount
		FROM `tabGL Entry` gle
		LEFT JOIN `tabJournal Entry` je ON je.name = gle.voucher_no
		WHERE {' AND '.join(conditions)}
			AND ABS(gle.debit - gle.credit) > 0
		ORDER BY gle.posting_date DESC, gle.voucher_no DESC
		""",
		args,
		as_dict=True,
	)

	has_employee_field = frappe.db.has_column("Sales Partner", "employee")
	for row in rows:
		row.source_doctype = "Journal Entry"
		row.customer = None
		row.territory = None
		row.amount = row.commission_amount
		row.commission_rate = 0
		row.currency = currency
		if not has_employee_field or not row.sales_partner:
			row.employee = None
			row.employee_name = None
		else:
			row.employee = frappe.db.get_value("Sales Partner", row.sales_partner, "employee")
			row.employee_name = (
				frappe.db.get_value("Employee", row.employee, "employee_name")
				if row.employee
				else None
			)
		row.create_payment_entry = ""

	return rows


def _get_commission_accounts(company):
	accounts = []
	if frappe.db.exists("DocType", "BOQ Settings"):
		acc = frappe.db.get_value("BOQ Settings", company, "sales_partner_commission_account")
		if acc:
			accounts.append(acc)

	return list(set(accounts))


def get_conditions(dt, filters, date_field):
	conditions = [
		dt.docstatus.eq(1),
		dt.sales_partner.isnotnull(),
		dt.sales_partner != "",
	]

	for field in ["company", "customer", "territory"]:
		if filters.get(field):
			conditions.append(dt[field].eq(filters.get(field)))

	if filters.get("sales_partner"):
		conditions.append(dt.sales_partner.eq(filters.get("sales_partner")))

	if filters.get("from_date"):
		conditions.append(date_field.gte(filters.get("from_date")))

	if filters.get("to_date"):
		conditions.append(date_field.lte(filters.get("to_date")))

	if filters.get("project"):
		conditions.append(dt.project.eq(filters.get("project")))

	return conditions
