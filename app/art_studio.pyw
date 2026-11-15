"""Standalone Windows editor for Time Stranger dot sprites and profile pictures."""
import sys

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QFrame, QMainWindow, QScrollArea, QTabWidget

from dot_sprite_tool import DotSpriteTab
from editor_theme import modern_dialog_stylesheet, modern_groupbox_style
from profile_portrait import PortraitPanel


class ArtStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Stranger Art Studio")
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        self.portraits = PortraitPanel()
        for label, panel in (("Dot Sprites", DotSpriteTab()), ("Portraits", self.portraits)):
            page = QScrollArea()
            page.setFrameShape(QFrame.Shape.NoFrame)
            page.setWidgetResizable(True)
            page.setWidget(panel)
            tabs.addTab(page, label)
        available = self.screen().availableGeometry().size()
        self.resize(QSize(1000, 820).boundedTo(available * 0.92))

    def closeEvent(self, event):
        self.portraits.shutdown()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Time Stranger Art Studio")
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in (
        (QPalette.ColorRole.Window, "#071b20"),
        (QPalette.ColorRole.WindowText, "#e8f2f1"),
        (QPalette.ColorRole.Base, "#041316"),
        (QPalette.ColorRole.AlternateBase, "#0e2b30"),
        (QPalette.ColorRole.Text, "#e8f2f1"),
        (QPalette.ColorRole.Button, "#102c30"),
        (QPalette.ColorRole.ButtonText, "#e8f2f1"),
        (QPalette.ColorRole.Highlight, "#246469"),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(modern_dialog_stylesheet() + modern_groupbox_style() + """
        QTabWidget::pane { border: 1px solid #34565b; }
        QTabBar::tab { padding: 10px 24px; color: #c5d5d5; }
        QTabBar::tab:selected { color: white; background: #103238; border-bottom: 3px solid #88e9e0; }
        QTabBar::tab:hover:!selected { background: #10292e; }
    """)
    window = ArtStudio()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
