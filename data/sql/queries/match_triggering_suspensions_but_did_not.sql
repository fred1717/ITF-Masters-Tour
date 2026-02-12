SELECT m.match_id, m.draw_id, m.match_status_id, m.player1_id, m.player2_id, m.winner_id
FROM Matches m
WHERE m.match_status_id IN (3, 6)
  AND NOT EXISTS (
      SELECT 1 FROM PlayerSuspensions ps
      WHERE ps.reason_match_status_id = m.match_status_id
        AND ps.player_id = CASE
            WHEN m.winner_id = m.player1_id THEN m.player2_id
            ELSE m.player1_id
        END
  );
