SELECT t.tournament_id, t.start_date, m.match_id, m.match_status_id,
       CASE WHEN m.winner_id = m.player1_id THEN m.player2_id ELSE m.player1_id END AS suspended_player_id
FROM Matches m
JOIN Draws d ON d.draw_id = m.draw_id
JOIN Tournaments t ON t.tournament_id = d.tournament_id
WHERE m.match_id IN (66, 173, 322, 538, 590, 601, 613)
ORDER BY m.match_id;
