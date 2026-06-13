"""Import batch FootyStats CSV into football.db."""
from __future__ import annotations

import os
import sys

from data_loader import load_csv

BASE = r"c:\Users\crazy\OneDrive\Desktop\DATABASE FOOTYSTATS"

IMPORTS = [
    ("south-korea-k-league-1.csv", "South Korea", "K League 1"),
    ("south-korea-k-league-2.csv", "South Korea", "K League 2"),
    ("spain-la-liga.csv", "Spain", "La Liga"),
    ("spain-segunda-division.csv", "Spain", "Segunda Division"),
    ("sweden-allsvenskan.csv", "Sweden", "Allsvenskan"),
    ("sweden-superettan.csv", "Sweden", "Superettan"),
    ("switzerland-super-league.csv", "Switzerland", "Super League"),
    ("turkey-super-lig.csv", "Turkey", "Super Lig"),
    ("ukraine-ukrainian-premier-league.csv", "Ukraine", "Ukrainian Premier League"),
    ("uruguay-primera-division.csv", "Uruguay", "Primera Division"),
    ("usa-mls.csv", "USA", "MLS"),
    ("argentina-prim-b-nacional.csv", "Argentina", "Prim B Nacional"),
    ("argentina-primera-division.csv", "Argentina", "Primera Division"),
    ("australia-a-league.csv", "Australia", "A League"),
    ("austria-2-liga.csv", "Austria", "2 Liga"),
    ("austria-bundesliga.csv", "Austria", "Bundesliga"),
    ("belgium-first-division-b.csv", "Belgium", "First Division B"),
    ("belgium-pro-league.csv", "Belgium", "Pro League"),
    ("bolivia-lfpb.csv", "Bolivia", "LFPB"),
    ("brazil-serie-a.csv", "Brazil", "Serie A"),
    ("brazil-serie-b.csv", "Brazil", "Serie B"),
    ("bulgaria-first-league.csv", "Bulgaria", "First League"),
    ("chile-primera-division.csv", "Chile", "Primera Division"),
    ("china-chinese-super-league.csv", "China", "Chinese Super League"),
    ("croatia-prva-hnl.csv", "Croatia", "Prva HNL"),
    ("czech-republic-first-league.csv", "Czech Republic", "First League"),
    ("denmark-1st-division.csv", "Denmark", "1st Division"),
    ("denmark-superliga.csv", "Denmark", "Superliga"),
    ("england-premier-league.csv", "England", "Premier League"),
    ("estonia-meistriliiga.csv", "Estonia", "Meistriliiga"),
    ("finland-kakkonen.csv", "Finland", "Kakkonen"),
    ("france-ligue-2.csv", "France", "Ligue 2"),
    ("germany-bundesliga.csv", "Germany", "Bundesliga"),
    ("italy-serie-a.csv", "Italy", "Serie A"),
    ("netherlands-eredivisie.csv", "Netherlands", "Eredivisie"),
    ("poland-1-liga.csv", "Poland", "1 Liga"),
    ("poland-ekstraklasa.csv", "Poland", "Ekstraklasa"),
    ("portugal-liga-nos.csv", "Portugal", "Liga Nos"),
    ("republic-of-ireland-first-division.csv", "Republic of Ireland", "First Division"),
    ("republic-of-ireland-premier-division.csv", "Republic of Ireland", "Premier Division"),
]


def main() -> int:
    total_added = 0
    total_skipped = 0
    failed = []

    for filename, country, championship in IMPORTS:
        path = os.path.join(BASE, filename)
        league = f"{country} - {championship}"
        if not os.path.isfile(path):
            failed.append((filename, "file not found"))
            print(f"MISSING  {filename}")
            continue

        result = load_csv(path, country=country, championship=championship)
        added = result.get("rows_added", 0)
        skipped = result.get("rows_skipped", 0)
        errors = result.get("errors", [])
        total_added += added
        total_skipped += skipped

        if errors:
            failed.append((filename, errors[0]))
            print(f"ERROR    {league}: {errors[0]}")
        else:
            print(f"OK       {league}: +{added} (skip {skipped})")

    print("-" * 60)
    print(f"TOTALE: +{total_added} partite | skip {total_skipped} | errori {len(failed)}")

    try:
        from database import invalidate_db_cache
        invalidate_db_cache()
    except ImportError:
        pass

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
