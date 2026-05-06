frappe.ui.form.on('Payment Entry', {
	refresh: function(frm) {
		// Show/hide PDC actions based on cheque status
		if (frm.doc.mode_of_payment && frm.doc.mode_of_payment.toLowerCase().includes('cheque')) {
			if ( frm.doc.custom_is_pdc_entry == 1) {
				return;
			}
			setup_pdc_actions(frm);
		}
	},
	
	mode_of_payment: function(frm) {
		// Auto-set posting date removed as per user request
	},
	
	pdc_cheque_date: function(frm) {
		// Auto-set posting date removed as per user request
	}
});

function setup_pdc_actions(frm) {
	// Remove existing PDC buttons
	frm.page.clear_custom_actions();
	
	// Add PDC workflow buttons based on status
	if (frm.doc.docstatus === 1) { // Only for submitted entries
		const status = frm.doc.pdc_cheque_status;
		
		if (status === 'Issued') {
			frm.add_custom_button(__('Mark Under Collection'), function() {
				mark_under_collection(frm);
			}, __('PDC Actions'));
		}
		
		if (status === 'Under Collection') {
			frm.add_custom_button(__('Mark Collected'), function() {
				mark_collected(frm);
			}, __('PDC Actions'));
			
			frm.add_custom_button(__('Mark Bounced'), function() {
				mark_bounced(frm);
			}, __('PDC Actions'));
		}
		
		if (status === 'Collected' || status === 'Paid') {
			frm.add_custom_button(__('Mark Bounced'), function() {
				mark_bounced(frm);
			}, __('PDC Actions'));
		}
	}
}

function mark_under_collection(frm) {
	frappe.confirm(
		__('Are you sure you want to mark this cheque as Under Collection? This will create a Journal Entry.'),
		function() {
			frappe.call({
				method: 'redtra_customisation.pdc.payment_entry_override.mark_pdc_under_collection',
				args: {
					name: frm.doc.name
				},
				callback: function(r) {
					if (!r.exc) {
						frm.reload_doc();
						frappe.show_alert({
							message: __('Cheque marked as Under Collection'),
							indicator: 'green'
						});
					}
				}
			});
		}
	);
}

function mark_collected(frm) {
	frappe.confirm(
		__('Are you sure you want to mark this cheque as Collected? This will create a Journal Entry.'),
		function() {
			frappe.call({
				method: 'redtra_customisation.pdc.payment_entry_override.mark_pdc_collected',
				args: {
					name: frm.doc.name
				},
				callback: function(r) {
					if (!r.exc) {
						frm.reload_doc();
						frappe.show_alert({
							message: __('Cheque marked as Collected'),
							indicator: 'green'
						});
					}
				}
			});
		}
	);
}

function mark_bounced(frm) {
	frappe.confirm(
		__('Are you sure you want to mark this cheque as Bounced? This will reverse the collection entries.'),
		function() {
			frappe.call({
				method: 'redtra_customisation.pdc.payment_entry_override.mark_pdc_bounced',
				args: {
					name: frm.doc.name
				},
				callback: function(r) {
					if (!r.exc) {
						frm.reload_doc();
						frappe.show_alert({
							message: __('Cheque marked as Bounced'),
							indicator: 'orange'
						});
					}
				}
			});
		}
	);
}
