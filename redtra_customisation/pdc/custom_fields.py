"""
Custom fields for PDC Management module
"""

PDC_CUSTOM_FIELDS = {
	"Payment Entry": [
		{
			"fieldname": "pdc_section",
			"fieldtype": "Section Break",
			"label": "Post-Dated Cheque Details",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "mode_of_payment",
			"collapsible": 1,
		},
		{
			"fieldname": "pdc_cheque_number",
			"fieldtype": "Data",
			"label": "Cheque Number",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "pdc_section",
		},
		{
			"fieldname": "pdc_cheque_date",
			"fieldtype": "Date",
			"label": "Cheque Date",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "pdc_cheque_number",
		},
		{
			"fieldname": "pdc_bank_account",
			"fieldtype": "Link",
			"label": "Bank Account",
			"options": "Account",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "pdc_cheque_date",
			"description": "Bank account where cheque is drawn/issued",
		},
		{
			"fieldname": "pdc_cheque_status",
			"fieldtype": "Select",
			"label": "Cheque Status",
			"options": "Issued\nUnder Collection\nCollected\nBounced\nPaid",
			"default": "Issued",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "pdc_bank_account",
			"description": "Status of the cheque",
			"allow_on_submit": 1,
			"read_only_depends_on": "eval:doc.docstatus == 0",
		},
		{
			"fieldname": "pdc_cheque_details_section",
			"fieldtype": "Section Break",
			"label": "Cheque Transaction History",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "pdc_cheque_status",
		},
		{
			"fieldname": "pdc_cheque_details",
			"fieldtype": "Table",
			"label": "Cheque Details",
			"options": "PDC Cheque Detail",
			"depends_on": "eval:doc.mode_of_payment && doc.mode_of_payment.toLowerCase().includes('cheque')",
			"insert_after": "pdc_cheque_details_section",
			"read_only": 1,
		},
	]
}
