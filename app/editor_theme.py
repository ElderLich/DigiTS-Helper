"""Shared Qt styles for Time Stranger Mod Studio editors and dialogs."""
from typing import Optional

from PyQt6 import sip
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog, QWidget


def modern_dialog_stylesheet() -> str:
    """Shared dark translucent styling for editor dialogs and popups."""
    return """
        QDialog, QMessageBox, QWizard {
            background-color: #041316;
            color: #e8f2f1;
        }
        QLabel {
            color: #dce9ea;
            font-size: 10.5pt;
        }
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #06181d;
            color: #e8f2f1;
            border: 1px solid rgba(143, 211, 207, 145);
            border-radius: 2px;
            padding: 8px;
            font-size: 10.5pt;
            selection-background-color: #d8872b;
            selection-color: #ffffff;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
        QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border-color: rgba(244, 235, 213, 230);
            background-color: #0a2529;
        }
        QSpinBox, QDoubleSpinBox {
            padding-right: 42px;
        }
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 30px;
            height: 19px;
            border-left: 1px solid rgba(143, 211, 207, 120);
            border-bottom: 1px solid rgba(143, 211, 207, 70);
            background-color: #08262a;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 30px;
            height: 19px;
            border-left: 1px solid rgba(143, 211, 207, 120);
            background-color: #08262a;
        }
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: rgba(216, 135, 43, 150);
        }
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
            image: none;
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-bottom: 6px solid #e8f2f1;
        }
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
            image: none;
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #e8f2f1;
        }
        QComboBox {
            padding-right: 42px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 32px;
            border-left: 1px solid rgba(143, 211, 207, 120);
            background-color: #08262a;
        }
        QComboBox::down-arrow {
            image: none;
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 7px solid #d8872b;
            margin-right: 10px;
        }
        QComboBox QAbstractItemView, QListWidget {
            background-color: #06181d;
            color: #e8f2f1;
            border: 1px solid rgba(143, 211, 207, 140);
            outline: 0;
            font-size: 10.5pt;
        }
        QComboBox QAbstractItemView::item, QListWidget::item {
            color: #e8f2f1;
            min-height: 34px;
            padding: 8px 10px;
            border-bottom: 1px solid rgba(143, 211, 207, 35);
        }
        QComboBox QAbstractItemView::item:hover, QListWidget::item:hover {
            background-color: rgba(35, 78, 77, 210);
            color: #ffffff;
        }
        QComboBox QAbstractItemView::item:selected, QListWidget::item:selected {
            background-color: #d8872b;
            color: #ffffff;
        }
        QListWidget::item:disabled {
            color: #90a4a6;
            background-color: rgba(58, 69, 72, 190);
        }
        QPushButton {
            background-color: #071b20;
            color: #f0f6f4;
            border: 1px solid rgba(143, 211, 207, 130);
            border-left: 4px solid #d8872b;
            border-radius: 2px;
            padding: 9px 14px;
            font-weight: 700;
            font-size: 10.5pt;
        }
        QPushButton:hover {
            background-color: rgba(35, 78, 77, 230);
            border-color: rgba(235, 229, 210, 200);
        }
        QPushButton:disabled {
            color: rgba(230, 238, 238, 90);
            background-color: rgba(12, 22, 27, 150);
            border-color: rgba(111, 137, 137, 65);
        }
        QDialogButtonBox QPushButton {
            min-width: 92px;
        }
        QScrollBar:vertical {
            background: rgba(4, 16, 20, 180);
            width: 12px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: rgba(186, 224, 216, 150);
            min-height: 40px;
            border-radius: 1px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(216, 135, 43, 220);
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
            background: transparent;
            border: none;
        }
    """


