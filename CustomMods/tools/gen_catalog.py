# -*- coding: utf-8 -*-
"""Generate the full weapon overclock catalog:
unpack all WeaponsNTools/<weapon>/Overclocks from game pak, then
- containers (Overclocks/OC_*.uasset): json dump -> quality (SCAT_*) + element refs in order
- elements (OC_BonusesAndPenalties/*): json dump -> UpgradeType + Amount
Output: CustomMods/data/weapon_overclock_catalog.json (+ .md quick reference)
"""
import os, re, json, subprocess, sys, tempfile, shutil

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WS = r'D:\drg-rc-drg.mod\ue-ugc-workspace\.bin'
UAS = os.path.join(WS, 'UAssetStudio.Cli.exe')
REPAK = os.path.join(WS, 'repak.exe')
PAK = r'D:\steam\steamapps\common\Deep Rock Galactic\FSD\Content\Paks\FSD-WindowsNoEditor.pak'
PAK_LIST = r'D:\drg-rc-drg.mod\_probe\pak_list.txt'
OUT_JSON = r'D:\drg-rc-drg.mod\DRGMod.CustomHazard\CustomMods\data\weapon_overclock_catalog.json'
OUT_MD = r'D:\drg-rc-drg.mod\DRGMod.CustomHazard\CustomMods\data\weapon_overclock_catalog.md'
WORK = r'D:\drg-rc-drg.mod\_probe\oc_all'
UE = 'VER_UE4_27'

QUALITY = {'SCAT_OC_Clean': 'Clean', 'SCAT_OC_Balanced': 'Balanced', 'SCAT_OC_Unstable': 'Unstable'}

# 1) which weapon dirs have Overclocks
lines = open(PAK_LIST, encoding='utf-8', errors='replace').read().splitlines()
weapons = []
for l in lines:
    if '/Overclocks/' not in l:
        continue
    m = re.match(r'FSD/Content/WeaponsNTools/([^/]+)/Overclocks/', l)
    if m and '/Audio/' not in l:
        weapons.append(m.group(1))
weapons = sorted(set(weapons))
print('weapons with Overclocks:', len(weapons))

# 2) unpack per-weapon (prefix + trailing * works with repak)
os.makedirs(WORK, exist_ok=True)
for i, w in enumerate(weapons):
    r = subprocess.run([REPAK, 'unpack', '--include', f'FSD/Content/WeaponsNTools/{w}/Overclocks/*',
                        '--output', WORK, PAK], capture_output=True, timeout=600)
    if (i + 1) % 10 == 0:
        print('unpacked', i + 1, '/', len(weapons), flush=True)

# 3) walk unpacked tree
containers, elements = {}, {}
for dirpath, _, files in os.walk(WORK):
    for f in files:
        if not f.endswith('.uasset'):
            continue
        p = os.path.join(dirpath, f)
        rel = os.path.relpath(p, WORK).replace(os.sep, '/')
        if '/OC_BonusesAndPenalties/' in rel:
            elements[f[:-7]] = p
        elif '/Overclocks/' in rel:
            containers[f[:-7]] = p
print('containers:', len(containers), 'elements:', len(elements))

def uas(cmd, path):
    r = subprocess.run([UAS] + cmd + ['--json'], capture_output=True, timeout=300)
    try:
        d = json.loads(r.stdout.decode('utf-8', errors='replace'))
    except Exception:
        return None
    return d if d.get('Status') == 'ok' else None

def load_dump(path):
    d = uas(['json', path, '--ue-version', UE], path)
    if not d:
        return None
    try:
        return json.load(open(d['Outputs'][0], encoding='utf-8'))
    except Exception:
        return None

