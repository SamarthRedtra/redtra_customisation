import frappe
from frappe import _
from frappe.utils import add_to_date, flt, now_datetime


def auto_complete_job_cards(doc, method=None):
	"""Submit and complete Job Cards tied to a Work Order once stock is fully transferred."""
	if doc.docstatus != 1:
		return

	settings = frappe.get_cached_doc("Redtra Custom Setting")
	if not settings.skip_job_card_process:
		return

	if not settings.default_employee:
		frappe.throw(_("Please set Default Employee in Redtra Custom Setting to auto-complete Job Cards."))

	current_status = doc.status or doc.get_status()
	if current_status not in ("In Process", "In Progress"):
		return

	qty_precision = doc.precision("qty") or 3
	transfer_precision = doc.precision("material_transferred_for_manufacturing") or qty_precision

	if flt(doc.material_transferred_for_manufacturing, transfer_precision) < flt(doc.qty, qty_precision):
		return

	job_cards = frappe.get_all(
		"Job Card",
		filters={"work_order": doc.name, "docstatus": 0},
		pluck="name",
	)

	for job_card in job_cards:
		_submit_and_complete_job_card(job_card, settings.default_employee)


def auto_complete_job_cards_from_stock_entry(doc, method=None):
	"""Trigger auto completion when material transfer Stock Entry is submitted."""
	if doc.purpose != "Material Transfer for Manufacture" or not doc.work_order:
		return

	work_order = frappe.get_doc("Work Order", doc.work_order)
	auto_complete_job_cards(work_order)


def _submit_and_complete_job_card(job_card_name: str, employee: str) -> None:
	job_card = frappe.get_doc("Job Card", job_card_name)
	employees_for_log = [{"employee": employee}]

	start_time = now_datetime()
	end_time = add_to_date(start_time, minutes=1)

	if not job_card.time_logs:
		job_card.add_time_logs(from_time=start_time, employees=employees_for_log)

	open_log_exists = any(log.employee == employee and not log.to_time for log in job_card.time_logs)
	if not open_log_exists:
		job_card.add_time_logs(from_time=start_time, employees=employees_for_log)

	job_card.add_time_logs(
		to_time=end_time, completed_qty=job_card.for_quantity, employees=employees_for_log
	)

	if job_card.transferred_qty < job_card.for_quantity:
		job_card.transferred_qty = job_card.for_quantity

	job_card.flags.ignore_permissions = True
	job_card.flags.ignore_version = True
	job_card.save()

	if job_card.docstatus == 0:
		job_card.submit()

	if job_card.status != "Completed":
		job_card.db_set("status", "Completed")
