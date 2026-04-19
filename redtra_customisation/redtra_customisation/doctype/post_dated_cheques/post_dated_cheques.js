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

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Invoices"), () => {
				frm.events.fetch_invoices(frm);
			});
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Pending") {
			frm.add_custom_button(__("Convert Cheque"), () => {
				frappe.route_options = {
					pdc: frm.doc.name,
					company: frm.doc.company,
				};
				frappe.set_route("Form", "Post Dated Cheques Tool");
			});
		}

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
		frm.clear_table("invoice_references");
		calculate_total_amount(frm);
	},
	party_type(frm) {
		frm.clear_table("invoice_references");
		calculate_total_amount(frm);
	},
	party(frm) {
		frm.clear_table("invoice_references");
		calculate_total_amount(frm);
	},

	fetch_invoices(frm) {
		if (!frm.doc.party) {
			frappe.msgprint(__("Please select a Party first."));
			return;
		}

		const party_field = frm.doc.party_type === "Customer" ? "customer" : "supplier";
		const fil = [
			["docstatus", "=", 1],
			["company", "=", frm.doc.company],
			[party_field, "=", frm.doc.party],
			["outstanding_amount", ">", 0]
		];

		const dialog = new frappe.ui.form.MultiSelectDialog({
			doctype: frm.doc.party_type === "Customer" ? "Sales Invoice" : "Purchase Invoice",
			target: frm,
			setters: [
				{
					fieldname: "company",
					label: __("Company"),
					fieldtype: "Link",
					options: "Company",
					default: frm.doc.company,
				},
				{
					fieldname: party_field,
					label: __(frm.doc.party_type),
					fieldtype: "Link",
					options: frm.doc.party_type,
					default: frm.doc.party,
				}
			],
			get_query() {
				return {
					filters: fil
				};
			},
			action(selections) {
				if (!selections.length) return;

				// Properly merge array filters
				const fetch_filters = [...fil, ["name", "in", selections]];

				frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: frm.doc.party_type === "Customer" ? "Sales Invoice" : "Purchase Invoice",
						filters: fetch_filters,
						fields: ["name", "grand_total", "outstanding_amount"]
					},
					callback(r) {
						if (r.message) {
							r.message.forEach(d => {
								const row = frm.add_child("invoice_references");
								row.reference_doctype = frm.doc.party_type === "Customer" ? "Sales Invoice" : "Purchase Invoice";
								row.reference_name = d.name;
								row.total_amount = d.grand_total;
								row.outstanding_amount = d.outstanding_amount;
								row.allocated_amount = d.outstanding_amount;
							});

							calculate_total_amount(frm);
							frm.refresh_field("invoice_references");
						}
					}
				});
				dialog.dialog.hide();
			}
		});
	}
});

frappe.ui.form.on("PDC Invoice Reference", {
	allocated_amount(frm, cdt, cdn) {
		calculate_total_amount(frm);
	},
	invoice_references_remove(frm, cdt, cdn) {
		calculate_total_amount(frm);
	},
	reference_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.reference_name) {
			frappe.db.get_value(row.reference_doctype, row.reference_name, ["grand_total", "outstanding_amount"], (r) => {
				if (r) {
					frappe.model.set_value(cdt, cdn, "total_amount", r.grand_total);
					frappe.model.set_value(cdt, cdn, "outstanding_amount", r.outstanding_amount);
					frappe.model.set_value(cdt, cdn, "allocated_amount", r.outstanding_amount);
					calculate_total_amount(frm);
				}
			});
		}
	}
});

function calculate_total_amount(frm) {
	let total = 0;
	(frm.doc.invoice_references || []).forEach(row => {
		total += flt(row.allocated_amount);
	});
	frm.set_value("amount", total);
}
