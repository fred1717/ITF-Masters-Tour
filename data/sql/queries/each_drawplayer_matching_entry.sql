SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM DrawPlayers dp
JOIN Draws d ON d.draw_id = dp.draw_id
WHERE NOT EXISTS (
    SELECT 1 FROM Entries e
    WHERE e.player_id = dp.player_id
      AND e.tournament_id = d.tournament_id
      AND e.age_category_id = d.age_category_id
);
