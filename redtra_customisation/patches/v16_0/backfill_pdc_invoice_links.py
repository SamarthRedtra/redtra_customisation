import frappe


def execute():
	"""Backfill Post Dated Cheques.invoice_links from existing invoice reference rows."""
	if not frappe.db.has_column("Post Dated Cheques", "invoice_links"):
		return

	rows = frappe.db.sql(
		"""
		SELECT
			pdc.name,
			GROUP_CONCAT(DISTINCT ref.reference_name ORDER BY ref.idx SEPARATOR ', ') AS invoice_links
		FROM `tabPost Dated Cheques` pdc
		LEFT JOIN `tabPDC Invoice Reference` ref
			ON ref.parent = pdc.name
			AND ref.parenttype = 'Post Dated Cheques'
			AND ref.parentfield = 'invoice_references'
			AND IFNULL(ref.reference_name, '') != ''
		GROUP BY pdc.name
		""",
		as_dict=True,
	)

	for row in rows:
		frappe.db.set_value(
			"Post Dated Cheques",
			row.name,
			{
				"invoice_links": row.invoice_links or "",
				"invoice_links_list": _get_invoice_links_list(row.invoice_links),
			},
			update_modified=False,
		)


def _get_invoice_links_list(invoice_links):
	references = [name.strip() for name in (invoice_links or "").split(",") if name.strip()]
	summary = references[:3]
	if len(references) > 3:
		summary.append(f"+{len(references) - 3} more")
	return ", ".join(summary)
