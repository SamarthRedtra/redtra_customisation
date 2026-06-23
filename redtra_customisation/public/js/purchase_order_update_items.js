// Copyright (c) 2026, redtra_customisation contributors

frappe.provide("redtra_customisation.utils");

redtra_customisation.utils.update_po_items_restricted = function (frm) {
	const child_docname = "items";
	const child_meta = frappe.get_meta("Purchase Order Item");
	const get_precision = (fieldname) =>
		child_meta.fields.find((f) => f.fieldname === fieldname)?.precision;

	const original_rows = {};
	(frm.doc.items || []).forEach((row) => {
		original_rows[row.name] = {
			item_code: row.item_code,
			rate: row.rate,
			uom: row.uom,
			schedule_date: row.schedule_date,
			description: row.description,
			conversion_factor: row.conversion_factor,
		};
	});

	const data = (frm.doc.items || []).map((d) => ({
		docname: d.name,
		name: d.name,
		item_code: d.item_code,
		item_name: d.item_name,
		schedule_date: d.schedule_date,
		conversion_factor: d.conversion_factor,
		qty: d.qty,
		rate: d.rate,
		uom: d.uom,
		description: d.description,
	}));

	const fields = [
		{
			fieldtype: "Data",
			fieldname: "docname",
			read_only: 1,
			hidden: 1,
		},
		{
			fieldtype: "Link",
			fieldname: "item_code",
			options: "Item",
			in_list_view: 1,
			label: __("Item Code"),
			get_query() {
				let filters = { is_purchase_item: 1 };
				if (frm.doc.is_subcontracted) {
					filters = frm.doc.is_old_subcontracting_flow
						? { is_sub_contracted_item: 1 }
						: { is_stock_item: 0 };
				}
				return {
					query: "erpnext.controllers.queries.item_query",
					filters,
				};
			},
			change() {
				const me = this;
				if (!this.value || original_rows[me.doc.docname]) {
					return;
				}

				frm.call({
					method: "erpnext.stock.get_item_details.get_item_details",
					args: {
						doc: frm.doc,
						ctx: {
							item_code: this.value,
							set_warehouse: frm.doc.set_warehouse,
							supplier: frm.doc.supplier,
							currency: frm.doc.currency,
							is_internal_supplier: frm.doc.is_internal_supplier,
							conversion_rate: frm.doc.conversion_rate,
							price_list: frm.doc.buying_price_list,
							price_list_currency: frm.doc.price_list_currency,
							plc_conversion_rate: frm.doc.plc_conversion_rate,
							company: frm.doc.company,
							is_subcontracted: frm.doc.is_subcontracted,
							ignore_pricing_rule: frm.doc.ignore_pricing_rule,
							doctype: frm.doc.doctype,
							name: frm.doc.name,
							qty: me.doc.qty || 1,
							uom: me.doc.uom,
							is_old_subcontracting_flow: frm.doc.is_old_subcontracting_flow,
							child_doctype: "Purchase Order Item",
						},
					},
					callback(r) {
						if (!r.message) {
							return;
						}
						const {
							qty,
							price_list_rate: rate,
							uom,
							conversion_factor,
							item_name,
							description,
						} = r.message;
						const row = dialog.fields_dict.trans_items.df.data.find(
							(row) => row.name === me.doc.name
						);
						if (row) {
							Object.assign(row, {
								conversion_factor: conversion_factor,
								uom,
								qty: row.qty || qty,
								rate,
								item_name,
								description,
							});
							dialog.fields_dict.trans_items.grid.refresh();
							lock_restricted_row_fields(dialog, original_rows);
						}
					},
				});
			},
		},
		{
			fieldtype: "Data",
			fieldname: "item_name",
			label: __("Item Name"),
			read_only: 1,
			in_list_view: 1,
		},
		{
			fieldtype: "Date",
			fieldname: "schedule_date",
			in_list_view: 1,
			label: __("Reqd by date"),
			reqd: 1,
			read_only: 1,
		},
		{
			fieldtype: "Float",
			fieldname: "conversion_factor",
			label: __("Conversion Factor"),
			read_only: 1,
			precision: get_precision("conversion_factor"),
		},
		{
			fieldtype: "Link",
			fieldname: "uom",
			options: "UOM",
			label: __("UOM"),
			reqd: 1,
			read_only: 1,
		},
		{
			fieldtype: "Float",
			fieldname: "qty",
			default: 0,
			in_list_view: 1,
			label: __("Qty"),
			precision: get_precision("qty"),
		},
		{
			fieldtype: "Currency",
			fieldname: "rate",
			options: "currency",
			default: 0,
			in_list_view: 1,
			label: __("Rate"),
			read_only: 0,
			precision: get_precision("rate"),
		},
		{
			fieldtype: "Text Editor",
			fieldname: "description",
			read_only: 1,
			label: __("Description"),
		},
	];

	const dialog = new frappe.ui.Dialog({
		title: __("Update Items"),
		size: "extra-large",
		fields: [
			{
				fieldname: "trans_items",
				fieldtype: "Table",
				label: __("Items"),
				cannot_add_rows: false,
				in_place_edit: false,
				reqd: 1,
				data,
				get_data: () => data,
				fields,
			},
		],
		primary_action() {
			const trans_items = this.get_values()["trans_items"].filter((item) => !!item.item_code);

			for (const item of trans_items) {
				const original = original_rows[item.docname];
				if (original) {
					if (original.item_code && item.item_code !== original.item_code) {
						frappe.throw(
							__(
								"Item Code cannot be changed for existing rows after a Receive Note is created."
							)
						);
					}
					if (flt(item.rate) !== flt(original.rate)) {
						frappe.throw(
							__(
								"Rate cannot be changed for existing rows after a Receive Note is created."
							)
						);
					}
					item.rate = original.rate;
					item.uom = original.uom;
					item.schedule_date = original.schedule_date;
					item.description = original.description;
					item.conversion_factor = original.conversion_factor;
				}
			}

			frappe.call({
				method: "redtra_customisation.override.provisional_purchase_order.update_po_items_with_restrictions",
				freeze: true,
				args: {
					parent_doctype: frm.doc.doctype,
					trans_items,
					parent_doctype_name: frm.doc.name,
					child_docname,
				},
				callback() {
					frm.reload_doc();
				},
			});
			this.hide();
		},
		primary_action_label: __("Update"),
	});

	dialog.show();
	setTimeout(() => lock_restricted_row_fields(dialog, original_rows), 200);
	const grid = dialog.fields_dict.trans_items.grid;
	if (grid && grid.wrapper) {
		grid.wrapper.on("grid-row-render", () => {
			lock_restricted_row_fields(dialog, original_rows);
		});
		grid.wrapper.on("click", ".grid-row-open", () => {
			setTimeout(() => lock_restricted_row_fields(dialog, original_rows), 100);
		});
	}
	if (typeof grid.add_new_row === "function") {
		const add_new_row = grid.add_new_row.bind(grid);
		grid.add_new_row = function (...args) {
			const row = add_new_row(...args);
			setTimeout(() => lock_restricted_row_fields(dialog, original_rows), 100);
			return row;
		};
	}
};

