# Copyright (c) 2026, samarth.upare@redtra.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, qb
from frappe.query_builder import Criterion


ALLOWED_DOCTYPES = {
	"Sales Order": "transaction_date",
	"Delivery Note": "posting_date",
	"Sales Invoice": "posting_date",
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
