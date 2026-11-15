"""Capture a model and export the character portrait used by the native UI."""
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile

from PIL import Image, ImageChops
from PyQt6.QtCore import Qt, QRect, QProcess, QSettings, QSaveFile, QIODevice, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QImage, QPixmap
from PyQt6.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton, QHBoxLayout,
                            QVBoxLayout, QFileDialog, QFormLayout, QSpinBox, QWidget, QMessageBox)


def portrait_name(icon_id):
    value = str(icon_id).strip('" ')
    if not value.isascii() or not value.isdecimal():
        raise ValueError("Choose a Digimon with a numeric character icon ID.")
    return f"ui_chara_icon_{value}.img"


PORTRAIT_FILL = (127, 173, 173)


def crop_artwork(image, crop, pixels):
    """Map the square preview to an arbitrary-size cutout without distorting it."""
    side = max(image.size)
    x = crop[0] * side - (side - image.width) / 2
    y = crop[1] * side - (side - image.height) / 2
    length = crop[2] * side
    box = (round(x), round(y), round(x + length), round(y + length))
    return image.convert("RGBA").crop(box).resize((pixels, pixels), Image.Resampling.LANCZOS)


def shifted(layer, x, y):
    result = Image.new(layer.mode, layer.size)
    result.paste(layer, (x, y))
    return result


def color_blend(image, color):
    """Photopea's nonseparable Color blend keeps the base layer's luminosity."""
    luminance = image.convert("L", (0.30, 0.59, 0.11, 0))
    center = sum(c * weight for c, weight in zip(color, (0.30, 0.59, 0.11)))
    offsets = [c - center for c in color]
    channels = []
    for offset in offsets:
        table = []
        for lum in range(256):
            scale = 1.0
            if lum + min(offsets) < 0:
                scale = lum / -min(offsets)
            elif lum + max(offsets) > 255:
                scale = (255 - lum) / max(offsets)
            table.append(round(lum + offset * scale))
        channels.append(luminance.point(table))
    return Image.merge("RGB", channels)


def tutorial_portrait(rgba):
    """Rebuild the tutorial layer stack in its 512px document coordinates."""
    rgba = rgba.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
    mask = rgba.getchannel("A")
    if mask.getbbox() is None:
        raise ValueError("The selected area is empty. Draw another crop around the face.")

    # Normal black drop shadow, distance 9 at 158 degrees, 100% spread, size 0.
    shadow = shifted(mask, 8, 3)
    rgb = Image.new("RGB", rgba.size, PORTRAIT_FILL)
    rgb.paste((0, 0, 0), mask=shadow)
    rgb.paste(rgba.convert("RGB"), mask=mask)

    # The moved duplicate has green unchecked in Blending Options.
    duplicate = shifted(rgba, 5, 5)
    overlay = Image.composite(duplicate.convert("RGB"), rgb, duplicate.getchannel("A"))
    rgb = Image.merge("RGB", (overlay.getchannel("R"), rgb.getchannel("G"), overlay.getchannel("B")))

    # Relative Selective Color, Blacks, K -8%, followed by the 45% Color fill.
    r, g, b = rgb.split()
    max_channel = ImageChops.lighter(ImageChops.lighter(r, g), b)
    lift = max_channel.point([round(0.08 * max(0, 255 - 2 * v)) for v in range(256)])
    rgb = Image.composite(Image.new("RGB", rgb.size, "white"), rgb, lift)
    rgb = Image.blend(rgb, color_blend(rgb, PORTRAIT_FILL), 0.45)

    # The author selects the pixels of the original + shadow smart object for Alpha 1.
    rgb.putalpha(ImageChops.screen(mask, shadow))
    return rgb


def style_portrait(source, output):
    with Image.open(source) as image:
        tutorial_portrait(image).save(output)


def verify_native_icon(path):
    data = Path(path).read_bytes()
    if (len(data) != 349700 or data[:4] != b'DDS ' or data[84:88] != b'DX10'
            or struct.unpack_from('<II', data, 12) != (512, 512)
            or struct.unpack_from('<I', data, 28)[0] != 10
            or struct.unpack_from('<III', data, 128) != (98, 3, 0)
            or struct.unpack_from('<I', data, 140)[0] != 1):
        raise ValueError("The encoder did not produce a 512 × 512 BC7 texture with ten mip levels.")
    return data


