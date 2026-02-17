After restarting the computer, restart the Docker container, so in PyCharm terminal:
```bash
docker start itf-postgres
```

Activate the virtual environment:
```bash
source venv/bin/activate
```

**Reset the database + Load the Schema and data:**
```bash
docker exec -i itf-postgres psql -U itfuser -d itf_tournament < data/sql/schema/create_itf_schema.sql
docker exec -i itf-postgres psql -U itfuser -d itf_tournament < data/sql/prerequisites/_run_all_prerequisites.sql
```
or
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
```

So the commands mean:
docker exec = run a command inside the container
-i = keep input open (so we can send SQL)
itf-postgres = name of the container
psql = PostgreSQL command-line tool
-U itfuser = connect as user "itfuser"
-d itf_tournament = connect to database "itf_tournament"
-p parent + don't error if the directory already exists.

Last command didn't work, so other command after confirming port mapping for PostgreSQL is 5432:
```bash
docker port itf-postgres
```
**Example output:**
```text
5432/tcp -> 0.0.0.0:5432
5432/tcp -> [::]:5432
```

**Running `_run_all_prerequisites.sql` to load prerequisite data into tables**
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
```

**Populate all tables with prerequisite data (in 17 tables) by running `_run_all_prerequisites.sql`:**
Indeed, `_run_all_prerequisites.sql` contains all 17 prerequisite tables.
```bash
\i data/sql/prerequisites/agecategory_prerequisites.sql
\i data/sql/prerequisites/gender_prerequisites.sql
\i data/sql/prerequisites/playerstatus_prerequisites.sql
\i data/sql/prerequisites/matchstatus_prerequisites.sql
\i data/sql/prerequisites/matchrounds_prerequisites.sql
\i data/sql/prerequisites/stageresults_prerequisites.sql
\i data/sql/prerequisites/seedingrules_prerequisites.sql
\i data/sql/prerequisites/drawstatus_prerequisites.sql
\i data/sql/prerequisites/country_prerequisites.sql
\i data/sql/prerequisites/location_prerequisites.sql
\i data/sql/prerequisites/venue_prerequisites.sql
\i data/sql/prerequisites/surfaces_prerequisites.sql
\i data/sql/prerequisites/tournamentcategories_prerequisites.sql
\i data/sql/prerequisites/pointsrules_prerequisites.sql
\i data/sql/prerequisites/players_prerequisites.sql
\i data/sql/prerequisites/tournaments_prerequisites.sql
\i data/sql/prerequisites/draws_prerequisites.sql
```
Each of the 17 commands above populates 1 table with prerequisite data (INSERT statements).
or better:
```bash
docker exec -i itf-postgres pg_dump \
  -U itfuser -d itf_tournament \
  --data-only \
  --column-inserts \
  --disable-triggers \
  --no-owner \
  --no-privileges \
  > data/sql/load_itf_data.sql
```
**Notes**
- `--data-only` ensures schema is not dumped (schema remains in `create_itf_schema.sql`).
- `--column-inserts` makes INSERTs explicit per column (readable, resilient to column order changes).
- `--disable-triggers` avoids FK issues during reload ordering.
- `--no-owner --no-privileges` avoids environment-specific noise.


**Cleanup commands:**
Command 1:
```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
```
What it does:
- `find .` : Scans from the current directory downward..
- `-type f` : Restricts matches to regular files.
- `-name "__pycache__"` : Matches directories named exactly `__pycache__`.
- `-prune` : Prevents find from descending into that matched directory (efficiency, and avoids listing files inside it).
- `-exec rm -rf {} +` : Deletes the matched directories:
- `{}` : is replaced by each matched path.
- `rm -rf` : removes the directory recursively and does not prompt.
- `+` : batches multiple matches into fewer `rm` calls (more efficient than `\;`).
Effect: every `__pycache__` folder under the current directory is deleted.

Command 2:
```bash
find . -type f -name "*.pyc" -delete
```
What it does:
- `find .` : Scans starting from the current directory (.) and all subdirectories.
- `-type d` : Restricts matches to directories only.
- `-name "*.pyc"` : Matches files ending in `.pyc` (compiled Python bytecode).
- `-delete` : Deletes each matched file.
Effect: any stray `.pyc` files anywhere in the tree are deleted (including those not inside `__pycache__`).

**Safety notes**
- Both commands operate relative to the current directory. Running them from the repository root confines deletions to the repo.
- Only cache artefacts are targeted (`__pycache__` directories and `.pyc` files). Source files (`*.py`) are not targeted.


**What `__pycache__` is:**
- `__pycache__` is a Python bytecode cache folder created automatically by the Python interpreter.
- It contains `*.pyc` files (compiled bytecode) such as `calculate_points_history.cpython-312.pyc`.

**Purpose:** faster imports / faster subsequent runs.
It is environment-specific and disposable: safe to delete at any time; Python will recreate it.

**What should be done with `__pycache__` and `*.pyc` in this project**
These are dev-only artefacts and should not be committed to Git.

**Git ignore rules (recommended)**
Add (or ensure) the following entries exist in `.gitignore`:
```text
__pycache__/
*.pyc
```

**One operational convention to prevent surprises when running from different working directories**
REPLACE
```bash
python3 scripts/recalculation/apply_sanctions.py
python3 scripts/recalculation/recalculate_points.py
python3 scripts/recalculation/recalculate_rankings.py
```
WITH
```bash
PYTHONPATH="$(pwd)" python3 scripts/recalculation/apply_sanctions.py
PYTHONPATH="$(pwd)" python3 scripts/recalculation/recalculate_points.py
PYTHONPATH="$(pwd)" python3 scripts/recalculation/recalculate_rankings.py
```

