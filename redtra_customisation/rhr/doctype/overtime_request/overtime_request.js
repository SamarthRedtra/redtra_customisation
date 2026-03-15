frappe.ui.form.on("Overtime Request", {
	refresh: function (frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__("Force Delete"), function () {
				frappe.confirm(
					__("This will delete the linked Attendance (if any) and then this Overtime Request. This cannot be undone."),
					function () {
						frappe.call({
							method: "redtra_customisation.rhr.doctype.overtime_request.overtime_request.force_delete_overtime_request",
							args: { name: frm.doc.name, delete_attendance: true },
							callback: function (r) {
								if (!r.exc) {
									frappe.show_alert({ message: __("Overtime Request and linked Attendance deleted"), indicator: "green" });
									frappe.set_route("List", "Overtime Request");
								}
							},
						});
					}
				);
			}).addClass("btn-danger");
		}
	},
});
