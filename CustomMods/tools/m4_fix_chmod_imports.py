# -*- coding: utf-8 -*-
"""CH_Mod full import repair: write CORRECT outers for all added imports, iterate until decompile-back is clean."""
import sys, json, subprocess, os, struct

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
UAS = r'D:\drg-rc-drg.mod\ue-ugc-workspace\.bin\UAssetStudio.Cli.exe'
WORK = r'D:\drg-rc-drg.mod\_probe\m3'
path = os.path.join(WORK, 'CH_Mod_CMhost2.uasset')

def jdump(p):
    r = subprocess.run([UAS, 'json', p, '--ue-version', 'VER_UE4_27', '--json'],
                       capture_output=True, timeout=300)
    d = json.loads(r.stdout.decode('utf-8', errors='replace'))
    return json.load(open(d['Outputs'][0], encoding='utf-8'))

for round_i in range(1, 6):
    dump = jdump(path)
    nm = dump['NameMap']
    imports = dump['Imports']
    # find suspicious: function imports whose outer magnitude doesn't match their owner class position
    # owner class for a Function import = the import entry its outer SHOULD point to.
    # Strategy: verify each added func (Map_Find, IsValid, MakeSoftObjectPath, LoadAsset_Blocking):
    # owner = ObjectName=='BlueprintMapLibrary' or 'KismetSystemLibrary' class import.
    fixes = []
    for fn, owner in [('Map_Find', 'BlueprintMapLibrary'), ('IsValid', 'KismetSystemLibrary'),
                      ('MakeSoftObjectPath', 'KismetSystemLibrary'), ('LoadAsset_Blocking', 'KismetSystemLibrary')]:
        fi = next(i for i, im in enumerate(imports) if im['ObjectName'] == fn)
        cur = imports[fi]['OuterIndex']
        ci = next(i for i, im in enumerate(imports) if im['ObjectName'] == owner)
        expected = -(ci + 1)
        if cur != expected:
            fixes.append((fn, cur, expected))
    print(f'round {round_i}: mismatches = {fixes}')
    if not fixes:
        break
    data = bytearray(open(path, 'rb').read())
    for fn, cur, expected in fixes:
        fidx = nm.index('Function')
        oidx = nm.index(fn)
        pat = struct.pack('<ii', fidx, 0) + struct.pack('<i', cur) + struct.pack('<ii', oidx, 0)
        hits = []
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        if len(hits) != 1:
            print(f'  !! {fn}: hits={len(hits)} — pattern search failed')
            continue
        off = hits[0] + 8
        struct.pack_into('<i', data, off, expected)
        print(f'  {fn}: {cur} -> {expected} @ {off}')
    open(path, 'wb').write(data)

# final verify
r = subprocess.run([UAS, 'decompile', path, '--ue-version', 'VER_UE4_27',
                    '--outdir', os.path.join(WORK, 'qa2'), '--json'],
                   capture_output=True, timeout=600)
d = json.loads(r.stdout.decode('utf-8', errors='replace'))
print('FINAL decompile-back CH_Mod ->', d.get('Status'), (d.get('Error') or {}).get('Message', '')[:120])
if d.get('Status') == 'ok':
    txt = open(d['Outputs'][0], encoding='utf-8-sig', errors='replace').read()
    print('CM markers: L_CM1 =', 'L_CM1' in txt, '| ModHubOpened apply =', 'InstanceVariable("DifficultyJson")' in txt)
