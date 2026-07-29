// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// List indicator uses custom `status` (Pending / Converted / Cancelled) instead of Draft / Submitted.

frappe.listview_settings["Post Dated Cheques"] = {
	add_fields: ["status", "invoice_links", "invoice_links_list", "party_type", "payment_type"],
	fields: JSON.stringify([
		{ fieldname: "status_field" },
		{ fieldname: "invoice_links_list" },
		{ fieldname: "party" },
		{ fieldname: "reference_no" },
		{ fieldname: "reference_date" },
		{ fieldname: "amount" },
	]),
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	onload(listview) {
		// The server enforces this scope. Add the single allowed Company as a
		// visible List View filter too, so the user can immediately see why
		// records from other companies are not included.
		frappe.call({
			method: "redtra_customisation.override.post_dated_cheques_permissions.get_current_user_companies",
		}).then(({ message: companies }) => {
			if (!Array.isArray(companies) || companies.length !== 1) {
				return;
			}

			if (!listview.filter_area.filter_list.get_filter("company")) {
				listview.filter_area.add("Post Dated Cheques", "company", "=", companies[0]);
				// The async scope lookup happens after the first list request. Reload
				// explicitly so the visible Company filter is applied immediately.
				listview.refresh();
			}
		});
	},
	formatters: {
		invoice_links_list(value, df, doc) {
			if (!value) {
				return "";
			}

			const invoice_doctype = doc.party_type === "Supplier" || doc.payment_type === "Pay"
				? "Purchase Invoice"
				: "Sales Invoice";
			const invoice_route = frappe.router.slug(invoice_doctype);

			return value
				.split(",")
				.map(v => v.trim())
				.filter(Boolean)
				.map(name => {
					if (name.startsWith("+")) {
						return `<span class="text-muted">${frappe.utils.escape_html(name)}</span>`;
					}
					const route = `/app/${invoice_route}/${encodeURIComponent(name)}`;
					return `<a class="pdc-invoice-link" href="${route}" onclick="event.stopPropagation()">${frappe.utils.escape_html(name)}</a>`;
				})
				.join(", ");
		}
	},
	get_indicator(doc) {
		const s = doc.status;
		if (!s) {
			return [__("—"), "gray", "name,!=,"];
		}
		const color = { Pending: "orange", Converted: "green", Cancelled: "grey" }[s] || "gray";
		return [__(s), color, "status,=," + s];
	},
};