MODERN_INLINE_STYLE_REPLACEMENTS = (
    ("background-color: white;", "background-color: rgba(3, 18, 23, 172);"),
    ("background-color: #ffffff;", "background-color: rgba(3, 18, 23, 172);"),
    ("background: white;", "background: rgba(3, 18, 23, 172);"),
    ("background-color: #f8f9fa;", "background-color: rgba(5, 24, 29, 180);"),
    ("background: #f8f9fa;", "background: rgba(5, 24, 29, 180);"),
    ("background: #f0f0f0;", "background: rgba(5, 24, 29, 180);"),
    ("background-color: #e7f5ff;", "background-color: rgba(9, 41, 48, 180);"),
    ("background-color: #eef4ff;", "background-color: rgba(9, 41, 48, 180);"),
    ("background-color: #e9ecef;", "background-color: rgba(8, 24, 31, 190);"),
    ("background: #f1f3f5;", "background: rgba(5, 24, 29, 180);"),
    ("background-color: #fff3cd;", "background-color: rgba(95, 62, 18, 170);"),
    ("background-color: #667eea;", "background-color: #071b20; border-left: 4px solid #d8872b;"),
    ("background-color: #5568d3;", "background-color: rgba(35, 78, 77, 230);"),
    ("background-color: #10b981;", "background-color: #071b20; border-left: 4px solid #20d6a3;"),
    ("background-color: #059669;", "background-color: rgba(20, 70, 56, 230);"),
    ("background-color: #2c9558;", "background-color: #071b20; border-left: 4px solid #20d6a3;"),
    ("background-color: #247a49;", "background-color: rgba(20, 70, 56, 230);"),
    ("background-color: #d9a400;", "background-color: #071b20; border-left: 4px solid #d8872b;"),
    ("background-color: #c29100;", "background-color: rgba(80, 61, 17, 230);"),
    ("stop:0 #667eea, stop:1 #764ba2", "stop:0 rgba(4, 35, 39, 230), stop:1 rgba(216, 135, 43, 210)"),
    ("stop:0 #f8f9fa, stop:1 #e9ecef", "stop:0 rgba(4, 35, 39, 230), stop:1 rgba(216, 135, 43, 210)"),
    ("color: #333333;", "color: #e8f2f1;"),
    ("color: #495057;", "color: #dce9ea;"),
    ("color: #667eea;", "color: #88e9e0;"),
    ("color: #4c63d9;", "color: #88e9e0;"),
    ("color: #4aa3c7;", "color: #88e9e0;"),
    ("color: #2c9558;", "color: #20d6a3;"),
    ("color: #087f5b;", "color: #20d6a3;"),
    ("color: #c967cc;", "color: #d8872b;"),
    ("color: #e85c89;", "color: #88e9e0;"),
    ("color: #c77d00;", "color: #88e9e0;"),
    ("color: #6f42c1;", "color: #88e9e0;"),
    ("color: #d9b12f;", "color: #88e9e0;"),
    ("color: #7d6aad;", "color: #88e9e0;"),
    ("color: #856404;", "color: #d9b77a;"),
    ("color: #555;", "color: #bfd1d2;"),
    ("color: #666;", "color: #a9c1c2;"),
    ("color: #6c757d;", "color: #9fb7b8;"),
    ("color: #adb5bd;", "color: rgba(230, 238, 238, 90);"),
    ("border: 2px solid #dee2e6;", "border: 1px solid rgba(143, 211, 207, 105);"),
    ("border: 2px solid #667eea;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #c9d6ff;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #8fd3f4;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #84fab0;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #fa709a;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #ffd166;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #9b5de5;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #f093fb;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #fee140;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border: 2px solid #a18cd1;", "border: 1px solid rgba(136, 233, 224, 115);"),
    ("border-color: #dee2e6;", "border-color: rgba(143, 211, 207, 105);"),
    ("border-color: #667eea;", "border-color: rgba(136, 233, 224, 115);"),
    ("border-color: #5568d3;", "border-color: rgba(235, 229, 210, 190);"),
    ("border-color: #10b981;", "border-color: rgba(32, 214, 163, 150);"),
    ("border-color: #059669;", "border-color: rgba(32, 214, 163, 150);"),
    ("border-radius: 8px;", "border-radius: 2px;"),
    ("border-radius: 6px;", "border-radius: 2px;"),
)


def modernize_inline_light_styles(root: QWidget) -> None:
    """Translate old inline light-panel styles into the modern dark surface."""
    if sip.isdeleted(root):
        return  # A parent can close the dialog before its queued style pass.
    for widget in [root, *root.findChildren(QWidget)]:
        style = widget.styleSheet()
        if not style:
            continue
        updated = style
        for old, new in MODERN_INLINE_STYLE_REPLACEMENTS:
            updated = updated.replace(old, new)
        if updated != style:
            widget.setStyleSheet(updated)


def apply_modern_dialog_theme(dialog: QDialog) -> None:
    dialog.setStyleSheet(modern_dialog_stylesheet())
    QTimer.singleShot(0, lambda: modernize_inline_light_styles(dialog))


def modern_groupbox_style(accent: str = "#88e9e0", title_color: Optional[str] = None) -> str:
    title = title_color or accent
    return f"""
        QGroupBox {{
            color: #e8f2f1;
            font-weight: 700;
            border: 1px solid {accent};
            border-radius: 2px;
            margin-top: 18px;
            padding: 18px 10px 10px 10px;
            background-color: rgba(3, 18, 23, 185);
            font-size: 11pt;
        }}
        QGroupBox::title {{
            color: {title};
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 9px;
            background-color: rgba(3, 18, 23, 235);
        }}
    """


def modern_action_button_style(accent: str = "#d8872b", checked_accent: str = "#20d6a3") -> str:
    return f"""
        QPushButton {{
            background-color: #071b20;
            color: #f0f6f4;
            border: 1px solid rgba(143, 211, 207, 130);
            border-left: 4px solid {accent};
            border-radius: 2px;
            padding: 9px 14px;
            font-weight: 700;
            font-size: 10pt;
        }}
        QPushButton:hover {{
            background-color: rgba(35, 78, 77, 230);
            border-color: rgba(235, 229, 210, 200);
        }}
        QPushButton:pressed {{
            background-color: rgba(216, 135, 43, 230);
            color: #ffffff;
        }}
        QPushButton:checked {{
            background-color: rgba(13, 66, 53, 230);
            border-left-color: {checked_accent};
            color: #ffffff;
        }}
        QPushButton:disabled {{
            color: rgba(230, 238, 238, 90);
            background-color: rgba(12, 22, 27, 150);
            border-color: rgba(111, 137, 137, 65);
            border-left-color: rgba(111, 137, 137, 80);
        }}
    """


def modern_info_panel_style(accent: str = "#88e9e0") -> str:
    return f"""
        color: #dce9ea;
        padding: 10px 12px;
        background-color: rgba(5, 24, 29, 190);
        border: 1px solid rgba(143, 211, 207, 95);
        border-left: 4px solid {accent};
        border-radius: 2px;
    """


def modern_status_panel_style(accent: str = "#88e9e0") -> str:
    return f"""
        color: #dce9ea;
        padding: 10px 12px;
        background-color: rgba(9, 41, 48, 180);
        border: 1px solid rgba(143, 211, 207, 100);
        border-left: 4px solid {accent};
        border-radius: 2px;
        margin-top: 10px;
    """


def modern_warning_panel_style() -> str:
    return """
        color: #f0d6a8;
        padding: 9px 12px;
        background-color: rgba(95, 62, 18, 170);
        border: 1px solid rgba(216, 135, 43, 135);
        border-left: 4px solid #d8872b;
        border-radius: 2px;
    """


def modern_muted_text_style(font_size: str = "9pt") -> str:
    return f"color: #a9c1c2; font-size: {font_size};"
