// Copyright (c) 2026, redtra_customisation contributors

function clear_paid_account_link_filters(frm) {
	const df = frappe.meta.get_docfield("Cash Bank Entry", "paid_account");
	if (df) df.link_filters = null;
	if (frm.fields_dict.paid_account?.df) {
		frm.fields_dict.paid_account.df.link_filters = null;
	}
}

function set_paid_account_query(frm) {
	clear_paid_account_link_filters(frm);
	frm.set_query("paid_account", () => {
		if (!frm.doc.company) {
			return { filters: { name: ["in", []] } };
		}
		return {
			filters: {
				company: frm.doc.company,
				is_group: 0,
				account_type: frm.doc.account_type || "Bank",
			},
		};
	});
}

function setup_journal_naming_series(frm) {
	frappe.call({
		method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_journal_naming_series",
		callback(r) {
			if (!r.message?.options?.length) return;
			const options = r.message.options.join("\n");
			const df = frm.fields_dict.journal_naming_series?.df;
			if (df) {
				df.options = options;
				frm.refresh_field("journal_naming_series");
			}
			if (frm.is_new() && !frm.doc.journal_naming_series) {
				set_default_journal_naming_series(frm, r.message.options);
			}
		},
	});
}

function set_default_journal_naming_series(frm, options) {
	frappe.call({
		method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_default_journal_naming_series_for_cbe",
		args: {
			account_type: frm.doc.account_type || "Bank",
			entry_type: frm.doc.entry_type || "Payment",
		},
		callback(r) {
			if (r.message) {
				frm.set_value("journal_naming_series", r.message);
			} else if (options?.length) {
				frm.set_value("journal_naming_series", options[0]);
			}
		},
	});
}

function get_invoice_doctype_for_row(row, entry_type) {
	if (row.reference_doctype) return row.reference_doctype;
	if (row.party_type === "Supplier" || entry_type === "Payment") {
		return "Purchase Invoice";
	}
	return "Sales Invoice";
}

function recalculate_total(frm) {
	let total = 0;
	(frm.doc.accounts || []).forEach(row => {
		total += flt(row.amount) * flt(row.exchange_rate || 1);
	});
	frm.set_value("amount", total);
}

function set_multi_currency_flag(frm) {
	if (!frm.doc.company) return;
	const company_currency =
		frappe.defaults.get_default("currency") ||
		(frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency);
	frappe.db.get_value("Company", frm.doc.company, "default_currency").then(r => {
		const cc = r.message?.default_currency || company_currency;
		let multi = 0;
		if (frm.doc.paid_account_currency && frm.doc.paid_account_currency !== cc) {
			multi = 1;
		}
		(frm.doc.accounts || []).forEach(row => {
			if (row.account_currency && row.account_currency !== cc) {
				multi = 1;
			}
		});
		frm.set_value("multi_currency", multi);
		toggle_currency_columns(frm, multi);
	});
}

function toggle_currency_columns(frm, multi) {
	const grid = frm.fields_dict.accounts?.grid;
	if (!grid) return;
	const fields = ["account_currency", "exchange_rate", "amount_in_company_currency"];
	grid.set_column_disp(fields, multi);
}

function default_row_dimensions(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.project && frm.doc.project) {
		frappe.model.set_value(cdt, cdn, "project", frm.doc.project);
	}
	if (!row.cost_center && frm.doc.cost_center) {
		frappe.model.set_value(cdt, cdn, "cost_center", frm.doc.cost_center);
	}
	if (!row.department && frm.doc.department) {
		frappe.model.set_value(cdt, cdn, "department", frm.doc.department);
	}
}

