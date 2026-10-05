# CH 老 bug 分诊（Iris 2026-10-05 委托"随便修一下"）

> 对象：iris-cat-dev/DRGMod.CustomHazard issue #1（12 条）+ #3 评论（跨配置污染）
> 分诊日期：2026-10-05 · 基于 v0.0.3 cooked 资产解剖 + Koncin 注释版对照

## 分诊总表

| # | bug | 根因层 | 可修性（当前工具） |
|---|---|---|---|
| 1 | scale 客机异常+碰撞体积异常 | UE 复制/生成层 | ❌ 深（需 CH_UI） |
| 2 | PointExtractionScalar 不起效 | **引擎层**（Koncin 注释原话："1和10没啥区别"） | ❌ 非 CH bug |
| 3 | remove 无法移除 ED_Terminator | CH_UI 应用链 | ❌ 需 CH_UI 可补丁 |
| 4 | DifficultyRating/Rarity 阈值(999 无效) | CH_UI 应用链（clamp） | ❌ 需 CH_UI |
| 5 | IdealSpawnSize 不生效 | **引擎层**（Koncin 注释 #10：与 min/max 并非等价） | ❌ 非 CH bug |
| 6 | StationaryEnemyDiversity 上限 4 | CH_UI 应用链 | ❌ 需 CH_UI |
| 7 | hazard 5++ 兼容 | 跨 mod 集成 | ⏳ 需与 Iris 对齐设计 |
| 8 | 部分单位 elite 套娃 | 敌人个体差异 | ⏳ 逐个排查 |
| 9 | DisruptiveEnemies 移除控制 | CH_UI 应用链 | ❌ 需 CH_UI |
| 10 | ~~HazardBonus 1.33 上限~~ | **Iris 已修**（最大 1.65） | ✅ 已关闭 |
| 11 | 新四生物无 Elite | **ED 资产缺 SpawnRarityItems**（实测：原版靠 SpawnRarityItems→精英变体 ED；四新 ED 无此数组，且无精英变体资产可指） | ⚠️ 需新工具造变体资产（或 Iris 提供精英变体 ED） |
| 12 | 5++ UI 开启后仍 5 级 | UI/模式判定 | ❌ 需 CH_UI |
| #3评论 | **跨配置污染**（加载 A 再 B，任务出 A+B 单位；官方难度也复现；重启恢复） | 配置应用不先重置（池子应用 52 处全在 CH_UI） | ❌ 需 CH_UI 可补丁（修复设计已备，见下） |

## 结论

**12 条里 8 条的应用链代码全在 CH_UI——当前 2026-06 版编译器对 CH_UI 资产级编译阻塞**（13 次探针实测：连 3 行的 Poll 函数都无法重编译，根因未查明）。**解锁 CH_UI = 解锁 8 条 bug**。

## 解锁路径（二选一）

1. **Iris 提供新版 UAssetStudio.Cli 构建**（仓库 2026-07-03 有 "enhance KismetScript" 提交，可能已修）——QQ 直传最快
2. 本机装 .NET 8 SDK + gh-proxy 拉源码自编译（上次 winget 安装被 UAC 取消，需用户在电脑前确认）

## 修复设计备稿（工具解锁后即可施工）

- **跨配置污染**：在配置应用前先重置——CH 每次应用新配置时，先还原上一份配置对池子/描述符的全部改动（需快照-还原机制；挂在我们已打通的触发点上，时序需挪到应用前）
- **新四生物 Elite**：为四 ED 补 SpawnRarityItems 指向精英变体；变体资产缺失需造新资产（--full 路线 + AssetRegistry，v1.1 已立项）
- **Threshold/clamp 类**：应用循环里的 clamp 常量放宽 + 文档注明安全范围
