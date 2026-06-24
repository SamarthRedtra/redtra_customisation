frappe.pages["item-tree"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Item Tree"),
		single_column: true,
	});

	page.main.addClass("frappe-card");

	if (!$("#item-tree-qty-style").length) {
		$("head").append(`
			<style id="item-tree-qty-style">
				.item-tree-container .tree-link .tree-label {
					display: inline-flex;
					align-items: center;
					gap: 8px;
					width: calc(100% - 24px);
				}
				.item-tree-container .item-tree-qty {
					margin-left: auto;
					font-size: 11px;
					color: var(--text-muted);
					white-space: nowrap;
				}
			</style>
		`);
	}

	page.tree_container = $('<div class="item-tree-container">').appendTo(page.main);

	page.search_timeout = null;

	const saved_warehouse = localStorage.getItem("item_tree_warehouse");

	page.warehouse_field = page.add_field({
		fieldname: "warehouse",
		label: __("Warehouse"),
		fieldtype: "Link",
		options: "Warehouse",
		default: saved_warehouse || undefined,
		get_query() {
			const company = frappe.defaults.get_user_default("Company");
			return company ? { filters: { company, is_group: 0 } } : {};
		},
		change() {
			const value = page.warehouse_field.get_value();
			if (value) {
				localStorage.setItem("item_tree_warehouse", value);
			} else {
				localStorage.removeItem("item_tree_warehouse");
			}
			page.rebuild_tree();
		},
	});

	page.root_item_group_field = page.add_field({
		fieldname: "root_item_group",
		label: __("Root Item Group"),
		fieldtype: "Link",
		options: "Item Group",
		change: () => page.rebuild_tree(),
	});

	page.search_field = page.add_field({
		fieldname: "search",
		label: __("Search"),
		fieldtype: "Data",
		change: () => {
			clearTimeout(page.search_timeout);
			page.search_timeout = setTimeout(() => page.rebuild_tree(), 300);
		},
	});

	page.stock_qty_filter_field = page.add_field({
		fieldname: "stock_qty_filter",
		label: __("Stock Qty"),
		fieldtype: "Select",
		options: "\nAll\nNon-Zero\nZero",
		change: () => page.rebuild_tree(),
	});

	page.brand_field = page.add_field({
		fieldname: "brand",
		label: __("Brand"),
		fieldtype: "Link",
		options: "Brand",
		change: () => page.rebuild_tree(),
	});

	page.is_stock_item_field = page.add_field({
		fieldname: "is_stock_item",
		label: __("Is Stock Item"),
		fieldtype: "Select",
		options: "\nYes\nNo",
		change: () => page.rebuild_tree(),
	});

	page.include_disabled_field = page.add_field({
		fieldname: "include_disabled",
		label: __("Include Disabled"),
		fieldtype: "Check",
		change: () => page.rebuild_tree(),
	});

	page.add_inner_button(__("Expand All"), () => page.expand_all());
	page.add_inner_button(__("Refresh"), () => page.rebuild_tree());

	if (!saved_warehouse) {
		frappe.db.get_single_value("Stock Settings", "default_warehouse").then((default_warehouse) => {
			if (default_warehouse && !page.warehouse_field.get_value()) {
				page.warehouse_field.set_value(default_warehouse);
			}
		});
	}

	page.get_tree_args = function () {
		return {
			doctype: "Item Group",
			include_disabled: page.include_disabled_field.get_value() ? 1 : 0,
			is_stock_item: page.is_stock_item_field.get_value(),
			brand: page.brand_field.get_value(),
			root_item_group: page.root_item_group_field.get_value(),
			search: page.search_field.get_value(),
			warehouse: page.warehouse_field.get_value(),
			stock_qty_filter: page.stock_qty_filter_field.get_value() || "All",
		};
	};

	page.get_tree_root = function () {
		return page.root_item_group_field.get_value() || __("All Item Groups");
	};

	page.can_create_item = frappe.boot.user.can_create.includes("Item");

	page.get_item_group_from_node = function (node) {
		if (node.data.is_item || !node.data.value || node.data.value === "All Item Groups") {
			return null;
		}
		return node.data.value;
	};

	page.new_item_in_group = function (item_group) {
		frappe.ui.form.make_quick_entry(
			"Item",
			() => page.rebuild_tree(),
			(qe) => {
				qe.hide_full_form_button = true;
				if (item_group) {
					qe.set_value("item_group", item_group);
				}
			},
			{ item_group },
			true
		);
	};

	page.rebuild_tree = function () {
		page.tree_container.empty();

		const root_label = page.get_tree_root();
		const root_value = page.root_item_group_field.get_value() || "All Item Groups";

		page.tree = new frappe.ui.Tree({
			parent: page.tree_container,
			label: root_value,
			root_value: root_value,
			expandable: true,
			icon_set: {
				open: frappe.utils.icon("folder-open", "md"),
				closed: frappe.utils.icon("folder-normal", "md"),
				leaf: frappe.utils.icon("tag", "sm"),
			},
			args: page.get_tree_args(),
			method: "redtra_customisation.api.item_tree.get_children",
			get_label(node) {
				if (node.is_root) {
					return __(root_label);
				}
				return node.title || node.label;
			},
			toolbar: {
				new_item: {
					label: __("New Item"),
					condition(node) {
						return page.can_create_item && page.get_item_group_from_node(node);
					},
					click(node) {
						page.new_item_in_group(page.get_item_group_from_node(node));
					},
				},
			},
			on_click: function (node) {
				if (node.data.is_item) {
					frappe.set_route("Form", "Item", node.data.value);
				}
			},
			on_render: function (node) {
				if (!node.data.is_item) {
					return;
				}
				const $label = node.$tree_link.find(".tree-label");
				$label.addClass("text-muted");

				if (node.data.stock_qty === undefined || node.data.stock_qty === null) {
					return;
				}

				const qty = flt(node.data.stock_qty);
				const uom = node.data.stock_uom || "";
				const qty_text = frappe.format(qty, { fieldtype: "Float", precision: 2 });
				const display = uom ? `${qty_text} ${uom}` : qty_text;

				if (!$label.find(".item-tree-qty").length) {
					$label.append(`<span class="item-tree-qty">${display}</span>`);
				}
			},
		});
	};

	page.expand_all = async function () {
		if (!page.tree) {
			return;
		}

		const expand = async (node) => {
			if (!node.expandable) {
				return;
			}

			if (!node.loaded) {
				await page.tree.load_children(node, false);
			} else if (node.$ul) {
				node.$ul.show();
				node.expanded = true;
				node.parent && node.parent.toggleClass("opened", true);
				if (page.tree.icon_set) {
					node.$tree_link
						.find(".node-parent")
						.html(page.tree.icon_set.open);
				}
			}

			const child_nodes = Object.values(page.tree.nodes).filter(
				(n) => n.parent_label === node.label && n.expandable
			);

			for (const child of child_nodes) {
				await expand(child);
			}
		};

		frappe.dom.freeze(__("Expanding..."));
		try {
			await expand(page.tree.root_node);
		} finally {
			frappe.dom.unfreeze();
		}
	};

	page.rebuild_tree();
};
