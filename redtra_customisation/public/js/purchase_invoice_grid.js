frappe.ui.form.on("Purchase Invoice", {
	onload(frm) {
		ensure_default_purchase_invoice_item_grid(frm);
	},
});

const DEFAULT_PURCHASE_INVOICE_ITEM_COLUMNS = [
	{ fieldname: "item_code", columns: 3, sticky: 1 },
	{ fieldname: "item_name", columns: 5, sticky: 1 },
	{ fieldname: "description", columns: 2, sticky: 0 },
	{ fieldname: "uom", columns: 2, sticky: 0 },
	{ fieldname: "cost_center", columns: 2, sticky: 0 },
	{ fieldname: "qty", columns: 2, sticky: 0 },
	{ fieldname: "rate", columns: 3, sticky: 0 },
	{ fieldname: "amount", columns: 2, sticky: 0 },
	{ fieldname: "custom_item_adjustment_amount", columns: 2, sticky: 0 },
	{ fieldname: "custom_item_adjustment_account", columns: 2, sticky: 0 },
	{ fieldname: "custom_purchase_discount_amount", columns: 2, sticky: 0 },
	{ fieldname: "custom_purchase_discount_account", columns: 2, sticky: 0 },
];

async function ensure_default_purchase_invoice_item_grid(frm) {
	const gridView = frappe.get_user_settings(frm.doctype, "GridView");
	if (gridView["Purchase Invoice Item"]?.length) {
		return;
	}

	const value = {
		"Purchase Invoice Item": DEFAULT_PURCHASE_INVOICE_ITEM_COLUMNS.map(column => ({
			...column,
		})),
	};
	await frappe.model.user_settings.save(frm.doctype, "GridView", value);
	window.setTimeout(() => frm.get_field("items")?.grid.reset_grid(), 0);
}
