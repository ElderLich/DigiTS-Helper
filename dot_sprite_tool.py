"""Map original 16-pixel poses to the game's four-frame dot texture."""
import io
import os
from pathlib import Path
import struct
import tempfile

from PIL import Image
from PyQt6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListView, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)


TILE = 16
SLOT_NAMES = ("Upper left", "Upper right", "Lower left", "Lower right")
# The original dot textures use a single uncompressed DDS surface, A1R5G5B5.
DDS_HEADER = struct.pack("<4s31I", b"DDS ", 124, 0x81007, 32, 32, 2048, 0, 0,
                         *([0] * 11), 32, 0x41, 0, 16, 0x7C00, 0x3E0, 0x1F, 0x8000,
                         0x1000, 0, 0, 0, 0)


class FrameGrid:
    def __init__(self, image, x=0, y=0, gap_x=0, gap_y=0):
        self.image = image
        self.x, self.y = x, y
        self.step_x, self.step_y = TILE + gap_x, TILE + gap_y
        if min(x, y, gap_x, gap_y) < 0:
            raise ValueError("Frame offsets and gaps must be zero or greater.")
        self.columns = max(0, (image.width - x + gap_x) // self.step_x)
        self.rows = max(0, (image.height - y + gap_y) // self.step_y)

    def __len__(self):
        return self.columns * self.rows

    def tile(self, index):
        if not 0 <= index < len(self):
            raise ValueError("Select a complete 16 × 16 frame.")
        x = self.x + index % self.columns * self.step_x
        y = self.y + index // self.columns * self.step_y
        return self.image.crop((x, y, x + TILE, y + TILE))

    def defaults(self):
        if (self.columns, self.rows) == (3, 4):
            # The standard color sheet's two idle poses, open jaws/attack, and fourth pose.
            return [0, 1, 11, 10]
        return [min(i, len(self) - 1) for i in range(4)] if len(self) else []


def encode_dot(grid, slots):
    if len(slots) != 4:
        raise ValueError("Choose all four game frames.")
    atlas = Image.new("RGBA", (32, 32))
    for i, frame in enumerate(slots):
        atlas.paste(grid.tile(frame), (i % 2 * TILE, i // 2 * TILE))
    # Vanilla stores transparent pixels as green with the alpha bit cleared.
    words = []
    for r, g, b, a in struct.iter_unpack("4B", atlas.tobytes()):
        if a < 128:
            words.append(0x03E0)
        else:
            words.append(0x8000 | (((r * 31 + 127) // 255) << 10)
                         | (((g * 31 + 127) // 255) << 5) | ((b * 31 + 127) // 255))
    return DDS_HEADER + struct.pack("<1024H", *words)


def load_sheet(path):
    with Image.open(path) as source:
        if Path(path).suffix.lower() in (".dds", ".img") and (source.format != "DDS" or source.size != (32, 32)):
            raise ValueError("A native dot atlas must be a 32 × 32 DDS or IMG texture.")
        if min(source.size) < TILE:
            raise ValueError("The artwork must contain at least one complete 16 × 16 frame.")
        return source.convert("RGBA")


def output_path(folder, digimon_id):
    if not isinstance(digimon_id, int) or not 1 <= digimon_id <= 2**31 - 1:
        raise ValueError("Enter the Digimon’s numeric ID.")
    folder = Path(folder)
    name = folder.name.casefold()
    if name == "dsts-loader":
        folder = folder / "patch" / "images"
    elif name == "patch":
        folder = folder / "images"
    elif name != "images":
        folder = folder / "dsts-loader" / "patch" / "images"
    dest = folder / f"dot{digimon_id:03d}.img"
    dds = dest.with_suffix(".dds")
    if dest.is_file() and dds.is_file():
        raise ValueError(f"Both {dest.name} and {dds.name} already exist. Choose one texture to keep before exporting.")
    return dds if dds.is_file() else dest


def save_texture(dest, data, previous):
    """Publish atomically and check the exact file version approved for replacement."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as out:
        temp = Path(out.name)
        try:
            out.write(data)
        except BaseException:
            out.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        if previous is None:
            # A hard link publishes the completed file only if the name is still free.
            if os.name == "nt":
                temp.rename(dest)
            else:
                os.link(temp, dest)
        else:
            if not dest.is_file() or dest.read_bytes() != previous:
                raise OSError(f"{dest.name} changed after you approved the replacement. Reopen it and retry.")
            os.replace(temp, dest)
    finally:
        temp.unlink(missing_ok=True)


def pixel_preview(image, zoom):
    image = image.convert("RGBA")
    bg = Image.new("RGB", image.size)
    colors = ((51, 67, 75), (84, 102, 109))
    bg.putdata([colors[(x // 2 + y // 2) % 2]
                for y in range(image.height) for x in range(image.width)])
    bg.paste(image, mask=image.getchannel("A"))
    rgb = bg.tobytes()
    picture = QImage(rgb, bg.width, bg.height, bg.width * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(picture).scaled(bg.width * zoom, bg.height * zoom,
                                            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)


class FrameModel(QAbstractListModel):
    def __init__(self, parent):
        super().__init__(parent)
        self.grid = None

    def set_grid(self, grid):
        self.beginResetModel()
        self.grid = grid
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.grid is None else len(self.grid)

    def data(self, index, role):
        if not index.isValid() or index.row() >= self.rowCount():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return str(index.row() + 1)
        if role == Qt.ItemDataRole.DecorationRole:
            return QIcon(pixel_preview(self.grid.tile(index.row()), 3))
        return None


class DotSpriteTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.source_path = None
        self.slots = []
        self.native_data = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        open_button = QPushButton("Open sprite sheet…")
        open_button.clicked.connect(self.choose_source)
        self.source = QLabel("Choose a color sprite sheet or a native dot atlas.")
        self.source.setWordWrap(True)
        top.addWidget(open_button)
        top.addWidget(self.source, 1)
        layout.addLayout(top)

        body = QHBoxLayout()
        source_box = QGroupBox("Source frames")
        left = QVBoxLayout(source_box)
        self.frames = QListView()
        self.frames.setViewMode(QListView.ViewMode.IconMode)
        self.frames.setResizeMode(QListView.ResizeMode.Adjust)
        self.frames.setMovement(QListView.Movement.Static)
        self.frames.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.frames.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.frames.setIconSize(QSize(48, 48))
        self.frames.setGridSize(QSize(68, 76))
        self.frames.setUniformItemSizes(True)
        self.frames.setAccessibleName("Source frames")
        self.model = FrameModel(self.frames)
        self.frames.setModel(self.model)
        self.frames.selectionModel().currentChanged.connect(self.show_preview)
        left.addWidget(self.frames, 1)
        cropping = QGridLayout()
        self.grid_fields = []
        for index, label in enumerate(("Left offset", "Top offset", "Column gap", "Row gap")):
            field = QSpinBox()
            field.setSuffix(" px")
            field.setAccessibleName(label)
            field.valueChanged.connect(self.update_grid)
            self.grid_fields.append(field)
            r, c = divmod(index, 2)
            cropping.addWidget(QLabel(label), r, c * 2)
            cropping.addWidget(field, r, c * 2 + 1)
        left.addLayout(cropping)
        self.grid_info = QLabel()
        self.grid_info.setWordWrap(True)
        left.addWidget(self.grid_info)
        body.addWidget(source_box, 1)

        output_box = QGroupBox("Game frames")
        right = QVBoxLayout(output_box)
        hint = QLabel("Select a source frame, then click the game slot where it belongs.")
        hint.setWordWrap(True)
        right.addWidget(hint)
        mapping = QGridLayout()
        self.slot_buttons = []
        for i, name in enumerate(SLOT_NAMES):
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, slot=i: self.assign_frame(slot))
            button.setToolTip(f"Use the selected source frame in the {name.lower()} slot")
            self.slot_buttons.append(button)
            mapping.addWidget(button, i // 2, i % 2)
        right.addLayout(mapping)
        views = QGridLayout()
        self.pose_preview = QLabel()
        self.atlas_preview = QLabel()
        self.atlas_preview.setToolTip("Native 5-bit RGB and 1-bit alpha. Pixels with alpha below 128 are transparent.")
        for col, (title, widget) in enumerate((("Selected 16 × 16", self.pose_preview), ("Game atlas 32 × 32", self.atlas_preview))):
            views.addWidget(QLabel(title), 0, col, Qt.AlignmentFlag.AlignCenter)
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            views.addWidget(widget, 1, col, Qt.AlignmentFlag.AlignCenter)
        right.addLayout(views, 1)
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Preview scale"))
        self.zoom = QComboBox()
        for factor in (1, 2, 4, 6):
            self.zoom.addItem(f"{factor}×", factor)
        self.zoom.setCurrentIndex(2)
        self.zoom.currentIndexChanged.connect(self.show_preview)
        zoom_row.addWidget(self.zoom)
        zoom_row.addStretch()
        right.addLayout(zoom_row)
        body.addWidget(output_box, 1)
        layout.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.addWidget(QLabel("Digimon ID"))
        self.digimon_id = QSpinBox()
        self.digimon_id.setRange(0, 2**31 - 1)
        self.digimon_id.setSpecialValueText("Choose ID")
        self.digimon_id.valueChanged.connect(self.update_destination)
        footer.addWidget(self.digimon_id)
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Output mod or staging folder")
        self.folder.textChanged.connect(self.update_destination)
        footer.addWidget(self.folder, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_folder)
        footer.addWidget(browse)
        self.export = QPushButton("Export dot sprite")
        self.export.clicked.connect(self.export_sprite)
        footer.addWidget(self.export)
        layout.addLayout(footer)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.show_preview()

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open sprite sheet", str(self.source_path or ""),
                                              "Sprite sheets (*.png *.bmp *.tga *.gif *.webp *.dds *.img)")
        if path:
            try:
                self.open_sheet(Path(path))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not open sprite sheet", str(exc))

    def open_sheet(self, path):
        path = Path(path)
        self.image = load_sheet(path)
        self.source_path = path
        self.source.setText(f"{path.name}   {self.image.width} × {self.image.height} px")
        self.source.setToolTip(str(path))
        for field, extent in zip(self.grid_fields, (self.image.width, self.image.height) * 2):
            field.blockSignals(True)
            field.setRange(0, extent)
            field.setValue(0)
            field.blockSignals(False)
        self.update_grid()

    def update_grid(self):
        if self.image is None:
            return
        grid = FrameGrid(self.image, *(field.value() for field in self.grid_fields))
        self.slots = grid.defaults()
        self.model.set_grid(grid)
        if len(grid):
            end_x = grid.x + (grid.columns - 1) * grid.step_x + TILE
            end_y = grid.y + (grid.rows - 1) * grid.step_y + TILE
            info = f"{grid.columns} columns × {grid.rows} rows of 16 × 16 pixels."
            if end_x < grid.image.width or end_y < grid.image.height:
                info += f" Outside the grid: {grid.image.width-end_x} px right, {grid.image.height-end_y} px below."
            self.grid_info.setText(info)
            self.frames.setCurrentIndex(self.model.index(0))
        else:
            self.grid_info.setText("No complete 16 × 16 frame fits at this offset.")
        self.show_preview()

    def assign_frame(self, slot):
        frame = self.frames.currentIndex()
        if frame.isValid() and self.slots:
            self.slots[slot] = frame.row()
            self.show_preview()

    def show_preview(self, *_args):
        frame = self.frames.currentIndex()
        grid = self.model.grid
        self.native_data = encode_dot(grid, self.slots) if self.slots else None
        zoom = self.zoom.currentData()
        for i, button in enumerate(self.slot_buttons):
            button.setEnabled(bool(self.slots and frame.isValid()))
            button.setText(f"{SLOT_NAMES[i]} · {self.slots[i] + 1}" if self.slots else SLOT_NAMES[i])
        self.pose_preview.clear()
        self.atlas_preview.clear()
        if self.native_data:
            if frame.isValid() and 0 <= frame.row() < len(grid):
                self.pose_preview.setPixmap(pixel_preview(grid.tile(frame.row()), zoom))
            with Image.open(io.BytesIO(self.native_data)) as decoded:
                self.atlas_preview.setPixmap(pixel_preview(decoded, zoom))
        self.update_destination()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose output mod or staging folder", self.folder.text())
        if path:
            self.folder.setText(path)

    def update_destination(self):
        self.export.setEnabled(False)
        self.status.clear()
        if not self.digimon_id.value() or not self.folder.text().strip():
            return
        try:
            target = output_path(self.folder.text().strip(), self.digimon_id.value())
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.status.setText(str(target))
        self.export.setEnabled(self.native_data is not None)

    def export_sprite(self):
        if not self.native_data or not self.folder.text().strip():
            return
        try:
            path = output_path(self.folder.text().strip(), self.digimon_id.value())
            previous = path.read_bytes() if path.exists() else None
            if previous is not None:
                answer = QMessageBox.question(self, "Replace dot sprite?", f"Replace the existing texture?\n\n{path}",
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                              QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            save_texture(path, self.native_data, previous)
            self.status.setText(f"Saved {path}")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Could not export dot sprite", str(exc))
