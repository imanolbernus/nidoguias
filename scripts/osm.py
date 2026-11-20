"""Descarga lugares de OpenStreetMap (Overpass) para cada zona de NIDO y los guarda en data/osm.json."""
import json, time, urllib.request, urllib.parse, sys

ZONES = json.load(open('data/zones.json'))
SERVERS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']

# capa: filtros Overpass
Q = {
  'sup': ['nwr["shop"~"^(supermarket|convenience|greengrocer|butcher|bakery|deli)$"]', 'nwr["amenity"="marketplace"]'],
  'sal': ['nwr["amenity"="pharmacy"]', 'nwr["healthcare"="paediatrician"]', 'nwr["healthcare:speciality"~"paediatric"]', 'nwr["amenity"~"^(clinic|doctors)$"]["healthcare:speciality"~"paediatric"]'],
  'kid': ['nwr["leisure"="playground"]', 'nwr["leisure"="park"]["name"]', 'nwr["tourism"="museum"]', 'nwr["amenity"="library"]'],
  'res': ['nwr["amenity"~"^(restaurant|cafe|fast_food|ice_cream)$"]["name"]'],
  'col': ['nwr["amenity"~"^(school|kindergarten)$"]["name"]'],
  'tra': ['node["railway"="station"]["name"]', 'node["station"="subway"]["name"]'],
}

def poly(z):
    return ' '.join(f'{lat} {lng}' for lat, lng in ZONES[z]['poly'])

def query(z):
    p = poly(z)
    parts = []
    for layer, fs in Q.items():
        for f in fs:
            parts.append(f'{f}(poly:"{p}");')
    return '[out:json][timeout:120];(' + ''.join(parts) + ');out center tags;'

def fetch(q):
    data = urllib.parse.urlencode({'data': q}).encode()
    for attempt in range(4):
        for s in SERVERS:
            try:
                req = urllib.request.Request(s, data=data, headers={'User-Agent': 'nidoguias/0.1 (github.com/imanolbernus/nidoguias)'})
                return json.load(urllib.request.urlopen(req, timeout=180))
            except Exception as e:
                print('retry', s, e, file=sys.stderr); time.sleep(10 * (attempt + 1))
    raise SystemExit('Overpass no respondió')

def classify(t):
    a, sh, le, hc = t.get('amenity'), t.get('shop'), t.get('leisure'), t.get('healthcare', '')
    if sh or a == 'marketplace': return 'sup'
    if a == 'pharmacy' or hc == 'paediatrician' or 'paediatric' in t.get('healthcare:speciality', ''): return 'sal'
    if le in ('playground', 'park') or t.get('tourism') == 'museum' or a == 'library': return 'kid'
    if a in ('restaurant', 'cafe', 'fast_food', 'ice_cream'): return 'res'
    if a in ('school', 'kindergarten'): return 'col'
    if t.get('railway') == 'station' or t.get('station') == 'subway': return 'tra'

def kind(t):
    a, sh, le = t.get('amenity'), t.get('shop'), t.get('leisure')
    m = {'supermarket': 'Supermercado', 'convenience': 'Tienda de conveniencia', 'greengrocer': 'Frutería', 'butcher': 'Carnicería', 'bakery': 'Panadería', 'deli': 'Delicatessen'}
    if sh: return m.get(sh, 'Tienda')
    if a == 'marketplace': return 'Mercado'
    if a == 'pharmacy': return 'Farmacia'
    if a in ('clinic', 'doctors') or t.get('healthcare'): return 'Pediatría'
    if le == 'playground': return 'Juegos infantiles'
    if le == 'park': return 'Parque'
    if t.get('tourism') == 'museum': return 'Museo'
    if a == 'library': return 'Biblioteca'
    if a == 'kindergarten': return 'Escuela infantil'
    if a == 'school':
        op = t.get('operator:type', '') or t.get('school:type', '')
        return {'public': 'Colegio público', 'private': 'Colegio privado', 'religious': 'Colegio religioso'}.get(op, 'Colegio')
    if a == 'restaurant': return 'Restaurante'
    if a == 'cafe': return 'Cafetería'
    if a == 'fast_food': return 'Comida rápida'
    if a == 'ice_cream': return 'Heladería'
    if t.get('station') == 'subway': return 'Metro'
    return 'Estación de tren'

def kids(t):
    return any(t.get(k) in ('yes', 'designated') for k in ('kids_area', 'highchair', 'changing_table', 'kids_area:indoor'))

out = {'generated': time.strftime('%Y-%m-%d'), 'zones': {}}
for z in ZONES:
    res = fetch(query(z)); time.sleep(5)
    seen, rows = set(), {}
    for e in res.get('elements', []):
        t = e.get('tags', {})
        lat = e.get('lat') or e.get('center', {}).get('lat'); lng = e.get('lon') or e.get('center', {}).get('lon')
        l = classify(t)
        if not l or lat is None: continue
        name = t.get('name') or ('Juegos infantiles' if t.get('leisure') == 'playground' else None)
        if not name: continue
        key = (l, name.lower(), round(lat, 3), round(lng, 3))
        if key in seen: continue
        seen.add(key)
        addr = ' '.join(x for x in [t.get('addr:street', ''), t.get('addr:housenumber', '')] if x)
        row = [name, round(lat, 5), round(lng, 5), kind(t), addr, t.get('opening_hours', ''), 1 if kids(t) else 0]
        rows.setdefault(l, []).append(row)
    for l in rows: rows[l].sort(key=lambda r: (-r[6], r[3], r[0]))
    out['zones'][z] = rows
    print(z, {l: len(v) for l, v in rows.items()})
json.dump(out, open('data/osm.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
