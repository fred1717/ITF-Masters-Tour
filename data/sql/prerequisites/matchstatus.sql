INSERT INTO MatchStatus (match_status_id, code, description) VALUES
(1, 'Scheduled', 'Match is in the draw but not yet played'),
(2, 'Completed', 'Match finished, result recorded'),
(3, 'Walkover', 'One player withdrew/didn''t show'),
(4, 'Retired', 'Player retired during match'),
(5, 'Cancelled', 'Match cancelled for some reason'),
(6, 'Disqualification', 'One player was disqualified')
;