def tool_path(name, settings, program_folders):
    saved = settings.value(name, "")
    if saved and Path(saved).is_file():
        return saved
    found = shutil.which(name)
    if found:
        return found
    bases = [Path(p) for key in ('ProgramW6432', 'ProgramFiles', 'LOCALAPPDATA')
             if (p := os.environ.get(key))]
    # Respect custom install locations advertised in Windows' installed-app list.
    if os.name == 'nt':
        import ctypes
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\Uninstall') as root:
                    for idx in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            with winreg.OpenKey(root, winreg.EnumKey(root, idx)) as key:
                                location = winreg.QueryValueEx(key, 'InstallLocation')[0]
                                if isinstance(location, str) and location:
                                    candidate = Path(location) / name
                                    if candidate.is_file():
                                        return str(candidate)
                        except OSError:
                            continue
            except OSError:
                continue
        # Portable installs commonly live on a second drive. Only probe conventional
        # program folders on fixed disks; don't recurse through user files or network drives.
        volumes = ctypes.windll.kernel32.GetLogicalDrives()
        for index in range(26):
            root = f"{chr(65 + index)}:/"
            if volumes & (1 << index) and ctypes.windll.kernel32.GetDriveTypeW(root) == 3:
                bases.extend(Path(root) / folder for folder in ("Programs", "Program Files"))
    hits = [p for base in dict.fromkeys(bases) for p in base.glob(program_folders + '/' + name)
            if p.is_file()]
    version_key = lambda p: [int(n) for n in re.findall(r'\d+', p.parent.name)]
    return str(max(hits, key=version_key)) if hits else ""


