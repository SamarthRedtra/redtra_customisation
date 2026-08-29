frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		set_purchase_discount_account_query(frm);
	},
	refresh(frm) {
		setup_line_discount_fields(frm);
		set_purchase_discount_account_query(frm);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Set Price Discount"), () => show_discount_dialog(frm));
		}
	},
	company(frm) {
		set_purchase_discount_account_query(frm);
	},
});

frappe.ui.form.on("Purchase Invoice Item", {
	async custom_purchase_discount_amount(frm, cdt, cdn) {
		await set_default_discount_account(frm, cdt, cdn);
		await sync_purchase_item_discounts(frm);
	},
	async custom_purchase_discount_account(frm) {
		await sync_purchase_item_discounts(frm);
	},
});

function setup_line_discount_fields(frm) {
	const grid = frm.get_field("items")?.grid;
	if (!grid) {
		return;
	}

	grid.update_docfield_property("discount_amount", "label", __("Price Reduction / Unit"));
	grid.update_docfield_property("custom_purchase_discount_amount", "in_list_view", 1);
	grid.update_docfield_property("custom_purchase_discount_account", "in_list_view", 1);
	grid.refresh();
}

async function set_default_discount_account(frm, cdt, cdn) {
	const item = locals[cdt][cdn];
	if (!flt(item.custom_purchase_discount_amount) || item.custom_purchase_discount_account) {
		return;
	}
	const account = await frappe.db.get_single_value(
		"Redtra Custom Setting",
		"default_purchase_invoice_discount_account"
	);
	if (account) {
		item.custom_purchase_discount_account = account;
		frm.refresh_field("items");
	}
}

function set_purchase_discount_account_query(frm) {
	frm.set_query("custom_purchase_discount_account", "items", () => ({
		filters: {
			company: frm.doc.company,
			is_group: 0,
			disabled: 0,
			report_type: "Profit and Loss",
		},
	}));
}

async function sync_purchase_item_discounts(frm) {
	if (!frm.doc.company || !frm.fields_dict.items) {
		return;
	}

	const accountTotals = new Map();
	for (const item of frm.doc.items || []) {
		const discount = flt(item.custom_purchase_discount_amount);
		const costCenter = item.cost_center || get_default_cost_center(frm);
		if (!discount || !item.custom_purchase_discount_account || !costCenter) {
			continue;
		}
		const amount = discount * flt(item.qty);
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
	reindex_tax_rows(frm);
	if (typeof configure_adjusted_tax_base === "function") {
		configure_adjusted_tax_base(frm);
	}
	const total = [...accountTotals.values()].reduce((sum, entry) => sum + entry.amount, 0);
	if (flt(frm.doc.custom_purchase_discount_total) !== flt(total)) {
		await frm.set_value("custom_purchase_discount_total", total);
	}
	frm.refresh_field("taxes");
	await frm.cscript.calculate_taxes_and_totals();
}

function reindex_tax_rows(frm) {
	(frm.doc.taxes || []).forEach((row, index) => {
		row.idx = index + 1;
	});
}

function get_default_cost_center(frm) {
	return (frm.doc.items || []).find(item => item.cost_center)?.cost_center || frm.doc.cost_center || "";
}

function show_discount_dialog(frm) {
	const discountByPercentage = flt(frm.doc.additional_discount_percentage) > 0;
	const dialog = new frappe.ui.Dialog({
		title: __("Set Discount"),
		fields: [
			{
				fieldname: "apply_discount_on",
				fieldtype: "Select",
				label: __("Apply Discount On"),
				options: "Grand Total\nNet Total",
				default: frm.doc.apply_discount_on || "Grand Total",
				reqd: 1,
			},
			{
				fieldname: "discount_type",
				fieldtype: "Select",
				label: __("Discount Type"),
				options: "Amount\nPercentage",
				default: discountByPercentage ? "Percentage" : "Amount",
				reqd: 1,
			},
			{
				fieldname: "discount_value",
				fieldtype: "Float",
				label: __("Discount Value"),
				default: discountByPercentage
					? frm.doc.additional_discount_percentage || 0
					: frm.doc.discount_amount || 0,
				reqd: 1,
			},
		],
		primary_action_label: __("Apply"),
		primary_action: async values => {
			const isPercentage = values.discount_type === "Percentage";
			await frm.set_value({
				apply_discount_on: values.apply_discount_on,
				additional_discount_percentage: isPercentage ? values.discount_value : 0,
				discount_amount: isPercentage ? 0 : values.discount_value,
			});
			await frm.cscript.calculate_taxes_and_totals();
			dialog.hide();
		},
	});
	dialog.show();
}
