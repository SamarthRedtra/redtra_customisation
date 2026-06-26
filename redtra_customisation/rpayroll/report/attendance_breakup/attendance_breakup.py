# Copyright (c) 2026, Redtra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, formatdate, cstr
from frappe.utils.jinja import get_jenv


def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 100,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Status"),
			"fieldname": "attendance_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Check In"),
			"fieldname": "check_in",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{
			"label": _("Check Out"),
			"fieldname": "check_out",
			"fieldtype": "Datetime",
			"width": 140,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 120,
		},
		{
			"label": _("Std Hrs"),
			"fieldname": "standard_working_hours",
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"label": _("Regular Hrs"),
			"fieldname": "regular_hours",
			"fieldtype": "Float",
			"width": 90,
		},
		{
			"label": _("OT Hrs"),
			"fieldname": "overtime_hours",
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"label": _("OT Amount"),
			"fieldname": "overtime_amount",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Salary Slip"),
			"fieldname": "salary_slip",
			"fieldtype": "Link",
			"options": "Salary Slip",
			"width": 140,
		},
	]


def get_data(filters):
	salary_slips = _get_salary_slips(filters)
	if not salary_slips:
		return []

	slip_names = [ss.name for ss in salary_slips]
	slip_map = {ss.name: ss for ss in salary_slips}

	# Fetch all attendance breakup rows for these slips in one query
	detail_filters = {"parent": ["in", slip_names]}
	if filters.get("project"):
		detail_filters["project"] = filters.get("project")

	breakup_rows = frappe.get_all(
		"Salary Slip Attendance Detail",
		filters=detail_filters,
		fields=[
			"parent",
			"date",
			"attendance_status",
			"check_in",
			"check_out",
			"project",
			"standard_working_hours",
			"regular_hours",
			"overtime_hours",
			"overtime_amount",
		],
		order_by="parent asc, date asc",
	)

	if filters.get("shift_type"):
		shift_attendances = frappe.get_all(
			"Attendance",
			filters={
				"attendance_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
				"shift": filters.get("shift_type"),
			},
			fields=["employee", "attendance_date"],
		)
		valid_pairs = {(att.employee, att.attendance_date) for att in shift_attendances}
		breakup_rows = [
			row for row in breakup_rows
			if (slip_map[row.parent].employee, row.date) in valid_pairs
		]

	data = []
	for row in breakup_rows:
		ss = slip_map.get(row.parent)
		if not ss:
			continue
		data.append({
			"employee": ss.employee,
			"employee_name": ss.employee_name,
			"date": row.date,
			"attendance_status": row.attendance_status,
			"check_in": row.check_in,
			"check_out": row.check_out,
			"project": row.project,
			"standard_working_hours": flt(row.standard_working_hours),
			"regular_hours": flt(row.regular_hours),
			"overtime_hours": flt(row.overtime_hours),
			"overtime_amount": flt(row.overtime_amount),
			"salary_slip": row.parent,
		})

	return data


def _get_salary_slips(filters):
	doc_status = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
	ss = frappe.qb.DocType("Salary Slip")
	query = frappe.qb.from_(ss).select(
		ss.name,
		ss.employee,
		ss.employee_name,
		ss.start_date,
		ss.end_date,
		ss.department,
		ss.company,
		ss.total_regular_hours,
		ss.total_overtime_hours,
		ss.total_overtime_amount,
		ss.gross_pay,
		ss.net_pay,
		ss.payment_days,
		ss.leave_without_pay,
		ss.absent_days,
	)

	if filters.get("docstatus"):
		query = query.where(ss.docstatus == doc_status[filters.get("docstatus")])

	if filters.get("from_date"):
		query = query.where(ss.start_date >= filters.get("from_date"))

	if filters.get("to_date"):
		query = query.where(ss.end_date <= filters.get("to_date"))

	if filters.get("company"):
		query = query.where(ss.company == filters.get("company"))

	if filters.get("employee"):
		query = query.where(ss.employee == filters.get("employee"))

	if filters.get("department"):
		query = query.where(ss.department == filters.get("department"))

	return query.run(as_dict=True)


