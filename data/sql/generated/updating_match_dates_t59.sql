-- Men 60 + Men 65 (draws 233, 235): Mon/Wed/Fri/Sun
UPDATE Matches SET match_date = '2026-02-16' WHERE draw_id IN (233, 235) AND round_id = 3;
UPDATE Matches SET match_date = '2026-02-18' WHERE draw_id IN (233, 235) AND round_id = 4;
UPDATE Matches SET match_date = '2026-02-20' WHERE draw_id IN (233, 235) AND round_id = 5;
UPDATE Matches SET match_date = '2026-02-22' WHERE draw_id IN (233, 235) AND round_id = 6;

-- Women 60 + Women 65 (draws 234, 236): Tue/Thu/Sat
UPDATE Matches SET match_date = '2026-02-17' WHERE draw_id IN (234, 236) AND round_id = 4;
UPDATE Matches SET match_date = '2026-02-19' WHERE draw_id IN (234, 236) AND round_id = 5;
UPDATE Matches SET match_date = '2026-02-21' WHERE draw_id IN (234, 236) AND round_id = 6;
