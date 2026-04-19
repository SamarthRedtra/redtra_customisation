frappe.ui.form.on("Post Dated Cheques Tool", {
	refresh(frm) {
		frm.disable_save();

		frm.add_custom_button(__("Convert Selected to Payment Entries"), async () => {
			await convert_selected(frm);
		});

		frm.trigger("apply_default_bank_account_to_all_rows");
	},

	apply_default_bank_account_to_all_rows(frm) {
		if (!frm.doc.apply_default_bank_account_to_all_rows) return;
		if (!frm.doc.default_bank_account) return;

		(frm.doc.cheques_details || []).forEach((row) => {
			row.bank_account = frm.doc.default_bank_account;
		});
		frm.refresh_field("cheques_details");
	},

	get_post_dated_cheques(frm) {
		fetch_pending(frm);
	},
});

async function fetch_pending(frm) {
	frappe.dom.freeze(__("Fetching post dated cheques..."));
	try {
		const r = await frappe.call({
			method: "redtra_customisation.pdc.conversion_tool.get_pending_post_dated_cheques",
			args: {
				filters: {
					company: frm.doc.company,
					from_date: frm.doc.from_date,
					to_date: frm.doc.to_date,
					cost_center: frm.doc.cost_center,
					department: frm.doc.department,
					currency: frm.doc.currency,
				},
			},
		});

		frm.clear_table("cheques_details");
		(r.message || []).forEach((d) => {
			const row = frm.add_child("cheques_details");
			row.pdc = d.name;
			row.mode_of_payment = d.mode_of_payment;
			row.payment_type = d.payment_type;
			row.reference_date = d.reference_date;
			row.amount = d.amount;
			row.party_type = d.party_type;
			row.party = d.party;
			row.party_name = d.party_name;
			row.account_currency = d.account_currency;
			row.bank_account = d.bank_account || frm.doc.default_bank_account;
			row.payment_entry = d.payment_entry || "";
			row.status = d.status;
		});

		frm.refresh_field("cheques_details");
	} finally {
		frappe.dom.unfreeze();
	}
}

async function convert_selected(frm) {
	const selected = (frm.doc.cheques_details || []).filter((r) => r.__checked);
	if (!selected.length) {
		frappe.msgprint(__("Select at least one row to convert."));
		return;
	}

	const rows = selected.map((r) => ({
		pdc: r.pdc,
		bank_account: r.bank_account || frm.doc.default_bank_account,
	}));

	frappe.dom.freeze(__("Creating Payment Entries..."));
	try {
		const r = await frappe.call({
			method: "redtra_customisation.pdc.conversion_tool.convert_post_dated_cheques",
			args: {
				rows,
				defaults: {
					company: frm.doc.company,
					default_bank_account: frm.doc.default_bank_account,
				},
			},
		});

		const out = r.message || {};
		const created = (out.created || []).filter((c) => !c.already_converted);
		const alreadyDone = (out.created || []).filter((c) => c.already_converted);

		if (created.length) {
			const names = created.map((c) => c.payment_entry).filter(Boolean);
			const n = created.length;
			const msg =
				n === 1
					? __("Payment Entry {0} created.", [names[0] || ""])
					: __("{0} Payment Entries created: {1}", [n, names.join(", ")]);
			frappe.show_alert({ message: msg, indicator: "green" });
		} else if (alreadyDone.length && !(out.failures && out.failures.length)) {
			frappe.show_alert({
				message: __("Selected row(s) were already converted."),
				indicator: "blue",
			});
		}

		if (out.failures && out.failures.length) {
			frappe.msgprint({
				title: __("Some rows failed"),
				message: `<pre style="white-space: pre-wrap;">${out.failures
					.map((f) => `${f.pdc}: ${f.error}`)
					.join("\n")}</pre>`,
				indicator: "orange",
			});
		}

		await fetch_pending(frm);
	} finally {
		frappe.dom.unfreeze();
	}
}

