SELECT 'FAIL' AS result, COUNT(*) AS bad_rows
FROM PointsHistory ph
WHERE ph.points_earned > 0
AND NOT EXISTS (
    SELECT 1 FROM Matches m
    WHERE m.draw_id IN (
        SELECT d.draw_id FROM Draws d WHERE d.tournament_id = ph.tournament_id
        AND d.age_category_id = ph.age_category_id
    )
    AND m.winner_id = ph.player_id
)
HAVING COUNT(*) > 0
UNION ALL
SELECT 'PASS', 0
WHERE NOT EXISTS (
    SELECT 1 FROM PointsHistory ph
    WHERE ph.points_earned > 0
    AND NOT EXISTS (
        SELECT 1 FROM Matches m
        WHERE m.draw_id IN (
            SELECT d.draw_id FROM Draws d WHERE d.tournament_id = ph.tournament_id
            AND d.age_category_id = ph.age_category_id
        )
        AND m.winner_id = ph.player_id
    )
);
