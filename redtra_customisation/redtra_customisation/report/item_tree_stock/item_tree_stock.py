# Copyright (c) 2026, Redtra Customisation and contributors

import frappe

from redtra_customisation.api.item_tree import build_item_tree_grid_result


def execute(filters=None):
	result = build_item_tree_grid_result(filters)
	return result["columns"], result["data"]
