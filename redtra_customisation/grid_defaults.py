"""Shared user-grid default persistence."""

import json

import frappe


def apply_grid_default_to_users(parent_doctype, child_doctype, columns):
	"""Set one child-grid layout for every active Desk user."""
	users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
	for user in users:
		if user == "Guest":
			continue
		settings = _get_user_settings(user, parent_doctype)
		settings.setdefault("GridView", {})[child_doctype] = [dict(column) for column in columns]
		_save_user_settings(user, parent_doctype, settings)


def _get_user_settings(user, doctype):
	result = frappe.db.sql(
		"select data from `__UserSettings` where user=%s and doctype=%s",
		(user, doctype),
	)
	if not result or not result[0][0]:
		return {}

	settings = json.loads(result[0][0])
	return settings if isinstance(settings, dict) else {}


def _save_user_settings(user, doctype, settings):
	data = json.dumps(settings)
	frappe.db.multisql(
		{
			"mariadb": """
				INSERT INTO `__UserSettings` (`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON DUPLICATE KEY UPDATE `data`=%s
			""",
			"*": """
				INSERT INTO `__UserSettings` (`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON CONFLICT (`user`, `doctype`) DO UPDATE SET `data`=%s
			""",
		},
		(user, doctype, data, data),
	)
	frappe.cache.hset("_user_settings", f"{doctype}::{user}", None)
