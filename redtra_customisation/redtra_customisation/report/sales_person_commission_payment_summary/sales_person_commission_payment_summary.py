# Copyright (c) 2026, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, qb
from frappe.query_builder import Criterion


ALLOWED_DOCTYPES = {
	"Sales Order": "transaction_date",
	"Delivery Note": "posting_date",
	"Sales Invoice": "posting_date",
	"Journal Entry": "posting_date",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})

	validate_filters(filters)

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data


def validate_filters(filters):
	if filters.get("doc_type") not in ALLOWED_DOCTYPES:
		msgprint(_("Please select a valid document type first"), raise_exception=1)


def get_columns(filters):
	return [
		{
			"label": _(filters["doc_type"]),
			"options": filters["doc_type"],
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
			"label": _("Territory"),
			"options": "Territory",
			"fieldname": "territory",
			"fieldtype": "Link",
			"width": 110,
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
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Sales Person"),
			"options": "Sales Person",
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"width": 140,
		},
		{
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
			"label": _("Contribution %"),
			"fieldname": "contribution_percentage",
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"label": _("Commission Rate %"),
			"fieldname": "commission_rate",
			"fieldtype": "Percent",
			"width": 120,
		},
		{
			"label": _("Contribution Amount"),
			"fieldname": "contribution_amount",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Commission Amount"),
			"fieldname": "commission_amount",
			"fieldtype": "Currency",
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
	if filters["doc_type"] == "Journal Entry":
		return get_journal_entries(filters)

	dt = qb.DocType(filters["doc_type"])
	st = qb.DocType("Sales Team")
	sp = qb.DocType("Sales Person")
	emp = qb.DocType("Employee")
	date_field = dt[ALLOWED_DOCTYPES[filters["doc_type"]]]

	conditions = get_conditions(dt, st, filters, date_field)
	entries = (
		qb.from_(dt)
		.join(st)
		.on(st.parent.eq(dt.name) & st.parenttype.eq(filters["doc_type"]))
		.left_join(sp)
		.on(sp.name.eq(st.sales_person))
		.left_join(emp)
		.on(emp.name.eq(sp.employee))
		.select(
			dt.name.as_("source_name"),
			dt.customer,
			dt.territory,
			date_field.as_("posting_date"),
			dt.company,
			dt.project,
			dt.base_net_total.as_("amount"),
			st.sales_person,
			sp.employee,
			emp.employee_name,
			st.allocated_percentage.as_("contribution_percentage"),
			st.commission_rate,
			st.allocated_amount.as_("contribution_amount"),
			st.incentives.as_("commission_amount"),
		)
		.where(Criterion.all(conditions))
		.orderby(dt.name, st.sales_person)
		.run(as_dict=True)
	)

	for entry in entries:
		entry.source_doctype = filters["doc_type"]
		entry.create_payment_entry = ""

	return entries


def get_journal_entries(filters):
	company = filters.get("company")
	if not company:
		return []

	commission_accounts = _get_commission_accounts(company)
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

	rows = frappe.db.sql(
		f"""
		SELECT
			gle.voucher_no AS source_name,
			gle.posting_date,
			gle.company,
			gle.project,
			gle.party AS employee,
			(gle.debit - gle.credit) AS commission_amount
		FROM `tabGL Entry` gle
		WHERE {' AND '.join(conditions)}
			AND ABS(gle.debit - gle.credit) > 0
		ORDER BY gle.posting_date DESC, gle.voucher_no DESC
		""",
		args,
		as_dict=True,
	)

	for row in rows:
		row.source_doctype = "Journal Entry"
		row.customer = None
		row.territory = None
		row.amount = row.commission_amount
		row.sales_person = None
		row.contribution_percentage = 0
		row.commission_rate = 0
		row.contribution_amount = row.commission_amount
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
		acc = frappe.db.get_value("BOQ Settings", company, "sales_person_commission_account")
		if acc:
			accounts.append(acc)

	filters = [
		["company", "=", company],
		["is_group", "=", 0],
		["account_name", "like", "%Sales commission%"],
	]
	additional = frappe.db.get_all("Account", filters=filters, pluck="name")
	accounts.extend(additional)
	
	filters_2 = [
		["company", "=", company],
		["is_group", "=", 0],
		["account_name", "like", "%Commission on Sales%"],
	]
	additional_2 = frappe.db.get_all("Account", filters=filters_2, pluck="name")
	accounts.extend(additional_2)

	return list(set(accounts))


def get_conditions(dt, st, filters, date_field):
	conditions = [dt.docstatus.eq(1)]

	from_dt = filters.get("from_date")
	to_dt = filters.get("to_date")
	if from_dt and to_dt:
		conditions.append(date_field.between(from_dt, to_dt))
	elif from_dt:
		conditions.append(date_field.gte(from_dt))
	elif to_dt:
		conditions.append(date_field.lte(to_dt))

	for field in ["company", "customer", "territory"]:
		if filters.get(field):
			conditions.append(dt[field].eq(filters.get(field)))

	if filters.get("sales_person"):
		conditions.append(st.sales_person.eq(filters.get("sales_person")))

	if filters.get("project"):
		conditions.append(dt.project.eq(filters.get("project")))

	return conditions
