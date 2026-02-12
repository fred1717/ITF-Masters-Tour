#!/usr/bin/env python3
"""
Recalculate WeeklyRanking Table
================================

This script recalculates all weekly rankings using the corrected logic
and updates the database.

Process:
1. Read all data from database (PointsHistory, Tournaments, Players)
2. Calculate rankings for all weeks
3. Export to CSV for verification
4. Optionally update database

Author: Malik Hamdane
Date: January 2026
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import csv
from datetime import datetime
from collections import defaultdict

from src.modules.db_connection import DatabaseConnection
from src.modules.calculate_weekly_ranking import calculate_weekly_ranking

from src.modules.ranking_window import add_iso_weeks


def get_all_ranking_weeks(db):
    """
    Get all ranking weeks from first ranking through current week.

    Rankings are published the week AFTER tournaments end:
    - Tournament in week N → Ranking published in week N+1
    - First tournament (ISO week 2, 2025) → First ranking (ISO week 3, 2025)
    - Last tournament (ISO week 3, 2026) → Last ranking (ISO week 4, 2026)

    Returns:
        List of (year, week) tuples sorted chronologically
    """
    from datetime import date

    # First tournament ISO week that has any PointsHistory rows
    query = """
            SELECT t.tournament_year, t.tournament_week
            FROM Tournaments t
                     INNER JOIN PointsHistory ph ON t.tournament_id = ph.tournament_id
            ORDER BY t.tournament_year ASC, t.tournament_week ASC LIMIT 1 \
            """
    rows = db.query(query)
    if not rows:
        return []

    first_tournament_year = int(rows[0]["tournament_year"])
    first_tournament_week = int(rows[0]["tournament_week"])

    # First ranking is the week AFTER the first tournament week
    first_ranking = add_iso_weeks(first_tournament_year, first_tournament_week, 1)

    today = date.today()
    current_iso = today.isocalendar()
    current_ranking_year = int(current_iso[0])
    current_ranking_week = int(current_iso[1])

    # Iterate ISO weeks correctly using add_iso_weeks
    weeks_list = []
    cur = first_ranking
    while True:
        weeks_list.append((cur.iso_year, cur.iso_week))
        if cur.iso_year == current_ranking_year and cur.iso_week == current_ranking_week:
            break
        cur = add_iso_weeks(cur.iso_year, cur.iso_week, 1)

    if weeks_list:
        print(f"   First ranking: {weeks_list[0][0]} week {weeks_list[0][1]}")
        print(f"   Last ranking: {weeks_list[-1][0]} week {weeks_list[-1][1]}")
        print(f"   Total ranking weeks: {len(weeks_list)}")

    return weeks_list


def recalculate_all_rankings():
    """
    Recalculate all weekly rankings and export to CSV.

    Returns:
        List of all calculated ranking records
    """
    db = DatabaseConnection()

    if not db.connect():
        print("✗ Failed to connect to database")
        return None

    print("=" * 80)
    print("RECALCULATING WEEKLY RANKINGS")
    print("=" * 80)

    # Load all data
    print("\n1. Loading data from database...")
    points_history = db.query("SELECT * FROM PointsHistory ORDER BY id")
    tournaments_list = db.query("SELECT tournament_id, tournament_year, tournament_week FROM Tournaments")
    players = db.query("SELECT player_id, gender_id FROM Players")

    print(f"   Loaded {len(points_history)} PointsHistory records")
    print(f"   Loaded {len(tournaments_list)} tournaments")
    print(f"   Loaded {len(players)} players")

    # Create lookup dictionaries
    tournaments_dict = {
        t['tournament_id']: {'year': t['tournament_year'], 'week': t['tournament_week']}
        for t in tournaments_list
    }

    player_gender = {p['player_id']: p['gender_id'] for p in players}

    # Determine ranking weeks
    print("\n2. Determining ranking weeks...")
    ranking_weeks = get_all_ranking_weeks(db)
    print(f"   Found {len(ranking_weeks)} weeks to calculate")

    # Calculate rankings for each week
    print("\n3. Calculating rankings...")
    all_rankings = []

    for year, week in ranking_weeks:
        weekly_rankings = calculate_weekly_ranking(
            ranking_year=year,
            ranking_week=week,
            points_history=points_history,
            tournaments=tournaments_dict,
            player_gender=player_gender
        )
        all_rankings.extend(weekly_rankings)

    print(f"\n   Calculated {len(all_rankings)} total ranking records")

    # Export to CSV
    print("\n4. Exporting to CSV...")
    csv_filename = f'weekly_rankings_corrected_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    with open(csv_filename, 'w', newline='') as f:
        if all_rankings:
            fieldnames = ['player_id', 'age_category_id', 'gender_id', 'ranking_year', 'ranking_week', 'total_points',
                          'rank_position']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for ranking in all_rankings:
                writer.writerow({k: ranking[k] for k in fieldnames})

    print(f"   ✓ Exported to {csv_filename}")

    db.disconnect()

    return all_rankings, csv_filename


def update_database(rankings):
    """
    Update WeeklyRanking table in database with corrected values.

    Args:
        rankings: List of ranking records to insert
    """
    db = DatabaseConnection()

    if not db.connect():
        print("✗ Failed to connect to database")
        return False

    print("\n5. Updating database...")

    try:
        cursor = db.connection.cursor()

        # Delete old rankings
        print("   Deleting old rankings...")
        cursor.execute("DELETE FROM WeeklyRanking")
        deleted_count = cursor.rowcount
        print(f"   Deleted {deleted_count} old records")

        # Insert new rankings
        print("   Inserting corrected rankings...")
        insert_sql = """
                     INSERT INTO WeeklyRanking
                     (player_id, age_category_id, gender_id, ranking_year, ranking_week, total_points, rank_position)
                     VALUES (%s, %s, %s, %s, %s, %s, %s) \
                     """

        for ranking in rankings:
            cursor.execute(insert_sql, (
                ranking['player_id'],
                ranking['age_category_id'],
                ranking['gender_id'],
                ranking['ranking_year'],
                ranking['ranking_week'],
                ranking['total_points'],
                ranking['rank_position']
            ))

        db.connection.commit()
        print(f"   ✓ Inserted {len(rankings)} corrected records")

        cursor.close()
        db.disconnect()

        return True

    except Exception as e:
        print(f"   ✗ Error updating database: {e}")
        db.connection.rollback()
        db.disconnect()
        return False


def main():
    """Main execution."""

    # Recalculate rankings
    result = recalculate_all_rankings()

    if not result:
        print("\n✗ Failed to recalculate rankings")
        return

    rankings, csv_file = result

    # Ask user if they want to update database
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"\n✓ Corrected rankings exported to: {csv_file}")
    print(f"✓ Total records: {len(rankings)}")
    print("\nPlease review the CSV file to verify correctness.")

    response = input("\nUpdate database with corrected rankings? (yes/no): ").strip().lower()

    if response == 'yes':
        success = update_database(rankings)
        if success:
            print("\n" + "=" * 80)
            print("✓✓✓ DATABASE UPDATED SUCCESSFULLY ✓✓✓")
            print("=" * 80)
            print("\nYou can now:")
            print("1. Run validate_itf_data.py to verify everything")
            print("2. Update your Excel file from the CSV if needed")
        else:
            print("\n✗ Database update failed")
    else:
        print("\nDatabase not updated. CSV file saved for review.")


if __name__ == '__main__':
    main()
