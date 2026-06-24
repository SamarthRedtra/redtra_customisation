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

function get_invoice_refs_for_row(frm, row) {
	return (frm.doc.invoice_references || []).filter(ref => ref.account_row === row.name);
}

function clear_invoice_refs_for_row(frm, row) {
	(frm.doc.invoice_references || [])
		.filter(ref => ref.account_row === row.name)
		.forEach(ref => frappe.model.clear_doc(ref.doctype, ref.name));
	frm.refresh_field("invoice_references");
}

function sync_row_from_invoice_refs(frm, row) {
	const refs = get_invoice_refs_for_row(frm, row);
	if (!refs.length) {
		return;
	}
	const total = refs.reduce((sum, ref) => sum + flt(ref.allocated_amount), 0);
	frappe.model.set_value(row.doctype, row.name, "amount", total);
	frappe.model.set_value(row.doctype, row.name, "allocated_amount", total);
	const first = refs[0];
	frappe.model.set_value(row.doctype, row.name, "reference_doctype", first.reference_doctype);
	frappe.model.set_value(row.doctype, row.name, "reference_name", first.reference_name);
	if (first.account) {
		frappe.model.set_value(row.doctype, row.name, "account", first.account);
	}
	recalculate_total(frm);
}

function fetch_invoices_for_row(frm, row) {
	if (!row.party_type || !row.party || !frm.doc.company) {
		frappe.msgprint(__("Set Party on the row before fetching invoices."));
		return;
	}
	if (!["Payment Entry", "Post Dated Cheque"].includes(frm.doc.settlement_mode)) {
		frappe.msgprint(__("Multi-invoice fetch is available for Payment Entry and Post Dated Cheque modes."));
		return;
	}

	const reference_doctype = get_invoice_doctype_for_row(row, frm.doc.entry_type);
	const is_purchase = reference_doctype === "Purchase Invoice";
	const existing_refs = get_invoice_refs_for_row(frm, row);
	const default_total = flt(row.amount) || existing_refs.reduce((s, r) => s + flt(r.allocated_amount), 0);

	frappe.call({
		method: "redtra_customisation.redtra_customisation.doctype.cash_bank_entry.cash_bank_entry.get_pending_invoices_for_cbe",
		args: {
			company: frm.doc.company,
			party_type: row.party_type,
			party: row.party,
			current_cbe: frm.doc.name,
		},
		callback(r) {
			const invoices = r.message || [];
			if (!invoices.length) {
				frappe.msgprint(__("No pending invoices found for this party."));
				return;
			}

			const fields = [
				{
					fieldtype: "Float",
					fieldname: "total_amount",
					label: __("Total Amount to Allocate"),
					default: default_total,
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldtype: "Float",
					fieldname: "unallocated_amount",
					label: __("Unallocated Amount"),
					read_only: 1,
					default: default_total,
				},
				{
					fieldtype: "Section Break",
				},
				{
					fieldtype: "Data",
					fieldname: "search_invoice",
					label: __("Search Invoice / Reference No"),
					placeholder: __("Search by name, supplier, or customer invoice number..."),
				},
				{
					fieldtype: "HTML",
					fieldname: "invoices_table_html",
				},
			];

			const d = new frappe.ui.Dialog({
				title: __("Allocate Invoices — Line {0}", [row.idx]),
				fields,
				size: "large",
				primary_action_label: __("Allocate"),
				primary_action() {
					const selected_rows = [];
					d.$wrapper.find(".invoice-row").each(function () {
						const $invoice_row = $(this);
						if (!$invoice_row.find(".invoice-check").is(":checked")) {
							return;
						}
						const allocated = flt($invoice_row.find(".alloc-input").val());
						if (allocated <= 0) {
							return;
						}
						selected_rows.push({
							reference_doctype: reference_doctype,
							reference_name: $invoice_row.data("name"),
							total_amount: flt($invoice_row.data("grand-total")),
							outstanding_amount: flt($invoice_row.data("outstanding")),
							allocated_amount: allocated,
							account: $invoice_row.data("account") || row.account,
						});
					});

					if (!selected_rows.length) {
						frappe.msgprint(__("No invoices selected or allocated."));
						return;
					}

					clear_invoice_refs_for_row(frm, row);
					selected_rows.forEach(item => {
						const child = frm.add_child("invoice_references");
						child.account_row = row.name;
						child.account_row_idx = row.idx;
						child.reference_doctype = item.reference_doctype;
						child.reference_name = item.reference_name;
						child.total_amount = item.total_amount;
						child.outstanding_amount = item.outstanding_amount;
						child.allocated_amount = item.allocated_amount;
					});

					frm.refresh_field("invoice_references");
					sync_row_from_invoice_refs(frm, row);
					d.hide();
				},
			});

			let html = `
				<div style="max-height: 350px; overflow-y: auto;">
					<table class="table table-bordered table-condensed table-hover" style="margin-bottom: 0;">
						<thead>
							<tr class="grid-heading-row" style="background-color: var(--bg-color); font-weight: bold;">
								<th style="width: 40px; text-align: center;"><input type="checkbox" class="select-all-check"></th>
								<th>${__("Invoice")}</th>
								${is_purchase ? `<th>${__("Supplier Invoice No")}</th>` : `<th>${__("Customer Invoice No")}</th>`}
								<th style="text-align: right;">${__("Grand Total")}</th>
								<th style="text-align: right;">${__("Outstanding")}</th>
								<th style="text-align: right;">${__("Remaining")}</th>
								<th style="width: 120px; text-align: right;">${__("Allocated")}</th>
							</tr>
						</thead>
						<tbody>
			`;

			const existing_map = {};
			existing_refs.forEach(ref => {
				existing_map[ref.reference_name] = flt(ref.allocated_amount);
			});

			invoices.forEach(inv => {
				const preselected = existing_map[inv.name] > 0;
				const prealloc = preselected ? existing_map[inv.name] : 0;
				html += `
					<tr class="invoice-row" data-name="${inv.name}" data-grand-total="${inv.grand_total}" data-outstanding="${inv.outstanding_amount}" data-remaining="${inv.remaining_allocatable}">
						<td style="text-align: center; vertical-align: middle;">
							<input type="checkbox" class="invoice-check" ${preselected ? "checked" : ""}>
						</td>
						<td style="vertical-align: middle;">
							<a href="/app/${is_purchase ? "purchase" : "sales"}-invoice/${inv.name}" target="_blank">${inv.name}</a>
						</td>
						${is_purchase ? `<td style="vertical-align: middle;">${inv.custom_supplier_invoice_no || ""}</td>` : `<td style="vertical-align: middle;">${inv.custom_customer_invoice_no || ""}</td>`}
						<td style="text-align: right; vertical-align: middle;">${format_currency(inv.grand_total, frm.doc.paid_account_currency)}</td>
						<td style="text-align: right; vertical-align: middle;">${format_currency(inv.outstanding_amount, frm.doc.paid_account_currency)}</td>
						<td style="text-align: right; vertical-align: middle;">${format_currency(inv.remaining_allocatable, frm.doc.paid_account_currency)}</td>
						<td style="text-align: right; vertical-align: middle;">
							<input type="number" class="form-control input-sm alloc-input" style="text-align: right; padding: 4px;" value="${prealloc}" min="0" step="any" ${preselected ? "" : "disabled"}>
						</td>
					</tr>
				`;
			});

			html += `
						</tbody>
					</table>
				</div>
			`;

			d.fields_dict.invoices_table_html.$wrapper.html(html);

			const $dialog = d.$wrapper;

			function recalculate_unallocated() {
				const total = flt(d.get_value("total_amount"));
				let allocated = 0;
				$dialog.find(".invoice-row").each(function () {
					const $invoice_row = $(this);
					if ($invoice_row.find(".invoice-check").is(":checked")) {
						allocated += flt($invoice_row.find(".alloc-input").val());
					}
				});
				d.set_value("unallocated_amount", total - allocated);
			}

			$dialog.on("change", ".invoice-check", function () {
				const $invoice_row = $(this).closest("tr");
				const checked = $(this).is(":checked");
				const remaining = flt($invoice_row.data("remaining"));
				const $input = $invoice_row.find(".alloc-input");

				if (checked) {
					$input.prop("disabled", false);
					if (flt($input.val()) === 0) {
						const unallocated = flt(d.get_value("unallocated_amount"));
						$input.val(Math.max(0, Math.min(remaining, unallocated)));
					}
				} else {
					$input.val(0);
					$input.prop("disabled", true);
				}
				recalculate_unallocated();
			});

			$dialog.on("change", ".select-all-check", function () {
				const checked = $(this).is(":checked");
				$dialog.find(".invoice-check").each(function () {
					if ($(this).is(":checked") !== checked) {
						$(this).prop("checked", checked).trigger("change");
					}
				});
			});

			$dialog.on("input change", ".alloc-input", function () {
				const $invoice_row = $(this).closest("tr");
				const remaining = flt($invoice_row.data("remaining"));
				let val = flt($(this).val());

				if (val < 0) {
					val = 0;
					$(this).val(0);
				}
				if (val > remaining) {
					frappe.show_alert({
						message: __("Amount cannot exceed remaining allocatable amount ({0})", [
							format_currency(remaining, frm.doc.paid_account_currency),
						]),
						indicator: "orange",
					});
					val = remaining;
					$(this).val(remaining);
				}

				const $check = $invoice_row.find(".invoice-check");
				if (val > 0 && !$check.is(":checked")) {
					$check.prop("checked", true);
					$(this).prop("disabled", false);
				}
				recalculate_unallocated();
			});

			d.fields_dict.search_invoice.$wrapper.on("input", "input", function () {
				const query = $(this).val().toLowerCase().trim();
				$dialog.find(".invoice-row").each(function () {
					const $invoice_row = $(this);
					const name = ($invoice_row.data("name") || "").toString().toLowerCase();
					const ref_no = ($invoice_row.find("td").eq(2).text() || "").toString().toLowerCase();
					$invoice_row.toggle(!query || name.includes(query) || ref_no.includes(query));
				});
			});

			d.fields_dict.total_amount.df.onchange = () => recalculate_unallocated();
			recalculate_unallocated();
			d.show();
		},
	});
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
		clear_invoice_refs_for_row(frm, row);
		frappe.model.set_value(cdt, cdn, "reference_name", "");
		frappe.model.set_value(cdt, cdn, "allocated_amount", 0);
	},
	accounts_remove(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.name) {
			clear_invoice_refs_for_row(frm, row);
		}
	},
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const grid_row = frm.fields_dict.accounts.grid.grid_rows_by_docname[cdn];
		if (!grid_row) return;

		const ref_count = get_invoice_refs_for_row(frm, row).length;
		const label = ref_count
			? __("Fetch Invoices ({0})", [ref_count])
			: __("Fetch Invoices");

		if (grid_row.fetch_invoice_btn) {
			grid_row.fetch_invoice_btn.text(label);
		} else {
			grid_row.fetch_invoice_btn = grid_row.add_custom_button(label, () => {
				fetch_invoices_for_row(frm, locals[cdt][cdn]);
			});
		}
	},
});

frappe.ui.form.on("Cash Bank Entry Invoice Reference", {
	invoice_references_remove(frm) {
		recalculate_total(frm);
	},
	allocated_amount(frm, cdt, cdn) {
		const ref_row = locals[cdt][cdn];
		const account_row = (frm.doc.accounts || []).find(r => r.name === ref_row.account_row);
		if (account_row) {
			sync_row_from_invoice_refs(frm, account_row);
		}
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
