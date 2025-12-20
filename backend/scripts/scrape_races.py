#!/usr/bin/env python3
"""
Race scraping script
Usage: python scripts/scrape_races.py --date 2024-12-22
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models import Race, Entry, Horse, Jockey
from app.services.scraper import RaceListScraper, RaceDetailScraper, HorseScraper


def scrape_and_save_races(target_date: date, db: Session):
    """Scrape races for a given date and save to database"""
    print(f"Scraping races for {target_date}...")

    # Get race list
    list_scraper = RaceListScraper()
    races = list_scraper.scrape(target_date)

    if not races:
        print("No races found")
        return 0

    print(f"Found {len(races)} races")

    # Get details for each race
    detail_scraper = RaceDetailScraper()
    horse_scraper = HorseScraper()

    saved_count = 0

    for race_info in races:
        race_id = race_info["race_id"]
        print(f"  Processing race {race_id}...")

        try:
            # Check if race already exists
            existing = db.query(Race).filter(Race.race_id == race_id).first()
            if existing:
                print(f"    Race {race_id} already exists, skipping")
                continue

            # Get race detail
            detail = detail_scraper.scrape(race_id)

            # Create Race record
            race = Race(
                race_id=race_id,
                date=target_date,
                course=detail.get("course", ""),
                race_number=detail.get("race_number", 0),
                race_name=detail.get("race_name"),
                distance=detail.get("distance", 0),
                track_type=detail.get("track_type", ""),
                weather=detail.get("weather"),
                condition=detail.get("condition"),
                grade=detail.get("grade"),
            )
            db.add(race)

            # Process entries
            for entry_data in detail.get("entries", []):
                horse_id = entry_data.get("horse_id")
                jockey_id = entry_data.get("jockey_id")

                # Get or create horse
                if horse_id:
                    horse = db.query(Horse).filter(Horse.horse_id == horse_id).first()
                    if not horse:
                        try:
                            horse_info = horse_scraper.scrape(horse_id)
                            horse = Horse(
                                horse_id=horse_id,
                                name=horse_info.get("name", entry_data.get("horse_name", "")),
                                sex=horse_info.get("sex", ""),
                                birth_year=horse_info.get("birth_year", 2020),
                                father=horse_info.get("father"),
                                mother=horse_info.get("mother"),
                                mother_father=horse_info.get("mother_father"),
                                trainer=horse_info.get("trainer"),
                                owner=horse_info.get("owner"),
                            )
                            db.add(horse)
                        except Exception as e:
                            print(f"    Warning: Could not get horse info for {horse_id}: {e}")
                            horse = Horse(
                                horse_id=horse_id,
                                name=entry_data.get("horse_name", "Unknown"),
                                sex="",
                                birth_year=2020,
                            )
                            db.add(horse)

                # Get or create jockey
                if jockey_id:
                    jockey = db.query(Jockey).filter(Jockey.jockey_id == jockey_id).first()
                    if not jockey:
                        jockey = Jockey(
                            jockey_id=jockey_id,
                            name=entry_data.get("jockey_name", "Unknown"),
                        )
                        db.add(jockey)

                # Create entry
                entry = Entry(
                    race_id=race_id,
                    horse_id=horse_id or "",
                    jockey_id=jockey_id,
                    frame_number=entry_data.get("frame_number"),
                    horse_number=entry_data.get("horse_number", 0),
                    weight=entry_data.get("weight"),
                    odds=entry_data.get("odds"),
                    popularity=entry_data.get("popularity"),
                )
                db.add(entry)

            db.commit()
            saved_count += 1
            print(f"    Saved race {race_id}")

        except Exception as e:
            db.rollback()
            print(f"    Error processing race {race_id}: {e}")
            continue

    return saved_count


def main():
    parser = argparse.ArgumentParser(description="Scrape race data from netkeiba")
    parser.add_argument(
        "--date",
        type=str,
        help="Target date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to scrape (default: 1)",
    )

    args = parser.parse_args()

    if args.date:
        start_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        start_date = date.today()

    db = SessionLocal()

    try:
        total_saved = 0
        for i in range(args.days):
            target = start_date - timedelta(days=i)
            saved = scrape_and_save_races(target, db)
            total_saved += saved

        print(f"\nTotal: Saved {total_saved} races")
    finally:
        db.close()


if __name__ == "__main__":
    main()
