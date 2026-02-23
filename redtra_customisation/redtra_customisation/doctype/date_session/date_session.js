// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Date Session", {
    refresh(frm) {
        if (frm.doc.is_active && frm.doc.session_date) {
            frm.dashboard.set_headline(
                __("Active Session Date: {0}", [
                    frappe.datetime.str_to_user(frm.doc.session_date),
                ])
            );
        }
    },
});

frappe.ui.form.on("Date Session Doctype", {
    document_type: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (!row.document_type) {
            frappe.model.set_value(cdt, cdn, "date_field", "");
            return;
        }
        show_field_picker(frm, cdt, cdn, row.document_type);
    },

    date_field: function (frm, cdt, cdn) {
        // Allow re-picking fields by clicking on the date_field cell
        var row = locals[cdt][cdn];
        if (row.document_type) {
            show_field_picker(frm, cdt, cdn, row.document_type);
        }
    },
});

function show_field_picker(frm, cdt, cdn, doctype) {
    frappe.call({
        method: "redtra_customisation.redtra_customisation.doctype.date_session.date_session.get_date_fields",
        args: { doctype: doctype },
        callback: function (r) {
            if (!r || !r.message || !r.message.length) {
                frappe.msgprint(
                    __("No Date/Datetime fields found in {0}", [doctype])
                );
                return;
            }

            var fields = r.message;
            var row = locals[cdt][cdn];

            // Parse existing selected fields
            var existing = (row.date_field || "")
                .split(",")
                .map(function (f) { return f.trim(); })
                .filter(function (f) { return f; });

            // Build checkboxes for each date field
            var dialog_fields = fields.map(function (f) {
                return {
                    fieldname: f.fieldname,
                    fieldtype: "Check",
                    label: f.label + "  (" + f.fieldname + ")  [" + f.fieldtype + "]",
                    default: existing.indexOf(f.fieldname) > -1 ? 1 : 0,
                };
            });

            var d = new frappe.ui.Dialog({
                title: __("Select Date Fields for {0}", [doctype]),
                fields: dialog_fields,
                primary_action_label: __("Set Fields"),
                primary_action: function (values) {
                    var selected = [];
                    fields.forEach(function (f) {
                        if (values[f.fieldname]) {
                            selected.push(f.fieldname);
                        }
                    });

                    if (!selected.length) {
                        frappe.msgprint(__("Please select at least one field."));
                        return;
                    }

                    frappe.model.set_value(cdt, cdn, "date_field", selected.join(", "));
                    d.hide();
                    frm.dirty();
                },
            });

            d.show();
        },
    });
}
