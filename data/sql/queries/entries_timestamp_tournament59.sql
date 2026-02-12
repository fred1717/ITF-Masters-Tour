SELECT e.entry_id, e.player_id, p.first_name, p.last_name,
       e.entry_points, e.entry_timestamp
FROM Entries e
JOIN Players p ON p.player_id = e.player_id
WHERE e.tournament_id = 59
ORDER BY e.age_category_id, e.gender_id, e.entry_points DESC;
