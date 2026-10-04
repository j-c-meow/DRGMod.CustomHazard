# 武器节规格（CustomMods Weapon JSON · FormatVersion 1）

> 状态：v1 草案（2026-10-04，基于 M0 实测资产结构定稿）；**格式归属定稿（用户拍板）：武器节并入难度 JSON 本体**
> 原则：**默认原版**——空配置/未启用 = 游戏零改动。只有玩家主动启用配置才生效。
> **玩家写配置看 [写法教程.md](写法教程.md)**（全字段中文注释 + 目录速查用法 + 坑列表，对标 Koncin 的难度 JSON 注释版）；本文是面向工具/开发者的规格。
> **查资产现值看 `data/weapon_overclock_catalog.md`**（全武器超频目录：资产名/品质/元素原值，自动生成，可重跑）。

## 格式归属（定稿 2026-10-04）

**不存在独立的玩家级武器配置文件**。武器节是难度 JSON（`.cd.json` 格式）的一个顶层字段：

```jsonc
{
  "Name": "Hazard hard level11 ...",      // ← 难度原有字段
  "MaxActiveCritters": 200,                // ← 难度原有字段
  "EnemyDescriptors": { ... },             // ← 生物节（CH 原有）
  "EnemyPool": { ... },                    // ← 生物池（CH 原有）
  "WeaponMods": {                          // ← 【新增】武器节，本文档的全部内容
    "Overrides": { ... },                  //    改现有超频/升级数值
    "CustomOverclocks": [ ... ]            //    创建全新超频（v1 槽位重铸）
  },
  "SeasonalEvents": [ ... ],               // ← 难度原有字段
  "EscortMule": { ... }                    // ← 难度原有字段
}
```

- 玩家体验：**一份代码三合一**（难度/生物/武器），CH 终端列表不变，选一份全部生效
- `WeaponMods` 缺省或为空 = 该配置不碰武器（纯难度配置完全向后兼容）
- 独立 `.cw.json` 文件 = **作者辅助/过渡格式**（cmgen 兼容读取，顶层即 WeaponMods 内容）；M3 目标是 CH 的配置加载器在游戏内直接解析 `WeaponMods` 节

## 设计对齐

与 CH 的 `.cd.json`（难度）同构：声明式 JSON、按需覆盖、可分享合集。数值字段与游戏资产一一映射，无发明概念。

## 顶层结构

```json
{
  "FormatVersion": 1,
  "Name": "配置名（必填）",
  "Description": "一句话说明（可选）",
  "Author": "作者署名（建议与 mod.io/GitHub 一致）",
  "Overrides": { ... },          // 节 1：改现有资产数值
  "CustomOverclocks": [ ... ]    // 节 2：创建全新超频
}
```

## 节 1：Overrides —— 修改现有超频/升级元素数值

键 = 游戏内元素资产名（不含路径）。生成器在游戏 pak 中按
`FSD/Content/WeaponsNTools/<Weapon>/Overclocks/OC_BonusesAndPenalties/<资产名>` 定位并做外科补丁。

```json
"Overrides": {
  "OC_Bonus_RoF+3_AssaultRifle": {
    "Weapon": "AssaultRifle",              // 必填：武器目录名（用于定位与校验）
    "Set": {
      "Amount": 6.0,                       // float：数值本体（改这里）
      "UpgradeType": "RateOfFire"          // 可选：枚举值名（来自 upgrade_enums.json）
    }
  }
}
```

- 可改字段仅两个：`Amount`（float）、`UpgradeType`（枚举值名）——这是元素资产的全部数据面。
- 每条 Override 生成一个 1 字节级外科补丁资产（M0 已实测：`Amount` 3.0→6.0 仅 1 字节差异）。
- 生成器对每个补丁跑 verify，往返不一致即拒绝产出。

## 节 2：CustomOverclocks —— 创建全新超频

```json
"CustomOverclocks": [
  {
    "Id": "MyFirst_OC",                    // 资产名后缀，最终资产 OC_MyFirst_OC
    "Weapon": "AssaultRifle",              // 归属武器目录
    "Quality": "Balanced",                 // Clean | Balanced | Unstable（→ SCAT_OC_*）
    "Name": "我的第一个超频",
    "Description": "说明文本",
    "StatTexts": ["+3 射速", "-30% 后坐力"], // 面板显示行（原作为文本引用）
    "Elements": [                          // 数值本体：一组升级元素（= 超频的加成/惩罚）
      { "Class": "AmmoDrivenWeaponUpgrade", "UpgradeType": "RateOfFire", "Amount": 3.0 },
      { "Class": "HitscanBaseUpgrade",     "UpgradeType": "RecoilMultiplier", "Amount": -0.3 }
    ]
  }
]
```

- `Class` + `UpgradeType` 必须是 `data/upgrade_enums.json` 中的合法组合（51 类已配对，318 个枚举值）。
- 生成器产出：N 个新元素资产 + 1 个新 OC 容器资产（引用元素、挂品质分类）→ 打入 pak 的
  `FSD/Content/WeaponsNTools/<Weapon>/Overclocks/` 下 → AssetRegistry 更新（新资产被发现的关键）。
- **v1 落地策略**：新超频默认以「替换既有 OC 槽位」形式注册（可在条目加 `"Replace": "OC_AssaultRifle_RoF_B"`
  指定被替换者；省略则替换同武器第一个同品质槽）。原生新槽位注册（OverclockBank 追加）列入 v1.1——
  依赖 BP 侧（M3）对解锁链的解剖结论。

## 枚举速查（摘录）

完整表见 `data/upgrade_enums.json`（55 枚举 / 318 值 / 51 类配对，从 Source/FSD 头文件生成）。

| 常用枚举 | 部分值 |
|---|---|
| EAmmoDrivenWeapnUpgradeType | MaxAmmo, ClipSize, RateOfFire, ReloadSpeed, RecoilMultiplier, BurstCount… |
| EDamageUpgrade | Damage, WeakpointDamageMultiplier, StaggerChance, RadialDamage, ArmorPenetration… |
| EHitScanBaseUpgradeType | MaxSpread, SpreadPerShot, RicochetChance, MaxPenetrations… |

## 校验规则（生成器强制）

1. `FormatVersion` 必须 = 1
2. Overrides 键必须能在游戏 pak 中唯一定位到元素资产
3. CustomOverclocks 的 Class/UpgradeType 必须命中映射表；Amount 必须是有限数字
4. Quality ∈ {Clean, Balanced, Unstable}
5. 任一资产补丁 verify 失败 → 整包拒绝产出（不产半成品）

## 示例

见 `examples/`：`00` 空配置（=原版）、`10` 单条改值（M0 实测同款）、`20` 新建超频。
