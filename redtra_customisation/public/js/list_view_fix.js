frappe.provide("frappe.views");

// Patch ListView.get_left_html to fix undefined col.df.fieldname error
// This fixes the error: Cannot read properties of undefined (reading 'fieldname')
frappe.views.ListView.prototype.get_left_html = function(doc) {
	let left_html = "";
	let has_value_in_second_column = true;
	for (let i = 0; i < this.columns.length; i++) {
		let col = this.columns[i];

		// Fix: Add null check for col.df before accessing fieldname
		if (i == 4 && col.df && !doc[col.df.fieldname] && doc[col.df.fieldname] != 0) {
			has_value_in_second_column = false;
		}

		if (frappe.is_mobile() && col.type == "Field" && [3, 4].includes(i)) {
			left_html += `<div class="mobile-layout ${
				i == 3 ? "mobile-layout-seperator" : ""
			}">${this.get_column_html(col, doc, true)}</div>`;
		} else {
			left_html += this.get_column_html(col, doc, false);
		}
	}

	if (!has_value_in_second_column) {
		const container = document.createElement("div");
		container.innerHTML = left_html;
		const firstMobileLayout = container.querySelector(".mobile-layout");

		if (firstMobileLayout) {
			firstMobileLayout.classList.add("no-seperator");
		}
		left_html = container.innerHTML;
	}

	left_html += this.generate_button_html(doc);
	left_html += this.generate_dropdown_html(doc);

	return left_html;
};
