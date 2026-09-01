import datetime

import frappe
from frappe.utils import add_to_date, flt, getdate, now_datetime, today

from erpnext.accounts.utils import get_fiscal_year
from erpnext.stock.doctype.bin.bin import get_actual_qty
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

DEMO_PROJECT_NAME = "Redtra Demo Project"
DEMO_CUSTOMER = "DEMO-CUST-001"
DEMO_ITEM = "DEMO-ITEM-001"
DEMO_SALES_PERSON = "DEMO-SP-001"
DEMO_ACTIVITY = "DEMO-Activity"

DEMO_BUDGET_AMOUNT = 100_000
STOCK_RECEIPT_QTY = 100
STOCK_RECEIPT_RATE = 500
MATERIAL_ISSUE_QTY = 20
SI_QTY = 10
SI_RATE = 8000

DEMO_TASKS = (
	{"subject": "Site Preparation", "progress": 100, "status": "Completed"},
	{"subject": "Material Procurement", "progress": 75, "status": "Working"},
	{"subject": "Installation", "progress": 40, "status": "Working"},
	{"subject": "Handover", "progress": 0, "status": "Open"},
)


def demo_project_exists():
	return bool(frappe.db.exists("Project", {"project_name": DEMO_PROJECT_NAME}))


def get_demo_context():
	company = _get_company()
	if not company:
		frappe.throw("No Company found for project demo seed")

	warehouse = frappe.db.get_value(
		"Warehouse", {"company": company, "is_group": 0}, "name", order_by="creation asc"
	)
	if not warehouse:
		frappe.throw(f"No warehouse found for company {company}")

	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	expense_account = (
		frappe.get_cached_value("Company", company, "default_expense_account")
		or frappe.get_cached_value("Company", company, "stock_adjustment_account")
	)
	income_account = frappe.get_cached_value("Company", company, "default_income_account")
	fiscal_year, fy_start, fy_end = get_fiscal_year(today(), company=company)

	return frappe._dict(
		company=company,
		warehouse=warehouse,
		cost_center=cost_center,
		expense_account=expense_account,
		income_account=income_account,
		fiscal_year=fiscal_year,
		fy_start=fy_start,
		fy_end=fy_end,
		customer=None,
		item=None,
		sales_person=None,
		employee=None,
		activity_type=None,
	)


def ensure_demo_masters(ctx):
	_ensure_boq_settings(ctx.company)
	ctx.customer = _ensure_customer(ctx.company)
	ctx.item = _ensure_item(ctx.company, ctx.warehouse)
	ctx.sales_person = _ensure_sales_person()
	ctx.activity_type = _ensure_activity_type()
	ctx.employee = _get_employee(ctx.company)
	return ctx


def create_demo_project(ctx):
	project = frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": DEMO_PROJECT_NAME,
			"status": "Open",
			"customer": ctx.customer,
			"company": ctx.company,
			"cost_center": ctx.cost_center,
			"estimated_costing": DEMO_BUDGET_AMOUNT,
			"percent_complete_method": "Task Progress",
			"expected_start_date": getdate(ctx.fy_start),
			"expected_end_date": getdate(ctx.fy_end),
		}
	)
	project.insert(ignore_permissions=True)
	return project.name


def create_demo_budget(ctx, project):
	budget = frappe.new_doc("Budget")
	budget.budget_against = "Project"
	budget.project = project
	budget.company = ctx.company
	budget.account = ctx.expense_account
	budget.from_fiscal_year = ctx.fiscal_year
	budget.to_fiscal_year = ctx.fiscal_year
	budget.budget_amount = DEMO_BUDGET_AMOUNT
	budget.distribution_frequency = "Monthly"
	budget.distribute_equally = 1
	budget.applicable_on_booking_actual_expenses = 1
	budget.action_if_annual_budget_exceeded = "Ignore"
	budget.action_if_accumulated_monthly_budget_exceeded = "Ignore"
	budget.insert(ignore_permissions=True)
	budget.submit()
	return budget.name


def create_demo_tasks(ctx, project):
	tasks = {}
	for row in DEMO_TASKS:
		task = frappe.get_doc(
			{
				"doctype": "Task",
				"subject": row["subject"],
				"project": project,
				"company": ctx.company,
				"progress": row["progress"],
				"status": row["status"],
			}
		)
		task.insert(ignore_permissions=True)
		tasks[row["subject"]] = task.name

	project_doc = frappe.get_doc("Project", project)
	project_doc.update_percent_complete()
	project_doc.save(ignore_permissions=True)
	return tasks


def ensure_item_stock(ctx, qty=STOCK_RECEIPT_QTY, rate=STOCK_RECEIPT_RATE):
	actual_qty = flt(get_actual_qty(ctx.item, ctx.warehouse))
	if actual_qty >= qty:
		return None

	make_stock_entry(
		item=ctx.item,
		qty=qty,
		target=ctx.warehouse,
		rate=rate,
		company=ctx.company,
		cost_center=ctx.cost_center,
		purpose="Material Receipt",
	)


