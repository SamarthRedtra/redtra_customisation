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
