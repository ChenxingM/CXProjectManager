# CX Project Manager

CX Project Manager 的重构版本，将原来的单一巨大文件拆分为多个模块，提升了代码的可读性和可维护性。

## 📁 完整项目结构

```
CXProjectManager/
    ├── requirements.txt          # 项目依赖
    ├── README.md                 # 项目说明文档
    ├── ae_settings/              # AE 渲染和输出模块设置
    ├── _imgs/                     # 图标和资源文件
    └── cx_project_manager/
            ├── __init__.py                # 项目包初始化
            ├── main.py                    # 主程序入口
            ├── core/                      # 核心业务逻辑
            │   ├── __init__.py             
            │   ├── project_manager.py     # 项目管理核心类
            │   └── registry.py            # 项目注册管理器
            ├── ui/                        # 用户界面
            │   ├── __init__.py            # 
            │   ├── main_window.py         # 主窗口
            │   ├── dialogs.py             # 各种对话框
            │   └── widgets.py             # 自定义控件
            └── utils/                     # 原有工具文件
                ├── qss.py                 # 样式表
                ├── version_info.py        # 版本信息
                ├── constants.py           # 常量定义
                ├── models.py              # 数据类定义
                └── utils.py               # 工具函数
```

## 🚀 使用方法

### 1. 安装依赖

```bash
pip install PySide6
```

### 2. 运行程序

```bash
# 方法1：直接运行主程序
python main.py

# 方法2：作为模块运行
python -m project_manager
```

## 🔧 模块说明

### 核心模块 (core/)

- **`project_manager.py`**: 包含 `ProjectManager` 类，负责项目的创建、加载、保存等核心业务逻辑
- **`registry.py`**: 包含 `ProjectRegistry` 类，负责项目注册管理

### 用户界面模块 (ui/)

- **`main_window.py`**: 主窗口类 `CXProjectManager`，处理所有UI交互
- **`dialogs.py`**: 各种对话框组件
  - `ProjectBrowserDialog`: 项目浏览器
  - `ReuseCutDialog`: 兼用卡创建对话框
  - `VersionConfirmDialog`: 版本确认对话框
  - `BatchAepDialog`: 批量AEP操作对话框
- **`widgets.py`**: 自定义控件
  - `SearchLineEdit`: 支持Esc清除的搜索框
  - `FileItemDelegate`: 文件列表项委托
  - `DetailedFileListWidget`: 详细文件列表控件

### 基础模块

- **`constants.py`**: 所有常量定义，包括文件扩展名、正则表达式、枚举类型等
- **`models.py`**: 数据类定义，包括项目信息、路径配置、兼用卡信息等
- **`utils.py`**: 通用工具函数，如文件操作、路径处理、版本提取等

## 📈 重构改进

### 1. 代码组织

- **模块化设计**: 将原来的4000+行代码拆分为多个专门的模块
- **职责分离**: 每个模块都有明确的职责范围
- **易于维护**: 修改特定功能时只需要关注相关模块

### 2. 导入优化

- **相对导入**: 使用相对导入避免循环依赖
- **按需导入**: 只导入需要的组件
- **类型提示**: 保持完整的类型提示支持

### 3. 扩展性

- **插件化**: 对话框和控件可以独立开发和测试
- **配置分离**: 常量和配置集中管理
- **接口清晰**: 各模块间的接口明确定义

## 🛠️ 开发指南

### 添加新功能

1. **新对话框**: 在 `ui/dialogs.py` 中添加
2. **新控件**: 在 `ui/widgets.py` 中添加
3. **新业务逻辑**: 在 `core/` 模块中添加
4. **新常量**: 在 `constants.py` 中定义
5. **新工具函数**: 在 `utils.py` 中添加

### 测试

```bash
# 测试单个模块
python -c "from core.project_manager import ProjectManager; print('ProjectManager OK')"
python -c "from ui.main_window import CXProjectManager; print('UI OK')"
```

### 调试

每个模块都可以独立导入和测试：

```python
# 测试项目管理器
from core.project_manager import ProjectManager
pm = ProjectManager()

# 测试对话框
from ui.dialogs import ProjectBrowserDialog
# dialog = ProjectBrowserDialog(registry, parent)
```

## ⚠️ 注意事项

1. **保持依赖**: `_utils/` 文件夹中的文件保持原样，确保样式和版本信息正常工作
2. **相对路径**: 运行时确保工作目录正确，图标和资源文件路径相对于主程序
3. **配置兼容**: 新版本与原版本的配置文件完全兼容
4. **创建 __init__.py**: 记得创建 `core/__init__.py` 和 `ui/__init__.py` 文件


## 🔮 未来计划

- [ ] 添加单元测试
- [ ] 完善文档字符串
- [ ] 添加日志系统
- [ ] 插件系统
- [ ] 国际化支持

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests 来改进这个项目！

---

**作者**: 千石まよひ  
**GitHub**: https://github.com/ChenxingM/CXProjectManager  
**邮箱**: tammcx@gmail.com