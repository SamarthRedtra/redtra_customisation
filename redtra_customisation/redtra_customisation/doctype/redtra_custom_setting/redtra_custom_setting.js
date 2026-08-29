// Copyright (c) 2025, samarth.upare@redtra.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Redtra Custom Setting", {
	setup(frm) {
		for (const fieldname of [
			"default_purchase_invoice_discount_account",
			"default_purchase_invoice_adjustment_account",
		]) {
			frm.set_query(fieldname, () => ({
				filters: { is_group: 0, disabled: 0 },
			}));
		}
	},
});
