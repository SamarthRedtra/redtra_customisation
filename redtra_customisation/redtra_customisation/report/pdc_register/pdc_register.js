// Copyright (c) 2025, samarth.upare@redtra.com and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["PDC Register"] = {
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
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Link",
			options: "DocType",
			get_query: function() {
				return {
					filters: {
						name: ["in", ["Customer", "Supplier"]]
					}
				};
			}
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Dynamic Link",
			options: "party_type",
			get_query: function() {
				var party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) {
					frappe.throw(__("Please select Party Type first"));
				}
				return {
					doctype: party_type,
				};
			}
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "Issued\nUnder Collection\nCollected\nBounced\nPaid"
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date"
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date"
		}
	]
};
