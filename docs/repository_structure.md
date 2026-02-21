```text
From top working directory `ITF-Masters-Tour`:
.env.example
.gitignore
app.py
Dockerfile
README.md
requirements.txt
run_local.sh



data/
    extracts/
        prerequisites/
            AgeCategory.xlsx
            Country.xlsx
            Draws.xlsx                      # for tournament_id=1-58 
            DrawStatus.xlsx
            Gender.xlsx
            Location.xlsx
            MatchRounds.xlsx
            MatchStatus.xlsx
            Players.xlsx
            PlayerStatus.xlsx
            PointsRules.xlsx
            SeedingRules.xlsx
            StageResults.xlsx
            Surfaces.xlsx
            TournamentCategory.xlsx
            Tournaments.xlsx
            Venue.xlsx

        generated/
            DrawPlayers.xlsx
            Draws.xlsx                              # from tournament_id=59 (before, all data in that table was prerequisite)
            DrawSeed.xlsx
            Entries.xlsx
            Matches.xlsx
            PlayerSuspensions.xlsx
            PointsHistory.xlsx
            WeeklyRanking.xlsx
            

    sql/
        prerequisites/
            _run_all_prerequisites.sql (aggregate all prerequisites.sql files in 1 file)
            agecategory.sql
            country.sql
            draws.sql                                # for tournament_id=1-58 (afterwards, the data in that table will be generated)
            drawstatus.sql
            gender.sql
            location.sql
            matchrounds.sql
            matchstatus.sql
            players.sql
            playerstatus.sql
            pointsrules.sql
            seedingrules.sql
            stageresults.sql
            surfaces.sql
            tournamentcategory.sql
            tournaments.sql
            venue.sql

        generated/
            _export_meta.txt                        # meta file to track which generated sql files have been run
            _run_all_generated_1to59.sql
            drawplayers.sql
            drawseed.sql
            drawseed_t3to58_draw_9to232.sql
            drawseed_t59_draw_233to236.sql
            draws.sql                               # from tournament_id=59 (before, all data in that table was prerequisite)
            entries.sql
            fix_7_unenforced_suspensions.sql
            matches.sql
            playersuspensions.sql
            pointshistory.sql
            updating_match_dates_t59.sql
            weeklyranking.sql
            weeklyranking_year2026_weeks7and8.sql

        queries/
            best4results_only_in_weeklyranking.sql
            check_suspension_durations_correct.sql
            completed_match_winner_won_2sets.sql
            counting_rows_inserted_in6tables.sql
            diagnostic_weekranking.sql
            dq_noshow_0points.sql
            each_drawplayer_matching_entry.sql
            entries_timestamp_tournament59.sql
            entries_tournament59_men60.sql
            entries_with_only_age_eligible_players.sql
            first_match_losers_0points.sql
            last52weeks_from_1feb2026_alain_bouvier.sql
            match_count_per_draw_t59.sql
            match_triggering_suspensions_but_did_not.sql
            match_winner_is_player1_or_2.sql
            miami_mt1000_2025_week16_men60.sql
            next_suspensions.sql
            points_history_points_correctness.sql
            rank_positions_no_gap_within_cat_and_week.sql
            suspension_durations_correct.sql
            suspension_id_renumbering.sql
            tiebreak_winner_completed_matches_set_winner.sql
            validated_seed_distribution_t59.sql
            weeklyranking_week9_vs_week8.sql
            weeklyranking_year2026_week7_men60.sql
            weeklyranking_year2026_week7_men65.sql
            weeklyranking_year2026_week7_women60.sql
            weeklyranking_year2026_week7_women65.sql

        schema/
            create_itf_schema.sql

        views/
        

docs/
    diagrams/
        itf-architecture-diagram.svg
        ITF-ER-Diagram.svg
    frontend.md
    ITF-queries.md
    repository_structure.md
    Rules.md
    script_workflow.md


evidence/
    screenshots/
        Local/
            AllEntries_T59_M60-F60-M65-F65_10feb2026_0h40.png
            Skeleton_T59_Draw233_M60_Winner_MatthewKelly_10feb2026_23h19.png
            Skeleton_T59_Draw234_F60_Winner_HelenKelly_10feb2026_23h21.png
            Skeleton_T59_Draw235_M65_Winner_MichelDurand_10feb2026_23h23.png
            Skeleton_T59_Draw236_F65_Winner_SylvieDessange_10feb2026_23h24.png
            T59_Draw233_M60_MatchList_10feb2026_23h25.png
            T59_Draw234_F60_MatchList_10feb2026_23h26.png
            T59_Draw234_F60_MatchList_10feb2026_23h26.png
            T59_Draw235_M65_MatchList_10feb2026_23h28.png
            T59_Draw236_F65_MatchList_10feb2026_23h29.png
            weeklyranking_2026_week7_F60_11feb2026_23h35.png
            weeklyranking_2026_week7_F65_11feb2026_23h36.png
            weeklyranking_2026_week7_M60_11feb2026_23h35.png
            weeklyranking_2026_week7_M65_11feb2026_23h36.png
            weeklyranking_2026_week8_F60_11feb2026_23h38.png
            weeklyranking_2026_week8_F65_11feb2026_23h39.png
            weeklyranking_2026_week8_M60_11feb2026_23h37.png
            weeklyranking_2026_week8_M65_11feb2026_23h38.png
            weeklyranking_2026_week9_F60_11feb2026_23h40.png
            weeklyranking_2026_week9_F65_11feb2026_23h42.png
            weeklyranking_2026_week9_M60_11feb2026_23h40.png
            weeklyranking_2026_week9_M65_11feb2026_23h41.png

        live/
            awscloudcase_AdminPage_17feb2026_21h46.png
            awscloudcase_AdminPage_t61_2026_Week10_MarcosJimenez_17feb2026_23h00.png
            awscloudcase_AdminPage_t61_2026_Week10_MarcosJimenez_player86_entered_17feb2026_23h02.png
            awscloudcase_t56_draw224_F65_17feb2026_22h53.png
            awscloudcase_T59_M60_Draw_17feb2026_21h41.png
            awscloudcase_tournament56_page_17feb2026_22h50.png
            awscloudcase_tournament59_page_17feb2026_21h38.png
            awscloudcase_tournaments_page_17feb2026_21h35
            awscloudcase_tournaments_page_after_Failover_17feb2026_22h12.png
            awscloudcase_WeeklyRankings_2026_Week9_M60_17feb2026_21h42.png
            Console_failure_code503_17feb2026_21h55.png
            Console_Promote_RDS_ReadReplica_BackingUp_Available_17feb2026_22h34.png
            Console_RDS_ReadReplica_NowPromoted_17feb2026_22h39.png
            Route53_HealthCheck_17feb2026_22h00.png


reports/
    nice_mt400_senior_2026_men60_draw.html
    analysis/

    exports/
        generate_outputs_t1_58.py
        __pycache__/
            generate_outputs_t1_58.cpython-312.pyc


scripts/
    __init__.py
    __pycache__/
        __init__.cpython-312

    generation/
        __init__.py
        generate_draw_players.py
        generate_draw_seed.py
        generate_entries.py
        generate_matches.py

    recalculation/
        apply_sanctions.py
        export_all_generated_xlsx.py
        export_drawseed_draw_9to236.py
        generate_outputs_t59.py
        generate_ranking_year2026_weeks7and8.py
        recalculate_points.py
        recalculate_rankings.py
        regenerate_matches.py

    services/
        __init__.py
        draw_service.py
        entry_service.py
        match_service.py
        view_service.py
        __pycache__/
            __init__.cpython-312.sql
            draw_service.cpython-312.sql
            entry_service.cpython-312.sql
            match_service.cpython-312.sql
            view_service.cpython-312.sql


    validation
        validate_draw_players.py
        validate_itf_data.py
        validate_tennis_matches.py
        __pycache__/
            validate_tennis_matches.cpython-312.sql


src/
    __init__.py

    __pycache__/
        __init__.cpython-312

    modules/
        __init__.py
        calculate_points_history.py
        calculate_weekly_ranking.py
        db_connection.py
        generate_player_suspensions.py
        match_scheduler.py
        ranking_window.py
        rules_engine.py
        score_generator.py
        seeding_engine.py
        weighted_sampler.py


templates/
    admin.html
    base.html
    draw.html
    rankings.html
    tournament_detail.html
    tournaments.html


terraform/
    .terraform/

    modules/
        dns/
            main.tf
            outputs.tf
            variables.tf

        ecs/
            main.tf
            outputs.tf
            variables.tf

        rds/
            main.tf
            outputs.tf
            variables.tf

        vpc/
            main.tf
            outputs.tf
            variables.tf

    .terraform.lock.hcl
    main.tf
    outputs.tf
    terraform.tfstate
    terraform.tfstate.backup
    terraform.tfvars
    terraform.tfvars.example
    variables.tf


tests/


venv/
    pyvenv.cfg

    bin/

    include/

    lib/

    lib64/


```



