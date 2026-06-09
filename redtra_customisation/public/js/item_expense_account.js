// Copyright (c) 2026, redtra_customisation contributors

frappe.ui.form.on("Item", {
	onload(frm) {
		apply_item_default_expense_account_query(frm);
	},
	refresh(frm) {
		apply_item_default_expense_account_query(frm);
	},
});

function apply_item_default_expense_account_query(frm) {
	frappe.call({
		method: "redtra_customisation.override.purchase_invoice_expense_account.is_any_account_allowed_on_pi",
		callback(r) {
			if (!r.message) {
				return;
			}

			const get_query = function (doc, cdt, cdn) {
				const row = cdn ? locals[cdt][cdn] : {};
				return {
					filters: {
						company: row.company,
						is_group: 0,
						disabled: 0,
					},
				};
			};

			frm.set_query("expense_account", "item_defaults", get_query);

			const expense_account_field = frm.fields_dict.item_defaults?.grid?.get_field(
				"expense_account"
			);
			if (expense_account_field) {
				expense_account_field.get_query = get_query;
			}
		},
	});
}
