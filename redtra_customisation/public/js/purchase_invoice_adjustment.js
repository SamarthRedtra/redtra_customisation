const PURCHASE_INVOICE_ADJUSTMENT_MARKER = "custom_is_purchase_invoice_adjustment";
const PURCHASE_INVOICE_ITEM_ADJUSTMENT_MARKER = "custom_is_purchase_invoice_item_adjustment";
const PURCHASE_INVOICE_ITEM_ADJUSTMENT_AMOUNT = "custom_item_adjustment_amount";
const PURCHASE_INVOICE_ITEM_ADJUSTMENT_ACCOUNT = "custom_item_adjustment_account";
const PURCHASE_INVOICE_ITEM_DISCOUNT_MARKER = "custom_is_purchase_item_discount";
const PURCHASE_INVOICE_ADJUSTED_TAX_BASE_MARKER = "custom_uses_adjusted_tax_base";
const PURCHASE_INVOICE_ORIGINAL_CHARGE_TYPE = "custom_original_charge_type";
const PURCHASE_INVOICE_ORIGINAL_ROW_ID = "custom_original_row_id";

frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		set_adjustment_account_query(frm);
		set_item_adjustment_account_query(frm);
	},
	refresh(frm) {
		set_adjustment_account_query(frm);
		set_item_adjustment_account_query(frm);
		refresh_adjustment_total(frm);
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Add Adjustment"), () => add_adjustment_row(frm));
		}
	},
	company(frm) {
		set_adjustment_account_query(frm);
		set_item_adjustment_account_query(frm);
	},
	taxes_remove(frm) {
		refresh_adjustment_total(frm);
	},
});

frappe.ui.form.on("Purchase Taxes and Charges", {
	tax_amount(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (cint(row[PURCHASE_INVOICE_ADJUSTMENT_MARKER]) && flt(row.tax_amount) < 0) {
			frappe.model.set_value(cdt, cdn, "tax_amount", Math.abs(flt(row.tax_amount)));
			frappe.model.set_value(cdt, cdn, "add_deduct_tax", "Deduct");
			return;
		}
		refresh_adjustment_total(frm);
	},
	add_deduct_tax(frm) {
		refresh_adjustment_total(frm);
	},
});

frappe.ui.form.on("Purchase Invoice Item", {
	async custom_item_adjustment_amount(frm, cdt, cdn) {
		await set_default_item_adjustment_account(frm, cdt, cdn);
		await sync_item_adjustments(frm);
	},
	async custom_item_adjustment_account(frm) {
		await sync_item_adjustments(frm);
	},
});

function set_adjustment_account_query(frm) {
	frm.set_query("account_head", "taxes", () => ({
		filters: { company: frm.doc.company, is_group: 0, disabled: 0 },
	}));
}

function set_item_adjustment_account_query(frm) {
	frm.set_query(PURCHASE_INVOICE_ITEM_ADJUSTMENT_ACCOUNT, "items", () => ({
		filters: { company: frm.doc.company, is_group: 0, disabled: 0 },
	}));
}

async function add_adjustment_row(frm) {
	const default_account = await get_default_adjustment_account(frm);
	frm.add_child("taxes", {
		charge_type: "Actual",
		category: "Total",
		add_deduct_tax: "Add",
		account_head: default_account,
		cost_center: get_default_cost_center(frm),
		description: __("Adjustment"),
		tax_amount: 0,
		included_in_print_rate: 0,
		included_in_paid_amount: 0,
		[PURCHASE_INVOICE_ADJUSTMENT_MARKER]: 1,
	});
	reindex_tax_rows(frm);
	frm.refresh_field("taxes");
	configure_adjusted_tax_base(frm);
	await frm.cscript.calculate_taxes_and_totals();
	refresh_adjustment_total(frm);
}

async function get_default_adjustment_account(frm) {
	return frappe.db.get_single_value(
		"Redtra Custom Setting",
		"default_purchase_invoice_adjustment_account"
	);
}

async function set_default_item_adjustment_account(frm, cdt, cdn) {
	const item = locals[cdt][cdn];
	if (!flt(item[PURCHASE_INVOICE_ITEM_ADJUSTMENT_AMOUNT]) || item[PURCHASE_INVOICE_ITEM_ADJUSTMENT_ACCOUNT]) {
		return;
	}
	const account = await get_default_adjustment_account(frm);
	if (account) {
		item[PURCHASE_INVOICE_ITEM_ADJUSTMENT_ACCOUNT] = account;
		frm.refresh_field("items");
	}
}

