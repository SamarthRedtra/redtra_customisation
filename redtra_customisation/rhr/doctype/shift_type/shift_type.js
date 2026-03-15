// Copyright (c) 2026, Redtra Customisation and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shift Type", {
	refresh: function (frm) {
		if (frm.doc.__islocal) return;

		hrms.add_shift_tools_button_to_form(frm, {
			action: "Assign Shift",
			shift_type: frm.doc.name,
		});

		frm.add_custom_button(__("Regenerate Food Allowance"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Regenerate Food Allowance"),
				fields: [
					{ fieldname: "from_date", fieldtype: "Date", label: __("From Date"), reqd: 1 },
					{ fieldname: "to_date", fieldtype: "Date", label: __("To Date"), reqd: 1 },
				],
				primary_action_label: __("Regenerate"),
				primary_action: (values) => {
					d.hide();
					frm.call({
						doc: frm.doc,
						method: "regenerate_food_allowance",
						args: { from_date: values.from_date, to_date: values.to_date },
						freeze: true,
						callback: (r) => {
							if (!r.exc && r.message) {
								frappe.show_alert({
									message: __("Created: {0}, Skipped: {1}, Processed: {2}", [
										r.message.created,
										r.message.skipped,
										r.message.processed,
									]),
									indicator: "green",
								});
							}
						},
					});
				},
			});
			d.show();
		});

		frm.add_custom_button(__("Mark Attendance"), () => {
			if (!frm.doc.enable_auto_attendance) {
				frm.scroll_to_field("enable_auto_attendance");
				frappe.throw(__("Please Enable Auto Attendance and complete the setup first."));
			}

			if (!frm.doc.process_attendance_after) {
				frm.scroll_to_field("process_attendance_after");
				frappe.throw(__("Please set {0}.", [__("Process Attendance After").bold()]));
			}

			if (!frm.doc.last_sync_of_checkin) {
				frm.scroll_to_field("last_sync_of_checkin");
				frappe.throw(__("Please set {0}.", [__("Last Sync of Checkin").bold()]));
			}

			frm.call({
				doc: frm.doc,
				method: "process_auto_attendance",
				freeze: true,
				callback: () => {
					frappe.msgprint(__("Attendance has been marked as per employee check-ins"));
				},
			});
		});
	},

	auto_update_last_sync: function (frm) {
		if (frm.doc.auto_update_last_sync) {
			frm.set_value("last_sync_of_checkin", "");
		}
	},
});
