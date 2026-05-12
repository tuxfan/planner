Export Options
==============

Export commands can load an optional YAML or Python export options file from
``--export-options`` or ``TUXFAN_PLANNER_EXPORT_OPTIONS``.

Task Table Columns
------------------

``task_table_columns`` is the preferred configuration key for Word task summary
tables. Each column can define an ``attribute``, an optional ``label``, and an
optional ``alignment``.

Supported attributes are ``site``, ``bnr``, ``cost``, ``funding_status``,
``funding``, ``type``, and ``tags``. ``funding`` is an alias for
``funding_status``.

Supported alignments are ``left``, ``center``, and ``right``. Alignment defaults
to ``center``.

Example:

.. code-block:: yaml

   task_table_columns:
     - attribute: site
       label: Site
     - attribute: bnr
       label: BNR
     - attribute: cost
       label: Cost
       alignment: right
     - attribute: funding
       label: Status
     - attribute: type
       label: Type

Legacy Attribute List
---------------------

The older ``task_table_attributes`` list remains supported:

.. code-block:: yaml

   task_table_attributes:
     - site
     - bnr
     - cost
     - funding_status
     - type
