# Cambodia fuel station POIs from OpenStreetMap

**1,650 mapped fuel POIs**, extracted from OpenStreetMap data as of **2026-09-30 20:22:42 UTC**. This is a nationwide OSM snapshot, **not a complete census of physical or currently operating stations**.

The main CSV has names, WGS84 latitude/longitude, available source addresses, brands/operators, source object links, and quality flags. Missing source information stays blank. Of the 1,650 records, **1,282 have at least one of `name`, `name:en`, or `name:km`; only 90 have any address tags**, many of them partial. No addresses were reverse-geocoded or fabricated. This dataset does not use Google Maps data.

## Files

- `cambodia_fuel_stations.csv`: main dataset; UTF-8 with BOM, comma-separated, one row per OSM object
- `cambodia_fuel_stations.geojson`: the same 1,650 representative points, with original text values and source tags
- `provenance.json`: source checksums, counts, software versions, and validation results
- `potential_duplicate_pairs.csv`: 25 candidate pairs involving 41 objects; human review required
- `excluded_osm_objects.csv`: 21 fuel objects omitted because their representative point lies outside the OSM Cambodia boundary
- `cambodia_filter_boundary.geojson`: the OSM country boundary actually used to filter the points
- `extract_fuel.py`, `requirements.txt`, and `validate_dataset.py`: reproducible extraction and validation
- `LICENSE.txt`: attribution and data license

## Source and inclusion criteria

Source: [Geofabrik Cambodia extract](https://download.geofabrik.de/asia/cambodia.html), pinned file [cambodia-260930.osm.pbf](https://download.geofabrik.de/asia/cambodia-260930.osm.pbf).

- Data timestamp, read from the PBF header: `2026-09-30T20:22:42Z`
- Downloaded and processed: 2026-10-02
- Source size: 41,018,214 bytes
- Published MD5 verified: `6e3f552b943465811cb8a896e9325703`
- Source SHA-256: `00d121ff4a4a6b84ab5f2124b00e15d2463fdc57737d59d639084f41cd4892be`

All nodes, ways, and relations with the **exact tag `amenity=fuel`** were examined. The extract contained 1,575 nodes, 96 ways, and zero tagged relations (1,671 objects). The final 1,650 rows comprise 1,555 nodes and 95 ways. No objects had unusable geometry. No repeated exact OSM identities were encountered.

Objects tagged only with lifecycle-prefixed fuel tags, such as `disused:amenity=fuel`, are outside this query. `amenity=fuel` is not a guarantee of public road-vehicle access, current operations, a specific fuel product, or a conventional full-service petrol station. Informal or specialist fuel sellers may be present. Current status was not independently verified.

## Coordinates and boundary filtering

- Node coordinates are the original mapped location
- Closed fuel ways use a **point on surface** of their assembled polygon, so the point is inside the mapped area. This is not necessarily the entrance, pump, or road access point
- The script also supports line midpoints for non-area ways and assembled multipolygon relations. Neither fallback was needed in this snapshot
- CSV coordinates are rounded to seven decimal places; this reflects storage precision, not surveyed accuracy. GeoJSON retains calculated point precision
- The country filter is OSM [Cambodia boundary relation 49898](https://www.openstreetmap.org/relation/49898), assembled from the same source snapshot. Only points inside or on this boundary are retained
- Geofabrik region extracts include margins and complete geometries near borders; simply treating every object in the file as Cambodian would have retained 21 out-of-country points. Those are audited separately
- The boundary is OSM's representation at the snapshot date, not an authoritative resolution of territorial or border questions. Country extraction and OSM mapping gaps can still cause omissions

## Names and addresses

- `display_name` selects the first nonblank tag in this order: `name`, `name:en`, `name:km`. `display_name_source_tag` records that choice. Brand and operator are not substituted for an absent station name
- `name`, `name_km`, `name_en`, `brand`, and `operator` retain their respective source values (subject only to CSV safety escaping below)
- `address` uses `addr:full` if present; otherwise it joins available source address components. It is not a verified, standardized, or necessarily complete postal address
- `addr_*` columns preserve individual source components. `address_tags_json` preserves every source `addr:*` key, including keys not given a dedicated column
- `source_tags_json` retains the selected source name, brand, operator, address, fuel, access, source/date, and lifecycle tags. It is a selected subset, not the entire OSM object
- Contributor usernames, user IDs, and changeset IDs are not collected or exported
- The main source object URL links to the live OSM object. Its live content can differ from this snapshot

## Duplicate review and quality

Only identical `(osm_type, osm_id)` identities would be deduplicated. Separate objects are **not merged**, even if they might represent one station. Candidate pairs are flagged if representative points are within 40 metres (haversine distance) or source geometries intersect. Adjacent distinct stations can therefore be false positives; more distant duplicates can be missed.

Quality flags in this snapshot:

- `missing_address_tags`: 1,560 objects
- `missing_name`: 368 objects, meaning none of the three selected name tags was populated
- `potential_duplicate_site`: 41 objects in 25 candidate pairs

There are 702 blank raw `name` values, but many have a Khmer or English name tag. The separate `display_name` field reduces these blanks to 368 without changing the original fields.

## CSV safety

Text cells beginning with a spreadsheet formula trigger (`=`, `+`, `-`, `@`, including after whitespace) or tab/newline/carriage return are prefixed with a single apostrophe. The affected columns are listed in `csv_escaped_fields`; one row required this protection. The corresponding original text remains available in JSON/GeoJSON. Treat the JSON tag fields as data, not formulas. CSV readers should decode UTF-8 with BOM (`utf-8-sig` in Python).

## Reproduce

Use Python 3.12 with the pinned packages in `requirements.txt`:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p source
curl -fL -o source/cambodia-260930.osm.pbf https://download.geofabrik.de/asia/cambodia-260930.osm.pbf
curl -fL -o source/cambodia-260930.osm.pbf.md5 https://download.geofabrik.de/asia/cambodia-260930.osm.pbf.md5
python extract_fuel.py
python validate_dataset.py
```

The script verifies the published MD5, extracts the OSM header timestamp, and records a SHA-256 digest. Compare it with the pinned SHA-256 above. Archived source availability is controlled by Geofabrik; retain a private copy for long-term reproducibility if needed. Do not commit the `.venv`, `.deps`, downloaded PBF, or local transfer helpers. No paid APIs or API credentials are needed.

## Attribution and license

**© OpenStreetMap contributors**. Map data is made available under the [Open Data Commons Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). This derived dataset is provided under the same license. [OSM copyright and attribution information](https://www.openstreetmap.org/copyright). Extract processing by Geofabrik.

When redistributing or building on this dataset, preserve the attribution and comply with the ODbL, including applicable share-alike obligations. The data is supplied without a warranty of completeness, accuracy, current operation, or suitability for a particular purpose.
