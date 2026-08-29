"""Restrict future Purchase Orders to the approved naming series."""

from redtra_customisation.purchase_order_naming import ensure_purchase_order_naming_series


def execute():
	ensure_purchase_order_naming_series()
