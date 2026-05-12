Python API
==========

The public API is intentionally small. Most callers should load a plan with
``load_plan`` or ``load_tasks`` and then use the CLI or exporters.

Loader
------

.. automodule:: planner.loader
   :members: load_plan, load_tasks

Models
------

.. automodule:: planner.models
   :members: ProjectPlan, Task, Risk, ExecutionItem, ValidationError, validate_tasks, build_schedule, fiscal_year_range, funding_totals

Export Options
--------------

.. automodule:: planner.export_options
   :members: ExportOptions, TaskTableColumn, load_export_options

Exporters
---------

.. automodule:: planner.exporters
   :members: write_docx, write_svg