class AngleBox(QSpinBox):
    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class PortraitCrop(QWidget):
    cropChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(400, 400)
        self.setAccessibleName("Model preview and square face crop")
        self.pixmap = QPixmap()
        self.selection = self.rect()
        self.start = None

    def set_preview(self, path):
        self.pixmap.load(str(path))
        self.selection = self.rect()
        self.update()

    def crop(self):
        return tuple(v/self.width() for v in (self.selection.x(), self.selection.y(), self.selection.width()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#465858"))
        if self.pixmap.isNull():
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Model preview")
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.setPen(QPen(QColor("#92f3e7"), 2))
        painter.drawRect(self.selection.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.pixmap.isNull():
            self.start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.start is None:
            return
        delta = event.position().toPoint() - self.start
        x, y = self.start.x(), self.start.y()
        side = min(max(abs(delta.x()), abs(delta.y())), self.width()-x if delta.x() >= 0 else x,
                   self.height()-y if delta.y() >= 0 else y)
        if side >= 8:
            self.selection = QRect(x if delta.x() >= 0 else x-side, y if delta.y() >= 0 else y-side, side, side)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start is None:
            return
        self.mouseMoveEvent(event)
        self.start = None
        self.cropChanged.emit()


class PortraitPanel(QWidget):
    """Stand-alone model portrait editor. Emit saved(path) after a verified export."""
    saved = pyqtSignal(str)

    def __init__(self, parent=None, destination=None, initial_model=None):
        super().__init__(parent)
        self.destination = Path(destination) if destination else None
        self.temp = tempfile.TemporaryDirectory(prefix="dsts-portrait-")
        self.work = Path(self.temp.name)
        self.settings = QSettings("Time Stranger Mod Studio", "Profile Portraits")
        self.blender = tool_path("blender.exe", self.settings, "Blender Foundation/Blender *")
        self.encoder = tool_path("nvcompress.exe", self.settings, "NVIDIA Corporation/NVIDIA Texture Tools")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.model = QLineEdit(str(initial_model or ""))
        self.model.setPlaceholderText("Select a model or a transparent PNG")
        pick = QPushButton("Browse…")
        pick.clicked.connect(self.pick_model)
        row = QHBoxLayout()
        row.addWidget(self.model)
        row.addWidget(pick)
        form.addRow("Model or artwork", row)
        self.yaw, self.pitch = AngleBox(), AngleBox()
        self.yaw.setRange(-180, 180)
        self.pitch.setRange(-85, 85)
        self.yaw.setValue(50)
        self.pitch.setValue(8)
        view = QHBoxLayout()
        view.setSpacing(6)
        for name, spin in (("Camera turn", self.yaw), ("Tilt", self.pitch)):
            label = QLabel(name)
            label.setBuddy(spin)
            spin.setAccessibleName(name)
            view.addWidget(label)
            spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            spin.setSuffix("°")
            view.addWidget(spin)
            view.addSpacing(10)
        view.addStretch(1)
        preview = QPushButton("Render preview")
        preview.clicked.connect(lambda: self.start_render(False))
        view.addWidget(preview)
        form.addRow(view)
        layout.addLayout(form)
        self.canvas = PortraitCrop()
        self.canvas.cropChanged.connect(self.update_styled_preview)
        previews = QHBoxLayout()
        previews.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        styled = QVBoxLayout()
        styled.setAlignment(Qt.AlignmentFlag.AlignCenter)
        styled.addWidget(QLabel("Game portrait"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.portrait_preview = QLabel()
        self.portrait_preview.setFixedSize(192, 192)
        self.portrait_preview.setAccessibleName("Styled portrait preview")
        styled.addWidget(self.portrait_preview)
        previews.addLayout(styled)
        layout.addLayout(previews)
        layout.addWidget(QLabel("Drag a square around the face to choose the portrait crop."))
        self.output_controls = []
        if not self.destination:
            output_form = QFormLayout()
            self.icon_id = QLineEdit()
            self.icon_id.setPlaceholderText("For example: 761")
            self.icon_id.setToolTip("Use the numeric icon ID in the Digimon's char_info entry.")
            output_form.addRow("Character icon ID", self.icon_id)
            self.folder = QLineEdit()
            self.folder.setPlaceholderText("Choose a mod or staging folder")
            browse_output = QPushButton("Browse…")
            browse_output.clicked.connect(self.pick_directory)
            out_row = QHBoxLayout()
            out_row.addWidget(self.folder)
            out_row.addWidget(browse_output)
            output_form.addRow("Export folder", out_row)
            layout.addLayout(output_form)
            self.output_controls = [self.icon_id, self.folder, browse_output]
        self.status = QLabel(str(self.destination or "Load a model and render a preview to begin."))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.save = QPushButton("Save profile picture")
        self.save.setEnabled(False)
        self.save.clicked.connect(lambda: self.start_render(True))
        self.png_save = QPushButton("Save styled PNG…")
        self.png_save.setEnabled(False)
        self.png_save.clicked.connect(self.save_png)
        save_row = QHBoxLayout()
        save_row.addWidget(self.png_save)
        save_row.addWidget(self.save)
        layout.addLayout(save_row)
        self.render_inputs = [self.model, pick, self.yaw, self.pitch, preview, self.canvas, *self.output_controls]
        self.rendered = None
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self.finished_process)
        self.process.errorOccurred.connect(self.process_error)
        self.stage = None
        for signal in (self.model.textChanged, self.yaw.valueChanged, self.pitch.valueChanged):
            signal.connect(self.changed)

    def changed(self):
        self.save.setEnabled(False)
        self.png_save.setEnabled(False)
        self.portrait_preview.clear()
        self.rendered = None
        self.status.setText("Render a new preview after changing the model or camera.")

    def pick_model(self):
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose model or transparent PNG", self.model.text(),
                                                "Models and artwork (*.glb *.gltf *.geom *.png)")
        if chosen:
            self.model.setText(chosen)

    def pick_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "Choose mod or staging folder", self.folder.text())
        if chosen:
            self.folder.setText(chosen)

    def target(self):
        if self.destination:
            return self.destination
        name = portrait_name(self.icon_id.text())
        folder = self.folder.text().strip('" ')
        if not folder or not Path(folder).is_absolute():
            raise ValueError("Choose an export folder first.")
        root = Path(folder)
        if root.name.lower() == "images":
            return root / name
        if root.name.lower() == "patch":
            return root / "images" / name
        if root.name.lower() != "dsts-loader":
            root = root / "dsts-loader"
        return root / "patch" / "images" / name

    def select_tool(self, name, current):
        if current and Path(current).is_file():
            return current
        path, _ = QFileDialog.getOpenFileName(self, f"Locate {name}", "", name)
        if path:
            self.settings.setValue(name, path)
        return path

    def busy(self, running):
        for control in self.render_inputs:
            control.setEnabled(not running)
        self.save.setEnabled(not running and self.rendered is not None)
        self.png_save.setEnabled(not running and self.rendered is not None)

    def save_png(self):
        filename = "portrait.png"
        try:
            filename = str(self.target().with_suffix(".png"))
        except ValueError:
            pass
        path, _ = QFileDialog.getSaveFileName(self, "Save styled portrait", filename, "PNG image (*.png)")
        if path:
            self.start_render(True, Path(path))

    def update_styled_preview(self):
        if self.rendered is None:
            return
        try:
            with Image.open(self.work / "preview.png") as image:
                preview = tutorial_portrait(crop_artwork(image, self.canvas.crop(), 512))
            preview.thumbnail((192, 192), Image.Resampling.LANCZOS)
            pixels = preview.tobytes()
            picture = QImage(pixels, preview.width, preview.height, preview.width * 4, QImage.Format.Format_RGBA8888)
            self.portrait_preview.setPixmap(QPixmap.fromImage(picture))
        except (OSError, ValueError) as exc:
            self.portrait_preview.clear()
            self.status.setText(str(exc))

    def show_preview(self):
        self.canvas.set_preview(self.work / "preview.png")
        self.rendered = self.model.text()
        self.status.setText("Drag a square around the face to preview the finished portrait.")
        self.update_styled_preview()

    def write_output(self, data):
        self.export_path.parent.mkdir(parents=True, exist_ok=True)
        output = QSaveFile(str(self.export_path))
        if (not output.open(QIODevice.OpenModeFlag.WriteOnly) or output.write(data) != len(data)
                or not output.commit()):
            raise OSError(output.errorString())
        self.status.setText(f"Saved {self.export_path}")
        if not self.saving_png:
            self.saved.emit(str(self.export_path))

    def finish_capture(self):
        style_portrait(self.work / "render.png", self.work / "styled.png")
        if self.saving_png:
            self.write_output((self.work / "styled.png").read_bytes())
        else:
            self.stage = "encode"
            self.status.setText("Encoding the portrait and its mipmaps…")
            self.process.start(self.encoder, ["-silent", "-nocuda", "-bc7", "-alpha", "-dds10",
                str(self.work / "styled.png"), str(self.work / "portrait.dds")])

    def start_render(self, saving, png_path=None):
        path = Path(self.model.text().strip('" '))
        artwork = path.suffix.lower() == ".png"
        if not path.is_file() or path.suffix.lower() not in {'.geom', '.glb', '.gltf', '.png'}:
            self.status.setText("Choose a GLB, glTF, GEOM or PNG first.")
            return
        if not artwork:
            self.blender = self.select_tool("blender.exe", self.blender)
            if not self.blender:
                return
        self.saving_png = png_path is not None
        if saving:
            try:
                self.export_path = png_path or self.target()
            except ValueError as exc:
                self.status.setText(str(exc))
                return
            # The PNG save dialog has already confirmed a replacement.
            if not self.saving_png and self.export_path.exists() and QMessageBox.question(
                self, "Replace profile picture?", f"Replace the existing portrait at\n{self.export_path}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return
            if not self.saving_png:
                self.encoder = self.select_tool("nvcompress.exe", self.encoder)
                if not self.encoder:
                    return
        self.stage = "capture" if saving else "preview"
        crop = self.canvas.crop() if saving else (0, 0, 1)
        self.busy(True)
        output = self.work / ("render.png" if saving else "preview.png")
        if artwork:
            try:
                with Image.open(path) as image:
                    crop_artwork(image, crop, 512 if saving else 640).save(output)
                if saving:
                    self.finish_capture()
                else:
                    self.show_preview()
            except (ValueError, OSError) as exc:
                self.status.setText(str(exc))
            if self.stage != "encode":
                self.stage = None
                self.busy(False)
            return
        self.status.setText("Rendering the face…" if saving else "Loading the model in Blender…")
        script = Path(__file__).resolve().parent / "assets/render_portrait.py"
        self.process.start(self.blender, ["--background", "--factory-startup", "--disable-autoexec", "-t", "6",
            "--python-exit-code", "1", "--python", str(script), "--", str(path), str(output),
            "--yaw", str(self.yaw.value()), "--pitch", str(self.pitch.value()),
            "--pixels", "1024" if saving else "640", "--crop", *map(str, crop)])

    def finished_process(self, code, status):
        if self.stage is None:
            return
        log = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        try:
            if code or status != QProcess.ExitStatus.NormalExit:
                raise ValueError(log.strip()[-1800:] or f"Capture tool exited with code {code}.")
            if self.stage == 'preview':
                self.show_preview()
            elif self.stage == 'capture':
                self.finish_capture()
                if self.stage == "encode":
                    return
            else:
                self.write_output(verify_native_icon(self.work/'portrait.dds'))
        except (ValueError, OSError, ImportError) as exc:
            self.status.setText(str(exc))
        self.stage = None
        self.busy(False)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.stage = None
            self.status.setText(self.process.errorString())
            self.busy(False)

    def shutdown(self):
        self.stage = None
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(3000)
        self.temp.cleanup()


class PortraitDialog(QDialog):
    def __init__(self, parent=None, destination=None, initial_model=None):
        super().__init__(parent)
        self.setWindowTitle("Capture profile picture")
        self.panel = PortraitPanel(self, destination, initial_model)
        QVBoxLayout(self).addWidget(self.panel)
        self.panel.saved.connect(self.accept)

    def done(self, result):
        self.panel.shutdown()
        super().done(result)
