"""Minimal command-line interface tying the modules together.

Example:
    python -m panchanga.cli --date 2026-01-15 --lat 12.9716 --lon 77.5946 \
        --tz Asia/Kolkata --ayanamsha lahiri
"""
from __future__ import annotations

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from . import ephemeris
from . import nakshatra as nakshatra_mod
from .ekadashi import classify_day
from .sunrise import Place, jd_to_utc_datetime


def _local_midnight_to_jd_ut(date_str: str, tz_name: str) -> float:
    tz = ZoneInfo(tz_name)
    local_midnight = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    utc_dt = local_midnight.astimezone(ZoneInfo("UTC"))
    ut_hour = utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600
    return ephemeris.julian_day_ut(utc_dt.year, utc_dt.month, utc_dt.day, ut_hour)


def main() -> None:
    parser = argparse.ArgumentParser(description="Panchanga: sunrise-anchored tithi/nakshatra/Ekadashi report")
    parser.add_argument("--date", required=True, help="Civil date, YYYY-MM-DD, in the given timezone")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--elevation", type=float, default=0.0)
    parser.add_argument("--tz", required=True, help="IANA timezone, e.g. Asia/Kolkata")
    parser.add_argument("--ayanamsha", default=ephemeris.DEFAULT_AYANAMSHA, choices=sorted(ephemeris.AYANAMSHA_MODES))
    args = parser.parse_args()

    ephemeris.set_ayanamsha(args.ayanamsha)
    place = Place(latitude_deg=args.lat, longitude_deg=args.lon, elevation_m=args.elevation)
    jd_midnight = _local_midnight_to_jd_ut(args.date, args.tz)

    report = classify_day(jd_midnight, place, args.date)
    tz = ZoneInfo(args.tz)

    print(f"Panchanga for {args.date} at ({args.lat}, {args.lon}), tz={args.tz}, ayanamsha={args.ayanamsha}")
    if report.sunrise_jd_ut is None:
        print(f"  {report.note}")
        return

    sunrise_local = jd_to_utc_datetime(report.sunrise_jd_ut).astimezone(tz)
    print(f"  Sunrise: {sunrise_local.isoformat()}")

    state = report.tithi_at_sunrise
    ends_local = jd_to_utc_datetime(state.ends_at_jd_ut).astimezone(tz)
    print(f"  Tithi at sunrise: #{state.index} {state.name}"
          f" (elongation {state.elongation_deg:.4f} deg, "
          f"{state.fraction_elapsed*100:.1f}% elapsed)")
    print(f"  Tithi ends at: {ends_local.isoformat()}")
    print(f"  Ekadashi by base sunrise rule: {report.is_ekadashi_by_sunrise_rule}")
    print(f"  Note: {report.note}")

    nak = nakshatra_mod.nakshatra_at(report.sunrise_jd_ut)
    nak_ends_local = jd_to_utc_datetime(nak.ends_at_jd_ut).astimezone(tz)
    print(f"  Nakshatra at sunrise: #{nak.index} {nak.name}"
          f" ({nak.fraction_elapsed*100:.1f}% elapsed)")
    print(f"  Nakshatra ends at: {nak_ends_local.isoformat()}")

    print(f"  Ayanamsha value: {ephemeris.ayanamsha_value(report.sunrise_jd_ut):.6f} deg")


if __name__ == "__main__":
    main()
