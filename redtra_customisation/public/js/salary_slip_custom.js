frappe.ui.form.on("Salary Slip", {
	custom_avoid_absenteeism: function (frm) {
		if (frm.doc.employee && frm.doc.start_date && frm.doc.end_date) {
			frm.events.get_emp_and_working_day_details(frm);
		}
	}
});
