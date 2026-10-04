# -*- coding: utf-8 -*-
"""M3-2 CLIENT FINAL: CH_Replication.OnRep_DifficultyJson calls CH_Mod's repurposed ModHubOpened.
Only proven constructs: existing-local reuse, bool local, member-add to existing class import."""
import subprocess, sys, os, json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
UAS = r'D:\drg-rc-drg.mod\ue-ugc-workspace\.bin\UAssetStudio.Cli.exe'
SRC = r'D:\drg-rc-drg.mod\_probe\ch_pak\FSD\Content\CustomHazard\CH_Replication.uasset'
KMS = r'D:\drg-rc-drg.mod\_probe\ch_dec\CH_Replication.kms'
WORK = r'D:\drg-rc-drg.mod\_probe\m3'

t = open(KMS, encoding='utf-8-sig').read()

# --- add ModHubOpened decl to EXISTING CH_Mod_C class import
A_CMC = '''    class CH_Mod_C {
        public SceneComponent DefaultSceneRoot_GEN_VARIABLE;
        public SceneComponent DefaultSceneRoot;
        public ObjectProperty CustomDifficulty;
    }'''
assert t.count(A_CMC) == 1, f'CH_Mod_C import count={t.count(A_CMC)}'
t = t.replace(A_CMC, '''    class CH_Mod_C {
        public SceneComponent DefaultSceneRoot_GEN_VARIABLE;
        public SceneComponent DefaultSceneRoot;
        public ObjectProperty CustomDifficulty;
        [UnknownSignature] public void ModHubOpened();
    }''', 1)

# --- locals: reuse existing Object<CH_Mod_C> local; add one bool
A_LOC = ('        Object<CH_Mod_C> CallFunc_GetActorOfClass_ReturnValue;\n'
         '        bool CallFunc_IsValid_ReturnValue;\n'
         '        bool CallFunc_IsValid_ReturnValue_1;\n'
         '        bool CallFunc_IsServer_ReturnValue;\n')
assert t.count(A_LOC) == 1
t = t.replace(A_LOC, A_LOC + '        bool CM_Flag;\n', 1)

# --- insert apply-call after ReceiveReplication at L_83
A_L83 = ('        L_83: Context(this.CustomDifficultySettings, LocalVirtualFunction("ReceiveReplication", InstanceVariable("DifficultyJson")));\n'
         '            return;\n')
assert t.count(A_L83) == 1, f'L83={t.count(A_L83)}'
INLINE = ('        L_83: Context(this.CustomDifficultySettings, LocalVirtualFunction("ReceiveReplication", InstanceVariable("DifficultyJson")));\n'
'''            // CM WeaponMods: trigger apply on the CH_Mod actor (reads UI field, idempotent, no-op when absent)
            LetObj(CallFunc_GetActorOfClass_ReturnValue,GameplayStatics.GetActorOfClass(this, CH_Mod_C));
            CM_Flag = (bool)(KismetSystemLibrary.IsValid(CallFunc_GetActorOfClass_ReturnValue));
            if (CM_Flag) {
                Context(CallFunc_GetActorOfClass_ReturnValue, FinalFunction("ModHubOpened"));
            }
            return;
''')
t = t.replace(A_L83, INLINE, 1)

kms = os.path.join(WORK, 'CH_Replication_CMf.kms')
open(kms, 'w', encoding='utf-8', newline='').write(t)
print('edited kms:', len(t))

out = os.path.join(WORK, 'CH_Replication_CMf.uasset')
r = subprocess.run([UAS, 'compile', kms, '--asset', SRC, '--out', out, '--json'],
                   capture_output=True, timeout=900)
d = json.loads(r.stdout.decode('utf-8', errors='replace'))
print('compile:', d.get('Status'))
if d.get('Status') == 'ok':
    print('changed:', [(f.get("Name") if isinstance(f, dict) else f) for f in (d.get("Data", {}).get("ChangedFunctions") or [])])
    print('outputs:', d.get('Outputs'))
else:
    print('ERROR:', json.dumps(d.get('Error'), ensure_ascii=False)[:400])
