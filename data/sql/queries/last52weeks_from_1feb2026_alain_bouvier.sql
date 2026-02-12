SELECT
    t.name as tournament_name,
    ph.points_earned,
    ph.created_at as points_added_date
FROM PointsHistory ph
JOIN Tournaments t ON ph.tournament_id = t.tournament_id
JOIN Players p ON ph.player_id = p.player_id
WHERE p.first_name = 'Alain'
    AND p.last_name = 'Bouvier'
    AND ph.age_category_id = 2
    AND ph.created_at BETWEEN '2025-02-03' AND '2026-02-02'
ORDER BY ph.points_earned DESC, ph.created_at DESC;
