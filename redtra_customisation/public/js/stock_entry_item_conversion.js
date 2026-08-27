const ITEM_CONVERSION_TYPE = 'Item Conversion / Dismantling';

function isItemConversion(frm) {
	return frm.doc.stock_entry_type === ITEM_CONVERSION_TYPE;
}

function configureItemConversionGrid(frm) {
	const grid = frm.fields_dict.items?.grid;
	if (!grid) return;

	const enabled = frm.doc.docstatus === 0 && isItemConversion(frm);
	grid.update_docfield_property('set_basic_rate_manually', 'hidden', !enabled);
	grid.update_docfield_property('set_basic_rate_manually', 'in_list_view', enabled);
	grid.update_docfield_property('basic_rate', 'in_list_view', enabled);
	grid.update_docfield_property('basic_rate', 'read_only', !enabled);
	grid.update_docfield_property('is_finished_item', 'hidden', enabled);
}

function enableItemConversionRate(frm, cdt, cdn) {
	if (!isItemConversion(frm)) return;

	const row = locals[cdt]?.[cdn];
	if (!row?.item_code) return;

	frappe.model.set_value(cdt, cdn, 'set_basic_rate_manually', 1);
}

function enableItemConversionRates(frm) {
	(frm.doc.items || []).forEach((row) => {
		enableItemConversionRate(frm, row.doctype, row.name);
	});
}

frappe.ui.form.on('Stock Entry', {
	refresh(frm) {
		configureItemConversionGrid(frm);
	},

	stock_entry_type(frm) {
		configureItemConversionGrid(frm);
		enableItemConversionRates(frm);
	}
});

frappe.ui.form.on('Stock Entry Detail', {
	item_code(frm, cdt, cdn) {
		enableItemConversionRate(frm, cdt, cdn);
	},

	s_warehouse(frm, cdt, cdn) {
		enableItemConversionRate(frm, cdt, cdn);
	},

	t_warehouse(frm, cdt, cdn) {
		enableItemConversionRate(frm, cdt, cdn);
	}
});
