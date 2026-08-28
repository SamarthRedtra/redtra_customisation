frappe.ui.form.on("Petty Cash Entry", {
	setup(frm) {
		frm.set_query("party_type", () => ({
			filters: { name: ["in", ["Customer", "Supplier", "Employee", "Shareholder"]] },
		}));
		frm.set_query("cash_account", () => ({
			filters: { company: frm.doc.company, account_type: "Cash", is_group: 0, disabled: 0 },
		}));
		frm.set_query("expense_account", "expense_lines", () => ({
			filters: { company: frm.doc.company, root_type: "Expense", is_group: 0, disabled: 0 },
		}));
	},
	party_type(frm) {
		frm.set_value("party", null);
	},
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		const payment_entries = get_payment_entries(frm);
		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("Open Payment Entry"), () => {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			}, __("View"));
		}
		if (payment_entries.length > 1) {
			frm.add_custom_button(__("Payment Entries"), () => {
				frappe.set_route("List", "Payment Entry", { name: ["in", payment_entries] });
			}, __("View"));
		}
		if (payment_entries.length) {
			frm.add_custom_button(__("GL Entries"), () => {
				frappe.set_route("List", "GL Entry", { custom_petty_cash_entry: frm.doc.name });
			}, __("View"));
		}
		if (payment_entries.length === 1) {
			frm.add_custom_button(__("General Ledger"), () => {
				frappe.route_options = {
					company: frm.doc.company,
					from_date: frm.doc.posting_date,
					to_date: frm.doc.posting_date,
					voucher_no: payment_entries[0],
				};
				frappe.set_route("query-report", "General Ledger");
			}, __("View"));
		}
	},
});

function get_payment_entries(frm) {
	return [...new Set([
		frm.doc.payment_entry,
		...(frm.doc.expense_lines || []).map(row => row.payment_entry),
	].filter(Boolean))];
}

frappe.ui.form.on("Petty Cash Entry Account", {
	amount(frm) {
		frm.trigger("refresh");
	},
	expense_lines_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		for (const fieldname of ["project", "cost_center", "department"]) {
			if (!row[fieldname] && frm.doc[fieldname]) {
				frappe.model.set_value(cdt, cdn, fieldname, frm.doc[fieldname]);
			}
		}
	},
});