@frappe.whitelist()
def download_employee_wise_print(
	from_date,
	to_date,
	company,
	employee=None,
	department=None,
	docstatus="Submitted",
	shift_type=None,
	project=None,
):
	"""Return an HTML page with one section (page-break) per employee."""
	filters = frappe._dict(
		from_date=from_date,
		to_date=to_date,
		company=company,
		employee=employee,
		department=department,
		docstatus=docstatus,
		shift_type=shift_type,
		project=project,
	)

	salary_slips = _get_salary_slips(filters)
	if not salary_slips:
		frappe.respond_as_web_page(
			_("No Records"),
			_("No salary slips found for the selected filters."),
		)
		return

	slip_names = [ss.name for ss in salary_slips]
	slip_map = {ss.name: ss for ss in salary_slips}

	# Fetch all attendance breakup rows for these slips in one query
	detail_filters = {"parent": ["in", slip_names]}
	if filters.get("project"):
		detail_filters["project"] = filters.get("project")

	breakup_rows = frappe.get_all(
		"Salary Slip Attendance Detail",
		filters=detail_filters,
		fields=[
			"parent",
			"date",
			"attendance_status",
			"check_in",
			"check_out",
			"project",
			"standard_working_hours",
			"regular_hours",
			"overtime_hours",
			"overtime_amount",
		],
		order_by="parent asc, date asc",
	)

	if filters.get("shift_type"):
		shift_attendances = frappe.get_all(
			"Attendance",
			filters={
				"attendance_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
				"shift": filters.get("shift_type"),
			},
			fields=["employee", "attendance_date"],
		)
		valid_pairs = {(att.employee, att.attendance_date) for att in shift_attendances}
		breakup_rows = [
			row for row in breakup_rows
			if (slip_map[row.parent].employee, row.date) in valid_pairs
		]

	# Group by salary slip (one per employee in the period)
	rows_by_slip = {}
	for row in breakup_rows:
		rows_by_slip.setdefault(row.parent, []).append(row)

	# Build per-employee groups: one entry per salary slip
	employee_groups = []
	for slip_name in slip_names:
		rows = rows_by_slip.get(slip_name, [])
		if (filters.get("project") or filters.get("shift_type")) and not rows:
			continue
		ss = slip_map[slip_name]
		employee_groups.append({
			"salary_slip": slip_name,
			"employee": ss.employee,
			"employee_name": ss.employee_name,
			"department": ss.department,
			"company": ss.company,
			"start_date": ss.start_date,
			"end_date": ss.end_date,
			"payment_days": flt(ss.payment_days),
			"leave_without_pay": flt(ss.leave_without_pay),
			"absent_days": flt(ss.absent_days),
			"total_regular_hours": flt(ss.total_regular_hours),
			"total_overtime_hours": flt(ss.total_overtime_hours),
			"total_overtime_amount": flt(ss.total_overtime_amount),
			"gross_pay": flt(ss.gross_pay),
			"net_pay": flt(ss.net_pay),
			"rows": rows,
		})

	if not employee_groups:
		frappe.respond_as_web_page(
			_("No Records"),
			_("No salary slips matching the selected project/shift type filters were found."),
		)
		return

	# Get company details (letter head etc.)
	company_doc = frappe.get_cached_doc("Company", company)

	# Get letter head HTML
	letter_head_html = ""
	default_letter_head = frappe.db.get_value("Letter Head", {"is_default": 1}, "name")
	if default_letter_head:
		letter_head_doc = frappe.get_cached_doc("Letter Head", default_letter_head)
		letter_head_html = letter_head_doc.get("content") or ""

	html = _render_print_html(
		employee_groups=employee_groups,
		filters=filters,
		company_doc=company_doc,
		letter_head_html=letter_head_html,
	)

	from werkzeug.wrappers import Response
	return Response(html, mimetype="text/html")


def _status_badge_color(status):
	"""Return a CSS colour for the attendance status badge."""
	status_lower = cstr(status).lower()
	if "present" in status_lower:
		return "#2ecc71"
	elif "absent" in status_lower:
		return "#e74c3c"
	elif "holiday" in status_lower:
		return "#3498db"
	elif "half" in status_lower:
		return "#f39c12"
	elif "leave" in status_lower:
		return "#9b59b6"
	else:
		return "#95a5a6"


def _fmt_time(dt_val):
	"""Format a datetime as HH:MM."""
	if not dt_val:
		return ""
	try:
		return dt_val.strftime("%H:%M")
	except Exception:
		return cstr(dt_val)


def _fmt_date(d):
	"""Format date as DD-Mon-YYYY."""
	if not d:
		return ""
	try:
		return d.strftime("%d %b %Y")
	except Exception:
		return cstr(d)


