SELECT
    p.player_id,
    p.last_name,
    p.first_name,
    sr.description as result,
    ph.points_earned
FROM Entries e
JOIN Players p ON e.player_id = p.player_id
JOIN Tournaments t ON e.tournament_id = t.tournament_id
JOIN PointsHistory ph ON ph.player_id = e.player_id
    AND ph.tournament_id = e.tournament_id
    AND ph.age_category_id = e.age_category_id
JOIN StageResults sr ON ph.stage_result_id = sr.id
WHERE t.name = 'Miami MT1000 Open 2025'
    AND e.age_category_id = 1
    AND e.gender_id = 1
ORDER BY sr.display_order;
