const getCommissionPrecision = (fieldname) =>
	fieldname === "commission_rate" ? 3 : 2;

const normalizeCommissionValue = (fieldname, value) =>
	flt(value, getCommissionPrecision(fieldname));

const commissionValueChanged = (fieldname, currentValue, nextValue) =>
	normalizeCommissionValue(fieldname, currentValue) !==
	normalizeCommissionValue(fieldname, nextValue);

const setIfChanged = (frm, fieldname, value) => {
	const normalizedValue = normalizeCommissionValue(fieldname, value);
	if (commissionValueChanged(fieldname, frm.doc[fieldname], normalizedValue)) {
		frm.set_value(fieldname, normalizedValue);
	}
};

const setChildIfChanged = (row, fieldname, value) => {
	const normalizedValue = normalizeCommissionValue(fieldname, value);
	if (commissionValueChanged(fieldname, row[fieldname], normalizedValue)) {
		frappe.model.set_value(row.doctype, row.name, fieldname, normalizedValue);
	}
};

const update_sales_order_commission_preview = (frm) => {
	if (!frm.doc.sales_team || !frm.doc.sales_team.length) {
		return;
	}

	frappe.call({
		method: "redtra_customisation.commission.get_sales_order_commission_preview",
		args: {
			doc: frm.doc,
		},
		callback: (response) => {
			const message = response.message || {};
			const rows = message.rows || [];
			const row_by_name = new Map(
				rows.filter((row) => row.name).map((row) => [row.name, row])
			);

			(frm.doc.sales_team || []).forEach((row) => {
				const updated_row =
					row_by_name.get(row.name) ||
					rows.find(
						(candidate) =>
							!candidate.name && candidate.sales_person === row.sales_person
					);

				if (!updated_row) {
					return;
				}

				setChildIfChanged(
					row,
					"commission_rate",
					updated_row.commission_rate || 0
				);
				setChildIfChanged(row, "incentives", updated_row.incentives || 0);
			});

			frm.refresh_field("sales_team");

			// Apply header values after child row updates so partner commission
			// remains based on team incentives during realtime preview.
			setIfChanged(
				frm,
				"amount_eligible_for_commission",
				message.amount_eligible_for_commission || 0
			);
			setIfChanged(frm, "commission_rate", message.commission_rate || 0);
			setIfChanged(frm, "total_commission", message.total_commission || 0);
			if ("custom_sales_partner_commission_percentage" in frm.doc) {
				setIfChanged(
					frm,
					"custom_sales_partner_commission_percentage",
					message.sales_partner_commission_percentage || 0
				);
			}
			if ("custom_sales_partner_commission_amount" in frm.doc) {
				setIfChanged(
					frm,
					"custom_sales_partner_commission_amount",
					message.sales_partner_commission_amount || 0
				);
			}
		},
	});
};

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		update_sales_order_commission_preview(frm);
	},
	project(frm) {
		update_sales_order_commission_preview(frm);
	},
	sales_partner(frm) {
		update_sales_order_commission_preview(frm);
	},
	sales_team_add(frm) {
		update_sales_order_commission_preview(frm);
	},
});

frappe.ui.form.on("Sales Team", {
	sales_person(frm) {
		update_sales_order_commission_preview(frm);
	},
	allocated_amount(frm) {
		update_sales_order_commission_preview(frm);
	},
	allocated_percentage(frm) {
		update_sales_order_commission_preview(frm);
	},
});

frappe.ui.form.on("Sales Order Item", {
	qty(frm) {
		update_sales_order_commission_preview(frm);
	},
	rate(frm) {
		update_sales_order_commission_preview(frm);
	},
	amount(frm) {
		update_sales_order_commission_preview(frm);
	},
	net_amount(frm) {
		update_sales_order_commission_preview(frm);
	},
	base_net_amount(frm) {
		update_sales_order_commission_preview(frm);
	},
});
