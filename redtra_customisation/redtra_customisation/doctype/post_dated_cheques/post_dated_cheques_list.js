// Copyright (c) 2026, samarth.upare@redtra.com and contributors
// List indicator uses custom `status` (Pending / Converted / Cancelled) instead of Draft / Submitted.

frappe.listview_settings["Post Dated Cheques"] = {
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	get_indicator(doc) {
		const s = doc.status;
		if (!s) {
			return [__("—"), "gray", "name,!=,"];
		}
		const color = { Pending: "orange", Converted: "green", Cancelled: "grey" }[s] || "gray";
		return [__(s), color, "status,=," + s];
	},
};
