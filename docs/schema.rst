Plan Schema
===========

A plan file can be either a raw task list or a mapping with a ``tasks`` key plus
optional plan metadata.

Top-Level Metadata
------------------

Supported metadata fields are:

``portfolio``
   Portfolio or parent program name.

``project``
   High-level project name.

``managers``
   List of manager names.

``pocs``
   List of point-of-contact names.

``summary``
   High-level plan summary.

``fiscal_range_begin`` and ``fiscal_range_end``
   Fiscal year range covered by the plan. Values are normalized to labels such
   as ``FY27``.

``execution``
   Execution metadata. The preferred shape is a mapping with ``overview`` text
   and ``sections`` entries containing ``label`` and ``description``. A legacy
   flat list of execution sections is still accepted.

Task Fields
-----------

Each task requires ``id``, ``label``, ``project``, ``description``, ``start``,
``deadline``, ``expected_duration``, ``milestone``, ``priority``, ``status``,
``dependencies``, and ``risk``. A task with ``status: complete`` and a
``completed`` fiscal period may omit the planning-only fields ``start``,
``deadline``, ``expected_duration``, ``milestone``, ``priority``,
``dependencies``, and ``risk``.

Optional task fields include ``site``, ``bnr``, ``cost``, ``funding_status``,
``funding``, ``type``, and ``tags``.

``id``
   String containing only letters, numbers, and underscores.

``start`` and ``deadline``
   Fiscal periods in ``M{month}Q{quarter}FY{year}`` format, such as
   ``M1Q3FY26``.

``expected_duration``
   Positive whole number of months.

``status``
   One of ``pending``, ``active``, ``ongoing``, ``blocked``, or ``complete``.

``completed``
   Optional fiscal period for already-completed work. When present on a
   complete task, it is used as the task's schedule position if ``start`` or
   ``deadline`` are omitted.

``dependencies``
   List of task ids. Every dependency must reference an existing task.

``risk``
   A mapping or list of mappings. Each risk entry must include ``type``,
   ``level``, and ``mitigation``, and may include ``description``. Risk levels
   are ``low``, ``medium``, ``high``, and ``extreme``.

``funding``
   Mapping of fiscal year labels to funding levels. Missing fiscal years are
   treated as unfunded for that task.

Multi-Part Tasks
----------------

A task can use ``parts`` instead of schedule fields on the parent. Parent
metadata such as ``project``, ``site``, ``bnr``, ``type``, ``tags``, and
``funding`` is inherited by each part.

Part ids expand to flat task ids using ``{parent_id}_{part_id}``. For example,
part ``A`` on parent ``HOFEM`` becomes ``HOFEM_A``. Dependencies inside a
multi-part task can reference sibling part ids, and other tasks can depend on
the parent id to depend on all expanded parts.

Validation
----------

Validation rejects missing required fields, invalid ids, invalid fiscal
periods, non-positive durations, invalid status or risk levels, dependencies
that reference missing tasks, dependency cycles, and tasks with ``start`` after
``deadline``.

Validated output is sorted by deadline, project, label, and id.
