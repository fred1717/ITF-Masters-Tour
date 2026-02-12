## 1. `services` folder inside `scripts` folder, containing:
- `__init__.py`: empty or just with a short comment (Purpose: it marks services/ as a Python package so imports work reliably)
- `entry_service.py`
- `draw_service.py`
- `match_service.py`
- `view_service.py` (names + seeds + formatted scores): will call these functions: 
    - get_draw_matches(draw_id) (joins names + seeds + scores)
    - format_score(...) (e.g., 7-6(5) / [10-8])
    - format_player(...).
This enables accurate draw rendering.


## 2. Add Flask routes (thin, no business logic)
The Flask app will be in `app.py`, in the Projects directory.
The html templates in the `templates` folder, in the Projects directory.

**Minimum routes:**
- Public
    - GET /tournaments (list)
    - GET /draw/<draw_id> (render bracket using view_service.get_draw_matches)
- Admin
    - POST `/admin/entry` (calls `entry_service.create_entry`)
    - POST `/admin/generate-draw` (calls `draw_service.generate_draw_from_entries`)
    - POST `/admin/create-skeleton` (calls `match_service.create_match_skeleton`)
    - POST `/admin/submit-result` (calls `match_service.apply_result_and_advance`)


## 3. Prove it works with 3 checks
- Page loads and shows player names + scores for a known draw (e.g., 217).
- Submitting a result updates the match and advances the winner.
- Running recalculation scripts updates `PointsHistory` / `WeeklyRanking`.


## 4. Only after this: Terraform
Once the local Flask app is stable, Terraform can deploy the same app to AWS with confidence.
