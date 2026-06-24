// Copyright (c) 2026, redtra_customisation contributors

function get_pi_item_by_row(frm, item_row) {
	return (frm.doc.items || []).find(row => cint(row.idx) === cint(item_row));
}

function sync_point_adjustment_row(frm, cdt, cdn) {
	const adj = locals[cdt][cdn];
	if (!adj.item_row) {
		return;
	}

	const item = get_pi_item_by_row(frm, adj.item_row);
	if (!item) {
		frappe.msgprint(
			__("Item Row #{0} was not found. Add the item line first.", [adj.item_row])
		);
		return;
	}

	frappe.model.set_value(cdt, cdn, "purchase_invoice_item", item.name);
	frappe.model.set_value(cdt, cdn, "item_code", item.item_code);
	frappe.model.set_value(cdt, cdn, "item_name", item.item_name);
	frappe.model.set_value(cdt, cdn, "reference_amount", flt(item.net_amount));
}

function recalculate_pi_with_point_adjustments(frm) {
	if (!frm.doc.point_adjustments?.length) {
		return;
	}
	frm.script_manager.trigger("calculate_taxes_and_totals");
}

function open_point_adjustment_dialog(frm, item_row) {
	const item = get_pi_item_by_row(frm, item_row);
	if (!item) {
		frappe.msgprint(__("Select a valid item line first."));
		return;
	}

	const d = new frappe.ui.Dialog({
		title: __("Point Adjustment — Row {0}", [item.idx]),
		fields: [
			{
				fieldtype: "Data",
				fieldname: "item_label",
				label: __("Item"),
				read_only: 1,
				default: `${item.item_code || ""} — ${item.item_name || ""}`.trim(),
			},
			{
				fieldtype: "Currency",
				fieldname: "reference_amount",
				label: __("Current Line Amount"),
				read_only: 1,
				default: flt(item.net_amount),
			},
			{
				fieldtype: "Currency",
				fieldname: "adjustment_amount",
				label: __("Adjustment Amount"),
				reqd: 1,
				description: __("Use positive or negative values. Example: 0.48 on a 4.98 line."),
			},
			{
				fieldtype: "Data",
				fieldname: "remarks",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Add Adjustment"),
		primary_action(values) {
			if (!flt(values.adjustment_amount)) {
				frappe.msgprint(__("Enter a non-zero adjustment amount."));
				return;
			}

			const child = frm.add_child("point_adjustments");
			child.item_row = item.idx;
			child.purchase_invoice_item = item.name;
			child.item_code = item.item_code;
			child.item_name = item.item_name;
			child.reference_amount = flt(item.net_amount);
			child.adjustment_amount = flt(values.adjustment_amount);
			child.remarks = values.remarks;
			frm.refresh_field("point_adjustments");
			recalculate_pi_with_point_adjustments(frm);
			d.hide();
		},
	});
	d.show();
}

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) {
			return;
		}

		frm.fields_dict.items?.grid?.add_custom_button(
			__("Point Adjustment"),
			() => {
				const selected = frm.fields_dict.items.grid.get_selected();
				if (selected?.length === 1) {
					open_point_adjustment_dialog(frm, locals[selected[0].doctype][selected[0].name].idx);
					return;
				}
				frappe.msgprint(__("Select one item row, then click Point Adjustment."));
			},
			__("Adjust")
		);
	},
	items_remove(frm) {
		recalculate_pi_with_point_adjustments(frm);
	},
});

frappe.ui.form.on("Purchase Invoice Point Adjustment", {
	item_row(frm, cdt, cdn) {
		sync_point_adjustment_row(frm, cdt, cdn);
		recalculate_pi_with_point_adjustments(frm);
	},
	adjustment_amount(frm, cdt, cdn) {
		recalculate_pi_with_point_adjustments(frm);
	},
	point_adjustments_remove(frm) {
		recalculate_pi_with_point_adjustments(frm);
	},
});
