// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Manufacturing Stock Entry Report"] = {
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
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "bom_no",
            label: __("BOM No"),
            fieldtype: "Link",
            options: "BOM",
        },
        {
            fieldname: "work_order",
            label: __("Work Order"),
            fieldtype: "Link",
            options: "Work Order",
        },
        {
            fieldname: "item_type",
            label: __("Item Type"),
            fieldtype: "Select",
            options: "\nProduced Item\nMaterial Consumed\nScrap Item",
        },
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (data && data.item_type) {
            if (data.item_type === "Material Consumed") {
                value = `<span style="color: #e24c4c; font-weight: 500;">${value}</span>`;
            } else if (data.item_type === "Produced Item") {
                value = `<span style="color: #38a169; font-weight: 600;">${value}</span>`;
            } else if (data.item_type === "Scrap Item") {
                value = `<span style="color: #e67e22; font-weight: 500;">${value}</span>`;
            }
        }

        return value;
    },
};
