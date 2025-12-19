"""
PDC Reminder Notifications
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate, today


def send_pdc_reminders():
	"""
	Scheduled task to send reminders for PDC cheques
	"""
	try:
		pdc_settings = frappe.get_single("PDC Settings")
		
		if not pdc_settings.send_reminders:
			return
		
		reminder_days_before = pdc_settings.reminder_days_before or 3
		reminder_days_after = pdc_settings.reminder_days_after or 5
		
		# Get cheques approaching due date
		approaching_date = add_days(today(), reminder_days_before)
		pending_deposit = get_pending_deposit_cheques(approaching_date)
		
		for cheque in pending_deposit:
			send_reminder(cheque, "deposit")
		
		# Get cheques overdue for clearance
		overdue_date = add_days(today(), -reminder_days_after)
		pending_clearance = get_pending_clearance_cheques(overdue_date)
		
		for cheque in pending_clearance:
			send_reminder(cheque, "clearance")
			
	except Exception as e:
		frappe.log_error(f"Error in PDC Reminders: {str(e)}", "PDC Reminders Error")


def get_pending_deposit_cheques(approaching_date):
	"""Get cheques that are approaching their cheque date"""
	return frappe.db.sql("""
		SELECT name, party, party_name, pdc_cheque_number, pdc_cheque_date, received_amount, paid_amount
		FROM `tabPayment Entry`
		WHERE docstatus = 1
			AND pdc_cheque_status = 'Issued'
			AND pdc_cheque_date <= %s
			AND pdc_cheque_date >= %s
			AND pdc_cheque_number IS NOT NULL
			AND pdc_cheque_number != ''
	""", (approaching_date, today()), as_dict=True)


def get_pending_clearance_cheques(overdue_date):
	"""Get cheques that are overdue for clearance"""
	return frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"pdc_cheque_status": "Under Collection",
			"posting_date": ["<=", overdue_date],
			"pdc_cheque_number": ["!=", ""]
		},
		fields=["name", "party", "party_name", "pdc_cheque_number", "pdc_cheque_date", "received_amount", "paid_amount", "payment_type", "posting_date"]
	)


def send_reminder(cheque, reminder_type):
	"""Send reminder notification for a cheque"""
	try:
		pe_doc = frappe.get_doc("Payment Entry", cheque.name)
		
		if reminder_type == "deposit":
			subject = _("PDC Cheque Approaching Due Date")
			message = _(
				"Cheque {0} (Amount: {1}) from {2} is due on {3}. "
				"Please arrange for deposit."
			).format(
				cheque.pdc_cheque_number,
				pe_doc.received_amount if pe_doc.payment_type == "Receive" else pe_doc.paid_amount,
				cheque.party_name or cheque.party,
				cheque.pdc_cheque_date
			)
		else:
			subject = _("PDC Cheque Overdue for Clearance")
			message = _(
				"Cheque {0} (Amount: {1}) from {2} deposited on {3} is overdue for clearance. "
				"Please verify clearance status."
			).format(
				cheque.pdc_cheque_number,
				pe_doc.received_amount if pe_doc.payment_type == "Receive" else pe_doc.paid_amount,
				cheque.party_name or cheque.party,
				pe_doc.posting_date
			)
		
		# Create notification for Accounts Manager role
		frappe.publish_realtime(
			event="notification",
			message={
				"type": "alert",
				"title": subject,
				"message": message,
				"indicator": "orange"
			},
			user=frappe.session.user
		)
		
		# Optionally send email
		# frappe.sendmail(
		# 	recipients=[frappe.session.user],
		# 	subject=subject,
		# 	message=message
		# )
		
	except Exception as e:
		frappe.log_error(f"Error sending PDC reminder: {str(e)}", "PDC Reminder Error")
