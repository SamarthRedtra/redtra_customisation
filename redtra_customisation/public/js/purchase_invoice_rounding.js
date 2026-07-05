// Copyright (c) 2026, redtra_customisation contributors

function has_manual_rounding(doc) {
	if (flt(doc.rounding_adjustment)) {
		return true;
	}

	const grand_total = flt(doc.grand_total);
	const rounded_total = flt(doc.rounded_total);
	return rounded_total && Math.abs(rounded_total - grand_total) > 0.0001;
}

function apply_manual_rounding(frm) {
	const doc = frm.doc;
	const conversion_rate = flt(doc.conversion_rate) || 1.0;
	const rounding = flt(doc.rounding_adjustment);
	const rounded = flt(doc.rounded_total);

	if (rounding) {
		doc.rounding_adjustment = rounding;
		doc.rounded_total = flt(doc.grand_total) + rounding;
	} else if (rounded) {
		doc.rounded_total = rounded;
		doc.rounding_adjustment = flt(rounded - flt(doc.grand_total));
	}

	doc.base_rounding_adjustment = flt(
		doc.rounding_adjustment * conversion_rate,
		precision("base_rounding_adjustment", doc)
	);
	doc.base_rounded_total = flt(doc.base_grand_total) + flt(doc.base_rounding_adjustment);

	if (doc.docstatus === 0) {
		doc.outstanding_amount = flt(doc.rounded_total) - flt(doc.paid_amount);
	}
}

function refresh_rounding_fields(frm) {
	frm.refresh_fields([
		"rounding_adjustment",
		"rounded_total",
		"base_rounding_adjustment",
		"base_rounded_total",
		"outstanding_amount",
	]);
}

function ensure_rounding_enabled(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}

	frm.set_df_property("rounding_adjustment", "read_only", 0);
	frm.set_df_property("rounded_total", "read_only", 0);

	const has_rounding = has_manual_rounding(frm.doc);

	if (has_rounding && frm.doc.disable_rounded_total) {
		frm.doc.disable_rounded_total = 0;
		frm.refresh_field("disable_rounded_total");
	}
}

function patch_pi_rounding_on_controller(frm) {
	const controller = frm.cscript;
	if (!controller || controller.__pi_manual_rounding_patched) {
		return;
	}

	controller.__pi_manual_rounding_patched = true;
	const original_set_rounded_total = controller.set_rounded_total.bind(controller);

	controller.set_rounded_total = function () {
		if (frm._manual_pi_rounding && has_manual_rounding(frm.doc)) {
			apply_manual_rounding(frm);
			return;
		}
		original_set_rounded_total();
	};
}

frappe.ui.form.on("Purchase Invoice", {
	onload(frm) {
		frm._manual_pi_rounding = has_manual_rounding(frm.doc);
		patch_pi_rounding_on_controller(frm);
		ensure_rounding_enabled(frm);
	},

	refresh(frm) {
		ensure_rounding_enabled(frm);
	},

	rounding_adjustment(frm) {
		frm._manual_pi_rounding = has_manual_rounding(frm.doc);
		ensure_rounding_enabled(frm);
		apply_manual_rounding(frm);
		refresh_rounding_fields(frm);
	},

	rounded_total(frm) {
		frm._manual_pi_rounding = has_manual_rounding(frm.doc);
		ensure_rounding_enabled(frm);
		apply_manual_rounding(frm);
		refresh_rounding_fields(frm);
	},

	disable_rounded_total(frm) {
		if (!frm.doc.disable_rounded_total) {
			return;
		}
		if (has_manual_rounding(frm.doc)) {
			frappe.msgprint(
				__(
					"Disable Rounded Total is turned on, so rounding adjustment will not post. Clear rounding values or uncheck Disable Rounded Total."
				)
			);
		}
	},
});
