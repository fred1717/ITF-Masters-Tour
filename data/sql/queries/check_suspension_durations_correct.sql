SELECT ps.*,
       CASE WHEN ps.reason_match_status_id = 3
            THEN ps.suspension_start + INTERVAL '2 months'
            ELSE ps.suspension_start + INTERVAL '6 months'
       END AS expected_end,
       ps.suspension_end = CASE
            WHEN ps.reason_match_status_id = 3
            THEN ps.suspension_start + INTERVAL '2 months'
            ELSE ps.suspension_start + INTERVAL '6 months'
       END AS duration_correct
FROM PlayerSuspensions ps;
