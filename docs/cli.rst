Command Line Interface
======================

The package installs two console scripts:

``planner``
   Primary command.

``tuxfan-planner``
   Backward-compatible alias.

Commands
--------

``validate [task_file]``
   Validate a YAML or Python plan file.

``list [task_file]``
   Print validated task details in planner sort order.

``summary [task_file]``
   Print task counts by project and milestone. Funding totals are included when
   the plan has fiscal years and task funding.

``schedule [task_file]``
   Print dependency-aware task order with ``COMPLETE``, ``ACTIVE``, ``ONGOING``,
   ``READY``, or ``BLOCKED`` state.

``export-docx [task_file] output_file``
   Write a Word document plan.

``export-svg [task_file] output_file``
   Write an SVG schedule diagram.

``completion [bash|zsh|fish]``
   Print a shell completion script.

Environment Variables
---------------------

``TUXFAN_PLANNER_DATAFILE``
   Default plan file. When set, basic commands can omit ``task_file`` and export
   commands can pass only the output path.

``TUXFAN_PLANNER_EXPORT_OPTIONS``
   Default export options file for ``export-docx`` and ``export-svg``.

Examples
--------

.. code-block:: bash

   planner validate planner/examples/tasks.yaml
   planner schedule planner/examples/tasks.yaml
   planner export-docx planner/examples/tasks.yaml /tmp/plan.docx

With default input and export options:

.. code-block:: bash

   export TUXFAN_PLANNER_DATAFILE=planner/examples/tasks.yaml
   export TUXFAN_PLANNER_EXPORT_OPTIONS=planner/examples/export-options.yaml
   planner export-docx /tmp/plan.docx