def create_demo_material_issue(ctx, project):
	stock_entry = make_stock_entry(
		item=ctx.item,
		qty=MATERIAL_ISSUE_QTY,
		source=ctx.warehouse,
		company=ctx.company,
		cost_center=ctx.cost_center,
		expense_account=ctx.expense_account,
		purpose="Material Issue",
		do_not_save=True,
		do_not_submit=True,
	)
	stock_entry.project = project
	for row in stock_entry.items:
		row.project = project
	stock_entry.insert(ignore_permissions=True)
	stock_entry.submit()
	return stock_entry.name


def create_demo_timesheet(ctx, project, tasks):
	if not ctx.employee:
		frappe.log_error(
			"Skipping demo timesheet because no Employee was found",
			"Project Demo Seed",
		)
		return None

	timesheet = frappe.new_doc("Timesheet")
	timesheet.employee = ctx.employee
	timesheet.company = ctx.company

	time_rows = (
		(4, tasks.get("Site Preparation")),
		(6, tasks.get("Installation")),
	)
	base_time = add_to_date(now_datetime(), days=-1)

	for index, (hours, task) in enumerate(time_rows):
		if not task:
			continue
		from_time = add_to_date(base_time, hours=index * 8)
		row = timesheet.append("time_logs", {})
		row.activity_type = ctx.activity_type
		row.from_time = from_time
		row.hours = hours
		row.to_time = from_time + datetime.timedelta(hours=hours)
		row.project = project
		row.task = task

	if not timesheet.get("time_logs"):
		return None

	timesheet.insert(ignore_permissions=True)
	timesheet.submit()
	return timesheet.name


def create_demo_sales_invoice(ctx, project):
	si = frappe.new_doc("Sales Invoice")
	si.customer = ctx.customer
	si.company = ctx.company
	si.project = project
	si.posting_date = today()
	si.due_date = today()
	si.update_stock = 0
	si.append(
		"items",
		{
			"item_code": ctx.item,
			"qty": SI_QTY,
			"rate": SI_RATE,
			"income_account": ctx.income_account,
			"cost_center": ctx.cost_center,
		},
	)
	si.append(
		"sales_team",
		{
			"sales_person": ctx.sales_person,
			"allocated_percentage": 100,
		},
	)
	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


def refresh_demo_project(project):
	project_doc = frappe.get_doc("Project", project)
	project_doc.update_percent_complete()
	project_doc.update_costing()
	project_doc.save(ignore_permissions=True)


def _ensure_customer(company):
	if frappe.db.exists("Customer", DEMO_CUSTOMER):
		return DEMO_CUSTOMER

	existing = frappe.db.get_value("Customer", {}, "name", order_by="creation asc")
	if existing:
		return existing

	customer = frappe.new_doc("Customer")
	customer.customer_name = DEMO_CUSTOMER
	customer.customer_type = "Company"
	customer.insert(ignore_permissions=True)
	return customer.name


def _ensure_item(company, warehouse):
	if frappe.db.exists("Item", DEMO_ITEM):
		return DEMO_ITEM

	item_group = frappe.db.get_value(
		"Item Group", {"is_group": 0}, "name", order_by="lft asc"
	) or "Products"

	item = frappe.new_doc("Item")
	item.item_code = DEMO_ITEM
	item.item_name = "Demo Project Item"
	item.item_group = item_group
	item.is_stock_item = 1
	item.stock_uom = "Nos"
	item.append(
		"item_defaults",
		{
			"company": company,
			"default_warehouse": warehouse,
		},
	)
	item.insert(ignore_permissions=True)
	return item.item_code


def _ensure_boq_settings(company):
	if not frappe.db.exists("DocType", "BOQ Settings"):
		return
	if frappe.db.exists("BOQ Settings", company):
		return

	from construction_management.construction_management.doctype.boq_settings.boq_settings import (
		create_default_boq_settings,
	)

	create_default_boq_settings(company)


def _ensure_sales_person():
	if frappe.db.exists("Sales Person", DEMO_SALES_PERSON):
		return DEMO_SALES_PERSON

	existing = frappe.db.get_value("Sales Person", {}, "name", order_by="creation asc")
	if existing:
		return existing

	sales_person = frappe.new_doc("Sales Person")
	sales_person.sales_person_name = DEMO_SALES_PERSON
	sales_person.insert(ignore_permissions=True)
	return sales_person.name


def _ensure_activity_type():
	if frappe.db.exists("Activity Type", DEMO_ACTIVITY):
		return DEMO_ACTIVITY

	existing = frappe.db.get_value("Activity Type", {"disabled": 0}, "name", order_by="creation asc")
	if existing:
		return existing

	activity = frappe.new_doc("Activity Type")
	activity.activity_type = DEMO_ACTIVITY
	activity.costing_rate = 500
	activity.billing_rate = 1000
	activity.insert(ignore_permissions=True)
	return activity.name


def _get_employee(company):
	employee = frappe.db.get_value(
		"Employee",
		{"company": company, "status": "Active"},
		"name",
		order_by="creation asc",
	)
	if employee:
		return employee

	return frappe.db.get_value("Employee", {"status": "Active"}, "name", order_by="creation asc")


def _get_company():
	default_company = frappe.defaults.get_global_default("company")
	if default_company and default_company != "_Test Company":
		return default_company

	for company in frappe.get_all("Company", pluck="name", order_by="creation asc"):
		if company != "_Test Company":
			return company

	return default_company or frappe.db.get_value("Company", {}, "name", order_by="creation asc")
