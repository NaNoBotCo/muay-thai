# Muay Thai

The eight limbs, the thirty named techniques, the four old schools, the ceremony, and
527 places to train in 58 countries — bilingual English and Thai,
every claim tiered and sourced.

**Live:** https://motdang.net/muay-thai · https://nanobotco.github.io/muay-thai/

Made by [hongdam.net](https://hongdam.net/), a bilingual web studio in Chiang Rai.

## What is in it

129 records across 18 types,
394 links between them, 169 sources, 266 fields
written in Thai, 113 pictures each with its author and licence.

## The three findings

**The curriculum is named after pictures, not movements.** The two lists of fifteen on the
Thai Wikipedia article at revision 13177866 give thirty named techniques.
29 of the 30 name a picture and one names the movement — and it does
that in Sanskrit. 14 name a figure from the Ramakien or its Hindu antecedents.
The full table is printed at `/names/` so a reader who would classify a row differently is
looking at the same row.

**OpenStreetMap barely knows this sport exists, and where it does, the gyms said so
themselves.** Two Overpass queries — one for the tag, one for the name in every script the
sport is written in — return 527 places in 58 countries.
252 were found by name only; `sport=muay_thai` is used fewer than
fifty times worldwide. A published figure puts overseas gyms above 3,800, so this is a
floor and the page says so.

**The record remembers 248 Thai fighters and five Thai women.** Wikidata's census of people
with the occupation Thai boxer holds 1186 people. That is a measurement of who
gets written about.

## Build

```
python3 tools/fetch_wiki.py          # the drafting corpus (gitignored)
python3 tools/fetch_geo.py           # country outlines, Natural Earth
python3 tools/harvest_osm.py --gyms  # gyms, camps and stadiums, worldwide
python3 tools/harvest_wikidata.py    # the roster
python3 tools/harvest_maemai.py      # the thirty names, off the article's wikitext
python3 tools/harvest_commons.py --harvest --apply
python3 tools/ingest_own.py --to <record> --apply   # our own pictures
./publish.sh                         # validate, build, draw, check links, into docs/
python3 tools/serve.py 8816          # a local preview, mounted where the host mounts it
```

## Licence

Records and text CC BY 4.0. Harvested rows keep their own: OpenStreetMap ODbL 1.0,
Wikidata CC0, Wikipedia CC BY-SA 4.0, pictures per file with the author beside each one.
Code MIT. See NOTICE.txt.

<!-- fleet-roster -->

## Elsewhere from the same publisher

- [Mot Dang](https://motdang.net/) — city directory for Chiang Mai and Chiang Rai
- [The Mae Hong Son Loop](https://nanobotco.github.io/mae-hong-son-loop/) — motorcycling the 600 km loop out of Chiang Mai — curves counted, air measured
- [Roads of Chiang Mai](https://motdang.net/roads/) — the square of 1296, four rings, and what each one did to the city — counted from the map
- [wichaa](https://wichaa.net/) — Lanna manuscripts, the amulet market, and the traditions around them
- [Hand Poke](https://nanobotco.github.io/hand-poke/) — 28 traditions of marking skin by hand — the leg-tattoo zone of Burma, the Shan States and Lanna, counted
- [Black Holes, Drawn](https://nanobotco.github.io/black-holes/) — black holes modelled and drawn from the equations — generators, the past, present and future, the legends
- [Quantum Computing, plainly](https://nanobotco.github.io/quantum-computing/) — the history and theory of quantum computing in plain words, with demos; refreshed weekly
- [Goin' Fast](https://nanobotco.github.io/goin-fast/) — a dirt-simple explainer about speed — twenty measured speeds from the ground under the house to light, and what each one costs
- [The Three-Body Problem](https://nanobotco.github.io/three-body/) — the mathematics of the three-body problem in plain words, with the orbits found rather than copied
- [Amulet Atlas](https://nanobotco.github.io/amulet-atlas/) — amulets, charms and talismans worldwide
- [Carolina Barbecue](https://nanobotco.github.io/carolina-barbecue/) — barbecue in North and South Carolina
- [Wing Country](https://nanobotco.github.io/buffalo-wings/) — the American chicken wing
- [Pink Box](https://nanobotco.github.io/pink-box/) — the American mom-and-pop donut shop
- [Basque Tables](https://nanobotco.github.io/basque-tables/) — Basque dining rooms of California, Nevada and Idaho
- [Pinot Country](https://nanobotco.github.io/pinot-noir/) — pinot noir: the vine, the regions, the cellars
- [Care Abroad](https://nanobotco.github.io/care-abroad/) — treatment across borders, with published prices and their dates
- [Thai Roots](https://nanobotco.github.io/thairoots/) — a root dictionary of Thai, with a word decomposer
- [The index](https://nanobotco.github.io/index/) — every corpus, site and repository, counted
- [Uptake](https://nanobotco.github.io/uptake/) — a field manual on publishing for machines that copy
- [NaNoBotCo](https://nanobotco.github.io/) — the portal
- [ฮักฝรั่ง](https://hakfarang.net/) — เรื่องเงิน วีซ่า และชีวิตกับแฟนฝรั่ง
- [Offrampt](https://offrampt.net/) — turning crypto into spendable local money, Thailand first

All of it, counted: https://nanobotco.github.io/index/ · roster as JSON: https://nanobotco.github.io/index/fleet.json
