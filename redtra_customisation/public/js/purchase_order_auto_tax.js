frappe.ui.form.on("Purchase Order", {
	onload(frm) {
		apply_default_purchase_order_tax_template(frm);
	},
	company(frm) {
		apply_default_purchase_order_tax_template(frm);
	},
});

async function apply_default_purchase_order_tax_template(frm) {
	if (!should_apply_default_purchase_order_tax_template(frm)) {
		return;
	}

	const result = await frappe.db.get_value(
		"Company",
		frm.doc.company,
		"custom_default_purchase_order_tax_template"
	);
	const taxTemplate = result.message?.custom_default_purchase_order_tax_template;
	if (!taxTemplate || !should_apply_default_purchase_order_tax_template(frm)) {
		return;
	}

	const taxes = await get_purchase_order_template_taxes(frm, taxTemplate);
	if (!taxes || !should_apply_default_purchase_order_tax_template(frm)) {
		return;
	}

	frm.doc.taxes_and_charges = taxTemplate;
	frm.refresh_field("taxes_and_charges");
	await frm.set_value("taxes", taxes);
	await frm.cscript.calculate_taxes_and_totals();
}

async function get_purchase_order_template_taxes(frm, taxTemplate) {
	const response = await frm.call({
		method: "erpnext.controllers.accounts_controller.get_taxes_and_charges",
		args: {
			master_doctype: "Purchase Taxes and Charges Template",
			master_name: taxTemplate,
		},
	});
	return response.message || [];
}

function should_apply_default_purchase_order_tax_template(frm) {
	return Boolean(
		frm.is_new() &&
		frm.doc.company &&
		!cint(frm.doc.is_return) &&
		!frm.doc.taxes_and_charges &&
		!(frm.doc.taxes || []).length
	);
}