async function sync_item_adjustments(frm) {
	if (!frm.doc.company || !frm.fields_dict.items) {
		return;
	}

	const defaultAccount = await get_default_adjustment_account(frm);
	const accountTotals = new Map();
	for (const item of frm.doc.items || []) {
		const amount = flt(item[PURCHASE_INVOICE_ITEM_ADJUSTMENT_AMOUNT]);
		if (!amount) {
			continue;
		}
		const account = item[PURCHASE_INVOICE_ITEM_ADJUSTMENT_ACCOUNT] || defaultAccount;
		const costCenter = item.cost_center || get_default_cost_center(frm);
		const key = `${account || ""}::${costCenter || ""}`;
		const entry = accountTotals.get(key) || { account, costCenter, amount: 0 };
		entry.amount = flt(entry.amount) + amount;
		accountTotals.set(key, entry);
	}

	frm.doc.taxes = (frm.doc.taxes || []).filter(
		row => !cint(row[PURCHASE_INVOICE_ITEM_ADJUSTMENT_MARKER])
	);
	for (const { account, costCenter, amount } of accountTotals.values()) {
		if (!amount) {
			continue;
		}
		frm.add_child("taxes", {
			charge_type: "Actual",
			category: "Total",
			add_deduct_tax: amount > 0 ? "Add" : "Deduct",
			account_head: account,
			cost_center: costCenter,
			description: __("Item Adjustments"),
			tax_amount: Math.abs(amount),
			included_in_print_rate: 0,
			included_in_paid_amount: 0,
			[PURCHASE_INVOICE_ADJUSTMENT_MARKER]: 1,
			[PURCHASE_INVOICE_ITEM_ADJUSTMENT_MARKER]: 1,
		});
	}
	reindex_tax_rows(frm);
	frm.refresh_field("taxes");
	configure_adjusted_tax_base(frm);
	await frm.cscript.calculate_taxes_and_totals();
	refresh_adjustment_total(frm);
}

function get_default_cost_center(frm) {
	return (frm.doc.items || []).find(item => item.cost_center)?.cost_center || frm.doc.cost_center || "";
}

function refresh_adjustment_total(frm) {
	const total = (frm.doc.taxes || [])
		.filter(row => cint(row[PURCHASE_INVOICE_ADJUSTMENT_MARKER]))
		.reduce((sum, row) => {
			const amount = flt(row.tax_amount);
			return sum + (row.add_deduct_tax === "Deduct" ? -amount : amount);
		}, 0);

	if (flt(frm.doc.custom_adjustment_total) !== total) {
		frm.set_value("custom_adjustment_total", total);
	}
}

function reindex_tax_rows(frm) {
	(frm.doc.taxes || []).forEach((row, index) => {
		row.idx = index + 1;
	});
}

function configure_adjusted_tax_base(frm) {
	const taxableBaseRows = (frm.doc.taxes || []).filter(is_taxable_base_row);
	if (!taxableBaseRows.length) {
		restore_original_tax_base(frm);
		reindex_tax_rows(frm);
		return;
	}

	frm.doc.taxes = [
		...taxableBaseRows,
		...(frm.doc.taxes || []).filter(row => !is_taxable_base_row(row)),
	];
	reindex_tax_rows(frm);
	const lastBaseRow = taxableBaseRows[taxableBaseRows.length - 1];

	for (const row of frm.doc.taxes) {
		if (is_taxable_base_row(row)) {
			continue;
		}
		if (row.charge_type === "On Net Total") {
			if (!cint(row[PURCHASE_INVOICE_ADJUSTED_TAX_BASE_MARKER])) {
				row[PURCHASE_INVOICE_ORIGINAL_CHARGE_TYPE] = row.charge_type;
				row[PURCHASE_INVOICE_ORIGINAL_ROW_ID] = row.row_id || "";
			}
			row.charge_type = "On Previous Row Total";
			row.row_id = lastBaseRow.idx;
			row[PURCHASE_INVOICE_ADJUSTED_TAX_BASE_MARKER] = 1;
		} else if (cint(row[PURCHASE_INVOICE_ADJUSTED_TAX_BASE_MARKER])) {
			row.row_id = lastBaseRow.idx;
		}
	}

	frm.refresh_field("taxes");
}

function restore_original_tax_base(frm) {
	for (const row of frm.doc.taxes || []) {
		if (!cint(row[PURCHASE_INVOICE_ADJUSTED_TAX_BASE_MARKER])) {
			continue;
		}
		row.charge_type = row[PURCHASE_INVOICE_ORIGINAL_CHARGE_TYPE] || "On Net Total";
		row.row_id = row[PURCHASE_INVOICE_ORIGINAL_ROW_ID] || "";
		row[PURCHASE_INVOICE_ADJUSTED_TAX_BASE_MARKER] = 0;
		row[PURCHASE_INVOICE_ORIGINAL_CHARGE_TYPE] = "";
		row[PURCHASE_INVOICE_ORIGINAL_ROW_ID] = "";
	}
}

function is_taxable_base_row(row) {
	return (
		cint(row[PURCHASE_INVOICE_ADJUSTMENT_MARKER]) ||
		cint(row[PURCHASE_INVOICE_ITEM_DISCOUNT_MARKER])
	);
}
