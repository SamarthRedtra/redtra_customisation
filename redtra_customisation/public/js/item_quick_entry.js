frappe.provide("frappe.ui.form");

frappe.ui.form.ItemQuickEntryForm = class ItemQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	constructor(doctype, after_insert, init_callback, doc, force) {
		super(doctype, after_insert, init_callback, doc, force);
		this.skip_redirect_on_error = true;
		this.allow_any_account_on_pi = false;
	}

	is_quick_entry() {
		return true;
	}

	render_dialog() {
		this.docfields = this.docfields.concat(this.get_variant_fields());
		super.render_dialog();
		this.setup_account_queries();
	}

	set_defaults() {
		if (!this.doc.company) {
			this.doc.company = frappe.defaults.get_default("company");
		}
		super.set_defaults();
	}

	insert() {
		const original_update_doc = this.update_doc.bind(this);
		this.update_doc = () => {
			original_update_doc();
			const { company, expense_account } = this.dialog.doc;
			if (company && expense_account) {
				this.dialog.doc.item_defaults = [
					{
						doctype: "Item Default",
						company,
						expense_account,
						default_warehouse: "",
					},
				];
			}
			delete this.dialog.doc.company;
			delete this.dialog.doc.expense_account;
		};
		return super.insert();
	}

	setup_account_queries() {
		frappe.call({
			method: "redtra_customisation.override.purchase_invoice_expense_account.is_any_account_allowed_on_pi",
			callback: (r) => {
				this.allow_any_account_on_pi = !!r.message;
				this.set_expense_account_query();
			},
		});

		if (this.fields_dict.company) {
			this.fields_dict.company.df.onchange = () => {
				this.set_value("expense_account", "");
				this.set_expense_account_query();
			};
		}
	}

	set_expense_account_query() {
		const expense_account_field = this.fields_dict.expense_account;
		if (!expense_account_field) {
			return;
		}

		expense_account_field.get_query = () => {
			const company = this.get_value("company");
			const filters = {
				company,
				is_group: 0,
				disabled: 0,
			};

			if (!this.allow_any_account_on_pi) {
				filters.root_type = "Expense";
			}

			return { filters };
		};
	}

	set_value(fieldname, value) {
		if (this.fields_dict[fieldname]) {
			this.fields_dict[fieldname].set_value(value);
		}
		this.doc[fieldname] = value;
	}

	get_value(fieldname) {
		return this.fields_dict[fieldname]?.get_value?.() || this.doc[fieldname];
	}

	get_variant_fields() {
		return [
			{
				fieldtype: "Section Break",
				label: __("Item Defaults"),
				collapsible: 0,
			},
			{
				fieldname: "company",
				label: __("Company"),
				fieldtype: "Link",
				options: "Company",
				reqd: 1,
			},
			{
				fieldname: "expense_account",
				label: __("Default Expense Account"),
				fieldtype: "Link",
				options: "Account",
				reqd: 1,
			},
		];
	}
};
