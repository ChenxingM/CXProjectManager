# CX Project Manager

跨平台深色主题 GUI，用于 **动画 / VFX** 项目目录生成与素材管理。

---

## ✨ 主要特性

| 模块 | 亮点 |
|------|------|
| **项目初始化** | • 一键创建 / 打开项目<br>• 记住默认根目录 & 最近项目（最多 8 个） |
| **Episode / Cut 管理** | • 支持 *多集* 与 *单集 / PV* 两种模式<br>• 单个 / 批量创建，自动检测已存在项 |
| **目录树** | • 实时展示磁盘结构<br>• 双击节点即可在系统文件管理器中定位 |
| **素材导入** | • BG / Cell / 3DCG / Timesheet 浏览导入<br>• 自动复制并规范命名，支持批量 |
| **AEP 模板克隆** | • 将 `*.aep` 放入 `07_master_assets/aep_templates/`，新建 Cut 时自动复制为 `*_v0.aep` |
| **持久化配置** | • 项目级 `project_config.json` 记录所有路径 / Episode / Cut 信息<br>• 软件级 `~/.cxpm_settings.json` 记忆默认根目录与最近项目 |
| **深色 UI** | • 纯 QSS 自定义高对比度界面 |

---

## 🛠 环境要求

- **Python 3.9+**
- **PySide6**   `pip install pyside6`
- Windows / macOS / Linux （调用系统 Explorer / open / xdg-open 打开文件夹）

---

## 🚀 快速上手

```bash
# 1. 安装依赖
pip install pyside6

# 2. 运行
python cx_project_manager.py
```

1. **设置默认根目录**（菜单 **文件 ▸ 设置默认路径**）。
2. **新建项目**：若已设置默认根目录，只需输入项目名即可创建；否则选择目录后输入名称。
3. 左侧面板 **Episode / Cut** 创建。右侧目录树实时刷新。
4. 导入素材：选择目标 Cut → 点击浏览按钮 → 自动复制并命名。

> **小贴士**：若预先将 AE 模板放入 `07_master_assets/aep_templates/`，新建 Cut 时会自动生成 `*_v0.aep` 版本。

---

## 📂 生成目录示例（多 Episode 模式）

```
AnimeProject/
├── 00_reference_project/              # 全项目通用参考资料
│   ├── character_design/              # 角色设定图、表情设定等
│   ├── art_design/                    # 背景风格、美术风格集
│   ├── concept_art/                   # 场景概念、美术氛围图
│   ├── storyboard/                    # 整体分镜结构、PV用分镜
│   ├── docs/                          # 世界观设定、用语集、制作文档
│   └── other_design/                  # UI、LOGO、道具、杂项设定
│
├── ep01/
│   ├── 00_reference/                  # 本集特有参考（分镜、脚本、注释）
│   │   ├── storyboard/
│   │   ├── script/
│   │   └── director_notes/
│   │ 
│   ├── 01_vfx/                        # AE 工程 + 素材 + 预渲染
│   │   ├── timesheets/               #  所有 cut 对应的摄影表 CSV
│   │   │   ├── 001.csv
│   │   │   ├── 002.csv
│   │   ├── 001/
│   │   │   ├── title_001_v001.aep    # AE 工程（多版本）
│   │   │   ├── cell/                 # 原画、动画层
│   │   │   │   ├── A1.png
│   │   │   │   └── A2.png
│   │   │   ├── bg/                   # 背景图像（可为 psd/png）
│   │   │   ├── prerender/            # AE 中预渲染缓存（Alpha通道特效等）
│   │   │   └── notes.txt             # 可选：cut 简述或变更记录
│   │   ├── 002/
│   │   └── ...
│   │
│   ├── 03_preview/                    # AE 输出的低清 mov 预览
│   │   ├── 001_preview.mov
│   │   ├── 002_preview.mov
│   │   └── ...
│   ├── 04_log/                        # 差分记录、版本记录等
│   │   ├── 001/
│   │   │   ├── changelog.json
│   │   │   └── auto_notes.md
│   │   │ 
│   └── 05_output_mixdown/            # 本集成品混剪或ED/OP片段等
│
├── ep02/                              # 其他 episode 结构一致
│   └── ...
│ 
├── 06_render/                            # 所有最终渲染集中统一管理
│   ├── ep01/
│   │   ├── 001/
│   │   │   ├── png_seq/
│   │   │   │   ├── title_001_0000.png
│   │   │   ├── prores/
│   │   │   │   └── title_001_v001.mov
│   │   │   ├── mp4/
│   │   │   └── thumbnail.jpg
│   │   ├── 002/
│   ├── ep02/
│   │   └── ...
│   
├── 07_master_assets/                     # 全项目共用素材
│   ├── fonts/
│   ├── logo/
│   └── fx_presets/
│ 
├── 08_tools/                             # 自动化脚本与工具
│   ├── ae_scripts/                    # AE 脚本等
│   ├── python/
│   └── config/                        # 工具配置文件（如路径映射）
│ 
├── project_config.json                # 工程配置文件
│ 
└── README.md                          # 项目说明，自动生成
```

*单集 / PV 模式* 会省略 `epXX` 层级，Cut 直接位于 `01_vfx` 与 `06_render` 下。

---

## 🔧 项目配置文件 `project_config.json`

```json
{
  "project_name": "MyAnimeProj",
  "project_path": "/path/to/MyAnimeProj",
  "no_episode": false,
  "episodes": {
    "ep01": ["001", "002"]
  },
  "cuts": [],
  "paths": {
    "reference": "00_reference_project",
    "render": "06_render",
    "assets": "07_master_assets",
    "aep_templates": "07_master_assets/aep_templates"
  },
  "created_time": "2025-06-27T12:34:56",
  "last_modified": "..."
}
```

---

## 🗄 软件设置 `~/.cxpm_settings.json`

```json
{
  "default_root": "/Volumes/Projects",
  "recent_projects": [
    "/Volumes/Projects/MyAnimeProj",
    "/Volumes/Projects/PV_Demo"
  ]
}
```

---

## ⏭️ 规划路线

- 🔄 文件系统监听，目录变化自动刷新
- 📝 Cut 状态 / 备注面板
- 🔍 标签与关键字搜索素材
- 🖥️ CLI 接口，方便 CI / 渲染农场

欢迎反馈与贡献，一起打造更高效的动画制作流水线！🚀


