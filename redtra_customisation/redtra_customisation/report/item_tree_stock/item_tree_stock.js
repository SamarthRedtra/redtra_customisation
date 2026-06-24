// Copyright (c) 2026, Redtra Customisation and contributors

frappe.query_reports["Item Tree Stock"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "warehouse_wise_columns",
			label: __("Warehouse Wise Columns"),
			fieldtype: "Check",
			default: 1,
			description: __("Show one column per warehouse. Uncheck to show only the selected warehouse column."),
		},
		{
			fieldname: "warehouses",
			label: __("Warehouse Columns"),
			fieldtype: "MultiSelectList",
			options: "Warehouse",
			description: __("Leave empty to include all company warehouses as columns."),
			get_data(txt) {
				const company = frappe.query_report.get_filter_value("company");
				if (!company) {
					return [];
				}
				return frappe.db.get_link_options("Warehouse", txt, {
					company,
					is_group: 0,
					disabled: 0,
				});
			},
		},
		{
			fieldname: "warehouse",
			label: __("Stock Filter Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			description: __("Optional. Used only for Zero / Non-Zero stock filter scope."),
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				return company ? { filters: { company, is_group: 0 } } : {};
			},
		},
		{
			fieldname: "root_item_group",
			label: __("Root Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "search",
			label: __("Search"),
			fieldtype: "Data",
		},
		{
			fieldname: "stock_qty_filter",
			label: __("Stock Qty"),
			fieldtype: "Select",
			options: "\nAll\nNon-Zero\nZero",
			default: "All",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "is_stock_item",
			label: __("Is Stock Item"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
		{
			fieldname: "include_disabled",
			label: __("Include Disabled"),
			fieldtype: "Check",
			default: 0,
		},
	],
	tree: true,
	initial_depth: 2,
	formatter(value, row, column, data, default_formatter) {
		if (data?.is_group_row && column.fieldname === "item_name") {
			return `<b>${frappe.utils.escape_html(value || data.item_group || "")}</b>`;
		}
		if (data?.is_group_row && column.fieldname === "item_code") {
			return "";
		}
		return default_formatter(value, row, column, data);
	},
};
