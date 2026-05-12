Quick Start
===========

Project Planner accepts YAML and Python plan files. The repository includes
examples under ``planner/examples``.

Run these commands from the repository root:

.. code-block:: bash

   planner validate planner/examples/tasks.yaml
   planner list planner/examples/tasks.yaml
   planner summary planner/examples/tasks.yaml
   planner schedule planner/examples/tasks.yaml
   planner export-docx planner/examples/tasks.yaml /tmp/plan.docx
   planner export-svg planner/examples/tasks.yaml /tmp/plan.svg

Default Plan File
-----------------

Set ``TUXFAN_PLANNER_DATAFILE`` to omit the input file for most commands:

.. code-block:: bash

   export TUXFAN_PLANNER_DATAFILE=planner/examples/tasks.yaml
   planner validate
   planner list
   planner export-docx /tmp/plan.docx
   planner export-svg /tmp/plan.svg

Shell Completion
----------------

The CLI prints completion scripts for ``bash``, ``zsh``, and ``fish``:

.. code-block:: bash

   planner completion bash
   planner completion zsh
   planner completion fish

For a one-session bash setup:

.. code-block:: bash

   source <(planner completion bash)
