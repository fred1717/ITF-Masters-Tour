SELECT ph.id, ph.player_id, p.first_name, p.last_name,
       ph.age_category_id, ph.stage_result_id, ph.points_earned,
       sr.description
FROM PointsHistory ph
JOIN Players p ON p.player_id = ph.player_id
JOIN StageResults sr ON sr.id = ph.stage_result_id
WHERE ph.tournament_id = 59
ORDER BY ph.age_category_id, ph.points_earned DESC;
