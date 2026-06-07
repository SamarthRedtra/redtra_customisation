// Copyright (c) 2026, redtra_customisation contributors

(function () {
	const REPORTS = ["General Ledger", "Advanced General Ledger"];

	function extend_report(name) {
		const settings = frappe.query_reports[name];
		if (!settings || settings._redtra_gl_extended) {
			return;
		}

		settings.filters = settings.filters || [];
		settings.filters.push(
			{
				fieldname: "include_against_account_entries",
				label: __("Include Against Account Entries"),
				fieldtype: "Check",
				default: 1,
			},
			{
				fieldname: "group_by_against_voucher",
				label: __("Group Payments With Against Invoice"),
				fieldtype: "Check",
				default: 1,
			}
		);

		settings._redtra_gl_extended = true;
	}

	function try_extend_all() {
		for (const name of REPORTS) {
			extend_report(name);
		}
	}

	try_extend_all();
	setTimeout(try_extend_all, 1000);
})();
