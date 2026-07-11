// Copyright (c) 2026, redtra_customisation contributors

(function () {
	const INVOICE_DOCTYPES = ["Purchase Invoice", "Sales Invoice"];
	const PDC_DOCTYPE = "Post Dated Cheques";
	const SECTION_CLASS = "redtra-pdc-connections";

	function get_status_badge(display_status, pdc_status, payment_entry_status) {
		const status = (pdc_status || "").trim();
		const pe_status = (payment_entry_status || "").trim();
		let color = "gray";

		if (status === "Pending") {
			color = "orange";
		} else if (status === "Converted") {
			if (["Collected", "Paid"].includes(pe_status)) {
				color = "green";
			} else if (pe_status === "Under Collection") {
				color = "blue";
			} else {
				color = "green";
			}
		} else if (status === "Cancelled" || pe_status === "Bounced") {
			color = "red";
		}

		const label = frappe.utils.escape_html(display_status || status || __("Pending"));
		return `<span class="indicator-pill ${color} filterable no-indicator-dot ellipsis">${label}</span>`;
	}

	function render_invoice_pdc_connections(frm) {
		if (!frm.doc.name || frm.doc.docstatus !== 1 || !frm.dashboard) {
			return;
		}

		frappe.call({
			method:
				"redtra_customisation.redtra_customisation.doctype.post_dated_cheques.post_dated_cheques.get_invoice_pdc_connections",
			args: {
				reference_doctype: frm.doctype,
				reference_name: frm.doc.name,
			},
			callback(r) {
				const pdcs = r.message || [];
				frm.dashboard.transactions_area.find(`.${SECTION_CLASS}`).remove();

				if (!pdcs.length) {
					return;
				}

				const currency = frm.doc.currency || frappe.defaults.get_default("currency");
				const form_docs = $(`<div class="form-documents ${SECTION_CLASS}"></div>`);
				const row_div = $('<div class="row"></div>').appendTo(form_docs);
				const col_div = $('<div class="col-md-12"></div>').appendTo(row_div);

				$(`<div class="form-link-title"><span>${__(PDC_DOCTYPE)}</span></div>`).appendTo(
					col_div
				);

				const table_rows = pdcs
					.map((pdc) => {
						const pdc_route = frappe.utils.get_form_link(PDC_DOCTYPE, pdc.name);
						const cheque_no = frappe.utils.escape_html(pdc.reference_no || "—");
						const cheque_date = pdc.reference_date
							? frappe.datetime.str_to_user(pdc.reference_date)
							: "—";
						const allocated = format_currency(
							pdc.display_amount ?? pdc.effective_allocated_amount ?? pdc.allocated_amount ?? 0,
							currency
						);
						const status_badge = get_status_badge(
							pdc.display_status,
							pdc.status,
							pdc.payment_entry_status
						);

						return `
							<tr>
								<td><a href="${pdc_route}">${frappe.utils.escape_html(pdc.name)}</a></td>
								<td>${cheque_no}</td>
								<td>${cheque_date}</td>
								<td class="text-right">${allocated}</td>
								<td>${status_badge}</td>
							</tr>
						`;
					})
					.join("");

				col_div.append(`
					<div class="table-responsive" style="margin-top: 8px;">
						<table class="table table-bordered table-sm redtra-pdc-connections-table">
							<thead>
								<tr>
									<th>${__("PDC")}</th>
									<th>${__("Cheque No")}</th>
									<th>${__("Cheque Date")}</th>
									<th class="text-right">${__("PDC Allocation")}</th>
									<th>${__("Status")}</th>
								</tr>
							</thead>
							<tbody>${table_rows}</tbody>
						</table>
					</div>
				`);

				frm.dashboard.transactions_area.append(form_docs);
				frm.dashboard.links_area.show();
				frm.dashboard.show();
			},
		});
	}

	INVOICE_DOCTYPES.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				setTimeout(() => render_invoice_pdc_connections(frm), 300);
			},
		});
	});
})();
