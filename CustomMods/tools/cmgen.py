# -*- coding: utf-8 -*-
"""cmgen — CustomMods weapon JSON -> asset patches -> mod pak.

Pipeline (all steps proven in M0):
  .cw.json -> validate -> locate assets in game pak (repak list cache)
  -> per override: repak get uasset+uexp -> UAssetStudio decompile -> edit .kms
     -> surgical compile (--asset) -> verify -> collect patched pair
  -> layout FSD/Content/... tree -> repak pack --version V11 --mount-point ../../../
  -> manifest json; refuse to produce pak on any failure.

Usage:
  python cmgen.py <config.cw.json> [--out DIR] [--pak-list CACHE.txt] [--dry-run] [--json]
"""
import argparse, json, os, re, subprocess, sys, tempfile, shutil, uuid

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WS = r'D:\drg-rc-drg.mod\ue-ugc-workspace\.bin'
UAS = os.path.join(WS, 'UAssetStudio.Cli.exe')
REPAK = os.path.join(WS, 'repak.exe')
DEFAULT_PAK = r'D:\steam\steamapps\common\Deep Rock Galactic\FSD\Content\Paks\FSD-WindowsNoEditor.pak'
ENUM_TABLE = r'D:\drg-rc-drg.mod\DRGMod.CustomHazard\CustomMods\data\upgrade_enums.json'
UE = 'VER_UE4_27'

QUALITY = {'Clean': 'SCAT_OC_Clean', 'Balanced': 'SCAT_OC_Balanced', 'Unstable': 'SCAT_OC_Unstable'}


