#!/usr/bin/env python3
"""Independent read-back validation of the delivered CSV/GeoJSON files."""
import csv, hashlib, json, math, pathlib
from shapely.geometry import Point, shape
B=pathlib.Path(__file__).resolve().parent
p=json.loads((B/'provenance.json').read_text())
rows=list(csv.DictReader((B/'cambodia_fuel_stations.csv').open(encoding='utf-8-sig',newline='')))
g=json.loads((B/'cambodia_fuel_stations.geojson').read_text())['features']
boundary=shape(json.loads((B/'cambodia_filter_boundary.geojson').read_text())['geometry'])
excluded=list(csv.DictReader((B/'excluded_osm_objects.csv').open(encoding='utf-8-sig',newline='')))
pairs=list(csv.DictReader((B/'potential_duplicate_pairs.csv').open(encoding='utf-8-sig',newline='')))
ids={(x['osm_type'],x['osm_id']) for x in rows}
assert len(rows)==len(g)==p['output_rows']==1650
assert len(ids)==len(rows)
assert len(rows)+len(excluded)==p['source_unique_tagged_objects']==1671
assert len(pairs)==p['potential_duplicate_pairs']==25
assert len(excluded)==p['excluded_objects']==21
assert boundary.is_valid
for r,f in zip(rows,g):
    assert f['id']==r['osm_type']+'/'+r['osm_id']
    lat,lon=float(r['latitude']),float(r['longitude'])
    assert math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180
    assert boundary.covers(Point(lon,lat))
    assert abs(lon-f['geometry']['coordinates'][0])<=5.01e-8
    assert abs(lat-f['geometry']['coordinates'][1])<=5.01e-8
    assert r['osm_url']=='https://www.openstreetmap.org/'+f['id']
    assert r['source_snapshot_utc']=='2026-09-30T20:22:42Z'
    raw=json.loads(r['source_tags_json']);addr=json.loads(r['address_tags_json'])
    assert raw['amenity']=='fuel'
    assert addr=={k:v for k,v in raw.items() if k.startswith('addr:')}
    escaped=set(filter(None,r['csv_escaped_fields'].split(';')))
    for col,tag in [('name','name'),('name_km','name:km'),('name_en','name:en'),('brand','brand'),('operator','operator')]:
        value=r[col][1:] if col in escaped else r[col]
        assert value==raw.get(tag,'')
    expected_key=next((k for k in ['name','name:en','name:km'] if raw.get(k)), '')
    assert r['display_name_source_tag']==expected_key
    assert (r['display_name'][1:] if 'display_name' in escaped else r['display_name'])==raw.get(expected_key,'')
    for col,v in r.items():
        assert not v or (v[0] not in '\t\r\n' and (not v.lstrip() or v.lstrip()[0] not in '=+-@')), (f['id'],col)
    for peer in filter(None,r['potential_duplicate_osm_objects'].split(';')):
        typ,num=peer.split('/');assert (typ,num) in ids
for e in excluded:
    assert e['reason']=='representative_point_outside_cambodia_osm_boundary'
    assert not boundary.covers(Point(float(e['longitude']),float(e['latitude'])))
for name,digest in p['output_sha256'].items():
    assert hashlib.sha256((B/name).read_bytes()).hexdigest()==digest
summary={'status':'PASS','csv_rows':len(rows),'geojson_features':len(g),'unique_identities':len(ids),'rounded_csv_points_inside_cambodia_boundary':len(rows),'excluded_points_outside_cambodia_boundary':len(excluded),'exact_source_text_preserved':True,'safe_csv_text_cells':True,'output_checksums_verified':len(p['output_sha256']),'name_rows':sum(bool(r['display_name']) for r in rows),'address_rows':sum(bool(r['address']) for r in rows),'potential_duplicate_pairs':len(pairs)}
print(json.dumps(summary,indent=2))
