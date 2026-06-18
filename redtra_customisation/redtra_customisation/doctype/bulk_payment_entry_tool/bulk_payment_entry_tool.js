// Copyright (c) 2026, Administrator and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Payment Entry Tool", {
	onload(frm) {
		if (!frm.doc.posting_date) {
			frm.set_value("posting_date", frappe.datetime.get_today());
		}
		if (!frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_default("company") || frappe.defaults.get_user_default("company"));
		}
		set_account_filters(frm);
		frm.trigger("payment_document_type");
	},
	refresh(frm) {
		frm.disable_save();
		set_account_filters(frm);
		frm.trigger("payment_document_type");
	},
	company(frm) {
		set_account_filters(frm);
	},
	payment_document_type(frm) {
		let doctypes = ["", "Sales Invoice", "Purchase Invoice"];
		if (frm.doc.payment_document_type === "Payment Entry") {
			doctypes = ["", "Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order", "Journal Entry"];
		}
		frm.fields_dict.payments.grid.update_docfield_property("invoice_doctype", "options", doctypes);
	},
	apply_default_to_rows(frm) {
		if (!frm.doc.payments || frm.doc.payments.length === 0) {
			frappe.msgprint(__("Add at least one payment row first."));
			return;
		}
		(frm.doc.payments || []).forEach((row) => {
			if (frm.doc.default_mode_of_payment && !row.mode_of_payment) {
				frappe.model.set_value(row.doctype, row.name, "mode_of_payment", frm.doc.default_mode_of_payment);
			}
			if (frm.doc.default_bank_cash_account && !row.bank_cash_account) {
				frappe.model.set_value(row.doctype, row.name, "bank_cash_account", frm.doc.default_bank_cash_account);
			}
		});
		frm.refresh_field("payments");
		frappe.show_alert({
			message: __("Default Mode of Payment and Bank Account applied to empty rows."),
			indicator: "green"
		});
	},
	create_payments(frm) {
		if (!frm.doc.payments || frm.doc.payments.length === 0) {
			frappe.msgprint(__("Please add at least one payment."));
			return;
		}

		// Validation before submitting to backend
		let missing_bank_account = false;
		let missing_pdc_details = false;
		
		(frm.doc.payments || []).forEach(row => {
			if (!row.bank_cash_account && !frm.doc.default_bank_cash_account && (!row.invoice_doctype || row.invoice_doctype === "None")) {
				missing_bank_account = true;
			}
			if (frm.doc.payment_document_type === "Post Dated Cheque") {
				if (!row.reference_no || !row.reference_date || !row.mode_of_payment) {
					missing_pdc_details = true;
				}
			}
		});

		if (missing_bank_account) {
			frappe.msgprint(__("Bank/Cash Account is mandatory for rows without invoice references."));
			return;
		}
		if (missing_pdc_details) {
			frappe.msgprint(__("Mode of Payment, Cheque No, and Cheque Date are mandatory for all rows when creating Post Dated Cheques."));
			return;
		}

		let doc_label = frm.doc.payment_document_type === "Post Dated Cheque" ? __("Post Dated Cheques") : __("Payment Entries");
		frappe.dom.freeze(__("Creating {0}...", [doc_label]));
		frappe.call({
			method: "redtra_customisation.redtra_customisation.doctype.bulk_payment_entry_tool.bulk_payment_entry_tool.create_bulk_payments",
			args: {
				company: frm.doc.company,
				posting_date: frm.doc.posting_date,
				action_type: frm.doc.action_type,
				payment_document_type: frm.doc.payment_document_type,
				payments: JSON.stringify(frm.doc.payments)
			},
			callback: function(r) {
				frappe.dom.unfreeze();
				if (r.message) {
					let results = r.message;
					let success_links = [];
					let failure_messages = [];

					results.forEach(res => {
						let row = (frm.doc.payments || []).find(p => p.name === res.name);
						if (row) {
							frappe.model.set_value(row.doctype, row.name, "status", res.status);
							if (res.status === "Success") {
								frappe.model.set_value(row.doctype, row.name, "payment_entry", res.payment_entry);
								frappe.model.set_value(row.doctype, row.name, "error_message", "");
								let route_name = res.payment_entry.startsWith("PDC-") ? "post-dated-cheques" : "payment-entry";
								success_links.push(`<a href="/app/${route_name}/${res.payment_entry}" target="_blank">${res.payment_entry}</a>`);
							} else {
								frappe.model.set_value(row.doctype, row.name, "error_message", res.error_message);
								failure_messages.push(`${row.party} (Row ${row.idx}): ${res.error_message}`);
							}
						}
					});
					frm.refresh_field("payments");

					if (success_links.length > 0) {
						frappe.msgprint({
							title: __("Documents Created"),
							message: __("Successfully created: {0}", [success_links.join(", ")]),
							indicator: "green"
						});
					}
					if (failure_messages.length > 0) {
						frappe.msgprint({
							title: __("Creation Failures"),
							message: __("Some rows failed to process:<br>{0}", [failure_messages.join("<br>")]),
							indicator: "red"
						});
					}
				}
			}
		});
	}
});

frappe.ui.form.on("Bulk Payment Entry Tool Detail", {
	invoice_name: function(frm, cdt, cdn) {
		let row = frappe.model.get_doc(cdt, cdn);
		if (row.invoice_name && row.invoice_doctype) {
			frappe.db.get_value(row.invoice_doctype, row.invoice_name, ["outstanding_amount", "customer", "supplier", "grand_total"], (r) => {
				if (r) {
					let amount = r.outstanding_amount !== undefined ? r.outstanding_amount : r.grand_total;
					frappe.model.set_value(cdt, cdn, "amount", amount);
					let party = r.customer || r.supplier;
					if (party && !row.party) {
						frappe.model.set_value(cdt, cdn, "party", party);
					}
				}
			});
		}
	},
	party_type: function(frm, cdt, cdn) {
		let row = frappe.model.get_doc(cdt, cdn);
		if (row.party_type === "Customer") {
			frappe.model.set_value(cdt, cdn, "payment_type", "Receive");
			frappe.model.set_value(cdt, cdn, "invoice_doctype", "Sales Invoice");
		} else if (row.party_type === "Supplier") {
			frappe.model.set_value(cdt, cdn, "payment_type", "Pay");
			frappe.model.set_value(cdt, cdn, "invoice_doctype", "Purchase Invoice");
		}
	}
});

function set_account_filters(frm) {
	const bank_account_filter = () => {
		return {
			filters: {
				company: frm.doc.company,
				is_group: 0,
				account_type: ["in", ["Bank", "Cash"]],
			}
		};
	};
	frm.set_query("default_bank_cash_account", bank_account_filter);
	frm.set_query("bank_cash_account", "payments", bank_account_filter);

	frm.set_query("invoice_name", "payments", (doc, cdn, cdg) => {
		let row = frappe.get_doc(cdn, cdg);
		let filters = {
			company: doc.company,
			docstatus: 1
		};
		if (row.party) {
			if (row.invoice_doctype === "Sales Invoice" || row.invoice_doctype === "Sales Order") {
				filters.customer = row.party;
			} else if (row.invoice_doctype === "Purchase Invoice" || row.invoice_doctype === "Purchase Order") {
				filters.supplier = row.party;
			}
		}
		return { filters: filters };
	});
}
