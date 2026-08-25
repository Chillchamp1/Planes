#!/usr/bin/env python3
"""One day of flights over Germany, from OpenSky ADS-B records.

Usage:
    python3 build_planes.py <flightlist.csv or .csv.gz> <YYYY-MM-DD> \
        --airports ourairports-data/airports.csv -o data/planes.json

There is no GTFS for aviation -- flight schedules are commercial data (IATA
SSIM), sold by OAG and Cirium, not published openly. What IS open is actual
radar: the OpenSky Network crowdsources ADS-B receivers worldwide and
reconstructs a flight list -- callsign, aircraft, origin airport, destination
airport, first-seen and last-seen timestamps -- which is exactly the shape a
GTFS trip already is, minus the timetable. ActiveConclusion's COVID19_AirTraffic
repository mirrors OpenSky's own monthly exports as plain CSV on GitHub, so it
is reachable without an account.

The day has to be chosen with the same honesty a GTFS date gets. The mirror
only covers January-April 2020, which means picking a day inside the window
that was NOT depressed by the pandemic: European travel restrictions began
in mid-March, so a January Wednesday is real, ordinary 2020 traffic, not a
locked-down sky. Wednesday 15 January 2020 is the default and is what ships.

first-seen and last-seen are not gate times -- first-seen is when a departing
aircraft is first caught by a receiver (usually seconds after wheels-up),
last-seen is the last message before landing or leaving coverage. Close enough
to treat as departure and arrival for an animation; the difference is a
caveat, not an error.
"""
import argparse, csv, gzip, io, json, math, os, sys
from datetime import date, timedelta

# Distance from the German endpoint decides the category. Domestic and
# European aircraft look different from long-haul in real life -- shorter
# stage lengths, more frequent, smaller aircraft -- so this reads closer to
# the truth than any name-based guess would, and it needs no external data.
EARTH_KM = 6371.0

def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))

CLASSES = ["domestic", "european", "longhaul"]

def classify(km, both_de):
    if both_de:
        return "domestic"
    return "european" if km < 3000 else "longhaul"


def load_airports(path):
    """ICAO/IATA/old-code -> (lat, lon, name, municipality). OurAirports
    reassigns a closed airport's ident (Tegel is 'DE-0876' now) and moves its
    old codes into a free-text keywords column, so those are indexed too --
    otherwise every airport that closed before this file was built vanishes
    from a dataset about when it was still open."""
    air = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rec = (float(r["latitude_deg"]), float(r["longitude_deg"]),
                       r["name"], r["municipality"])
            except ValueError:
                continue
            for key in (r["icao_code"], r["gps_code"], r["ident"], r["iata_code"]):
                if key:
                    air.setdefault(key, rec)
            for kw in (r["keywords"] or "").split(","):
                kw = kw.strip()
                if len(kw) in (3, 4) and kw.isalnum():
                    air.setdefault(kw, rec)
    return air


def open_maybe_gz(path):
    return gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") \
        else open(path, encoding="utf-8")