function fetch_exchange_rate(frm, cdt, cdn, account_field) {
	const row = locals[cdt][cdn];
	const account = row[account_field || "account"];
	const date_to_use = row.posting_date || frm.doc.posting_date;
	if (!account || !frm.doc.company || !date_to_use) return;

	frappe.call({
		method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_exchange_rate_for_row",
		args: {
			posting_date: date_to_use,
			account,
			company: frm.doc.company,
			account_currency: row.account_currency,
			reference_type: row.reference_doctype,
			reference_name: row.reference_name,
			debit: flt(row.amount),
			exchange_rate: row.exchange_rate,
		},
		callback(r) {
			if (r.message) {
				frappe.model.set_value(cdt, cdn, "exchange_rate", r.message);
				frappe.model.set_value(
					cdt,
					cdn,
					"amount_in_company_currency",
					flt(row.amount) * flt(r.message)
				);
				recalculate_total(frm);
			}
		},
	});
}

function fetch_paid_account_exchange_rate(frm) {
	if (!frm.doc.paid_account || !frm.doc.company || !frm.doc.posting_date) return;
	frappe.call({
		method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_exchange_rate_for_row",
		args: {
			posting_date: frm.doc.posting_date,
			account: frm.doc.paid_account,
			company: frm.doc.company,
			account_currency: frm.doc.paid_account_currency,
			exchange_rate: frm.doc.paid_account_exchange_rate,
		},
		callback(r) {
			if (r.message) {
				frm.set_value("paid_account_exchange_rate", r.message);
			}
		},
	});
}

function compute_row_tax(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const template =
		frm.doc.entry_type === "Payment" ? row.purchase_tax_template : row.sales_tax_template;
	if (!template && !flt(row.tax_rate)) {
		frappe.model.set_value(cdt, cdn, "tax_amount", 0);
		return;
	}
	frappe.call({
		method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_tax_from_template",
		args: {
			template,
			amount: flt(row.amount),
			entry_type: frm.doc.entry_type,
			company: frm.doc.company,
		},
		callback(r) {
			if (!r.message) return;
			frappe.model.set_value(cdt, cdn, "tax_amount", flt(r.message.tax_amount));
			if (r.message.tax_account && !row.tax_account) {
				frappe.model.set_value(cdt, cdn, "tax_account", r.message.tax_account);
			}
		},
	});
}

function fetch_invoices_for_row(frm, row) {
	if (!row.party_type || !row.party || !frm.doc.company) {
		frappe.msgprint(__("Set Party on the row before fetching invoices."));
		return;
	}
	const reference_doctype = get_invoice_doctype_for_row(row, frm.doc.entry_type);
	const d = new frappe.ui.Dialog({
		title: __("Fetch Invoices"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "invoice",
				label: __("Invoice"),
				options: reference_doctype,
				get_query() {
					return {
						query: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.search_invoices_for_cbe",
						filters: {
							reference_doctype,
							company: frm.doc.company,
							party: row.party,
						},
					};
				},
			},
		],
		primary_action_label: __("Add"),
		primary_action(values) {
			if (!values.invoice) return;
			frappe.call({
				method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_cbe_invoice_details",
				args: {
					reference_doctype,
					invoices: [values.invoice],
				},
				callback(r) {
					const inv = (r.message || [])[0];
					if (!inv) {
						frappe.msgprint(__("Selected invoice is invalid, not submitted, or has no outstanding amount."));
						d.hide();
						return;
					}
					frappe.model.set_value(row.doctype, row.name, "reference_doctype", reference_doctype);
					frappe.model.set_value(row.doctype, row.name, "reference_name", inv.name);
					frappe.model.set_value(
						row.doctype,
						row.name,
						"allocated_amount",
						flt(inv.remaining_allocatable)
					);
					if (inv.account) {
						frappe.model.set_value(row.doctype, row.name, "account", inv.account);
					}
					if (!flt(row.amount)) {
						frappe.model.set_value(row.doctype, row.name, "amount", flt(inv.remaining_allocatable));
					}
					d.hide();
					recalculate_total(frm);
				},
			});
		},
	});
	d.show();
}