def run(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def uas_json(cmd_args, timeout=300):
    """Run UAssetStudio.Cli with --json, parse result. Raises on non-ok."""
    rc, out, err = run([UAS] + cmd_args + ['--json'], timeout)
    try:
        d = json.loads(out.decode('utf-8', errors='replace'))
    except Exception:
        raise RuntimeError(f'UAS non-JSON output rc={rc}: {err.decode(errors="replace")[:300]}')
    if d.get('Status') != 'ok':
        raise RuntimeError(f"UAS {d.get('Command')} {d.get('Status')}: {d.get('Error')}")
    return d


def load_pak_index(cache_path, game_pak):
    """Return dict assetName -> pak entry path, from list cache (rebuild if missing)."""
    if not os.path.exists(cache_path):
        rc, out, _ = run([REPAK, 'list', game_pak], timeout=600)
        open(cache_path, 'wb').write(out)
    idx = {}
    for line in open(cache_path, encoding='utf-8', errors='replace').read().splitlines():
        line = line.strip()
        if line.endswith('.uasset') and '/WeaponsNTools/' in line and '/Overclocks/' in line:
            idx[os.path.basename(line)[:-7]] = line
    return idx


def repak_get(game_pak, entry, dest):
    rc, out, _ = run([REPAK, 'get', game_pak, entry], timeout=120)
    if rc != 0 or not out:
        raise RuntimeError(f'repak get failed: {entry}')
    open(dest, 'wb').write(out)


def apply_kms_edit(kms_text, set_spec):
    """Edit Amount / UpgradeType lines in element .kms text. Returns (new_text, changes)."""
    t, changes = kms_text, []
    if 'Amount' in set_spec:
        val = float(set_spec['Amount'])
        t2, n = re.subn(r'float Amount = [-\d.]+f;', f'float Amount = {val}f;', t)
        if n != 1:
            raise RuntimeError(f'Amount line match={n} (expected 1)')
        changes.append(f'Amount={val}')
        t = t2
    if 'UpgradeType' in set_spec:
        ut = str(set_spec['UpgradeType'])
        m = re.search(r'UpgradeType = `(E\w+)::\w+`;', t)
        if not m:
            raise RuntimeError('UpgradeType line not found')
        t, n = re.subn(r'UpgradeType = `E\w+::\w+`;',
                       f'UpgradeType = `{m.group(1)}::{ut}`;', t)
        if n != 1:
            raise RuntimeError('UpgradeType replace failed')
        changes.append(f'UpgradeType={ut}')
    return t, changes


def patch_element(workdir, game_pak, pak_entry, set_spec, tag):
    """Full proven pipeline for one element asset. Returns dict result."""
    os.makedirs(workdir, exist_ok=True)
    name = os.path.basename(pak_entry)[:-7]
    src_uasset = os.path.join(workdir, tag + '.uasset')
    src_uexp = os.path.join(workdir, tag + '.uexp')
    repak_get(game_pak, pak_entry, src_uasset)
    repak_get(game_pak, pak_entry[:-7] + '.uexp', src_uexp)

    dec = uas_json(['decompile', src_uasset, '--ue-version', UE, '--outdir', workdir])
    kms_path = dec['Outputs'][0]
    kms = open(kms_path, encoding='utf-8').read()

    # validate enum membership when UpgradeType is being set
    if 'UpgradeType' in set_spec:
        enum_used = re.search(r'Enum<(E\w+)>', kms)
        if enum_used:
            table = json.load(open(ENUM_TABLE, encoding='utf-8'))
            vals = table['enums'].get(enum_used.group(1), [])
            if set_spec['UpgradeType'] not in vals:
                raise RuntimeError(f"{set_spec['UpgradeType']} not in {enum_used.group(1)}")

    new_kms, changes = apply_kms_edit(kms, set_spec)
    edited = os.path.join(workdir, tag + '_edited.kms')
    open(edited, 'w', encoding='utf-8', newline='').write(new_kms)

    out_uasset = os.path.join(workdir, tag + '_patched.uasset')
    comp = uas_json(['compile', edited, '--asset', src_uasset, '--out', out_uasset])
    changed_props = comp['Data'].get('ChangedProperties', [])
    if not comp['Data'].get('HasChanges'):
        # value identical to vanilla -> nothing to ship for this asset
        return {'name': name, 'pak_entry': pak_entry, 'changes': [],
                'changed_props': [], 'uasset': None, 'uexp': None, 'unchanged': True}
    out_uexp = out_uasset[:-7] + '.uexp'
    if not os.path.exists(out_uexp):
        raise RuntimeError('compile did not produce .uexp')

    # verify patched asset round-trips
    uas_json(['verify', out_uasset, '--ue-version', UE, '--outdir', workdir])

    return {'name': name, 'pak_entry': pak_entry, 'changes': changes,
            'changed_props': changed_props,
            'uasset': out_uasset, 'uexp': out_uexp}


def parse_oc_container(workdir, game_pak, oc_entry, tag):
    """Parse an OC container's CombinedUpgrades array (in order) -> element asset names."""
    src = os.path.join(workdir, tag + '.uasset')
    repak_get(game_pak, oc_entry, src)
    repak_get(game_pak, oc_entry[:-7] + '.uexp', src[:-7] + '.uexp')
    d = uas_json(['json', src, '--ue-version', UE])
    dump = json.load(open(d['Outputs'][0], encoding='utf-8'))
    elements = []
    for exp in dump.get('Exports', []):
        for prop in exp.get('Data', []):
            if prop.get('Name') != 'CombinedUpgrades':
                continue
            for item in prop.get('Value', []):
                v = item.get('Value')
                if not isinstance(v, dict):
                    continue
                ap = v.get('AssetPath') or {}
                path = ap.get('PackageName') or ap.get('AssetName') or v.get('SubPathString') or ''
                if not path:
                    continue
                if path.startswith('/Game/'):
                    # /Game/A/B/name -> name (strip leading '/' of package when needed)
                    name = path.rstrip('/').rsplit('/', 1)[-1]
                else:
                    name = path.lstrip('/').rsplit('/', 1)[-1]
                name = name.split('.')[0]
                if name and not name.endswith(('.uasset', '.uexp')):
                    elements.append(name)
    seen, ordered = set(), []
    for e in elements:
        if e not in seen:
            seen.add(e)
            ordered.append(e)
    return ordered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('config')
    ap.add_argument('--out', default=None)
    ap.add_argument('--pak-list', default=r'D:\drg-rc-drg.mod\_probe\pak_list.txt')
    ap.add_argument('--game-pak', default=DEFAULT_PAK)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding='utf-8'))
    # unified format: difficulty JSON with top-level WeaponMods section.
    # WeaponMods may be: {"Overrides": {...}, "CustomOverclocks": [...]} (authoring)
    # or a runtime ARRAY: [{"Asset": name, "Weapon": w, "Amount": v}, ...] (CH in-game format)
    if isinstance(cfg.get('WeaponMods'), (dict, list)):
        wm = cfg['WeaponMods']
        if isinstance(wm, list):
            overrides = {}
            for entry in wm:
                a = entry.get('Asset')
                if a:
                    overrides[a] = {'Weapon': entry.get('Weapon', ''),
                                    'Set': {k: v for k, v in entry.items() if k in ('Amount', 'UpgradeType')}}
            cfg = {'FormatVersion': 1, 'Name': cfg.get('Name') or 'CM',
                   'Overrides': overrides, 'CustomOverclocks': []}
        else:
            cfg = {'FormatVersion': cfg.get('FormatVersion', 1),
                   'Name': cfg.get('Name') or 'CM',
                   'Overrides': wm.get('Overrides') or {},
                   'CustomOverclocks': wm.get('CustomOverclocks') or []}
    outdir = args.out or os.path.join(os.path.dirname(os.path.abspath(args.config)), 'cmgen_out')
    result = {'config': cfg.get('Name'), 'patches': [], 'errors': [], 'pak': None}

    try:
        if cfg.get('FormatVersion') != 1:
            raise RuntimeError('FormatVersion must be 1')
        overrides = dict(cfg.get('Overrides') or {})
        customs = list(cfg.get('CustomOverclocks') or [])

        idx = load_pak_index(args.pak_list, args.game_pak)

        # expand CustomOverclocks (Replace strategy) into element overrides
        work = os.path.join(tempfile.gettempdir(), 'cmgen_' + uuid.uuid4().hex[:8])
        os.makedirs(work, exist_ok=True)
        try:
            for co in customs:
                rid = co.get('Replace') or ''
                oc_entry = idx.get(rid)
                if not oc_entry:
                    raise RuntimeError(f'CustomOverclocks Replace target not found: {rid}')
                elems = parse_oc_container(work, args.game_pak, oc_entry, 'oc_' + rid)
                want = co.get('Elements', [])
                if len(want) > len(elems):
                    raise RuntimeError(f'{co["Id"]}: wants {len(want)} elements, template {rid} has {len(elems)}')
                for i, el in enumerate(want):
                    spec = {k: v for k, v in el.items() if k in ('Amount', 'UpgradeType')}
                    overrides[elems[i]] = {'Weapon': co.get('Weapon', ''), 'Set': spec,
                                           '_via': f"CustomOverclocks:{co['Id']}"}

            if args.dry_run:
                result['plan'] = {k: v['Set'] for k, v in overrides.items()}
            else:
                stage = os.path.join(outdir, 'stage')
                if os.path.exists(stage):
                    shutil.rmtree(stage)
                for name, spec in overrides.items():
                    entry = idx.get(name)
                    if not entry:
                        raise RuntimeError(f'Override asset not found in pak: {name}')
                    pr = patch_element(os.path.join(work, 'p'), args.game_pak, entry, spec['Set'], name.replace('+', '_'))
                    if pr.get('unchanged'):
                        result['patches'].append(pr)
                        continue
                    rel = entry  # e.g. FSD/Content/.../X.uasset
                    dst = os.path.join(stage, rel.replace('/', os.sep))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(pr['uasset'], dst)
                    shutil.copy2(pr['uexp'], dst[:-7] + '.uexp')
                    pr['staged'] = rel
                    result['patches'].append(pr)

                # pack from stage parent so entries keep FSD/ prefix
                pak_out = os.path.join(outdir, (cfg.get('Name') or 'CM').replace(' ', '_') + '.pak')
                rc, o, e = run([REPAK, 'pack', '--version', 'V11', '--mount-point', '../../../', stage, pak_out])
                if rc != 0:
                    raise RuntimeError(f'repak pack failed: {e.decode(errors="replace")[:200]}')
                result['pak'] = pak_out
        finally:
            shutil.rmtree(work, ignore_errors=True)

        result['status'] = 'ok'
    except Exception as ex:
        result['status'] = 'error'
        result['errors'].append(str(ex))

    print(json.dumps(result, ensure_ascii=False, indent=1))
    sys.exit(0 if result['status'] == 'ok' else 1)


if __name__ == '__main__':
    main()
