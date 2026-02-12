INSERT INTO DrawStatus (status_id, status_name, description) VALUES
(1, 'Open', 'Entries are being accepted (before Tuesday 10:00 UTC deadline)'),
(2, 'Closed', 'Entry deadline passed, num_players calculated, but draw not yet generated'),
(3, 'Generated', 'Draw/bracket created, seeding and byes assigned'),
(4, 'Completed', 'All matches finished, results recorded'),
(5, 'Cancelled', 'Tournament cancelled (e.g., fewer than 6 players)')
;