frappe.ui.form.on("Cash Bank Entry", {
	setup(frm) {
		set_paid_account_query(frm);
		setup_journal_naming_series(frm);
		frm.set_query("mode_of_payment", () => ({
			filters: { enabled: 1 },
		}));
	},
	onload(frm) {
		set_paid_account_query(frm);
		setup_journal_naming_series(frm);
	},
	refresh(frm) {
		set_paid_account_query(frm);
		set_multi_currency_flag(frm);

		if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
			frm.add_custom_button(__("Open Journal Entry"), () => {
				frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry);
			});
		}
		if (frm.doc.docstatus === 1 && frm.doc.payment_entry) {
			frm.add_custom_button(__("Open Payment Entry"), () => {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			});
		}
		if (frm.doc.docstatus === 1 && frm.doc.post_dated_cheque) {
			frm.add_custom_button(__("Open Post Dated Cheque"), () => {
				frappe.set_route("Form", "Post Dated Cheques", frm.doc.post_dated_cheque);
			});
		}
		if (frm.doc.docstatus === 1 && (frm.doc.journal_entry || frm.doc.payment_entry || frm.doc.post_dated_cheque)) {
			frm.add_custom_button(__("General Ledger"), () => {
				const voucher = frm.doc.journal_entry || frm.doc.payment_entry || frm.doc.post_dated_cheque;
				const voucher_type = frm.doc.journal_entry ? "Journal Entry" : (frm.doc.payment_entry ? "Payment Entry" : "Post Dated Cheques");
				frappe.route_options = {
					company: frm.doc.company,
					from_date: frm.doc.posting_date,
					to_date: frm.doc.posting_date,
					voucher_no: voucher,
				};
				frappe.set_route("query-report", "General Ledger");
			});
		}

		// Render custom connection dashboard
		setTimeout(() => {
			render_custom_dashboard(frm);
		}, 100);
	},
	company(frm) {
		set_paid_account_query(frm);
		set_multi_currency_flag(frm);
	},
	posting_date(frm) {
		fetch_paid_account_exchange_rate(frm);
		(frm.doc.accounts || []).forEach(row => {
			fetch_exchange_rate(frm, row.doctype, row.name);
		});
	},
	entry_type(frm) {
		set_multi_currency_flag(frm);
		if (frm.is_new()) {
			setup_journal_naming_series(frm);
		}
	},
	account_type(frm) {
		frm.set_value("paid_account", "");
		set_paid_account_query(frm);
		if (frm.is_new()) {
			setup_journal_naming_series(frm);
		}
	},
	paid_account(frm) {
		fetch_paid_account_exchange_rate(frm);
		set_multi_currency_flag(frm);
	},
	settlement_mode(frm) {
		// No alert needed as both PE and PDC support row-by-row multi-party settlement.
	},
	project(frm) {
		(frm.doc.accounts || []).forEach(row => {
			if (!row.project) {
				frappe.model.set_value(row.doctype, row.name, "project", frm.doc.project);
			}
		});
	},
	cost_center(frm) {
		(frm.doc.accounts || []).forEach(row => {
			if (!row.cost_center) {
				frappe.model.set_value(row.doctype, row.name, "cost_center", frm.doc.cost_center);
			}
		});
	},
});

