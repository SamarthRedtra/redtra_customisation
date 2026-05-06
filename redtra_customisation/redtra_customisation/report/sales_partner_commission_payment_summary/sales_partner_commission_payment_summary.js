// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// For license information, please see license.txt
/* eslint-disable */

const SALES_PARTNER_PAYMENT_ACTION_CLASS = "redtra-sales-partner-create-payment-entry";

function ensure_redtra_commission_pe_button_styles() {
	if (document.getElementById("redtra-commission-pe-style")) {
		return;
	}
	const el = document.createElement("style");
	el.id = "redtra-commission-pe-style";
	el.textContent = `
		.redtra-commission-pe-btn {
			background: #111111 !important;
			color: #ffffff !important;
			border: 1px solid #000000 !important;
			border-radius: 4px !important;
			padding: 5px 12px !important;
			font-size: 12px !important;
			font-weight: 500 !important;
			cursor: pointer !important;
			line-height: 1.25 !important;
			font-family: inherit !important;
			text-decoration: none !important;
			white-space: nowrap;
			box-sizing: border-box;
		}
		.redtra-commission-pe-btn:hover {
			background: #000000 !important;
			color: #ffffff !important;
		}
		.redtra-commission-pe-btn:focus {
			outline: 2px solid var(--primary, #2490ef);
			outline-offset: 2px;
		}
	`;
	document.head.appendChild(el);
}

function get_sales_partner_payment_entry_route_options(row) {
	const commission_amount = flt(row.commission_amount || 0);
	const sp = row.sales_partner || "";
	const route_options = {
		payment_type: "Pay",
		company: row.company,
		paid_amount: commission_amount,
		received_amount: commission_amount,
		remarks: `Commission payout for ${row.source_doctype || "Document"} ${row.source_name}${
			sp ? ` · ${sp}` : ""
		}`,
	};

	if (row.project) {
		route_options.project = row.project;
	}

	// Employee on Sales Partner is optional; when set, pre-fill Pay-to Employee.
	if (row.employee) {
		route_options.party_type = "Employee";
		route_options.party = row.employee;
	}

	return route_options;
}

function bind_sales_partner_payment_entry_actions(datatable) {
	$(datatable.wrapper)
		.find(`.${SALES_PARTNER_PAYMENT_ACTION_CLASS}`)
		.off("click")
		.on("click", function (event) {
			event.preventDefault();

			const payload = $(this).attr("data-payload");
			if (!payload) {
				return;
			}

			frappe.new_doc("Payment Entry", JSON.parse(decodeURIComponent(payload)));
		});
}

frappe.query_reports["Sales Partner Commission Payment Summary"] = {
	onload: function () {
		ensure_redtra_commission_pe_button_styles();
	},

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "sales_partner",
			label: __("Sales Partner"),
			fieldtype: "Link",
			options: "Sales Partner",
		},
		{
			fieldname: "doctype",
			label: __("Document Type"),
			fieldtype: "Select",
			options: "Sales Order\nDelivery Note\nSales Invoice\nPOS Invoice\nJournal Entry",
			default: "Sales Order",
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldname === "create_payment_entry") {
			if (!data || !data.sales_partner) {
				return "";
			}

			if (!flt(data.commission_amount)) {
				return `<span class="text-muted">${__("No Commission")}</span>`;
			}

			const payload = encodeURIComponent(
				JSON.stringify(get_sales_partner_payment_entry_route_options(data))
			).replace(/'/g, "%27");

			return `<button type="button" class="redtra-commission-pe-btn ${SALES_PARTNER_PAYMENT_ACTION_CLASS}" data-payload="${payload}">${__(
				"Create Payment Entry"
			)}</button>`;
		}

		return default_formatter(value, row, column, data);
	},

	after_datatable_render: function (datatable) {
		bind_sales_partner_payment_entry_actions(datatable);
	},
};
