frappe.listview_settings["Cash Bank Entry"] = {
	add_fields: ["entry_type", "account_type", "paid_account", "amount", "status", "journal_entry", "payment_entry"],
	get_indicator(doc) {
		const colors = {
			Draft: "grey",
			Submitted: "green",
			Cancelled: "red",
		};
		return [__(doc.status || "Draft"), colors[doc.status] || "grey", "status,=," + doc.status];
	},
};
