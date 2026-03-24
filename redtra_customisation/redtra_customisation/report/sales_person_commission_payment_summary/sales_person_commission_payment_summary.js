// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// For license information, please see license.txt
/* eslint-disable */

const SALES_PERSON_PAYMENT_ACTION_CLASS = "redtra-sales-person-create-payment-entry";

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

function get_sales_person_payment_entry_route_options(row) {
	const commission_amount = flt(row.commission_amount || 0);
	const route_options = {
		payment_type: "Pay",
		party_type: "Employee",
		party: row.employee,
		company: row.company,
		paid_amount: commission_amount,
		received_amount: commission_amount,
		remarks: `Commission payout for ${row.source_doctype || "Document"} ${row.source_name}`,
	};

	if (row.project) {
		route_options.project = row.project;
	}

	return route_options;
}

function bind_sales_person_payment_entry_actions(datatable) {
	$(datatable.wrapper)
		.find(`.${SALES_PERSON_PAYMENT_ACTION_CLASS}`)
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

frappe.query_reports["Sales Person Commission Payment Summary"] = {
	onload: function () {
		ensure_redtra_commission_pe_button_styles();
	},

	filters: [
		{
			fieldname: "sales_person",
			label: __("Sales Person"),
			fieldtype: "Link",
			options: "Sales Person",
		},
		{
			fieldname: "doc_type",
			label: __("Document Type"),
			fieldtype: "Select",
			options: "Sales Order\nDelivery Note\nSales Invoice",
			default: "Sales Order",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
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
			if (!data || !data.sales_person) {
				return "";
			}

			if (!data.employee) {
				return `<span class="text-muted">${__("Missing Employee")}</span>`;
			}

			if (!flt(data.commission_amount)) {
				return `<span class="text-muted">${__("No Commission")}</span>`;
			}

			const payload = encodeURIComponent(
				JSON.stringify(get_sales_person_payment_entry_route_options(data))
			).replace(/'/g, "%27");

			return `<button type="button" class="redtra-commission-pe-btn ${SALES_PERSON_PAYMENT_ACTION_CLASS}" data-payload="${payload}">${__(
				"Create Payment Entry"
			)}</button>`;
		}

		return default_formatter(value, row, column, data);
	},

	after_datatable_render: function (datatable) {
		bind_sales_person_payment_entry_actions(datatable);
	},
};
