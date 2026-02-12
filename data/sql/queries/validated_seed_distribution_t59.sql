SELECT ds.draw_id, d.age_category_id, d.gender_id,
       COUNT(*) AS num_seeds,
       (SELECT COUNT(*) FROM DrawPlayers dp WHERE dp.draw_id = ds.draw_id) AS num_players
FROM DrawSeed ds
JOIN Draws d ON d.draw_id = ds.draw_id
WHERE ds.draw_id IN (233, 234, 235, 236)
GROUP BY ds.draw_id, d.age_category_id, d.gender_id
ORDER BY ds.draw_id;
