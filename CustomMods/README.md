# CustomMods — 武器节（WeaponMods）能力

> 2026-10-04：**单 CH pak 交付**——CH 本体已具备解析 `WeaponMods` 节并在游戏内运行时套用武器数值的能力（CM 能力）。

## 交付物

| 文件 | 说明 |
|---|---|
| `patched/CustomHazard_CM.pak` | **单 CH pak**（v0.0.3 cooked + CH_Mod/CH_Replication 补丁），106 文件 |
| `tools/m3_patch_chmod.py` | CH_Mod 补丁脚本（重编译产物见 `_probe\m3\`） |
| `tools/m3_patch_replication.py` | CH_Replication 补丁脚本 |
| `tools/cmgen.py` | 生成器（过渡期 pak 路线，双格式兼容） |
| `写法教程.md` / `schema.md` / `data/` | 玩家文档与数据目录 |

## CM 能力的实现（给 reviewer）

基于 CH v0.0.3 的**烘焙资产外科补丁**（UAssetStudio.Cli 编译，全部补丁 verify/validate 通过）：

1. **CH_Mod**（2 处改动）
   - 空存根函数 `ModHubOpened`（原 ubergraph 块为空操作，征用零损失）改写为套用逻辑：
     读 `CustomDifficulty.DifficultyJson` → 取 `WeaponMods` 数组 → 逐条
     `LoadAsset_Blocking(/Game/WeaponsNTools/<Weapon>/Overclocks/OC_BonusesAndPenalties/<Asset>)`
     → `SetObjectPropertyByName(Amount)`。幂等；配置无 `WeaponMods` 键时零开销返回。
   - `OnReplicateDifficulty` 开头加一行 `this.ModHubOpened()`——**房主侧触发**（保存/载入配置必经）。
2. **CH_Replication**（1 处改动）
   - `OnRep_DifficultyJson`（客户端复制到达）在 `ReceiveReplication` 之后
     `GetActorOfClass(CH_Mod_C)` → 调 `ModHubOpened`——**客机侧触发**（此时 UI 已解析完 JSON）。
3. 导入表只做**已有类导入的成员追加**（Map_Find/KSL 原生函数），无新增类导入——规避了
   2026-06 版 KismetCompiler 的两处限制（类默认符号创建未实现 / ubergraph 存根重编译受限，详见交接文档 §五）。

## 运行时 JSON 格式（难度 JSON 顶层）

```json
"WeaponMods": [
  { "Asset": "OC_Bonus_RoF+3_AssaultRifle", "Weapon": "AssaultRifle", "Amount": 6.0 }
]
```

- `Asset`：元素资产名（查 `data/weapon_overclock_catalog.md`）
- `Amount`：新数值（float）
- 不写 `WeaponMods` = 纯难度配置，完全向后兼容；删除该节后已改数值保留至重启（v1 语义）
- `UpgradeType` 运行时改动与"全新超频资产"→ 走 cmgen/pak 路线（v1.1）

## 已知限制 / 测试点

- [ ] 游戏内实测（挂载、数值生效、多人一致）——**待测**
- [ ] 反编译回读对补丁产物报 import-index（decompiler 侧限制；validate/json 两条独立校验全绿）
- v1 不做强度适配/自动平衡（用户拍板）；默认一切原版
