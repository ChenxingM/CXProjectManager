QSS_THEME = """
/* 全局样式 */
* {
    color: #E0E0E0;
    font-family: "MiSans", "微软雅黑", "Segoe UI", Arial;
    font-size: 13px;
}

QMainWindow, QWidget {
    background-color: #1E1E1E;
}

/* 按钮样式 */
QPushButton {
    background-color: #2D2D2D;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #3A3A3A;
    border-color: #4A4A4A;
}

QPushButton:pressed {
    background-color: #252525;
}

QPushButton:disabled {
    color: #666666;
    background-color: #242424;
}

/* 输入框样式 */
QLineEdit, QSpinBox, QComboBox {
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    padding: 4px 6px;
    min-height: 24px;
    height: 24px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #03A9F4;
    background-color: #2A2A2A;
}

/* 标签样式 */
QLabel {
    padding: 2px;
}

/* 分组框样式 */
QGroupBox {
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

/* 列表控件样式 */
QListWidget {
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    outline: none;
    alternate-background-color: #2F2F2F;  /* 隔行背景色 - 调亮一点 */
}

QListWidget::item {
    padding: 4px 8px;
    background-color: transparent;
}

QListWidget::item:alternate {
    background-color: #2F2F2F;  /* 偶数行背景色 */
}

QListWidget::item:hover {
    background-color: #3A3A3A !important;  /* 确保悬停效果优先 */
}

QListWidget::item:selected {
    background-color: #03A9F4 !important;  /* 确保选中效果优先 */
}

/* Tab控件样式 */
QTabWidget::pane {
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    top: -1px;
}

QTabWidget::tab-bar {
    left: 0px;
}

QTabBar::tab {
    background-color: #2D2D2D;
    color: #B0B0B0;
    border: 1px solid #3C3C3C;
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    min-width: 60px;
}

QTabBar::tab {
    border-top-left-radius: 4px;
}

QTabBar::tab {
    border-top-right-radius: 4px;
}

QTabBar::tab:hover {
    background-color: #3A3A3A;
    color: #E0E0E0;
}

QTabBar::tab:selected {
    background-color: #03A9F4;
    color: #FFFFFF;
    font-weight: bold;
    border-color: #03A9F4;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

/* 菜单样式 */
QMenuBar {
    background-color: #2D2D2D;
    border-bottom: 1px solid #3C3C3C;
}

QMenuBar::item:selected {
    background-color: #3A3A3A;
}

QMenu {
    background-color: #2D2D2D;
    border: 1px solid #3C3C3C;
}

QMenu::item:selected {
    background-color: #03A9F4;
}

/* 状态栏样式 */
QStatusBar {
    background-color: #252525;
    border-top: 1px solid #3C3C3C;
}

/* 复选框样式 */
QCheckBox {
    spacing: 10px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
    background-color: #262626;
}

QCheckBox::indicator:checked {
    background-color: #03A9F4;
    border-color: #03A9F4;
}

QCheckBox::indicator:checked::after {
    content: "";
    position: absolute;
    width: 6px;
    height: 10px;
    border: solid white;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
    top: 2px;
    left: 5px;
}

/* 分割器样式 */
QSplitter::handle {
    background-color: #2D2D2D;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

QSplitter::handle:hover {
    background-color: #03A9F4;
}

/* 树控件样式 */
QTreeWidget {
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    outline: none;
    alternate-background-color: #2F2F2F;  /* 隔行背景色 - 调亮一点 */
}

QTreeWidget::item {
    padding: 4px;
    background-color: transparent;
}

QTreeWidget::item:alternate {
    background-color: #2F2F2F;  /* 偶数行背景色 */
}

QTreeWidget::item:hover {
    background-color: #3A3A3A !important;  /* 确保悬停效果优先 */
}

QTreeWidget::item:selected {
    background-color: #03A9F4 !important;  /* 确保选中效果优先 */
}

/* 树控件展开/折叠箭头 - 16x16像素 */
QTreeWidget::branch:has-children:closed {
    image: url(_imgs/tree_arrow_closed.png);
}

QTreeWidget::branch:has-children:open {
    image: url(_imgs/tree_arrow_open.png);
}

QTreeWidget::branch:has-children:closed:hover {
    image: url(_imgs/tree_arrow_closed_hover.png);
}

QTreeWidget::branch:has-children:open:hover {
    image: url(_imgs/tree_arrow_open_hover.png);
}

/* 树控件标题栏样式 */
QHeaderView::section {
    background: #3C3C3C;
    border: none;
    padding: 4px 8px;
    font-weight: bold;
    color: #B0B0B0;
}

QHeaderView::section:hover {
    background: #4A4A4A;
    color: #E0E0E0;
}

QHeaderView {
    background: none;
    border: none;
}

/* 文本编辑框样式 */
QTextEdit {
    font-family: "MiSans", "微软雅黑", "Segoe UI", Arial;
    background-color: #262626;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
}

/* 滚动条样式 */
QScrollBar:vertical {
    background-color: #262626;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #3C3C3C;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4A4A4A;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #262626;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #3C3C3C;
    min-width: 20px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4A4A4A;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* SpinBox按钮样式 */
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #2D2D2D;
    border: 1px solid #3C3C3C;
    width: 16px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #03A9F4;
}

/* SpinBox箭头 - 12x12像素 */
QSpinBox::up-arrow {
    image: url(_imgs/spinbox_arrow_up.png);
    width: 8px;
    height: 8px;
}

QSpinBox::down-arrow {
    image: url(_imgs/spinbox_arrow_down.png);
    width: 8px;
    height: 8px;
}

QSpinBox::up-arrow:hover {
    image: url(_imgs/spinbox_arrow_up_hover.png);
}

QSpinBox::down-arrow:hover {
    image: url(_imgs/spinbox_arrow_down_hover.png);
}

QSpinBox::up-arrow:disabled {
    image: url(_imgs/spinbox_up_arrow_disabled.png);
}

QSpinBox::down-arrow:disabled {
    image: url(_imgs/spinbox_down_arrow_disabled.png);
}

/* ComboBox下拉按钮样式 */
QComboBox::drop-down {
    border: none;
    width: 20px;
    background-color: transparent;
}

/* ComboBox箭头 - 12x12像素 */
QComboBox::down-arrow {
    image: url(_imgs/combobox_arrow_down.png);
    width: 8px;
    height: 8px;
}

QComboBox::down-arrow:hover {
    image: url(_imgs/combobox_arrow_down_hover.png);
}

QComboBox::down-arrow:on {
    image: url(_imgs/combobox_arrow_up.png);  /* 展开时显示向上箭头 */
}

QComboBox::down-arrow:disabled {
    image: url(_imgs/combobox_arrow_disabled.png);
}

QComboBox QAbstractItemView {
    background-color: #2D2D2D;
    border: 1px solid #3C3C3C;
    selection-background-color: #03A9F4;
    outline: none;
}
"""
