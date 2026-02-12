SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM PointsHistory ph
JOIN Draws d ON d.tournament_id = ph.tournament_id
    AND d.age_category_id = ph.age_category_id
JOIN Matches m ON m.draw_id = d.draw_id
    AND m.match_status_id IN (3, 6)
    AND (m.player1_id = ph.player_id OR m.player2_id = ph.player_id)
    AND m.winner_id != ph.player_id
WHERE ph.points_earned > 0;