frappe.ui.form.on("Cash Bank Entry Account", {
	accounts_add(frm, cdt, cdn) {
		default_row_dimensions(frm, cdt, cdn);
		const row = locals[cdt][cdn];
		if (!row.exchange_rate) {
			frappe.model.set_value(cdt, cdn, "exchange_rate", 1);
		}
	},
	account(frm, cdt, cdn) {
		fetch_exchange_rate(frm, cdt, cdn);
		set_multi_currency_flag(frm);
	},
	fetch_invoice(frm, cdt, cdn) {
		fetch_invoices_for_row(frm, locals[cdt][cdn]);
	},
	posting_date(frm, cdt, cdn) {
		fetch_exchange_rate(frm, cdt, cdn);
	},
	amount(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(
			cdt,
			cdn,
			"amount_in_company_currency",
			flt(row.amount) * flt(row.exchange_rate || 1)
		);
		compute_row_tax(frm, cdt, cdn);
		recalculate_total(frm);
	},
	exchange_rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(
			cdt,
			cdn,
			"amount_in_company_currency",
			flt(row.amount) * flt(row.exchange_rate || 1)
		);
		recalculate_total(frm);
	},
	purchase_tax_template(frm, cdt, cdn) {
		compute_row_tax(frm, cdt, cdn);
	},
	sales_tax_template(frm, cdt, cdn) {
		compute_row_tax(frm, cdt, cdn);
	},
	tax_rate(frm, cdt, cdn) {
		compute_row_tax(frm, cdt, cdn);
	},
	party(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.party_type === "Customer") {
			frappe.model.set_value(cdt, cdn, "reference_doctype", "Sales Invoice");
		} else if (row.party_type === "Supplier") {
			frappe.model.set_value(cdt, cdn, "reference_doctype", "Purchase Invoice");
		}
	},
	form_render(frm, cdt, cdn) {
		const grid_row = frm.fields_dict.accounts.grid.grid_rows_by_docname[cdn];
		if (!grid_row || grid_row.fetch_invoice_btn) return;
		grid_row.fetch_invoice_btn = grid_row.add_custom_button(__("Fetch Invoice"), () => {
			fetch_invoices_for_row(frm, locals[cdt][cdn]);
		});
	},
});

function render_custom_dashboard(frm) {
	if (frm.doc.__islocal) {
		if (frm.dashboard) frm.dashboard.hide();
		return;
	}

	// Gather all linked documents
	const payment_entries = [];
	if (frm.doc.payment_entry) {
		payment_entries.push(frm.doc.payment_entry);
	}
	(frm.doc.accounts || []).forEach(row => {
		if (row.payment_entry && !payment_entries.includes(row.payment_entry)) {
			payment_entries.push(row.payment_entry);
		}
	});

	const post_dated_cheques = [];
	if (frm.doc.post_dated_cheque) {
		post_dated_cheques.push(frm.doc.post_dated_cheque);
	}
	(frm.doc.accounts || []).forEach(row => {
		if (row.post_dated_cheque && !post_dated_cheques.includes(row.post_dated_cheque)) {
			post_dated_cheques.push(row.post_dated_cheque);
		}
	});

	const journal_entries = [];
	if (frm.doc.journal_entry) {
		journal_entries.push(frm.doc.journal_entry);
	}

	// If no linked documents, hide the dashboard links area
	if (!payment_entries.length && !post_dated_cheques.length && !journal_entries.length) {
		if (frm.dashboard) {
			frm.dashboard.links_area.hide();
		}
		return;
	}

	if (!frm.dashboard) return;

	// Prepare dashboard section
	frm.dashboard.links_area.show();
	frm.dashboard.transactions_area.empty();

	// Construct form-documents div
	const form_docs = $('<div class="form-documents"></div>');
	const row_div = $('<div class="row"></div>').appendTo(form_docs);
	const col_div = $('<div class="col-md-4"></div>').appendTo(row_div);

	$(`
		<div class="form-link-title">
			<span>${__("Accounting")}</span>
		</div>
	`).appendTo(col_div);

	// Helper to add a link badge
	function add_badge_link(doctype, items) {
		if (!items.length) return;

		const count = items.length;
		const doc_link = $(`
			<div class="document-link" data-doctype="${doctype}">
				<div class="document-link-badge" data-doctype="${doctype}">
					<a class="badge-link">${__(doctype)}</a>
					<span class="count">${count}</span>
				</div>
			</div>
		`);

		doc_link.find(".badge-link").on("click", () => {
			if (count === 1) {
				frappe.set_route("Form", doctype, items[0]);
			} else {
				frappe.route_options = { name: ["in", items] };
				frappe.set_route("List", doctype, "List");
			}
		});

		col_div.append(doc_link);
	}

	add_badge_link("Journal Entry", journal_entries);
	add_badge_link("Payment Entry", payment_entries);
	add_badge_link("Post Dated Cheques", post_dated_cheques);

	frm.dashboard.transactions_area.append(form_docs);
	frm.dashboard.show();
}
