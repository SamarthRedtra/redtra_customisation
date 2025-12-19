frappe.ui.form.on('Payment Entry', {
	refresh: function(frm) {
		// Show/hide PDC actions based on cheque status
		if (frm.doc.mode_of_payment && frm.doc.mode_of_payment.toLowerCase().includes('cheque')) {
			setup_pdc_actions(frm);
			setup_pdc_queries(frm);
		}
	},
	
	mode_of_payment: function(frm) {
		// Auto-set posting date to cheque date for PDC
		if (frm.doc.mode_of_payment && frm.doc.mode_of_payment.toLowerCase().includes('cheque')) {
			if (frm.doc.pdc_cheque_date && frm.doc.pdc_cheque_date > frm.doc.posting_date) {
				frm.set_value('posting_date', frm.doc.pdc_cheque_date);
			}
		}
	},
	
	pdc_cheque_date: function(frm) {
		// Auto-set posting date to cheque date for PDC
		if (frm.doc.mode_of_payment && frm.doc.mode_of_payment.toLowerCase().includes('cheque')) {
			if (frm.doc.pdc_cheque_date && frm.doc.pdc_cheque_date > frm.doc.posting_date) {
				frm.set_value('posting_date', frm.doc.pdc_cheque_date);
			}
		}
	},
	
	pdc_cheque_status: function(frm) {
		// Allow status change after submission
		if (frm.doc.docstatus === 1 && frm.doc.mode_of_payment && 
			frm.doc.mode_of_payment.toLowerCase().includes('cheque')) {
			// Field is now editable, validation happens on server side
			// Just save when status changes
			if (frm.is_dirty()) {
				frm.save().then(() => {
					frappe.show_alert({
						message: __('Cheque status updated to {0}', [frm.doc.pdc_cheque_status]),
						indicator: 'green'
					});
				});
			}
		}
	},
	
	pdc_bank_account: function(frm) {
		// Validate that selected account is not a group account
		if (frm.doc.pdc_bank_account) {
			frappe.db.get_value('Account', frm.doc.pdc_bank_account, 'is_group', (r) => {
				if (r && r.is_group) {
					frappe.msgprint({
						title: __('Invalid Account'),
						message: __('Bank Account "{0}" is a Group Account. Please select a ledger account instead.', [frm.doc.pdc_bank_account]),
						indicator: 'red'
					});
					frm.set_value('pdc_bank_account', '');
				}
			});
		}
	}
});

function setup_pdc_queries(frm) {
	// Set query filter for bank account to exclude group accounts
	frm.set_query('pdc_bank_account', function() {
		return {
			filters: {
				is_group: 0,
				company: frm.doc.company || '',
				account_type: ['in', ['Bank', 'Cash']]
			}
		};
	});
}

function setup_pdc_actions(frm) {
	// Remove existing PDC buttons
	frm.page.clear_custom_actions();
	
	// Make status field editable after submission
	if (frm.doc.docstatus === 1 && frm.doc.mode_of_payment && 
		frm.doc.mode_of_payment.toLowerCase().includes('cheque')) {
		// Remove read-only restriction
		if (frm.fields_dict.pdc_cheque_status) {
			frm.set_df_property('pdc_cheque_status', 'read_only', 0);
		}
	}
	
	// Add PDC workflow buttons based on status (optional - users can also edit field directly)
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
