#!/usr/bin/env python3
"""
Initial data population script
Usage:
    python scripts/init_data.py --days 7        # Scrape last 7 days
    python scripts/init_data.py --from 2024-12-01 --to 2024-12-22
    python scripts/init_data.py --demo          # Create demo data
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models import Race, Entry, Horse, Jockey, Training
from app.services.scraper import (
    RaceListScraper,
    RaceDetailScraper,
    HorseScraper,
    JockeyScraper,
    TrainingScraper,
)


def create_demo_data(db: Session):
    """Create demo data for testing"""
    print("Creating demo data...")

    # Demo horses
    demo_horses = [
        {"horse_id": "demo001", "name": "デモホース1", "sex": "牡", "birth_year": 2020, "father": "ディープインパクト"},
        {"horse_id": "demo002", "name": "デモホース2", "sex": "牝", "birth_year": 2021, "father": "キタサンブラック"},
        {"horse_id": "demo003", "name": "デモホース3", "sex": "牡", "birth_year": 2020, "father": "ハーツクライ"},
    ]

    for h in demo_horses:
        existing = db.query(Horse).filter(Horse.horse_id == h["horse_id"]).first()
        if not existing:
            horse = Horse(**h)
            db.add(horse)
            print(f"  Added horse: {h['name']}")

    # Demo jockeys
    demo_jockeys = [
        {"jockey_id": "demo01", "name": "デモ騎手1", "win_rate": 15.5, "place_rate": 28.0},
        {"jockey_id": "demo02", "name": "デモ騎手2", "win_rate": 12.3, "place_rate": 25.5},
    ]

    for j in demo_jockeys:
        existing = db.query(Jockey).filter(Jockey.jockey_id == j["jockey_id"]).first()
        if not existing:
            jockey = Jockey(**j)
            db.add(jockey)
            print(f"  Added jockey: {j['name']}")

    # Demo race
    demo_race_id = "demo00000001"
    existing_race = db.query(Race).filter(Race.race_id == demo_race_id).first()
    if not existing_race:
        race = Race(
            race_id=demo_race_id,
            date=date.today(),
            course="東京",
            race_number=11,
            race_name="デモステークス",
            distance=2000,
            track_type="芝",
            weather="晴",
            condition="良",
            grade="G2",
        )
        db.add(race)
        print(f"  Added race: {race.race_name}")

        # Demo entries
        for i, (horse, jockey) in enumerate(zip(demo_horses, demo_jockeys + [demo_jockeys[0]]), 1):
            entry = Entry(
                race_id=demo_race_id,
                horse_id=horse["horse_id"],
                jockey_id=jockey["jockey_id"],
                frame_number=i,
                horse_number=i,
                weight=57.0 if horse["sex"] == "牡" else 55.0,
                odds=3.0 + i * 1.5,
                popularity=i,
            )
            db.add(entry)

        # Demo training data
        for i, horse in enumerate(demo_horses, 1):
            training = Training(
                race_id=demo_race_id,
                horse_id=horse["horse_id"],
                horse_number=i,
                training_course="栗東坂路",
                training_time="52.5",
                lap_times="13.2-12.8-12.5-14.0",
                training_rank="B" if i == 1 else "A",
            )
            db.add(training)
            print(f"  Added training for: {horse['name']}")

    db.commit()
    print("Demo data created successfully!")


def scrape_historical_data(
    db: Session,
    start_date: date,
    end_date: date,
    include_training: bool = True,
):
    """Scrape historical race data"""
    print(f"Scraping races from {start_date} to {end_date}...")

    list_scraper = RaceListScraper()
    detail_scraper = RaceDetailScraper()
    horse_scraper = HorseScraper()
    jockey_scraper = JockeyScraper()
    training_scraper = TrainingScraper()

    current_date = start_date
    total_races = 0
    total_entries = 0

    while current_date <= end_date:
        print(f"\n=== Processing {current_date} ===")

        try:
            races = list_scraper.scrape(current_date)
        except Exception as e:
            print(f"  Error getting race list: {e}")
            current_date += timedelta(days=1)
            continue

        if not races:
            print("  No races found")
            current_date += timedelta(days=1)
            continue

        print(f"  Found {len(races)} races")

        for race_info in races:
            race_id = race_info["race_id"]

            # Check if race already exists
            existing = db.query(Race).filter(Race.race_id == race_id).first()
            if existing:
                print(f"    Race {race_id} already exists, skipping")
                continue

            try:
                # Get race detail
                detail = detail_scraper.scrape(race_id)

                # Create Race record
                race = Race(
                    race_id=race_id,
                    date=current_date,
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
                entries = detail.get("entries", [])
                for entry_data in entries:
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
                                    sex=horse_info.get("sex", entry_data.get("sex", "")),
                                    birth_year=horse_info.get("birth_year", 2020),
                                    father=horse_info.get("father"),
                                    mother=horse_info.get("mother"),
                                    mother_father=horse_info.get("mother_father"),
                                    trainer=horse_info.get("trainer"),
                                )
                                db.add(horse)
                            except Exception as e:
                                print(f"      Warning: Could not get horse {horse_id}: {e}")
                                horse = Horse(
                                    horse_id=horse_id,
                                    name=entry_data.get("horse_name", "Unknown"),
                                    sex=entry_data.get("sex", ""),
                                    birth_year=2020,
                                )
                                db.add(horse)

                    # Get or create jockey
                    if jockey_id:
                        jockey = db.query(Jockey).filter(Jockey.jockey_id == jockey_id).first()
                        if not jockey:
                            try:
                                jockey_info = jockey_scraper.scrape(jockey_id)
                                jockey = Jockey(
                                    jockey_id=jockey_id,
                                    name=jockey_info.get("name", entry_data.get("jockey_name", "")),
                                    win_rate=jockey_info.get("win_rate"),
                                    place_rate=jockey_info.get("place_rate"),
                                    show_rate=jockey_info.get("show_rate"),
                                )
                                db.add(jockey)
                            except Exception:
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
                        result=entry_data.get("result"),
                        finish_time=entry_data.get("finish_time"),
                    )
                    db.add(entry)
                    total_entries += 1

                # Get training data if requested
                if include_training:
                    try:
                        training_data = training_scraper.scrape(race_id)
                        for t_data in training_data:
                            training = Training(
                                race_id=race_id,
                                horse_id=t_data.get("horse_id", ""),
                                horse_number=t_data.get("horse_number"),
                                training_course=t_data.get("training_course"),
                                training_time=t_data.get("training_time"),
                                lap_times=t_data.get("lap_times"),
                                training_rank=t_data.get("training_rank"),
                            )
                            db.add(training)
                    except Exception as e:
                        print(f"      Warning: Could not get training data: {e}")

                db.commit()
                total_races += 1
                print(f"    Saved: {race_id} ({len(entries)} entries)")

            except Exception as e:
                db.rollback()
                print(f"    Error processing {race_id}: {e}")
                continue

        current_date += timedelta(days=1)

    print(f"\n=== Summary ===")
    print(f"Total races saved: {total_races}")
    print(f"Total entries saved: {total_entries}")


def main():
    parser = argparse.ArgumentParser(description="Initialize database with race data")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Create demo data only",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Scrape last N days of data",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--no-training",
        action="store_true",
        help="Skip training data scraping",
    )

    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.demo:
            create_demo_data(db)
        elif args.days:
            end_date = date.today()
            start_date = end_date - timedelta(days=args.days - 1)
            scrape_historical_data(
                db, start_date, end_date, include_training=not args.no_training
            )
        elif args.from_date:
            start_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
            end_date = (
                datetime.strptime(args.to_date, "%Y-%m-%d").date()
                if args.to_date
                else date.today()
            )
            scrape_historical_data(
                db, start_date, end_date, include_training=not args.no_training
            )
        else:
            print("Usage:")
            print("  python scripts/init_data.py --demo        # Create demo data")
            print("  python scripts/init_data.py --days 7      # Scrape last 7 days")
            print("  python scripts/init_data.py --from 2024-12-01 --to 2024-12-22")
            print()
            print("Options:")
            print("  --no-training    Skip training data scraping")
    finally:
        db.close()


if __name__ == "__main__":
    main()
