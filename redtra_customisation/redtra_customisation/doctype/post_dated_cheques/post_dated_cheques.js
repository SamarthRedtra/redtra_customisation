// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// For license information, please see license.txt

/**
 * Frappe Link: if `link_filters` is any non-empty string (including "[]"), link.js treats it
 * as active and overwrites get_query on every search — frm.set_query then never wins.
 * Do not set link_filters in JSON; clear any leftover on the field df + register query here.
 */
function clear_bank_account_link_filters(frm) {
	const df = frappe.meta.get_docfield("Post Dated Cheques", "bank_account");
	if (df) {
		df.link_filters = null;
	}
	if (frm.fields_dict.bank_account && frm.fields_dict.bank_account.df) {
		frm.fields_dict.bank_account.df.link_filters = null;
	}
}

function set_bank_account_query(frm) {
	clear_bank_account_link_filters(frm);
	frm.set_query("bank_account", function () {
		if (!frm.doc.company) {
			return { filters: { name: ["in", []] } };
		}
		return {
			filters: {
				company: frm.doc.company,
				is_group: 0,
				account_type: ["in", ["Bank", "Cash"]],
			},
		};
	});
}

frappe.ui.form.on("Post Dated Cheques", {
	setup(frm) {
		set_bank_account_query(frm);
	},
	onload(frm) {
		set_bank_account_query(frm);
	},
	refresh(frm) {
		set_bank_account_query(frm);
		if (frm.is_new()) return;

		if (frm.doc.payment_entry) {
			frm.add_custom_button(
				__("Open Payment Entry"),
				() => frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry),
				__("Payment")
			);
			frm.add_custom_button(
				__("General Ledger"),
				() => {
					frappe.route_options = {
						company: frm.doc.company,
						voucher_no: frm.doc.payment_entry,
						from_date: frm.doc.reference_date,
						to_date: frm.doc.reference_date,
					};
					frappe.set_route("query-report", "General Ledger");
				},
				__("Payment")
			);
		}
	},
	company(frm) {
        frm.set_value("bank_account", "");
		set_bank_account_query(frm);
	},
});
