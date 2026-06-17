// Copyright (c) 2026, redtra_customisation contributors

(function () {
	const REPORTS = ["General Ledger", "Advanced General Ledger"];

	let settingsPromise = null;

	function get_redtra_gl_settings() {
		if (!settingsPromise) {
			settingsPromise = frappe.db
				.get_doc("Redtra Custom Setting", "Redtra Custom Setting")
				.then((doc) => ({
					include_against_account_entries: cint(
						doc?.include_against_account_entries_in_gl ?? 1
					),
					group_by_against_voucher: cint(doc?.group_by_against_voucher_in_gl ?? 1),
				}))
				.catch(() => ({
					include_against_account_entries: 1,
					group_by_against_voucher: 1,
				}));
		}
		return settingsPromise;
	}

	function extend_report(name, defaults) {
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
				default: defaults.include_against_account_entries,
			},
			{
				fieldname: "group_by_against_voucher",
				label: __("Group Payments With Against Invoice"),
				fieldtype: "Check",
				default: defaults.group_by_against_voucher,
			}
		);

		settings._redtra_gl_extended = true;
	}

	function try_extend_all() {
		get_redtra_gl_settings().then((defaults) => {
			for (const name of REPORTS) {
				extend_report(name, defaults);
			}
		});
	}

	try_extend_all();
	setTimeout(try_extend_all, 1000);
})();
