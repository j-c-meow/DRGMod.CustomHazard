# -*- coding: utf-8 -*-
"""M3-2 HOST v2: no Map-typed locals (they crash the compiler).
JSON navigation via InstanceVariable("Object") nested expressions. All proven constructs."""
import subprocess, sys, os, json, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
UAS = r'D:\drg-rc-drg.mod\ue-ugc-workspace\.bin\UAssetStudio.Cli.exe'
SRC = r'D:\drg-rc-drg.mod\_probe\ch_pak\FSD\Content\CustomHazard\CH_Mod.uasset'
KMS = r'D:\drg-rc-drg.mod\_probe\ch_dec\CH_Mod.kms'
WORK = r'D:\drg-rc-drg.mod\_probe\m3'

t = open(KMS, encoding='utf-8-sig').read()

# imports
A_BM = '        [UnknownSignature, FinalFunction] public sealed void Map_Values();\n'
assert t.count(A_BM) == 1
t = t.replace(A_BM, A_BM + '        [UnknownSignature, FinalFunction] public sealed void Map_Find();\n', 1)
A_KSL = '        [UnknownSignature, MathFunction] public static sealed void SetObjectPropertyByName();\n'
assert t.count(A_KSL) == 1
t = t.replace(A_KSL, A_KSL +
    '        [UnknownSignature, MathFunction] public static sealed void IsValid();\n'
    '        [UnknownSignature, MathFunction] public static sealed void MakeSoftObjectPath();\n'
    '        [UnknownSignature, MathFunction] public static sealed void LoadAsset_Blocking();\n', 1)

mm = re.search(r'(\[[^\]]*\]\s*\n\s+public void ModHubOpened\(\) \{[^}]*\})', t)
STUB = mm.group(1)

FULL_LOCALS = '''        bool CM_Flag;
        bool CM_MapFind;
        Object<Object> CM_Root;
        Object<Object> CM_Wm;
        Array<Object<Object>> CM_Items;
        bool CM_ArrOk;
        int CM_Idx;
        int CM_Len;
        Object<Object> CM_Item;
        bool CM_ImOk;
        bool CM_Find1;
        Object<Object> CM_A;
        string CM_Asset;
        bool CM_S1;
        bool CM_Find2;
        Object<Object> CM_W;
        string CM_Weapon;
        bool CM_S2;
        bool CM_Find3;
        Object<Object> CM_N;
        float CM_Amount;
        bool CM_NOk;
        string CM_P1;
        string CM_P2;
        string CM_Path;
        Object<Object> CM_Obj;'''

NEW_BODY = f'''    [BlueprintCallable, BlueprintEvent]
    public void ModHubOpened() {{
        // Locals
{FULL_LOCALS}

        // Block 1
        CM_Flag = (bool)(KismetSystemLibrary.IsValid(this.CustomDifficulty));
        if (!CM_Flag) return;
        CM_Root = Context(this.CustomDifficulty, InstanceVariable("DifficultyJson"));
        CM_Flag = (bool)(KismetSystemLibrary.IsValid(CM_Root));
        if (!CM_Flag) return;
        CM_MapFind = (bool)(Context(Default__BlueprintMapLibrary, FinalFunction("Map_Find", Context(CM_Root, InstanceVariable("Object")), "WeaponMods", CM_Wm)));
        if (!CM_MapFind) return;
        Context(CM_Wm, LocalVirtualFunction("GetArray", CM_Items, CM_ArrOk));
        if (!CM_ArrOk) return;
        CM_Len = Context(Default__KismetArrayLibrary, FinalFunction("Array_Length", CM_Items));
        CM_Idx = 0;

        // Block 2
        L_CM1: CM_Flag = (bool)(KismetMathLibrary.Less_IntInt(CM_Idx, CM_Len));
        if (!CM_Flag) return;
        Context(Default__KismetArrayLibrary, FinalFunction("Array_Get", CM_Items, CM_Idx, CM_Item));
        CM_Find1 = (bool)(Context(Default__BlueprintMapLibrary, FinalFunction("Map_Find", Context(CM_Item, InstanceVariable("Object")), "Asset", CM_A)));
        if (!CM_Find1) goto L_CMnext;
        Context(CM_A, LocalVirtualFunction("GetString", CM_Asset, CM_S1));
        if (!CM_S1) goto L_CMnext;
        CM_Find2 = (bool)(Context(Default__BlueprintMapLibrary, FinalFunction("Map_Find", Context(CM_Item, InstanceVariable("Object")), "Weapon", CM_W)));
        if (!CM_Find2) goto L_CMnext;
        Context(CM_W, LocalVirtualFunction("GetString", CM_Weapon, CM_S2));
        if (!CM_S2) goto L_CMnext;
        CM_Find3 = (bool)(Context(Default__BlueprintMapLibrary, FinalFunction("Map_Find", Context(CM_Item, InstanceVariable("Object")), "Amount", CM_N)));
        if (!CM_Find3) goto L_CMnext;
        Context(CM_N, LocalVirtualFunction("GetNumber", CM_Amount, CM_NOk));
        if (!CM_NOk) goto L_CMnext;
        CM_P1 = KismetStringLibrary.Concat_StrStr("/Game/WeaponsNTools/", CM_Weapon);
        CM_P2 = KismetStringLibrary.Concat_StrStr(CM_P1, "/Overclocks/OC_BonusesAndPenalties/");
        CM_Path = KismetStringLibrary.Concat_StrStr(CM_P2, CM_Asset);
        CM_Obj = KismetSystemLibrary.LoadAsset_Blocking(KismetSystemLibrary.MakeSoftObjectPath(CM_Path));
        CM_Flag = (bool)(KismetSystemLibrary.IsValid(CM_Obj));
        if (CM_Flag) {{
            KismetSystemLibrary.SetObjectPropertyByName(CM_Obj, NameConst("Amount"), CM_Amount);
        }}

        // Block 3
        L_CMnext: CM_Idx = KismetMathLibrary.Add_IntInt(CM_Idx, 1);
        goto L_CM1;

    }}'''
t = t.replace(STUB, NEW_BODY, 1)

# OnReplicateDifficulty trigger
OLD_ONREP = '''    void OnReplicateDifficulty([BlueprintVisible, BlueprintReadOnly] string Difficulty) {
        // Block 1
        LetValueOnPersistentFrame("K2Node_CustomEvent_Difficulty", Difficulty);'''
assert t.count(OLD_ONREP) == 1
t = t.replace(OLD_ONREP, '''    void OnReplicateDifficulty([BlueprintVisible, BlueprintReadOnly] string Difficulty) {
        // Block 1
        this.ModHubOpened();
        LetValueOnPersistentFrame("K2Node_CustomEvent_Difficulty", Difficulty);''', 1)

kms = os.path.join(WORK, 'CH_Mod_CMhost2.kms')
open(kms, 'w', encoding='utf-8', newline='').write(t)
print('edited kms:', len(t))

out = os.path.join(WORK, 'CH_Mod_CMhost2.uasset')
r = subprocess.run([UAS, 'compile', kms, '--asset', SRC, '--out', out, '--json'],
                   capture_output=True, timeout=1200)
d = json.loads(r.stdout.decode('utf-8', errors='replace'))
print('compile:', d.get('Status'))
if d.get('Status') == 'ok':
    data = d.get('Data', {})
    print('changed:', [(f.get("Name") if isinstance(f, dict) else f) for f in (data.get("ChangedFunctions") or [])])
    print('warnings:', data.get('Warnings'))
    print('outputs:', d.get('Outputs'))
else:
    print('ERROR:', json.dumps(d.get('Error'), ensure_ascii=False)[:400])
