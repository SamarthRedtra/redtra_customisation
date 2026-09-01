from unittest.mock import MagicMock, patch

from frappe.tests import UnitTestCase

from redtra_customisation.patches.v16_0.seed_project_demo_utils import (
	DEMO_PROJECT_NAME,
	DEMO_TASKS,
	demo_project_exists,
)
from redtra_customisation.patches.v16_0.seed_project_demo_utils import _get_company
from redtra_customisation.patches.v16_0.seed_project_demo_workflow import execute


class TestSeedProjectDemo(UnitTestCase):
	def test_demo_project_exists(self):
		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_utils.frappe.db.exists",
			return_value=True,
		) as exists:
			self.assertTrue(demo_project_exists())
			exists.assert_called_once_with("Project", {"project_name": DEMO_PROJECT_NAME})

	def test_execute_skips_when_demo_project_exists(self):
		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_workflow.demo_project_exists",
			return_value=True,
		):
			with patch(
				"redtra_customisation.patches.v16_0.seed_project_demo_workflow._run_seed"
			) as run_seed:
				execute()
				run_seed.assert_not_called()

	def test_execute_skips_when_no_company(self):
		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_workflow.demo_project_exists",
			return_value=False,
		):
			with patch(
				"redtra_customisation.patches.v16_0.seed_project_demo_workflow.frappe.get_all",
				return_value=[],
			):
				with patch(
					"redtra_customisation.patches.v16_0.seed_project_demo_workflow._run_seed"
				) as run_seed:
					execute()
					run_seed.assert_not_called()

	def test_execute_runs_seed_once_when_site_is_ready(self):
		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_workflow.demo_project_exists",
			return_value=False,
		):
			with patch(
				"redtra_customisation.patches.v16_0.seed_project_demo_workflow.frappe.get_all",
				return_value=[{"name": "Test Company"}],
			):
				with patch(
					"redtra_customisation.patches.v16_0.seed_project_demo_workflow._run_seed"
				) as run_seed:
					execute()
					run_seed.assert_called_once()

	def test_execute_logs_and_swallows_seed_failures(self):
		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_workflow.demo_project_exists",
			return_value=False,
		):
			with patch(
				"redtra_customisation.patches.v16_0.seed_project_demo_workflow.frappe.get_all",
				return_value=[{"name": "Test Company"}],
			):
				with patch(
					"redtra_customisation.patches.v16_0.seed_project_demo_workflow._run_seed",
					side_effect=RuntimeError("seed failed"),
				):
					with patch(
						"redtra_customisation.patches.v16_0.seed_project_demo_workflow.frappe.log_error"
					) as log_error:
						with patch(
							"redtra_customisation.patches.v16_0.seed_project_demo_workflow.frappe.db.rollback"
						) as rollback:
							execute()
							rollback.assert_called_once()
							log_error.assert_called_once()

	def test_get_company_prefers_real_company_over_test_company(self):
		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_utils.frappe.defaults.get_global_default",
			return_value="_Test Company",
		):
			with patch(
				"redtra_customisation.patches.v16_0.seed_project_demo_utils.frappe.get_all",
				return_value=["_Test Company", "Deltachem Middle East LLC"],
			):
				self.assertEqual(_get_company(), "Deltachem Middle East LLC")

	def test_demo_task_blueprint_has_four_progress_stages(self):
		self.assertEqual(len(DEMO_TASKS), 4)
		self.assertEqual(sum(row["progress"] for row in DEMO_TASKS), 215)

	def test_run_seed_orchestrates_workflow(self):
		ctx = MagicMock()
		tasks = {"Site Preparation": "TASK-1", "Installation": "TASK-3"}

		with patch(
			"redtra_customisation.patches.v16_0.seed_project_demo_workflow.get_demo_context",
			return_value=ctx,
		):
			with patch(
				"redtra_customisation.patches.v16_0.seed_project_demo_workflow.ensure_demo_masters"
			) as ensure_demo_masters:
				with patch(
					"redtra_customisation.patches.v16_0.seed_project_demo_workflow.create_demo_project",
					return_value="PROJ-001",
				) as create_demo_project:
					with patch(
						"redtra_customisation.patches.v16_0.seed_project_demo_workflow.create_demo_budget"
					) as create_demo_budget:
						with patch(
							"redtra_customisation.patches.v16_0.seed_project_demo_workflow.create_demo_tasks",
							return_value=tasks,
						) as create_demo_tasks:
							with patch(
								"redtra_customisation.patches.v16_0.seed_project_demo_workflow.ensure_item_stock"
							) as ensure_item_stock:
								with patch(
									"redtra_customisation.patches.v16_0.seed_project_demo_workflow.create_demo_material_issue"
								) as create_demo_material_issue:
									with patch(
										"redtra_customisation.patches.v16_0.seed_project_demo_workflow.create_demo_timesheet"
									) as create_demo_timesheet:
										with patch(
											"redtra_customisation.patches.v16_0.seed_project_demo_workflow.create_demo_sales_invoice"
										) as create_demo_sales_invoice:
											with patch(
												"redtra_customisation.patches.v16_0.seed_project_demo_workflow.refresh_demo_project"
											) as refresh_demo_project:
												from redtra_customisation.patches.v16_0 import (
													seed_project_demo_workflow,
												)

												seed_project_demo_workflow._run_seed()

		ensure_demo_masters.assert_called_once_with(ctx)
		create_demo_project.assert_called_once_with(ctx)
		create_demo_budget.assert_called_once_with(ctx, "PROJ-001")
		create_demo_tasks.assert_called_once_with(ctx, "PROJ-001")
		ensure_item_stock.assert_called_once_with(ctx)
		create_demo_material_issue.assert_called_once_with(ctx, "PROJ-001")
		create_demo_timesheet.assert_called_once_with(ctx, "PROJ-001", tasks)
		create_demo_sales_invoice.assert_called_once_with(ctx, "PROJ-001")
		refresh_demo_project.assert_called_once_with("PROJ-001")