# 4) parse elements: UpgradeType + Amount from export data
print('parsing elements...')
elem_data = {}
for i, (name, path) in enumerate(sorted(elements.items())):
    dump = load_dump(path)
    if not dump:
        continue
    ut, amt = None, None
    for exp in dump.get('Exports', []):
        for prop in exp.get('Data', []):
            if prop.get('Name') == 'UpgradeType' and isinstance(prop.get('Value'), str):
                ut = prop['Value'].split('::')[-1]
            elif prop.get('Name') == 'Amount':
                amt = prop.get('Value')
    if ut is not None or amt is not None:
        elem_data[name] = {'type': ut, 'amount': amt}
    if (i + 1) % 100 == 0:
        print('elements', i + 1, '/', len(elements), flush=True)
print('parsed elements:', len(elem_data))

# 5) parse containers: quality + element refs in CombinedUpgrades order
print('parsing containers...')
catalog = {}
for i, (name, path) in enumerate(sorted(containers.items())):
    if not name.startswith('OC_'):
        continue
    dump = load_dump(path)
    if not dump:
        continue
    weapon = None
    m = re.search(r'WeaponsNTools[/\\]([^/\\]+)[/\\]Overclocks', path)
    weapon = m.group(1) if m else '?'
    quality, refs = None, []
    namemap = set(dump.get('NameMap', []))
    for n in dump.get('NameMap', []):
        if n in QUALITY:
            quality = QUALITY[n]
    for exp in dump.get('Exports', []):
        for prop in exp.get('Data', []):
            if prop.get('Name') != 'CombinedUpgrades':
                continue
            for item in prop.get('Value', []):
                v = item.get('Value')
                if not isinstance(v, dict):
                    continue
                ap = v.get('AssetPath') or {}
                pathstr = ap.get('PackageName') or ap.get('AssetName') or ''
                if pathstr:
                    refs.append(pathstr.rstrip('/').rsplit('/', 1)[-1].split('.')[0])
    entry = {'asset': name, 'quality': quality, 'elements': refs}
    catalog.setdefault(weapon, []).append(entry)
    if (i + 1) % 50 == 0:
        print('containers', i + 1, '/', len(containers), flush=True)

# 6) enrich + write outputs
final = {}
n_el_resolved = 0
for weapon, ocs in sorted(catalog.items()):
    final[weapon] = []
    for oc in sorted(ocs, key=lambda e: e['asset']):
        enriched = []
        for ref in oc['elements']:
            e = elem_data.get(ref)
            if e:
                enriched.append({'asset': ref, 'type': e['type'], 'amount': e['amount']})
                n_el_resolved += 1
            else:
                enriched.append({'asset': ref, 'type': None, 'amount': None})
        final[weapon].append({'asset': oc['asset'], 'quality': oc['quality'], 'elements': enriched})

os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
json.dump({'generated': '2026-10-04', 'weapons': len(final),
           'overclocks': sum(len(v) for v in final.values()),
           'elements_resolved': n_el_resolved,
           'catalog': final}, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('# 武器超频资产目录（自动生成，写 .cw.json 时的速查表）\n\n')
    f.write(f'> 生成：2026-10-04 · {len(final)} 武器 · {sum(len(v) for v in final.values())} 超频 · 元素值解析 {n_el_resolved} 条\n')
    f.write('> 资产名 = Overrides 的键；Amount/UpgradeType = 当前原版值（改之前的参照）\n')
    f.write('> `None` = 该元素是特殊结构（带组件/蓝图引用），不是简单数值，v1 不建议改它\n\n')
    for weapon, ocs in final.items():
        f.write(f'## {weapon}\n\n')
        for oc in ocs:
            q = oc['quality'] or '?'
            f.write(f"- **{oc['asset']}**（{q}）\n")
            for e in oc['elements']:
                f.write(f"  - `{e['asset']}`: {e['type']} = {e['amount']}\n")
        f.write('\n')

print('DONE. weapons:', len(final), 'ocs:', sum(len(v) for v in final.values()), 'elements:', n_el_resolved)
print('->', OUT_JSON)
print('->', OUT_MD)
