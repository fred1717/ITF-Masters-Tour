SELECT e.player_id, p.first_name, p.last_name
FROM Entries e
JOIN Players p ON p.player_id = e.player_id
WHERE e.tournament_id = 59
  AND e.age_category_id = 1
  AND e.gender_id = 1
ORDER BY e.player_id;
