frappe.ui.form.on('Customer', {
	refresh: function(frm) {
		// Add PDC section to dashboard
		if (frm.dashboard.add_section && !frm.custom_pdc_dashboard_added) {
			add_pdc_dashboard_section(frm, "Customer");
			frm.custom_pdc_dashboard_added = true;
		}
	}
});

function add_pdc_dashboard_section(frm, party_type) {
	frappe.call({
		method: 'redtra_customisation.pdc.dashboard.get_party_pdc_dashboard',
		args: {
			party_type: party_type,
			party: frm.doc.name
		},
		callback: function(r) {
			if (r.message && r.message.total_count > 0) {
				const summary = r.message;
				const status_breakdown = summary.status_breakdown || {};
				
				let html = `<div class="pdc-dashboard-section">
					<div class="row">
						<div class="col-md-6">
							<h6>Total PDC ${summary.type === 'received' ? 'Received' : 'Issued'}: ${summary.total_count}</h6>
							<h5>${format_currency(summary.total_amount, frm.doc.default_currency || 'USD')}</h5>
						</div>
						<div class="col-md-6">
							<h6>Status Breakdown:</h6>
							<ul>`;
				
				for (const [status, data] of Object.entries(status_breakdown)) {
					html += `<li>${status}: ${data.count} cheques - ${format_currency(data.amount, frm.doc.default_currency || 'USD')}</li>`;
				}
				
				html += `</ul></div></div>
					<div class="row mt-2">
						<div class="col-md-12">
							<button class="btn btn-sm btn-primary" onclick="frappe.set_route('query-report', 'PDC Register', {party_type: '${party_type}', party: '${frm.doc.name}'})">
								View PDC Register
							</button>
						</div>
					</div>
				</div>`;
				
				frm.dashboard.add_section(html, "Post-Dated Cheques", true);
			}
		}
	});
}