def _render_print_html(employee_groups, filters, company_doc, letter_head_html):
	"""Build the full HTML string for employee-wise print."""

	css = """
	<style>
		@page { size: A4 landscape; margin: 12mm; }
		* { box-sizing: border-box; }
		body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt; color: #222; margin: 0; padding: 0; }
		.emp-section { page-break-after: always; padding: 0 0 8mm 0; }
		.emp-section:last-child { page-break-after: avoid; }
		.letter-head { text-align: center; margin-bottom: 6px; }
		.report-title { text-align: center; font-size: 14pt; font-weight: bold; margin: 4px 0 2px 0; color: #1a3a5c; }
		.date-range { text-align: center; font-size: 9pt; color: #555; margin-bottom: 8px; }
		.emp-header { background: #1a3a5c; color: #fff; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; }
		.emp-header .emp-name { font-size: 11pt; font-weight: bold; }
		.emp-header .emp-meta { font-size: 8.5pt; opacity: 0.85; }
		.summary-bar { display: flex; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
		.summary-card { background: #f0f4fa; border: 1px solid #c8d5e8; border-radius: 4px; padding: 4px 10px; text-align: center; min-width: 100px; }
		.summary-card .val { font-size: 11pt; font-weight: bold; color: #1a3a5c; }
		.summary-card .lbl { font-size: 7.5pt; color: #666; }
		table { width: 100%; border-collapse: collapse; font-size: 8.5pt; }
		th { background: #2c5f8a; color: #fff; padding: 4px 6px; text-align: center; border: 1px solid #1a3a5c; font-weight: 600; }
		td { padding: 3px 6px; border: 1px solid #d0d8e4; text-align: center; vertical-align: middle; }
		tr:nth-child(even) td { background: #f5f8fc; }
		tr:nth-child(odd) td { background: #fff; }
		.status-badge { display: inline-block; padding: 1px 6px; border-radius: 10px; color: #fff; font-size: 7.5pt; font-weight: bold; white-space: nowrap; }
		.text-left { text-align: left; }
		.text-right { text-align: right; }
		.totals-row td { background: #e8f0fa !important; font-weight: bold; border-top: 2px solid #2c5f8a; }
		.print-footer { text-align: right; font-size: 7.5pt; color: #999; margin-top: 4px; }
		.no-rows { text-align: center; color: #999; padding: 10px; font-style: italic; }
	</style>
	"""

	sections = []
	for i, emp in enumerate(employee_groups):
		rows_html = ""
		total_regular = 0.0
		total_ot = 0.0
		total_ot_amt = 0.0

		if emp["rows"]:
			row_items = []
			for idx, row in enumerate(emp["rows"]):
				date_str = _fmt_date(row.date)
				status = cstr(row.attendance_status)
				badge_color = _status_badge_color(status)
				check_in = _fmt_time(row.check_in)
				check_out = _fmt_time(row.check_out)
				project = cstr(row.project) if row.project else "-"
				std_hrs = flt(row.standard_working_hours)
				reg_hrs = flt(row.regular_hours)
				ot_hrs = flt(row.overtime_hours)
				ot_amt = flt(row.overtime_amount)

				total_regular += reg_hrs
				total_ot += ot_hrs
				total_ot_amt += ot_amt

				row_items.append(f"""
				<tr>
					<td>{idx + 1}</td>
					<td class="text-left">{date_str}</td>
					<td><span class="status-badge" style="background:{badge_color}">{status or '-'}</span></td>
					<td>{check_in or '-'}</td>
					<td>{check_out or '-'}</td>
					<td class="text-left">{project}</td>
					<td class="text-right">{f'{std_hrs:.2f}' if std_hrs else '-'}</td>
					<td class="text-right">{reg_hrs:.2f}</td>
					<td class="text-right">{ot_hrs:.2f}</td>
					<td class="text-right">{ot_amt:,.2f}</td>
				</tr>
				""")

			totals_row = f"""
			<tr class="totals-row">
				<td colspan="6" class="text-right">Total</td>
				<td class="text-right">-</td>
				<td class="text-right">{total_regular:.2f}</td>
				<td class="text-right">{total_ot:.2f}</td>
				<td class="text-right">{total_ot_amt:,.2f}</td>
			</tr>
			"""
			rows_html = "".join(row_items) + totals_row
		else:
			rows_html = '<tr><td colspan="10" class="no-rows">No attendance records found.</td></tr>'

		section = f"""
		<div class="emp-section">
			<div class="letter-head">{letter_head_html}</div>
			<div class="report-title">Attendance Breakup Report</div>
			<div class="date-range">
				Period: {_fmt_date(filters.from_date)} to {_fmt_date(filters.to_date)} &nbsp;|&nbsp; Salary Slip: {emp['salary_slip']}
			</div>
			<div class="emp-header">
				<div>
					<div class="emp-name">{emp['employee_name']} &nbsp;<span style="font-size:9pt;opacity:0.8">({emp['employee']})</span></div>
					<div class="emp-meta">
						Department: {emp['department'] or '-'} &nbsp;|&nbsp;
						Company: {emp['company']}
					</div>
				</div>
				<div class="emp-meta" style="text-align:right;">
					Period: {_fmt_date(emp['start_date'])} to {_fmt_date(emp['end_date'])}
				</div>
			</div>
			<table>
				<thead>
					<tr>
						<th>#</th>
						<th>Date</th>
						<th>Status</th>
						<th>Check In</th>
						<th>Check Out</th>
						<th>Project</th>
						<th>Std Hrs</th>
						<th>Regular Hrs</th>
						<th>OT Hrs</th>
						<th>OT Amount</th>
					</tr>
				</thead>
				<tbody>
					{rows_html}
				</tbody>
			</table>
			<div class="print-footer">Printed on: {frappe.utils.now_datetime().strftime('%d %b %Y %H:%M')}</div>
		</div>
		"""
		sections.append(section)

	html = f"""<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8">
	<title>Attendance Breakup - {filters.from_date} to {filters.to_date}</title>
	{css}
</head>
<body>
{''.join(sections)}
<script>window.onload = function() {{ window.print(); }};</script>
</body>
</html>"""

	return html
