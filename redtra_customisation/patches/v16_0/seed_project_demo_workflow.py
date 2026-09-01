import frappe

from redtra_customisation.patches.v16_0.seed_project_demo_utils import (
	create_demo_budget,
	create_demo_material_issue,
	create_demo_project,
	create_demo_sales_invoice,
	create_demo_tasks,
	create_demo_timesheet,
	demo_project_exists,
	ensure_demo_masters,
	ensure_item_stock,
	get_demo_context,
	refresh_demo_project,
)


def execute():
	if demo_project_exists():
		return

	if not frappe.get_all("Company", limit=1):
		return

	try:
		_run_seed()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Project Demo Seed Failed")
		# Do not re-raise: a demo seed failure must not block migrate.


def _run_seed():
	ctx = get_demo_context()
	ensure_demo_masters(ctx)

	project = create_demo_project(ctx)
	create_demo_budget(ctx, project)
	tasks = create_demo_tasks(ctx, project)

	ensure_item_stock(ctx)
	create_demo_material_issue(ctx, project)
	create_demo_timesheet(ctx, project, tasks)
	create_demo_sales_invoice(ctx, project)
	refresh_demo_project(project)
