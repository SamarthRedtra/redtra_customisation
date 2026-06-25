frappe.ui.form.on("Employee Attendance Tool", {
	refresh: function (frm) {
		frm.events.mark_full_day_attendance = function (frm, employees_to_mark_full_day, employees_to_mark_half_day) {
			frappe.call({
				method: "hrms.hr.doctype.employee_attendance_tool.employee_attendance_tool.mark_employee_attendance",
				args: {
					employee_list: employees_to_mark_full_day,
					status: frm.doc.status,
					date: frm.doc.date,
					late_entry: frm.doc.late_entry,
					early_exit: frm.doc.early_exit,
					shift: frm.doc.shift,
					project: frm.doc.project,
					mark_half_day: employees_to_mark_half_day.length ? true : false,
					half_day_status: frm.doc.half_day_status,
					half_day_employee_list: employees_to_mark_half_day,
					custom_from_date: frm.doc.custom_from_date,
					custom_to_date: frm.doc.custom_to_date,
				},
				freeze: true,
				freeze_message: __("Marking Attendance"),
				callback: function (r) {
					if (!r.exc) {
						frappe.show_alert({
							message: __("Attendance marked successfully"),
							indicator: "green",
						});
						frm.refresh();
					}
				}
			});
		};
	},
	custom_from_date: function (frm) {
		if (frm.doc.custom_from_date) {
			frm.set_value("date", frm.doc.custom_from_date);
		}
	}
});
