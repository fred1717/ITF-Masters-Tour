SELECT draw_id, COUNT(*) AS match_count
FROM Matches
WHERE draw_id IN (233, 234, 235, 236)
GROUP BY draw_id
ORDER BY draw_id;
