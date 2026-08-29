// Copyright (c) 2026, redtra_customisation contributors

frappe.ui.form.on("Purchase Order", {
	onload(frm) {
		lock_purchase_order_naming_series(frm);
		apply_non_stock_user_defaults(frm);
		setup_purchase_type(frm);
		setup_provisional_po_form(frm);
	},
	onload_post_render(frm) {
		setup_purchase_type(frm);
	},
	refresh(frm) {
		lock_purchase_order_naming_series(frm);
		apply_non_stock_user_defaults(frm);
		setup_purchase_type(frm);
		setup_provisional_po_form(frm);
		setup_provisional_purchase_receipt_button(frm);
		setup_restricted_update_items(frm);
	},
});

function lock_purchase_order_naming_series(frm) {
	const namingSeries = "PUR-ORD-.YYYY.-";
	if (!frm.fields_dict.naming_series) {
		return;
	}

	frm.set_df_property("naming_series", "options", namingSeries);
	frm.set_df_property("naming_series", "read_only", 1);
	if (frm.is_new() && frm.doc.naming_series !== namingSeries) {
		frm.set_value("naming_series", namingSeries);
	}
}

function apply_non_stock_user_defaults(frm) {
	frappe.call({
		method: "redtra_customisation.override.purchase_order_permissions.is_current_user_restricted",
		callback(r) {
			if (!r.message) return;

			if (frm.is_new() && !frm.doc.is_nonstock) {
				frm.set_value("is_nonstock", 1);
			}

			frm.set_df_property("is_nonstock", "read_only", 1);
		},
	});
}

function setup_purchase_type(frm) {
	if (!frm.fields_dict.custom_purchase_type) {
		return;
	}

	frappe.call({
		method:
			"redtra_customisation.override.purchase_order_permissions.get_current_user_purchase_type_configuration",
		callback(r) {
			const configuration = r.message || {};
			const allowedTypes = configuration.allowed_types?.length
				? configuration.allowed_types
				: ["Domestic", "International", "Admin"];

			frm.set_df_property("custom_purchase_type", "options", allowedTypes.join("\n"));
			frm.set_df_property("custom_purchase_type", "reqd", 1);
			frm.set_df_property("custom_purchase_type", "read_only", allowedTypes.length === 1);

			if (frm.is_new() && !frm.doc.custom_purchase_type && configuration.default_type) {
				frm.set_value("custom_purchase_type", configuration.default_type);
			}
		},
	});
}

function setup_provisional_po_form(frm) {
	if (frm.fields_dict.custom_is_provisional_po) {
		frm.toggle_display("custom_is_provisional_po", true);
	}

	frappe.call({
		method: "redtra_customisation.override.provisional_purchase_order.get_provisional_po_settings",
		callback(r) {
			const settings = r.message || {};
			const enabled = cint(settings.enabled);

			if (frm.fields_dict.custom_is_provisional_po) {
				frm.toggle_display("custom_is_provisional_po", enabled);
			}

			const $note = $(frm.layout.wrapper.find(".provisional-po-note"));
			if ($note.length) {
				$note.closest(".form-message").remove();
			}

			if (enabled && cint(frm.doc.custom_is_provisional_po) && !frm.is_new()) {
				frm.layout.show_message(
					`<div class="provisional-po-note">${__(
						"This is a Provisional / Open PO. You can create multiple Purchase Receipts against it until fully billed."
					)}</div>`,
					"yellow",
					true
				);
			}
		},
	});
}

function setup_provisional_purchase_receipt_button(frm) {
	if (frm.doc.docstatus !== 1 || !cint(frm.doc.custom_is_provisional_po)) {
		return;
	}
	if (["Closed", "Delivered"].includes(frm.doc.status)) {
		return;
	}
	if (flt(frm.doc.per_billed) >= 100) {
		return;
	}

	frappe.call({
		method: "redtra_customisation.override.provisional_purchase_order.get_provisional_po_settings",
		callback(r) {
			if (!cint(r.message?.enabled)) {
				return;
			}

			setTimeout(() => {
				frm.remove_custom_button(__("Purchase Receipt"), __("Create"));
				frm.add_custom_button(
					__("Purchase Receipt"),
					() => {
						if (frm.doc.__unsaved) {
							frappe.throw(
								__("You have unsaved changes in this form. Please save before you continue.")
							);
						}

						frappe.model.open_mapped_doc({
							method:
								"redtra_customisation.override.provisional_purchase_order.make_provisional_purchase_receipt",
							source_name: frm.doc.name,
							freeze_message: __("Creating Purchase Receipt ..."),
						});
					},
					__("Create")
				);
			}, 600);
		},
	});
}

function setup_restricted_update_items(frm) {
	if (frm.doc.docstatus !== 1) {
		return;
	}
	if (["Closed", "Delivered"].includes(frm.doc.status)) {
		return;
	}
	if (flt(frm.doc.per_billed) >= 100) {
		return;
	}
	if (frm.doc.__onload && frm.doc.__onload.can_update_items === false) {
		return;
	}

	setTimeout(() => {
		frappe.call({
			method: "redtra_customisation.override.purchase_order.po_has_submitted_receipt",
			args: { purchase_order: frm.doc.name },
			callback(r) {
				if (!r.message) {
					return;
				}

				frm.remove_custom_button(__("Update Items"));
				frm.add_custom_button(__("Update Items"), () => {
					redtra_customisation.utils.update_po_items_restricted(frm);
				});
			},
		});
	}, 500);
}