function lock_restricted_row_fields(dialog, original_rows) {
	const grid = dialog.fields_dict.trans_items.grid;
	if (!grid || !grid.grid_rows) {
		return;
	}

	const locked_for_existing = [
		"item_code",
		"rate",
		"uom",
		"schedule_date",
		"description",
		"conversion_factor",
	];
	const locked_for_new = ["uom", "schedule_date", "description", "conversion_factor"];

	grid.grid_rows.forEach((grid_row) => {
		const is_existing = !!original_rows[grid_row.doc.docname];

		if (is_existing) {
			locked_for_existing.forEach((fieldname) => {
				set_field_editable(grid_row, fieldname, false);
			});
		} else {
			set_field_editable(grid_row, "item_code", true);
			set_field_editable(grid_row, "rate", true);
			locked_for_new.forEach((fieldname) => {
				set_field_editable(grid_row, fieldname, false);
			});
		}

		set_field_editable(grid_row, "qty", true);
	});
}

function set_field_editable(grid_row, fieldname, editable) {
	if (typeof grid_row.toggle_editable === "function") {
		grid_row.toggle_editable(fieldname, editable);
		return;
	}

	const field = grid_row.on_grid_fields_dict?.[fieldname];
	if (field) {
		field.df.read_only = editable ? 0 : 1;
		field.refresh();
	}
}
