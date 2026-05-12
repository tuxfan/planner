Project Planner
===============

Project Planner is a small Python planning tool for validating project task
definitions, printing dependency-aware schedules, and exporting plans to Word
and SVG files.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quickstart
   schema
   cli
   export-options
   api

Installation
------------

Install the package locally from the repository root:

.. code-block:: bash

   python3 -m pip install -e .

Install documentation dependencies when you want to build this documentation:

.. code-block:: bash

   python3 -m pip install -e ".[docs]"

Build the HTML documentation with:

.. code-block:: bash

   python3 -m sphinx docs docs/_build/html
