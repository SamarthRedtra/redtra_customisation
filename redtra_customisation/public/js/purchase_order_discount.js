frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		set_discount_account_query(frm);
	},
	onload(frm) {
		ensure_default_item_grid_columns(frm);
	},
	refresh(frm) {
		setup_line_discount_fields(frm);
		set_discount_account_query(frm);
	},
	company(frm) {
		set_discount_account_query(frm);
	},
	taxes_and_charges(frm) {
		window.setTimeout(() => sync_item_discounts(frm), 350);
	},
});

const DEFAULT_ITEM_GRID_COLUMNS = [
	{ fieldname: "cost_center", columns: 2, sticky: 0 },
	{ fieldname: "item_code", columns: 3, sticky: 0 },
	{ fieldname: "item_name", columns: 1, sticky: 0 },
	{ fieldname: "description", columns: 5, sticky: 0 },
	{ fieldname: "qty", columns: 1, sticky: 0 },
	{ fieldname: "uom", columns: 1, sticky: 0 },
	{ fieldname: "rate", columns: 2, sticky: 0 },
	{ fieldname: "amount", columns: 2, sticky: 0 },
	{ fieldname: "custom_purchase_discount_amount", columns: 2, sticky: 0 },
	{ fieldname: "custom_purchase_discount_account", columns: 2, sticky: 0 },
];

frappe.ui.form.on("Purchase Order Item", {
	async custom_purchase_discount_amount(frm, cdt, cdn) {
		if (await ensure_discount_account(frm, cdt, cdn)) {
			return;
		}
		await sync_item_discounts(frm);
	},
	async custom_purchase_discount_account(frm) {
		await sync_item_discounts(frm);
	},
});

function setup_line_discount_fields(frm) {
	const grid = frm.get_field("items")?.grid;
	if (!grid) {
		return;
	}

	grid.update_docfield_property("discount_amount", "in_list_view", 0);
	grid.update_docfield_property("discount_percentage", "in_list_view", 0);
	grid.update_docfield_property("custom_purchase_discount_amount", "label", __("Discount Amount"));
	grid.update_docfield_property("custom_purchase_discount_amount", "in_list_view", 1);
	grid.update_docfield_property("custom_purchase_discount_account", "in_list_view", 1);
	grid.refresh();
}

async function ensure_default_item_grid_columns(frm) {
	const gridView = frappe.get_user_settings(frm.doctype, "GridView");
	if (gridView["Purchase Order Item"]?.length) {
		return;
	}

	const value = {
		"Purchase Order Item": DEFAULT_ITEM_GRID_COLUMNS.map(column => ({ ...column })),
	};
	await frappe.model.user_settings.save(frm.doctype, "GridView", value);
	window.setTimeout(() => frm.get_field("items")?.grid.reset_grid(), 0);
}

function set_discount_account_query(frm) {
	frm.set_query("custom_purchase_discount_account", "items", () => ({
		filters: {
			company: frm.doc.company,
			is_group: 0,
			disabled: 0,
			report_type: "Profit and Loss",
		},
	}));
}

async function sync_item_discounts(frm) {
	if (!frm.doc.company || !frm.fields_dict.items) {
		return;
	}

	const accountTotals = new Map();
	for (const item of frm.doc.items || []) {
		const discount = flt(item.custom_purchase_discount_amount);
		if (discount < 0) {
			frappe.throw(__("Row {0}: Discount Amount cannot be negative.", [item.idx]));
		}
		const rowAmount = Math.max(flt(item.amount), flt(item.rate) * flt(item.qty));
		if (discount > rowAmount) {
			frappe.throw(__("Row {0}: Discount Amount cannot exceed the row amount.", [item.idx]));
		}
		const costCenter = item.cost_center || get_default_cost_center(frm);
		if (!discount || !item.custom_purchase_discount_account || !costCenter) {
			continue;
		}
		const amount = discount;
		const key = `${item.custom_purchase_discount_account}::${costCenter}`;
		const entry = accountTotals.get(key) || {
			account: item.custom_purchase_discount_account,
			costCenter,
			amount: 0,
		};
		entry.amount = flt(entry.amount) + amount;
		accountTotals.set(key, entry);
	}

	frm.doc.taxes = (frm.doc.taxes || []).filter(
		row => !cint(row.custom_is_purchase_item_discount)
	);
	for (const { account, costCenter, amount } of accountTotals.values()) {
		frm.add_child("taxes", {
			charge_type: "Actual",
			category: "Total",
			add_deduct_tax: "Deduct",
			account_head: account,
			cost_center: costCenter,
			description: __("Item Discounts"),
			tax_amount: amount,
			included_in_print_rate: 0,
			included_in_paid_amount: 0,
			custom_is_purchase_item_discount: 1,
		});
	}
	configure_discounted_tax_base(frm);
	reindex_tax_rows(frm);
	const total = [...accountTotals.values()].reduce((sum, entry) => sum + entry.amount, 0);
	if (flt(frm.doc.custom_purchase_discount_total) !== flt(total)) {
		await frm.set_value("custom_purchase_discount_total", total);
	}
	frm.refresh_field("taxes");
	await frm.cscript.calculate_taxes_and_totals();
}

async function ensure_discount_account(frm, cdt, cdn) {
	const item = locals[cdt]?.[cdn];
	if (!item || !flt(item.custom_purchase_discount_amount) || item.custom_purchase_discount_account) {
		return false;
	}

	const account = await frappe.db.get_single_value(
		"Redtra Custom Setting",
		"default_purchase_invoice_discount_account"
	);
	if (!account) {
		return false;
	}

	await frappe.model.set_value(cdt, cdn, "custom_purchase_discount_account", account);
	return true;
}

function configure_discounted_tax_base(frm) {
	const discountRows = (frm.doc.taxes || []).filter(row => cint(row.custom_is_purchase_item_discount));
	if (!discountRows.length) {
		restore_tax_template_rows(frm);
		return;
	}

	const otherRows = (frm.doc.taxes || []).filter(row => !cint(row.custom_is_purchase_item_discount));
	frm.doc.taxes = [...discountRows, ...otherRows];
	reindex_tax_rows(frm);
	const lastDiscountRow = discountRows[discountRows.length - 1];

	for (const row of otherRows) {
		if (row.charge_type === "On Net Total") {
			row.custom_original_charge_type = "On Net Total";
			row.custom_original_row_id = row.row_id || null;
			row.charge_type = "On Previous Row Total";
			row.row_id = lastDiscountRow.idx;
			row.custom_uses_adjusted_tax_base = 1;
		} else if (cint(row.custom_uses_adjusted_tax_base)) {
			row.row_id = lastDiscountRow.idx;
		}
	}
}

function restore_tax_template_rows(frm) {
	for (const row of frm.doc.taxes || []) {
		if (!cint(row.custom_uses_adjusted_tax_base)) {
			continue;
		}
		row.charge_type = row.custom_original_charge_type || "On Net Total";
		row.row_id = row.custom_original_row_id || null;
		row.custom_uses_adjusted_tax_base = 0;
		row.custom_original_charge_type = null;
		row.custom_original_row_id = null;
	}
}

function reindex_tax_rows(frm) {
	(frm.doc.taxes || []).forEach((row, index) => {
		row.idx = index + 1;
	});
}

function get_default_cost_center(frm) {
	return (frm.doc.items || []).find(item => item.cost_center)?.cost_center || frm.doc.cost_center || "";
}
