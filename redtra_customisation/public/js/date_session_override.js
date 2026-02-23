/**
 * Date Session Override
 * ---------------------
 * When a Date Session is active, this script automatically:
 *   1. Ticks "Edit Posting Date and Time" ONLY when posting_date is configured
 *   2. Sets all configured date fields to the session date
 * Works on all forms including ones created via mapping (e.g. BOM → Work Order).
 */
(function () {
    frappe.date_session = null;

    // Fetch the active date session on desk load
    frappe.after_ajax(function () {
        frappe.call({
            method:
                "redtra_customisation.redtra_customisation.doctype.date_session.date_session.get_active_date_session",
            async: true,
            callback: function (r) {
                if (r && r.message) {
                    frappe.date_session = r.message;
                } else {
                    frappe.date_session = null;
                }

                // If form already loaded before async session fetch completes,
                // apply immediately on the current form as well.
                if (frappe.date_session && cur_frm) {
                    apply_date_session(cur_frm);
                }
            },
        });
    });

    // Patch Form.prototype.refresh to intercept every form refresh
    var _original_refresh = frappe.ui.form.Form.prototype.refresh;
    frappe.ui.form.Form.prototype.refresh = function () {
        var result = _original_refresh.apply(this, arguments);

        if (frappe.date_session) {
            apply_date_session(this);
        }

        return result;
    };

    function apply_date_session(frm) {
        if (!frm || !frappe.date_session || !frappe.date_session.session_date) return;

        var doctype = frm.doctype;
        var doctypes = frappe.date_session.doctypes || {};

        // Check if this doctype is in the configured list
        if (!doctypes[doctype]) return;

        // Only apply on new (unsaved) documents
        if (!frm.is_new()) return;

        var session_date = frappe.date_session.session_date;
        var date_fields = doctypes[doctype]; // Array of field names

        // Run in multiple passes because mapped docs (e.g. BOM -> Work Order)
        // can populate/overwrite fields asynchronously after initial refresh.
        var passes = [0, 300, 800, 1500, 2500];
        passes.forEach(function (delay) {
            setTimeout(function () {
                if (!frm.is_new()) return;
                if (!frappe.date_session || !frappe.date_session.session_date) return;

                // Tick "Edit Posting Date and Time" ONLY if posting_date is configured
                if (date_fields.indexOf("posting_date") > -1) {
                    if (frm.fields_dict["set_posting_time"]) {
                        frm.set_value("set_posting_time", 1);
                    } else if (frm.fields_dict["edit_posting_date_and_time"]) {
                        frm.set_value("edit_posting_date_and_time", 1);
                    }
                }

                // Intentionally force override for new docs,
                // even when value already exists.
                date_fields.forEach(function (field_name) {
                    if (frm.fields_dict[field_name]) {
                        frm.set_value(field_name, session_date);
                    }
                });
            }, delay);
        });
    }
})();
