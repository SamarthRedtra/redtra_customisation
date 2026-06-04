// Copyright (c) 2026, redtra_customisation contributors

frappe.ui.form.on("Purchase Order", {
	onload(frm) {
		apply_non_stock_user_defaults(frm);
	},
	refresh(frm) {
		apply_non_stock_user_defaults(frm);
	},
});

function apply_non_stock_user_defaults(frm) {
	frappe.call({
		method: "redtra_customisation.override.purchase_order_permissions.is_current_user_restricted",
		callback(r) {
			if (!r.message) return;

			if (frm.is_new() && !frm.doc.is_nonstock) {
				frm.set_value("is_nonstock", 1);
			}

			frm.set_df_property("is_nonstock", "read_only", 1);
		},
	});
}
