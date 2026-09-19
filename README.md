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
