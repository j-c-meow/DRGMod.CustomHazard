# -*- coding: utf-8 -*-
import sys, json, subprocess, os, struct

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
UAS = r'D:\drg-rc-drg.mod\ue-ugc-workspace\.bin\UAssetStudio.Cli.exe'
WORK = r'D:\drg-rc-drg.mod\_probe\m3'

def jdump(path):
    r = subprocess.run([UAS, 'json', path, '--ue-version', 'VER_UE4_27', '--json'],
                       capture_output=True, timeout=300)
    d = json.loads(r.stdout.decode('utf-8', errors='replace'))
    return json.load(open(d['Outputs'][0], encoding='utf-8'))

def fix(path, func_name, owner_class):
    dump = jdump(path)
    nm = dump['NameMap']
    imports = dump['Imports']
    fi = next(i for i, im in enumerate(imports) if im['ObjectName'] == func_name)
    cur = imports[fi]['OuterIndex']
    ci = next(i for i, im in enumerate(imports) if im['ObjectName'] == owner_class)
    expected = -(ci + 1)
    print(f'{os.path.basename(path)}: {func_name} cur={cur} | {owner_class}@pos{ci} expected={expected}')
    if cur > 0 and expected == -cur:
        data = bytearray(open(path, 'rb').read())
        fidx = nm.index('Function')
        oidx = nm.index(func_name)
        pat = struct.pack('<ii', fidx, 0) + struct.pack('<i', cur) + struct.pack('<ii', oidx, 0)
        hits = []
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        assert len(hits) == 1, f'hits={len(hits)}'
        off = hits[0] + 8
        struct.pack_into('<i', data, off, expected)
        open(path, 'wb').write(data)
        print(f'  patched @ {off} -> {expected}')
        return True
    print(f'  SKIP (cur={"neg" if cur < 0 else cur}, expected={expected})')
    return False

fix(os.path.join(WORK, 'CH_Mod_CMhost2.uasset'), 'Map_Find', 'BlueprintMapLibrary')
fix(os.path.join(WORK, 'CH_Replication_CMf.uasset'), 'ModHubOpened', 'CH_Mod_C')

for name in ['CH_Mod_CMhost2', 'CH_Replication_CMf']:
    r = subprocess.run([UAS, 'decompile', os.path.join(WORK, name + '.uasset'),
                        '--ue-version', 'VER_UE4_27', '--outdir', os.path.join(WORK, 'qa2'), '--json'],
                       capture_output=True, timeout=600)
    d = json.loads(r.stdout.decode('utf-8', errors='replace'))
    print('decompile-back', name, '->', d.get('Status'), (d.get('Error') or {}).get('Message', '')[:90])
