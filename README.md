# A day of flights over Germany

A 24-hour time-lapse of one real Wednesday of air traffic touching a German
airport, built from actual radar data. It is the same idea as
[the rail time-lapse project](https://github.com/Chillchamp1/github.io) this
was forked in spirit from — a dark map, a running clock, every scheduled
movement as a dot — applied to planes instead of trains.

**Live: https://chillchamp1.github.io/Planes/**

## Why this looks different from the rail maps

The rail project is built on GTFS — an open, standardised "here is exactly
what runs today" feed that transit agencies publish for free. Aviation has no
equivalent. Flight schedules (the IATA SSIM format airlines exchange with
airports) are commercial data, sold by OAG and Cirium; nobody publishes a
free, open "here is today's flight schedule" file, for Germany or anywhere.

What *is* open is radar. The [OpenSky Network](https://opensky-network.org/)
crowdsources ADS-B receivers worldwide and reconstructs a flight list —
callsign, aircraft, origin airport, destination airport, and the first and
last timestamp a receiver heard the aircraft. That is structurally the same
shape as a GTFS trip (two stops, a departure, an arrival), just without a
timetable behind it: it is what actually flew, not what was scheduled to.

This map is built from
[ActiveConclusion's COVID19_AirTraffic](https://github.com/ActiveConclusion/COVID19_AirTraffic)
mirror of OpenSky's own monthly exports, published as plain CSV on GitHub —
reachable without an OpenSky account.

## The date is 15 January 2020, and here is why

The mirror only covers January–April 2020 — it was built to document the
collapse of air traffic during COVID-19, not to be a general archive.
European travel restrictions began in mid-March 2020, so a **January**
Wednesday inside that window is real, ordinary traffic, not a locked-down
sky. **Wednesday 15 January 2020** was picked after checking: it isn't New
Year's week, it sits mid-month, and it has 2,687 flights touching Germany,
in line with the Wednesdays on either side of it (2,641 and 2,686).

This is not "today." It is the newest openly mirrored day that is not
COVID-depressed — the same trade the rail project makes when a country's
newest reachable timetable is a year or more old, stated plainly rather than
dressed up.

## What is on screen

**2,312 flights**, in three categories set purely by great-circle distance
from the German airport (not by airline or aircraft type, which this dataset
doesn't reliably carry):

- **Domestic** — within Germany
- **European** — under 3,000 km
- **Long-haul** — everything further: North America, the Gulf, East Asia

The frame is Germany's, centred on the country's own centre point (10.45°E,
51.2°N): Germany fills most of the height and the rest of Europe is hinted
at the edges rather than mapped. A flight to Los Angeles or Tokyo leaves the
frame within minutes, the same way a cross-border train used to leave the
edge of a single-country rail map — the dot keeps moving correctly, it just
stops being the subject.

A tall phone screen has to get its extra height from somewhere. Padding the
top and bottom is the obvious answer and the wrong one: it stretches the
frame from the Alps to central Sweden and leaves Germany filling barely a
third of the screen. So the latitude span is capped and the frame narrows
instead, never past the country plus a margin.

Each aircraft trails a streak showing **where it was over the last five
simulated minutes**. The trail is a window in time, not a fixed fraction of
the journey, so its length *is* the aircraft's speed: a long-haul jet at 900
km/h lays down nearly twice the streak a domestic hop does, because in those
five minutes it genuinely covered nearly twice the ground. Five is set
against the frame rather than the clock — about 6% of the map's width for a
jet at cruise, the same share of the frame the rail maps give an ICE.

Every airport in the day gets a dot, in three sizes by how much traffic it
actually saw — the same way the rail maps size a station by its number of
calls rather than from a fixed list. The busiest two dozen are named. Where
several airports share a city the busiest one keeps the name (London has
three in this data), except Berlin, which really did have two working
airports in January 2020 and gets both.

Hover a dot for its callsign and route. The strip behind the scrubber shows
departures per 15 minutes across the day.

## Known gaps and quality notes

- **first-seen and last-seen are not gate times.** first-seen is usually
  seconds after wheels-up (when a departing aircraft first appears on
  someone's receiver); last-seen is the last message before landing or
  leaving coverage. Close enough to animate as departure and arrival; the
  difference is a caveat, not an error.
- **A transponder can keep transmitting on the ground.** A handful of
  records showed a "flight" lasting most of a day between two airports 300
  km apart — the aircraft sat parked in range of a receiver long after
  landing. `build/build_planes.py` drops any flight whose average speed
  (great-circle distance ÷ duration) implies less than ~500 km/h once 1.5
  hours of taxi/climb/descent overhead is allowed for. On 15 January 2020
  that caught 5 flights out of 2,325 candidates, plus 8 more logged as
  departing and arriving at the *same* airport. A flat speed cutoff would
  have wrongly dropped hundreds of genuine short hops — a 150 km regional
  hop with 30 minutes of overhead legitimately averages under 300 km/h —
  so the cutoff scales with distance instead.
- **Only flights touching a German airport are shown.** Overflight traffic
  that merely crosses German airspace without landing or departing here is
  invisible to this dataset — OpenSky's flight list is built from
  approach/departure radar, not full enroute trajectories.
- **1,014 flights were dropped for missing an endpoint.** origin or
  destination is blank in the source data when OpenSky's own matching
  couldn't resolve an airport from the trajectory.
- **A closed airport can steal a live airport's code.** OurAirports
  reassigns the ident of an airport that has shut and moves its old ICAO
  code into a free-text `keywords` column. Those keywords have to be indexed
  or Berlin-Tegel — open and busy on this day, closed since 2020 — would
  vanish from the map. But indexing them naively lets a dead airport outrank
  a live one: Munich-Riem closed in **1992**, still carries `EDDM` in its
  keywords, and sorts ahead of Franz Josef Strauss in the file, which put
  all 672 Munich flights 24 km southwest of the airport they actually used.
  `load_airports()` now claims official codes in a first pass and lets
  keywords fill only what nothing live claims.
- **Airport labels come from the city, not the parish.** OurAirports'
  `municipality` is where the runway physically sits, which is often not the
  city the airport is known as — Brussels Airport is in Zaventem, Leipzig/
  Halle is in Schkeuditz, Milan Malpensa is in "Ferno (VA)". Parentheses and
  anything after a comma are stripped ("Paris (Roissy-en-France,
  Val-d'Oise)" → Paris), and a four-entry override table in the builder
  handles the rest.
- **A flight belongs to the day its departure falls on**, in local time
  (CET, UTC+1 in January) — not the source file's own `day` column, which
  tags by *last* message instead. This matters the way it matters for a
  night train: a flight departing 23:50 and landing after midnight needs to
  read as one continuous trip on the day it left, with its arrival time
  simply extending past 24:00, not as a flight arriving with a negative
  departure time.

## Rebuilding

```sh
git clone --depth 1 https://github.com/ActiveConclusion/COVID19_AirTraffic.git
git clone --depth 1 https://github.com/davidmegginson/ourairports-data.git

python3 build/build_planes.py \
    COVID19_AirTraffic/opensky_data/flightlist_20200101_20200131.csv.gz \
    2020-01-15 --airports ourairports-data/airports.csv \
    -o data/planes.json \
    --note "Source: OpenSky Network ADS-B records, mirrored as plain CSV by ActiveConclusion/COVID19_AirTraffic on GitHub."
```

(`build_planes.py` reads `.csv.gz` directly, no manual decompression needed.)

The basemap:

```sh
npm pack world-atlas@2   # unpacks to package/countries-10m.json (1:10m)
tar xf world-atlas-2.*.tgz

python3 build/build_geo_countries.py package/countries-10m.json \
    -o data/planes-geo.json \
    --home Germany \
    --neighbours France Austria Switzerland Czechia Poland Denmark \
        "United Kingdom" Ireland Netherlands Belgium Luxembourg Italy \
        Spain Portugal Norway Sweden Finland Slovakia Hungary Croatia \
        Slovenia Romania Ukraine Belarus Lithuania Latvia Estonia \
        Iceland Greece Turkey Morocco Algeria Tunisia \
        "Bosnia and Herzegovina" Serbia Montenegro Albania \
        "North Macedonia" Bulgaria Moldova Cyprus Malta Kosovo \
    --box -25.0 30.0 45.0 68.0

python3 build/simplify_geo.py data/planes-geo.json
```

Germany is filled as the home country; everything from Iceland to Turkey and
North Africa is drawn as thin border lines, so a flight's initial heading out
over a real coastline reads correctly without the file running to 180,000+
points of Natural Earth's full coastal detail. `simplify_geo.py` is the same
Douglas–Peucker pass the rail project uses throughout, at 400 m for the
outline and 600 m for the thinner interior borders.

## What this doesn't have yet

This is a first version, deliberately smaller in scope than the rail
project it borrows its look from:

- No zoom or pan — one fixed frame.
- No video export.
- No distinction by aircraft type or airline, only by distance.
- Flights fly great-circle-straight between airports. Real routings bend
  around airspace and follow tracks; this dataset carries only the two
  endpoints, so the line between them is the honest thing to draw.
- Frankfurt and Munich dominate visually because they are Germany's two
  long-haul hubs; that is real, not a rendering artefact.

## Layout

```
index.html              the whole visualisation, fetches its data at runtime
data/planes.json         generated flight list for one day
data/planes-geo.json     generated basemap (Germany + neighbours)
build/build_planes.py    OpenSky CSV + airport coordinates -> compact JSON
```

## Licensing

Code is MIT. Data is not — see [LICENSE](LICENSE) for the sources and their
own terms.
