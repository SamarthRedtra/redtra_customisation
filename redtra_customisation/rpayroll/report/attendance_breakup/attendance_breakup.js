// Copyright (c) 2026, Redtra and contributors
// For license information, please see license.txt

frappe.query_reports["Attendance Breakup"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
			width: "100px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			width: "100px",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			width: "150px",
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			width: "120px",
			get_query: function () {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
					},
				};
			},
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			width: "120px",
			get_query: function () {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
					},
				};
			},
		},
		{
			fieldname: "shift_type",
			label: __("Shift Type"),
			fieldtype: "Link",
			options: "Shift Type",
			width: "120px",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
			width: "120px",
		},
		{
			fieldname: "docstatus",
			label: __("Document Status"),
			fieldtype: "Select",
			options: ["Draft", "Submitted"],
			default: "Submitted",
			width: "100px",
		},
	],

	onload: function (report) {
		report.page.add_inner_button(__("Print Employee-wise"), function () {
			let filters = report.get_values();
			if (!filters.from_date || !filters.to_date || !filters.company) {
				frappe.msgprint(__("Please set From Date, To Date and Company filters first."));
				return;
			}

			// Open print in a new tab using the dedicated print URL
			let url = frappe.urllib.get_full_url(
				"/api/method/redtra_customisation.rpayroll.report.attendance_breakup.attendance_breakup.download_employee_wise_print"
				+ "?from_date=" + encodeURIComponent(filters.from_date)
				+ "&to_date=" + encodeURIComponent(filters.to_date)
				+ "&company=" + encodeURIComponent(filters.company)
				+ (filters.employee ? "&employee=" + encodeURIComponent(filters.employee) : "")
				+ (filters.department ? "&department=" + encodeURIComponent(filters.department) : "")
				+ (filters.docstatus ? "&docstatus=" + encodeURIComponent(filters.docstatus) : "")
				+ (filters.shift_type ? "&shift_type=" + encodeURIComponent(filters.shift_type) : "")
				+ (filters.project ? "&project=" + encodeURIComponent(filters.project) : "")
			);
			window.open(url);
		}, __("Print"));
	},
};
