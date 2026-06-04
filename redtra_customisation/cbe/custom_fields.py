"""Custom fields linking Journal Entry and Payment Entry to Cash Bank Entry."""

CBE_LINK_CUSTOM_FIELDS = {
	"Journal Entry": [
		{
			"fieldname": "custom_cash_bank_entry",
			"fieldtype": "Link",
			"label": "Cash Bank Entry",
			"options": "Cash Bank Entry",
			"insert_after": "user_remark",
			"read_only": 1,
			"allow_on_submit": 1,
		}
	],
	"Payment Entry": [
		{
			"fieldname": "custom_cash_bank_entry",
			"fieldtype": "Link",
			"label": "Cash Bank Entry",
			"options": "Cash Bank Entry",
			"insert_after": "custom_is_pdc_entry",
			"read_only": 1,
			"allow_on_submit": 1,
		}
	],
}
