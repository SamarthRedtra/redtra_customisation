// Copyright (c) 2026, redtra_customisation contributors

frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		apply_pi_expense_account_query(frm);
	},
	refresh(frm) {
		apply_pi_expense_account_query(frm);
	},
	company(frm) {
		apply_pi_expense_account_query(frm);
	},
});

function apply_pi_expense_account_query(frm) {
	frappe.call({
		method: "redtra_customisation.override.purchase_invoice_expense_account.is_any_account_allowed_on_pi",
		callback(r) {
			if (!r.message) {
				return;
			}

			const get_query = function (doc) {
				return {
					filters: {
						company: doc.company,
						is_group: 0,
						disabled: 0,
					},
				};
			};

			frm.set_query("expense_account", "items", function () {
				return get_query(frm.doc);
			});

			if (frm.fields_dict.items?.grid?.get_field("expense_account")) {
				frm.fields_dict.items.grid.get_field("expense_account").get_query = function (doc) {
					return get_query(doc);
				};
			}
		},
	});
}
