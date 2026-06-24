frappe.pages["item-tree"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Item Tree"),
		single_column: true,
	});

	page.main.addClass("frappe-card");

	if (!$("#item-tree-style").length) {
		$("head").append(`
			<style id="item-tree-style">
				.item-tree-container .tree-link .tree-label {
					display: inline-flex;
					align-items: center;
					gap: 8px;
					width: calc(100% - 24px);
					flex-wrap: wrap;
				}
				.item-tree-container .item-tree-qty {
					margin-left: auto;
					font-size: 11px;
					color: var(--text-muted);
					white-space: nowrap;
				}
				.item-tree-container .item-tree-wh-grid {
					display: flex;
					flex-wrap: wrap;
					gap: 6px;
					margin-left: auto;
					justify-content: flex-end;
				}
				.item-tree-container .item-tree-wh-badge {
					font-size: 10px;
					padding: 1px 6px;
					border-radius: 10px;
					background: var(--control-bg);
					color: var(--text-muted);
					white-space: nowrap;
				}
				.item-tree-grid-container {
					margin-top: 12px;
					overflow: auto;
					width: 100%;
				}
				.item-tree-grid-container .dt-scrollable {
					max-height: calc(100vh - 280px);
					overflow: auto;
				}
				.item-tree-grid-container .datatable {
					margin-left: 0;
					margin-right: 0;
				}
			</style>
		`);
	}

	page.tree_container = $('<div class="item-tree-container">').appendTo(page.main);
	page.grid_container = $('<div class="item-tree-grid-container hide">').appendTo(page.main);

	page.search_timeout = null;
	page.view_mode = localStorage.getItem("item_tree_view_mode") || "Tree";
	page.grid_data = null;

	const saved_warehouse = localStorage.getItem("item_tree_warehouse");

	page.company_field = page.add_field({
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		default: frappe.defaults.get_user_default("Company"),
		reqd: 1,
		change() {
			page.warehouse_field.set_value("");
			page.refresh_view();
		},
	});

	page.view_mode_field = page.add_field({
		fieldname: "view_mode",
		label: __("View"),
		fieldtype: "Select",
		options: "Tree\nGrid",
		default: page.view_mode,
		change() {
			page.view_mode = page.view_mode_field.get_value() || "Tree";
			localStorage.setItem("item_tree_view_mode", page.view_mode);
			page.refresh_view();
		},
	});

	page.warehouse_field = page.add_field({
		fieldname: "warehouse",
		label: __("Stock Filter Warehouse"),
		fieldtype: "Link",
		options: "Warehouse",
		default: saved_warehouse || undefined,
		description: __("Optional. Used for Zero/Non-Zero filter. Does not limit warehouse columns when Warehouse Wise Columns is checked."),
		get_query() {
			const company = page.company_field.get_value();
			return company ? { filters: { company, is_group: 0 } } : {};
		},
		change() {
			const value = page.warehouse_field.get_value();
			if (value) {
				localStorage.setItem("item_tree_warehouse", value);
			} else {
				localStorage.removeItem("item_tree_warehouse");
			}
			page.refresh_view();
		},
	});

	page.warehouse_wise_columns_field = page.add_field({
		fieldname: "warehouse_wise_columns",
		label: __("Warehouse Wise Columns"),
		fieldtype: "Check",
		default: 1,
		change: () => page.refresh_view(),
	});

	page.warehouses_field = page.add_field({
		fieldname: "warehouses",
		label: __("Warehouse Columns"),
		fieldtype: "MultiSelectList",
		options: "Warehouse",
		description: __("Leave empty to show all company warehouses as columns."),
		get_data(txt) {
			const company = page.company_field.get_value();
			if (!company) {
				return [];
			}
			return frappe.db.get_link_options("Warehouse", txt, {
				company,
				is_group: 0,
				disabled: 0,
			});
		},
		change: () => page.refresh_view(),
	});

	page.root_item_group_field = page.add_field({
		fieldname: "root_item_group",
		label: __("Root Item Group"),
		fieldtype: "Link",
		options: "Item Group",
		change: () => page.refresh_view(),
	});

	page.search_field = page.add_field({
		fieldname: "search",
		label: __("Search"),
		fieldtype: "Data",
		change: () => {
			clearTimeout(page.search_timeout);
			page.search_timeout = setTimeout(() => page.refresh_view(), 300);
		},
	});

	page.stock_qty_filter_field = page.add_field({
		fieldname: "stock_qty_filter",
		label: __("Stock Qty"),
		fieldtype: "Select",
		options: "\nAll\nNon-Zero\nZero",
		description: __("Non-Zero = items with stock. Zero = stock items with no balance."),
		change: () => page.refresh_view(),
	});

	page.brand_field = page.add_field({
		fieldname: "brand",
		label: __("Brand"),
		fieldtype: "Link",
		options: "Brand",
		change: () => page.refresh_view(),
	});

	page.is_stock_item_field = page.add_field({
		fieldname: "is_stock_item",
		label: __("Is Stock Item"),
		fieldtype: "Select",
		options: "\nYes\nNo",
		change: () => page.refresh_view(),
	});

	page.include_disabled_field = page.add_field({
		fieldname: "include_disabled",
		label: __("Include Disabled"),
		fieldtype: "Check",
		change: () => page.refresh_view(),
	});

	page.add_inner_button(__("Expand All"), () => page.expand_all(), __("Tree"));
	page.add_inner_button(__("Refresh"), () => page.refresh_view());

	page.setup_export_menu = function () {
		page.clear_menu();

		page.add_menu_item(__("Refresh"), () => page.refresh_view());
		page.add_menu_item(__("Export"), () => page.export_grid("Excel"));
		page.add_menu_item(__("Export as CSV"), () => page.export_grid("CSV"));
		page.add_menu_item(__("Print"), () => page.print_grid());
		page.add_menu_item(__("PDF"), () => page.export_grid("PDF"));
		page.add_menu_item(__("Open Report"), () => {
			frappe.route_options = page.get_filter_args();
			frappe.set_route("query-report", "Item Tree Stock");
		});
	};

	page.print_grid = function () {
		if (!page.company_field.get_value()) {
			frappe.msgprint(__("Please select Company"));
			return;
		}

		frappe
			.xcall("redtra_customisation.api.item_tree.get_grid_print_html", {
				filters: page.get_filter_args(),
				title: __("Item Tree Stock"),
			})
			.then((html) => {
				const print_window = window.open("");
				print_window.document.write(`
					<html>
						<head>
							<title>${__("Item Tree Stock")}</title>
							<link rel="stylesheet" href="/assets/frappe/css/bootstrap.css">
							<link rel="stylesheet" href="/assets/frappe/css/frappe-web.css">
							<style>
								body { padding: 20px; }
								table { width: 100%; font-size: 11px; }
								th, td { padding: 4px 6px; }
							</style>
						</head>
						<body>${html}</body>
					</html>
				`);
				print_window.document.close();
				print_window.focus();
				print_window.print();
			});
	};

	page.get_filter_args = function () {
		const warehouse_wise =
			page.warehouse_wise_columns_field.get_value() === 0 ? 0 : 1;
		return {
			company: page.company_field.get_value(),
			include_disabled: page.include_disabled_field.get_value() ? 1 : 0,
			is_stock_item: page.is_stock_item_field.get_value(),
			brand: page.brand_field.get_value(),
			root_item_group: page.root_item_group_field.get_value(),
			search: page.search_field.get_value(),
			warehouse: page.warehouse_field.get_value(),
			warehouses: page.warehouses_field.get_value(),
			warehouse_wise_columns: warehouse_wise,
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
			() => page.refresh_view(),
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

	page.refresh_view = function () {
		page.view_mode = page.view_mode_field.get_value() || "Tree";
		if (page.view_mode === "Grid") {
			page.render_grid();
		} else {
			page.rebuild_tree();
		}
	};

	page.render_warehouse_badges = function ($label, node) {
		$label.find(".item-tree-qty, .item-tree-wh-grid").remove();

		const breakdown = node.data.warehouse_breakdown || [];
		if (breakdown.length > 1) {
			const $grid = $('<span class="item-tree-wh-grid">');
			breakdown.forEach((entry) => {
				const qty_text = frappe.format(flt(entry.qty), { fieldtype: "Float", precision: 2 });
				const uom = node.data.stock_uom || "";
				$grid.append(
					`<span class="item-tree-wh-badge">${frappe.utils.escape_html(entry.warehouse)}: ${qty_text}${uom ? ` ${uom}` : ""}</span>`
				);
			});
			$label.append($grid);
			return;
		}

		if (node.data.stock_qty === undefined || node.data.stock_qty === null) {
			return;
		}

		const qty = flt(node.data.stock_qty);
		const uom = node.data.stock_uom || "";
		const qty_text = frappe.format(qty, { fieldtype: "Float", precision: 2 });
		const display = uom ? `${qty_text} ${uom}` : qty_text;
		$label.append(`<span class="item-tree-qty">${display}</span>`);
	};

	page.rebuild_tree = function () {
		page.tree_container.removeClass("hide");
		page.grid_container.addClass("hide");
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
			args: page.get_filter_args(),
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
			on_click(node) {
				if (node.data.is_item) {
					frappe.set_route("Form", "Item", node.data.value);
				}
			},
			on_render(node) {
				if (!node.data.is_item) {
					return;
				}
				const $label = node.$tree_link.find(".tree-label");
				$label.addClass("text-muted");
				page.render_warehouse_badges($label, node);
			},
		});
	};

	page.render_grid = function () {
		page.tree_container.addClass("hide");
		page.grid_container.removeClass("hide");

		if (!page.company_field.get_value()) {
			page.grid_container.html(
				`<div class="text-muted text-center padding">${__("Please select Company")}</div>`
			);
			return;
		}

		frappe.dom.freeze(__("Loading..."));
		frappe.require("report.bundle.js", () => {
			frappe
				.call({
					method: "redtra_customisation.api.item_tree.get_grid_data",
					args: page.get_filter_args(),
				})
				.then((r) => {
					page.grid_data = r.message || {};
					page.build_datatable(page.grid_data);
				})
				.always(() => frappe.dom.unfreeze());
		});
	};

	page.build_datatable = function (data) {
		page.grid_container.empty();

		const rows = data.rows || [];
		if (!rows.length) {
			page.grid_container.html(
				`<div class="text-muted text-center padding">${__("No items found for the selected filters.")}</div>`
			);
			return;
		}

		if (page.datatable?.destroy) {
			page.datatable.destroy();
			page.datatable = null;
		}

		const columns = (data.columns || []).map((col) => {
			const column = frappe.report_utils.prepare_field_from_column(col);
			return Object.assign({}, column, {
				id: column.fieldname,
				name: column.label,
				width: parseInt(column.width) || 120,
				editable: false,
				format: (value, row, column, row_data) => {
					if (row_data?.is_group_row) {
						if (column.id === "item_name") {
							return `<b>${frappe.utils.escape_html(value || row_data.item_group || "")}</b>`;
						}
						if (column.id === "item_code") {
							return "";
						}
					}
					if (column.id === "item_code" && value && !row_data?.is_group_row) {
						return `<a class="grey item-tree-item-link" data-item-code="${frappe.utils.escape_html(
							value
						)}">${frappe.utils.escape_html(value)}</a>`;
					}
					if (value === null || value === undefined || value === "") {
						return "";
					}
					return frappe.format(
						value,
						column,
						{ for_print: false, always_show_decimals: true },
						row_data
					);
				},
			});
		});

		page.datatable = new window.DataTable(page.grid_container[0], {
			columns,
			data: rows,
			inlineFilters: true,
			language: frappe.boot.lang,
			translations: frappe.utils.datatable.get_translations(),
			layout: "fixed",
			cellHeight: 33,
			serialNoColumn: false,
			checkboxColumn: false,
			treeView: true,
			direction: frappe.utils.is_rtl() ? "rtl" : "ltr",
		});

		if (page.datatable.rowmanager?.setTreeDepth) {
			page.datatable.rowmanager.setTreeDepth(2);
		}

		page.grid_container
			.off("click.item-tree-link")
			.on("click.item-tree-link", "a.item-tree-item-link", function () {
				const item_code = $(this).attr("data-item-code");
				if (item_code) {
					frappe.set_route("Form", "Item", item_code);
				}
			});
	};

	page.get_print_html = function () {
		return frappe.xcall("redtra_customisation.api.item_tree.get_grid_print_html", {
			filters: page.get_filter_args(),
			title: __("Item Tree Stock"),
		});
	};

	page.export_grid = function (file_format) {
		if (!page.company_field.get_value()) {
			frappe.msgprint(__("Please select Company"));
			return;
		}

		const args = {
			...page.get_filter_args(),
			file_format,
		};

		open_url_post(
			"/api/method/redtra_customisation.api.item_tree.export_item_tree_grid",
			args
		);
	};

	page.expand_all = async function () {
		if (!page.tree || page.view_mode !== "Tree") {
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
					node.$tree_link.find(".node-parent").html(page.tree.icon_set.open);
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

	page.setup_export_menu();

	page.refresh_view();
};