def parse_ts(s):
    # "2019-12-31 00:19:47+00:00" -- always UTC, always this shape.
    from datetime import datetime, timezone
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flightlist")
    ap.add_argument("date", help="YYYY-MM-DD, matches the CSV's own 'day' column")
    ap.add_argument("--airports", required=True)
    ap.add_argument("-o", "--out", default="data/planes.json")
    ap.add_argument("--note", default="")
    ap.add_argument("--bbox", default="4.5,46.5,16.0,55.5",
                    help="a flight is kept if either endpoint falls inside")
    ap.add_argument("--tz-offset", type=float, default=1.0,
                    help="hours added to UTC for display -- CET in January")
    args = ap.parse_args()
    minlon, minlat, maxlon, maxlat = (float(x) for x in args.bbox.split(","))

    air = load_airports(args.airports)
    target = date.fromisoformat(args.date)

    # A flight is attributed to the day its departure falls on in local
    # time, not the source file's own "day" column (which tags by *last*
    # message, i.e. arrival). GTFS makes the same choice for night trains --
    # a service starting at 23:50 belongs to that day even if it lands after
    # midnight -- and for the same reason: it keeps every trip's own time
    # non-negative, extending past 24:00 instead of running below zero. The
    # window is +-1 day either side of the CSV's own day tag, which is all a
    # local-time reattribution could ever move a flight by.
    window = {(target - timedelta(days=1)).isoformat(),
              target.isoformat(), (target + timedelta(days=1)).isoformat()}

    kept, dropped_unresolved, dropped_incomplete, out_of_frame, wrong_day, \
        dropped_same, dropped_slow = [], 0, 0, 0, 0, 0, 0
    with open_maybe_gz(args.flightlist) as f:
        for r in csv.DictReader(f):
            if r["day"][:10] not in window:
                continue
            o, d = r["origin"], r["destination"]
            if not o.startswith("ED") and not d.startswith("ED"):
                continue
            if not o or not d:
                dropped_incomplete += 1
                continue
            if o not in air or d not in air:
                dropped_unresolved += 1
                continue
            olat, olon, oname, ocity = air[o]
            dlat, dlon, dname, dcity = air[d]
            if not (minlon <= olon <= maxlon and minlat <= olat <= maxlat) and \
               not (minlon <= dlon <= maxlon and minlat <= dlat <= maxlat):
                out_of_frame += 1
                continue
            try:
                dep, arr = parse_ts(r["firstseen"]), parse_ts(r["lastseen"])
            except ValueError:
                continue
            if arr <= dep:
                continue
            local_dep = dep + timedelta(hours=args.tz_offset)
            if local_dep.date() != target:
                wrong_day += 1
                continue
            if o == d:
                dropped_same += 1
                continue
            km = haversine(olat, olon, dlat, dlon)
            hours = (arr - dep).total_seconds() / 3600
            # A transponder kept transmitting on the ground reads as a
            # flight that took a day to go nowhere -- firstseen/lastseen are
            # radar coverage, not gate times, and this is the artifact that
            # comes with that trade. No aircraft averages below ~500 km/h
            # over any real distance once taxi, climb and descent (call it
            # 90 minutes) are allowed for; below that, the timestamps are
            # coverage gaps, not a flight.
            if hours > km / 500 + 1.5:
                dropped_slow += 1
                continue
            kept.append({
                "callsign": (r["callsign"] or "").strip(),
                "typecode": r["typecode"], "o": o, "d": d,
                "olat": olat, "olon": olon, "oname": oname, "ocity": ocity,
                "dlat": dlat, "dlon": dlon, "dname": dname, "dcity": dcity,
                "dep": dep, "arr": arr, "km": km,
                "both_de": o.startswith("ED") and d.startswith("ED"),
            })

    print(f"{args.date}: {len(kept)} kept, {dropped_incomplete} missing an "
          f"endpoint, {dropped_unresolved} with an unresolved airport code, "
          f"{out_of_frame} with both endpoints outside the frame, "
          f"{wrong_day} reattributed to a neighbouring day by local time "
          f"and so not this day after all, {dropped_same} same airport to "
          f"itself, {dropped_slow} implausibly slow for their distance "
          f"(a transponder still on the ground, not a real flight)")

    from datetime import datetime as _dt, timezone as _tz
    midnight_local = _dt(target.year, target.month, target.day,
                         tzinfo=_tz(timedelta(hours=args.tz_offset)))
    def minutes(t):
        # t is UTC; midnight_local carries the display offset, so the
        # subtraction lands directly in local minutes-since-midnight, and a
        # flight that lands after local midnight simply reads past 1440.
        return (t - midnight_local).total_seconds() / 60

    stations, st_index = [], {}
    def idx(code, lat, lon, name, city):
        if code in st_index:
            return st_index[code]
        i = len(stations)
        st_index[code] = i
        label = city if city else name
        stations.append([round(lon, 4), round(lat, 4), label])
        return i

    counts = {c: 0 for c in CLASSES}
    trips = []
    for t in kept:
        oi = idx(t["o"], t["olat"], t["olon"], t["oname"], t["ocity"])
        di = idx(t["d"], t["dlat"], t["dlon"], t["dname"], t["dcity"])
        dep_m, arr_m = round(minutes(t["dep"])), round(minutes(t["arr"]))
        cls = classify(t["km"], t["both_de"])
        counts[cls] += 1
        label = t["callsign"] or t["typecode"] or ""
        trips.append({"c": CLASSES.index(cls), "n": label,
                      "s": [[oi, dep_m, dep_m], [di, arr_m, arr_m]]})

    doc = {"tunit": "min", "date": target.isoformat(),
           "weekday": target.strftime("%A"), "classes": CLASSES,
           "counts": counts, "source": "OpenSky Network via ActiveConclusion/COVID19_AirTraffic",
           "note": args.note, "stations": stations, "trips": trips}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"), ensure_ascii=False)
    print(f"{args.out}: {len(trips)} trips, {len(stations)} airports, "
          f"{os.path.getsize(args.out)/1e6:.2f} MB")
    for c in CLASSES:
        print(f"  {c:<10} {counts[c]}")


if __name__ == "__main__":
    main()
