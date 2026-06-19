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

function get_pdc_invoice_doctype(frm) {
	return frm.doc.party_type === "Supplier" || frm.doc.payment_type === "Pay"
		? "Purchase Invoice"
		: "Sales Invoice";
}

function render_invoice_links(frm) {
	const wrapper = frm.fields_dict.invoice_links_html?.$wrapper;
	const display = frm.fields_dict.invoice_links?.$wrapper;

	const links = (frm.doc.invoice_links || "")
		.split(",")
		.map(v => v.trim())
		.filter(Boolean);

	if (!links.length) {
		if (wrapper) {
			wrapper.html("");
		}
		return;
	}

	const invoice_doctype = get_pdc_invoice_doctype(frm);
	const invoice_route = frappe.router.slug(invoice_doctype);
	const inline_html = links.map(name => {
		const route = `/app/${invoice_route}/${encodeURIComponent(name)}`;
		return `<a href="${route}">${frappe.utils.escape_html(name)}</a>`;
	}).join(", ");
	const button_html = links.map(name => {
		const route = `/app/${invoice_route}/${encodeURIComponent(name)}`;
		return `<a class="btn btn-xs btn-default" style="margin: 0 6px 6px 0;" href="${route}">
			<i class="fa fa-external-link"></i> ${frappe.utils.escape_html(name)}
		</a>`;
	}).join("");

	if (display) {
		display.find(".control-value").html(inline_html);
	}
	if (wrapper) {
		wrapper.html(`<div class="pdc-invoice-links">${button_html}</div>`);
	}
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
		render_invoice_links(frm);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Invoices"), () => {
				frm.events.fetch_invoices(frm);
			});
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Pending") {
			frm.add_custom_button(__("Convert Cheque"), () => {
				frappe.prompt([
					{
						label: __("Execution Date"),
						fieldname: "execution_date",
						fieldtype: "Date",
						default: frm.doc.reference_date,
						reqd: 1
					}
				], (values) => {
					frappe.call({
						method: "redtra_customisation.pdc.conversion_tool.convert_post_dated_cheques",
						args: {
							rows: [{
								pdc: frm.doc.name,
								bank_account: frm.doc.bank_account,
								posting_date_override: values.execution_date
							}],
							defaults: {
								company: frm.doc.company
							}
						},
						callback: function(r) {
							if (r.message && r.message.created && r.message.created.length) {
								const pe_name = r.message.created[0].payment_entry;
								frappe.show_alert({
									message: __("Converted to Payment Entry: {0}", [
										`<a href="/app/payment-entry/${pe_name}">${pe_name}</a>`
									]),
									indicator: "green"
								});
								frm.reload_doc();
							}
							if (r.message && r.message.failures && r.message.failures.length) {
								frappe.msgprint({
									title: __("Conversion Failed"),
									message: r.message.failures[0].error,
									indicator: "red"
								});
							}
						}
					});
				}, __("Convert to Payment Entry"), __("Convert"));
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
	payment_type(frm) {
		if (frm.doc.payment_type === "Receive") {
			frm.set_value("party_type", "Customer");
		} else if (frm.doc.payment_type === "Pay") {
			frm.set_value("party_type", "Supplier");
		}
	},
	party_type(frm) {
		frm.set_value("party", "");
		frm.set_value("party_name", "");
		frm.clear_table("invoice_references");
		calculate_total_amount(frm);
	},
	party(frm) {
		if (frm.doc.party && frm.doc.party_type) {
			const name_field = frm.doc.party_type === "Customer" ? "customer_name" : "supplier_name";
			frappe.db.get_value(frm.doc.party_type, frm.doc.party, name_field, (r) => {
				if (r && r[name_field]) {
					frm.set_value("party_name", r[name_field]);
				}
			});
		} else {
			frm.set_value("party_name", "");
		}
		frm.clear_table("invoice_references");
		calculate_total_amount(frm);
	},

	fetch_invoices(frm) {
		if (!frm.doc.party) {
			frappe.msgprint(__("Please select a Party first."));
			return;
		}

		frappe.call({
			method: "redtra_customisation.redtra_customisation.doctype.post_dated_cheques.post_dated_cheques.get_pending_invoices",
			args: {
				company: frm.doc.company,
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				current_pdc: frm.doc.name
			},
			callback(r) {
				const invoices = r.message || [];
				if (!invoices.length) {
					frappe.msgprint(__("No pending invoices found for this party."));
					return;
				}

				const is_purchase = frm.doc.party_type !== "Customer";
				const target_doctype = is_purchase ? "Purchase Invoice" : "Sales Invoice";

				const fields = [
					{
						fieldtype: "Float",
						fieldname: "total_amount",
						label: __("Total Amount to Allocate"),
						default: frm.doc.amount || 0
					},
					{
						fieldtype: "Column Break"
					},
					{
						fieldtype: "Float",
						fieldname: "unallocated_amount",
						label: __("Unallocated Amount"),
						read_only: 1,
						default: frm.doc.amount || 0
					},
					{
						fieldtype: "Section Break"
					},
					{
						fieldtype: "Data",
						fieldname: "search_invoice",
						label: __("Search Invoice / Reference No"),
						placeholder: __("Search by name, supplier, or customer invoice number...")
					},
					{
						fieldtype: "HTML",
						fieldname: "invoices_table_html"
					}
				];

				const d = new frappe.ui.Dialog({
					title: __("Allocate Outstanding Invoices"),
					fields: fields,
					size: "large",
					primary_action_label: __("Allocate"),
					primary_action(values) {
						const selected_rows = [];
						d.$wrapper.find(".invoice-row").each(function() {
							const $row = $(this);
							const checkbox = $row.find(".invoice-check");
							if (checkbox.is(":checked")) {
								const inv_name = $row.data("name");
								const grand_total = flt($row.data("grand-total"));
								const outstanding = flt($row.data("outstanding"));
								const allocated = flt($row.find(".alloc-input").val());
								if (allocated > 0) {
									selected_rows.push({
										reference_doctype: target_doctype,
										reference_name: inv_name,
										total_amount: grand_total,
										outstanding_amount: outstanding,
										allocated_amount: allocated
									});
								}
							}
						});

						if (!selected_rows.length) {
							frappe.msgprint(__("No invoices selected or allocated."));
							return;
						}

						selected_rows.forEach(item => {
							let exists = false;
							(frm.doc.invoice_references || []).forEach(row => {
								if (row.reference_name === item.reference_name) {
									row.allocated_amount = item.allocated_amount;
									exists = true;
								}
							});
							if (!exists) {
								const row = frm.add_child("invoice_references");
								row.reference_doctype = item.reference_doctype;
								row.reference_name = item.reference_name;
								row.total_amount = item.total_amount;
								row.outstanding_amount = item.outstanding_amount;
								row.allocated_amount = item.allocated_amount;
							}
						});

						calculate_total_amount(frm);
						frm.refresh_field("invoice_references");
						d.hide();
					}
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

				invoices.forEach(inv => {
					html += `
						<tr class="invoice-row" data-name="${inv.name}" data-grand-total="${inv.grand_total}" data-outstanding="${inv.outstanding_amount}" data-remaining="${inv.remaining_allocatable}">
							<td style="text-align: center; vertical-align: middle;">
								<input type="checkbox" class="invoice-check">
							</td>
							<td style="vertical-align: middle;">
								<a href="/app/${is_purchase ? 'purchase' : 'sales'}-invoice/${inv.name}" target="_blank">${inv.name}</a>
							</td>
							${is_purchase ? `<td style="vertical-align: middle;">${inv.custom_supplier_invoice_no || ""}</td>` : `<td style="vertical-align: middle;">${inv.custom_customer_invoice_no || ""}</td>`}
							<td style="text-align: right; vertical-align: middle;">${format_currency(inv.grand_total, frm.doc.account_currency)}</td>
							<td style="text-align: right; vertical-align: middle;">${format_currency(inv.outstanding_amount, frm.doc.account_currency)}</td>
							<td style="text-align: right; vertical-align: middle;">${format_currency(inv.remaining_allocatable, frm.doc.account_currency)}</td>
							<td style="text-align: right; vertical-align: middle;">
								<input type="number" class="form-control input-sm alloc-input" style="text-align: right; padding: 4px;" value="0" min="0" step="any" disabled>
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
					$dialog.find(".invoice-row").each(function() {
						const $row = $(this);
						if ($row.find(".invoice-check").is(":checked")) {
							allocated += flt($row.find(".alloc-input").val());
						}
					});
					d.set_value("unallocated_amount", total - allocated);
				}

				$dialog.on("change", ".invoice-check", function() {
					const $row = $(this).closest("tr");
					const checked = $(this).is(":checked");
					const remaining = flt($row.data("remaining"));
					const $input = $row.find(".alloc-input");
					
					if (checked) {
						$input.prop("disabled", false);
						if (flt($input.val()) === 0) {
							const unallocated = flt(d.get_value("unallocated_amount"));
							const amount_to_set = Math.max(0, Math.min(remaining, unallocated));
							$input.val(amount_to_set);
						}
					} else {
						$input.val(0);
						$input.prop("disabled", true);
					}
					recalculate_unallocated();
				});

				$dialog.on("change", ".select-all-check", function() {
					const checked = $(this).is(":checked");
					$dialog.find(".invoice-check").each(function() {
						const is_checked = $(this).is(":checked");
						if (is_checked !== checked) {
							$(this).prop("checked", checked).trigger("change");
						}
					});
				});

				$dialog.on("input change", ".alloc-input", function() {
					const $row = $(this).closest("tr");
					const remaining = flt($row.data("remaining"));
					let val = flt($(this).val());
					
					if (val < 0) {
						val = 0;
						$(this).val(0);
					}
					if (val > remaining) {
						frappe.show_alert({
							message: __("Amount cannot exceed remaining allocatable amount ({0})", [format_currency(remaining, frm.doc.account_currency)]),
							indicator: "orange"
						});
						val = remaining;
						$(this).val(remaining);
					}
					
					const $check = $row.find(".invoice-check");
					if (val > 0 && !$check.is(":checked")) {
						$check.prop("checked", true);
						$(this).prop("disabled", false);
					}
					
					recalculate_unallocated();
				});

				// Text search/filter
				d.fields_dict.search_invoice.$wrapper.on("input", "input", function() {
					const query = $(this).val().toLowerCase().trim();
					$dialog.find(".invoice-row").each(function() {
						const $row = $(this);
						const name = ($row.data("name") || "").toString().toLowerCase();
						const ref_no = ($row.find("td").eq(2).text() || "").toString().toLowerCase();
						if (!query || name.includes(query) || ref_no.includes(query)) {
							$row.show();
						} else {
							$row.hide();
						}
					});
				});

				d.fields_dict.total_amount.df.onchange = () => {
					recalculate_unallocated();
				};

				d.show();
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
