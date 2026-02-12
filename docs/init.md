`__init__.py` files are only needed in directories that will be imported as packages.

With imports like:
- `from src.modules.db_connection import DatabaseConnection`
- `from scripts.generation.generate_entries import calculate_entry_deadline`

The required package markers are:
- `src/__init__.py`
- `src/modules/__init__.py`
- `scripts/__init__.py`
- `scripts/generation/__init__.py`

Nothing in `/scripts/recalculation` or `/scripts/validation` is required unless imports will use those paths too, like:
- `from scripts.recalculation.recalculate_points import ...`
- `from scripts.validation.validate_itf_data import ...`

If those package imports are planned, then add:
- `scripts/recalculation/__init__.py`
- `scripts/validation/__init__.py`

