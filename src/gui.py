import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QItemSelectionModel, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from . import config, importer, storage
from .errors import ManagerError, VaultError, WrongPassword
from .fsutil import ensure_private_dir, write_private
from .idiomas import LANG_NAMES, resolve_language, set_language, tr
from .launcher import Launcher, client_missing, game_uri
from .logger import log
from .settings import CLIENT_CUSTOM, CLIENTS, DEFAULT_CLIENT, FONT_SCALES, THEMES
from .theme import SYSTEM_ACCENT, THEME_COLORS
from .validation import (
    MAX_PASSWORD_LENGTH, command_problem, validate_game, validate_master,
    validate_password, validate_username,
)
from .vault import Vault

MASK = "••••••••"
EMPTY = "—"
STAMP_FORMAT = "%d/%m %H:%M"
CLIENT_CHECK_MS = 2500
MAX_LISTED_LINES = 30


def button_box(dialog):
    box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


def secret_field(accessible_name="", limit=MAX_PASSWORD_LENGTH):
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    field.setMaxLength(limit)
    if accessible_name:
        field.setAccessibleName(accessible_name)
    return field


def ask_master(parent, vault, settings, prompt_key="pw_confirm"):
    wait = settings.wait_seconds()
    if wait:
        QMessageBox.warning(parent, tr("pw_title"), tr("lock_wait", n=wait))
        return False
    password, accepted = QInputDialog.getText(
        parent, tr("pw_title"), tr(prompt_key), QLineEdit.Password
    )
    if not accepted:
        return False
    if vault.verify(password):
        settings.register_success()
        return True
    wait = settings.register_failure()
    log.error(tr("log_unlock_fail", n=settings["fails"]))
    QMessageBox.warning(
        parent, tr("pw_title"), tr("lock_wait", n=wait) if wait else tr("lock_wrong")
    )
    return False


class Appearance:
    def __init__(self, app):
        self.app = app
        self.base_font = QFont(app.font())
        self.base_palette = QPalette(app.palette())

    def apply(self, theme, font_key):
        size = self.base_font.pointSizeF()
        font = QFont(self.base_font)
        font.setPointSizeF((size if size > 0 else 10.0) * FONT_SCALES[font_key])
        self.app.setFont(font)
        if theme == "system":
            self.app.setPalette(self.base_palette)
            accent, accent_text = SYSTEM_ACCENT
        else:
            colors = THEME_COLORS[theme]
            palette = QPalette()
            roles = (
                (QPalette.Window, "window"), (QPalette.Base, "base"),
                (QPalette.AlternateBase, "window"), (QPalette.Text, "text"),
                (QPalette.WindowText, "text"), (QPalette.ButtonText, "text"),
                (QPalette.Button, "button"), (QPalette.Highlight, "highlight"),
                (QPalette.HighlightedText, "hltext"), (QPalette.ToolTipBase, "base"),
                (QPalette.ToolTipText, "text"), (QPalette.PlaceholderText, "text"),
            )
            for role, key in roles:
                palette.setColor(role, QColor(colors[key]))
            self.app.setPalette(palette)
            accent, accent_text = colors["accent"], colors["accent_text"]
        self.app.setStyleSheet(f"""
            QPushButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus,
            QCheckBox:focus, QTableWidget:focus {{ border: 3px solid palette(highlight); }}
            QPushButton#entrar {{ background:{accent}; color:{accent_text}; padding:8px 18px;
                                 border-radius:5px; font-weight:600; }}
            QPushButton#entrar:disabled {{ background:palette(mid); color:palette(window-text); }}
            QPlainTextEdit {{ font-family:monospace; }}
        """)


class AccountDialog(QDialog):
    def __init__(self, parent=None, account=None):
        super().__init__(parent)
        self.editing = account is not None
        self.setWindowTitle(tr("dlg_edit") if self.editing else tr("dlg_add"))
        self.setMinimumWidth(480)
        self.user = QLineEdit()
        self.user.setMaxLength(60)
        self.user.setText(account["username"] if account else "")
        self.password = secret_field(tr("col_password"))
        if self.editing:
            self.password.setPlaceholderText(tr("ph_keep_pw"))
        self.group = QLineEdit()
        self.group.setMaxLength(60)
        self.group.setText(account["group"] if account else "")
        self.notes = QLineEdit()
        self.notes.setMaxLength(120)
        self.notes.setText(account["notes"] if account else "")
        self.show_pw = QCheckBox(tr("chk_show_pw"))
        self.show_pw.toggled.connect(self._toggle_echo)
        self.clear_pw = QCheckBox(tr("chk_clear_pw")) if self.editing else None
        for widget, key in ((self.user, "col_user"), (self.group, "col_group"), (self.notes, "col_notes")):
            widget.setAccessibleName(tr(key))
        form = QFormLayout()
        form.addRow(tr("col_user"), self.user)
        form.addRow(tr("col_password"), self.password)
        form.addRow("", self.show_pw)
        if self.clear_pw is not None:
            form.addRow("", self.clear_pw)
        form.addRow(tr("col_group"), self.group)
        form.addRow(tr("col_notes"), self.notes)
        hint = QLabel(tr("hint_add"))
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(button_box(self))

    def _toggle_echo(self, visible):
        self.password.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    def values(self):
        text = self.password.text()
        if self.clear_pw is not None and self.clear_pw.isChecked():
            password = ""
        elif self.editing and not text:
            password = None
        else:
            password = text
        return {
            "username": self.user.text().strip(),
            "password": password,
            "group": self.group.text(),
            "notes": self.notes.text(),
        }

    def accept(self):
        try:
            validate_username(self.user.text())
            validate_password(self.password.text())
        except ManagerError as exc:
            QMessageBox.warning(self, tr("warn_user_title"), str(exc))
            return
        super().accept()

    def clear(self):
        self.password.clear()


class RemoveDialog(QDialog):
    def __init__(self, parent, count):
        super().__init__(parent)
        self.setWindowTitle(tr("ask_remove_title"))
        self.delete_profile = QCheckBox(tr("chk_delete_profile"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("ask_remove", n=count)))
        layout.addWidget(self.delete_profile)
        layout.addWidget(button_box(self))


class CreateVaultDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self.setWindowTitle(tr("dlg_create_title"))
        self.setMinimumWidth(460)
        self.first = secret_field(tr("lbl_master"), 1000)
        self.second = secret_field(tr("lbl_master_repeat"), 1000)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        prompt = QLabel(tr("create_prompt"))
        prompt.setWordWrap(True)
        form = QFormLayout()
        form.addRow(tr("lbl_master"), self.first)
        form.addRow(tr("lbl_master_repeat"), self.second)
        layout = QVBoxLayout(self)
        layout.addWidget(prompt)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(button_box(self))

    def password(self):
        return self.first.text()

    def accept(self):
        try:
            validate_master(self.first.text())
        except ManagerError as exc:
            self.message.setText(str(exc))
            return
        if self.first.text() != self.second.text():
            self.message.setText(tr("pw_mismatch"))
            return
        super().accept()

    def clear(self):
        self.first.clear()
        self.second.clear()


class UnlockDialog(QDialog):
    def __init__(self, settings, check):
        super().__init__(None)
        self.settings = settings
        self.check = check
        self._waiting = False
        self.setWindowTitle(tr("lock_title"))
        self.setModal(True)
        self.setMinimumWidth(380)
        self.pw = secret_field(tr("lock_prompt"), 1000)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.msg.setAccessibleName(tr("lock_title"))
        self.ok = QPushButton(tr("btn_unlock"))
        self.ok.setDefault(True)
        quit_button = QPushButton(tr("btn_quit"))
        self.ok.clicked.connect(self.attempt)
        self.pw.returnPressed.connect(self.attempt)
        quit_button.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(quit_button)
        row.addWidget(self.ok)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("lock_prompt")))
        layout.addWidget(self.pw)
        layout.addWidget(self.msg)
        layout.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tick()

    def tick(self):
        wait = self.settings.wait_seconds()
        self.ok.setEnabled(wait == 0)
        if wait:
            self.msg.setText(tr("lock_wait", n=wait))
            self._waiting = True
        elif self._waiting:
            self.msg.setText("")
            self._waiting = False

    def attempt(self):
        password = self.pw.text()
        self.pw.clear()
        wait = self.settings.wait_seconds()
        if wait:
            self.msg.setText(tr("lock_wait", n=wait))
            return
        try:
            granted = self.check(password)
        except ManagerError as exc:
            self.msg.setText(str(exc))
            return
        if granted:
            self.settings.register_success()
            self.accept()
            return
        wait = self.settings.register_failure()
        log.error(tr("log_unlock_fail", n=self.settings["fails"]))
        self.msg.setText(tr("lock_wait", n=wait) if wait else tr("lock_wrong"))
        self.ok.setEnabled(wait == 0)
        self.pw.setFocus()


class SecretDialog(QDialog):
    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.field = QLineEdit(text)
        self.field.setReadOnly(True)
        self.field.setAccessibleName(title)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.field)
        layout.addWidget(box)
        self.field.selectAll()

    def done(self, result):
        self.field.clear()
        super().done(result)


class PasteDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("import_title"))
        self.setMinimumSize(520, 380)
        hint = QLabel(tr("import_text_hint"))
        hint.setWordWrap(True)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName(tr("import_title"))
        self.editor.setPlaceholderText("usuario1:senha1\nusuario2:senha2")
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.editor, 1)
        layout.addWidget(button_box(self))

    def text(self):
        return self.editor.toPlainText()

    def clear(self):
        self.editor.clear()


class TextDialog(QDialog):
    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 400)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setAccessibleName(title)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(box)


class SettingsDialog(QDialog):
    def __init__(self, parent, settings, vault):
        super().__init__(parent)
        self.settings = settings
        self.vault = vault
        self.wiped = False
        self.setWindowTitle(tr("settings_title"))
        self.setMinimumWidth(620)
        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), tr("tab_general"))
        tabs.addTab(self._security_tab(), tr("tab_security"))
        tabs.addTab(self._access_tab(), tr("tab_access"))
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(button_box(self))

    def _general_tab(self):
        widget = QWidget()
        self.client = QComboBox()
        self.client.addItems(CLIENTS.keys())
        self.client.setCurrentText(self.settings["client"])
        self.command = QLineEdit(self.settings["launch_command"])
        self.client.currentTextChanged.connect(self._preset)
        self.isolate = QCheckBox(tr("chk_isolate"))
        self.isolate.setChecked(self.settings["isolate_profiles"])
        hint = QLabel(tr("hint_command"))
        hint.setWordWrap(True)
        form = QFormLayout()
        form.addRow(tr("lbl_client"), self.client)
        form.addRow(tr("lbl_command"), self.command)
        layout = QVBoxLayout(widget)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.isolate)
        layout.addStretch()
        self.client.setAccessibleName(tr("lbl_client"))
        self.command.setAccessibleName(tr("lbl_command"))
        return widget

    def _security_tab(self):
        widget = QWidget()
        self.allow_custom = QCheckBox(tr("chk_custom"))
        self.allow_custom.setChecked(self.settings["allow_custom"])
        self.allow_custom.toggled.connect(lambda _: self._preset(self.client.currentText()))
        hint_custom = QLabel(tr("hint_custom"))
        hint_custom.setWordWrap(True)
        self.maxbatch = QSpinBox()
        self.maxbatch.setRange(1, 20)
        self.maxbatch.setValue(self.settings["max_batch"])
        self.maxbatch.setAccessibleName(tr("lbl_maxbatch"))
        self.idle = QSpinBox()
        self.idle.setRange(0, 120)
        self.idle.setValue(self.settings["idle_lock_minutes"])
        self.idle.setSuffix(tr("idle_suffix"))
        self.idle.setSpecialValueText(tr("idle_off"))
        self.idle.setAccessibleName(tr("lbl_idle"))
        change = QPushButton(tr("btn_changemaster"))
        change.clicked.connect(self.change_master)
        hint_lock = QLabel(tr("hint_lock"))
        hint_lock.setWordWrap(True)
        wipe = QPushButton(tr("btn_wipe"))
        wipe.clicked.connect(self.wipe)
        privacy = QLabel(tr("sec_privacy"))
        privacy.setWordWrap(True)
        form = QFormLayout()
        form.addRow(tr("lbl_maxbatch"), self.maxbatch)
        form.addRow(tr("lbl_idle"), self.idle)
        layout = QVBoxLayout(widget)
        layout.addWidget(privacy)
        layout.addWidget(self.allow_custom)
        layout.addWidget(hint_custom)
        layout.addLayout(form)
        layout.addWidget(change)
        layout.addWidget(hint_lock)
        layout.addStretch()
        layout.addWidget(wipe)
        self._preset(self.client.currentText())
        return widget

    def _access_tab(self):
        widget = QWidget()
        self.language = QComboBox()
        self.language.addItem(tr("lang_auto"), "auto")
        for code, name in LANG_NAMES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(self.settings["language"])))
        self.font = QComboBox()
        for key in FONT_SCALES:
            self.font.addItem(tr("font_" + key), key)
        self.font.setCurrentIndex(self.font.findData(self.settings["font"]))
        self.theme = QComboBox()
        for key in THEMES:
            self.theme.addItem(tr("theme_" + key), key)
        self.theme.setCurrentIndex(self.theme.findData(self.settings["theme"]))
        for control, key in ((self.language, "lbl_language"), (self.font, "lbl_font"), (self.theme, "lbl_theme")):
            control.setAccessibleName(tr(key))
        form = QFormLayout(widget)
        form.addRow(tr("lbl_language"), self.language)
        form.addRow(tr("lbl_font"), self.font)
        form.addRow(tr("lbl_theme"), self.theme)
        return widget

    def _preset(self, name):
        if CLIENTS.get(name):
            self.command.setText(CLIENTS[name])
        self.command.setEnabled(name == CLIENT_CUSTOM and self.allow_custom.isChecked())

    def change_master(self):
        if not ask_master(self, self.vault, self.settings, "pw_current"):
            return
        new, accepted = QInputDialog.getText(self, tr("pw_title"), tr("pw_new"), QLineEdit.Password)
        if not accepted:
            return
        try:
            validate_master(new)
        except ManagerError as exc:
            QMessageBox.warning(self, tr("pw_title"), str(exc))
            return
        again, accepted = QInputDialog.getText(self, tr("pw_title"), tr("pw_repeat"), QLineEdit.Password)
        if not accepted:
            return
        if again != new:
            QMessageBox.warning(self, tr("pw_title"), tr("pw_mismatch"))
            return
        self.vault.change_password(new)
        self.vault.save()
        log.success(tr("log_master_changed"))
        QMessageBox.information(self, tr("pw_title"), tr("log_master_changed"))

    def wipe(self):
        if not ask_master(self, self.vault, self.settings):
            return
        answer = QMessageBox.warning(
            self, tr("ask_wipe_title"), tr("ask_wipe"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        storage.wipe_all(config.CONFIG_DIR)
        self.wiped = True
        log.warn(tr("info_wipe_done"))
        QMessageBox.information(self, tr("ask_wipe_title"), tr("info_wipe_done"))
        self.reject()

    def accept(self):
        client = self.client.currentText()
        command = self.command.text().strip()
        if client == CLIENT_CUSTOM:
            if not self.allow_custom.isChecked():
                client, command = DEFAULT_CLIENT, CLIENTS[DEFAULT_CLIENT]
            else:
                problem = command_problem(command)
                if problem:
                    QMessageBox.warning(
                        self, tr("settings_title"),
                        tr("custom_blocked", why=tr("why_" + problem)),
                    )
                    return
        else:
            command = CLIENTS[client]
        self.settings.update(
            client=client,
            launch_command=command,
            allow_custom=self.allow_custom.isChecked(),
            isolate_profiles=self.isolate.isChecked(),
            language=self.language.currentData(),
            font=self.font.currentData(),
            theme=self.theme.currentData(),
            max_batch=self.maxbatch.value(),
            idle_lock_minutes=self.idle.value(),
        )
        self.settings.save()
        super().accept()


class ActivityFilter(QObject):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel):
            self.callback()
        return False


class MainWindow(QMainWindow):
    def __init__(self, settings, vault, appearance):
        super().__init__()
        self.settings = settings
        self.vault = vault
        self.appearance = appearance
        self.launcher = Launcher(
            vault, config.PROFILES_DIR, config.SESSIONS_DIR, config.STATE_FILE
        )
        self.queue = []
        self.batch_size = 0
        self.locked = False
        self.clip_value = ""
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(lambda: self.lock_now("log_idle_lock"))
        self.clip_timer = QTimer(self)
        self.clip_timer.setSingleShot(True)
        self.clip_timer.timeout.connect(self.clear_clipboard)
        self._build_ui()
        self.apply_settings()
        log.add_listener(self._on_log)
        log.info(tr("log_ready"))
        self.activity = ActivityFilter(self.reset_idle)
        QApplication.instance().installEventFilter(self.activity)

    def _guard(self, action):
        def run(*_):
            try:
                action()
            except ManagerError as exc:
                log.error(str(exc))
                QMessageBox.warning(self, tr("warn_title"), str(exc))

        return run

    def _build_ui(self):
        self.resize(980, 660)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)

        self.table = QTableWidget(0, 5)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._guard(self.edit_account))

        self.buttons = {}
        toolbar = QHBoxLayout()
        for key, slot in (
            ("btn_add", self.add_account), ("btn_edit", self.edit_account),
            ("btn_remove", self.remove_accounts), ("btn_login", self.open_for_login),
            ("btn_copy", self.copy_password),
        ):
            button = QPushButton()
            button.clicked.connect(self._guard(slot))
            self.buttons[key] = button
            toolbar.addWidget(button)
        toolbar.addStretch()
        for key, slot in (("btn_lock", self.lock_now), ("btn_settings", self.open_settings)):
            button = QPushButton()
            button.clicked.connect(self._guard(slot))
            self.buttons[key] = button
            toolbar.addWidget(button)

        self.place = QLineEdit()
        self.place.setMaxLength(19)
        self.place.setText(self.settings["last_place"])
        self.job = QLineEdit()
        self.job.setMaxLength(36)
        self.delay = QSpinBox()
        self.delay.setRange(0, 120)
        self.delay.setValue(10)
        self.launch_btn = QPushButton()
        self.launch_btn.setObjectName("entrar")
        self.launch_btn.clicked.connect(self._guard(self.launch_selected))
        launch = QHBoxLayout()
        launch.addWidget(self.place, 2)
        launch.addWidget(self.job, 2)
        launch.addWidget(self.delay)
        launch.addWidget(self.launch_btn)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(140)
        self.console.setMaximumBlockCount(500)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(toolbar)
        layout.addWidget(self.search)
        layout.addWidget(self.table, 1)
        layout.addLayout(launch)
        layout.addWidget(self.console)
        self.setCentralWidget(central)

        order = [
            self.search, self.table,
            *[self.buttons[key] for key in ("btn_add", "btn_edit", "btn_remove", "btn_login", "btn_copy", "btn_lock", "btn_settings")],
            self.place, self.job, self.delay, self.launch_btn, self.console,
        ]
        for first, second in zip(order, order[1:]):
            QWidget.setTabOrder(first, second)

        self.menu_file = self.menuBar().addMenu("")
        self.menu_help = self.menuBar().addMenu("")
        self.actions = {}

        def act(key, slot, shortcut, menu):
            action = QAction(self)
            action.triggered.connect(self._guard(slot))
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            menu.addAction(action)
            self.actions[key] = action

        act("act_add", self.add_account, "Ctrl+N", self.menu_file)
        act("act_edit", self.edit_account, "Ctrl+E", self.menu_file)
        act("act_remove", self.remove_accounts, QKeySequence.Delete, self.menu_file)
        act("act_login", self.open_for_login, "Ctrl+O", self.menu_file)
        act("act_launch", self.launch_selected, "Ctrl+Return", self.menu_file)
        self.menu_file.addSeparator()
        act("act_copy", self.copy_password, "Ctrl+Shift+C", self.menu_file)
        act("act_show", self.show_password, "Ctrl+Shift+P", self.menu_file)
        self.menu_file.addSeparator()
        act("act_import", self.import_file, "Ctrl+I", self.menu_file)
        act("act_import_text", self.import_text, "Ctrl+Shift+I", self.menu_file)
        act("act_export", self.export_file, "Ctrl+Shift+E", self.menu_file)
        self.menu_file.addSeparator()
        act("act_save_session", self.save_session, None, self.menu_file)
        self.menu_file.addSeparator()
        act("act_lock", self.lock_now, "Ctrl+L", self.menu_file)
        act("act_settings", self.open_settings, "Ctrl+,", self.menu_file)
        self.menu_file.addSeparator()
        act("act_quit", self.close, "Ctrl+Q", self.menu_file)
        act("act_guide", self.show_guide, "F1", self.menu_help)
        act("act_about", self.show_about, None, self.menu_help)

    def retranslate(self):
        self.setWindowTitle(tr("app_title"))
        self.menu_file.setTitle(tr("menu_file"))
        self.menu_help.setTitle(tr("menu_help"))
        for key, action in self.actions.items():
            action.setText(tr(key))
        self.table.setHorizontalHeaderLabels(
            [tr(key) for key in ("col_user", "col_password", "col_group", "col_last", "col_notes")]
        )
        self.table.setAccessibleName(tr("accounts_list"))
        shortcuts = {
            "btn_add": "Ctrl+N", "btn_edit": "Ctrl+E", "btn_remove": "Del",
            "btn_login": "Ctrl+O", "btn_copy": "Ctrl+Shift+C", "btn_lock": "Ctrl+L",
            "btn_settings": "Ctrl+,",
        }
        for key, button in self.buttons.items():
            button.setText(tr(key))
            button.setAccessibleName(tr(key))
            button.setToolTip(f"{tr(key)} ({shortcuts[key]})")
        self.search.setPlaceholderText(tr("ph_search"))
        self.search.setAccessibleName(tr("ph_search"))
        self.place.setPlaceholderText(tr("ph_place"))
        self.place.setAccessibleName(tr("ph_place"))
        self.job.setPlaceholderText(tr("ph_job"))
        self.job.setAccessibleName(tr("ph_job"))
        self.delay.setSuffix(tr("delay_suffix"))
        self.delay.setAccessibleName(tr("delay_suffix").strip())
        self.launch_btn.setText(tr("btn_launch"))
        self.launch_btn.setAccessibleName(tr("btn_launch"))
        self.launch_btn.setToolTip(f"{tr('btn_launch')} (Ctrl+Enter)")
        self.console.setAccessibleName(tr("log_panel"))

    def apply_settings(self):
        set_language(resolve_language(self.settings["language"]))
        self.appearance.apply(self.settings["theme"], self.settings["font"])
        self.retranslate()
        self.refresh()
        self.reset_idle()

    def _on_log(self, level, text):
        prefix = "" if level in ("INFO", "SUCCESS") else f"{level}: "
        self.console.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {prefix}{text}")

    def selected_ids(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        return [self.table.item(row, 0).data(Qt.UserRole) for row in rows]

    def selected_account(self):
        ids = self.selected_ids()
        account = self.vault.get(ids[0]) if ids else None
        if account is None:
            QMessageBox.warning(self, tr("warn_noacc_title"), tr("warn_noacc"))
        return account

    def refresh(self, *_):
        needle = self.search.text().strip().lower()
        keep = set(self.selected_ids())
        shown = [
            item for item in self.vault.all()
            if not needle or needle in " ".join((item["username"], item["group"], item["notes"])).lower()
        ]
        self.table.setRowCount(len(shown))
        selection = self.table.selectionModel()
        for row, item in enumerate(shown):
            values = [
                item["username"],
                MASK if item["password"] else EMPTY,
                item["group"],
                item["last_launch"] or tr("never"),
                item["notes"],
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.UserRole, item["id"])
                self.table.setItem(row, column, cell)
            if item["id"] in keep:
                selection.select(
                    self.table.model().index(row, 0),
                    QItemSelectionModel.Select | QItemSelectionModel.Rows,
                )

    def warn(self, title_key, text_key, **params):
        QMessageBox.warning(self, tr(title_key), tr(text_key, **params))

    def _context_menu(self, position):
        if not self.table.indexAt(position).isValid():
            return
        menu = QMenu(self)
        for key in ("act_edit", "act_login", "act_copy", "act_show", "act_remove"):
            menu.addAction(self.actions[key])
        menu.exec(self.table.viewport().mapToGlobal(position))

    def reset_idle(self):
        minutes = self.settings["idle_lock_minutes"]
        if minutes and not self.locked:
            self.idle_timer.start(minutes * 60_000)
        else:
            self.idle_timer.stop()

    def lock_now(self, reason="log_locked"):
        if self.locked:
            return
        if reason == "log_idle_lock" and QApplication.activeModalWidget() is not None:
            self.reset_idle()
            return
        self.locked = True
        self.idle_timer.stop()
        self.clear_clipboard()
        log.info(tr(reason))
        self.hide()
        granted = UnlockDialog(self.settings, self.vault.verify).exec() == QDialog.Accepted
        self.locked = False
        if granted:
            log.info(tr("log_unlocked"))
            self.show()
            self.reset_idle()
        else:
            QApplication.instance().quit()

    def add_account(self):
        dialog = AccountDialog(self)
        if dialog.exec() != QDialog.Accepted:
            dialog.clear()
            return
        values = dialog.values()
        dialog.clear()
        outcome, item = self.vault.add(
            values["username"], values["password"] or "", values["group"], values["notes"]
        )
        if outcome == "exists":
            raise VaultError("err_exists", name=item["username"])
        self.vault.save()
        self.refresh()
        log.success(tr("log_added", name=item["username"]))

    def edit_account(self):
        ids = self.selected_ids()
        account = self.vault.get(ids[0]) if ids else None
        if account is None:
            return
        dialog = AccountDialog(self, account)
        if dialog.exec() != QDialog.Accepted:
            dialog.clear()
            return
        values = dialog.values()
        dialog.clear()
        updated = self.vault.update(account["id"], **values)
        self.vault.save()
        self.refresh()
        log.success(tr("log_updated", name=updated["username"]))

    def remove_accounts(self):
        ids = self.selected_ids()
        if not ids:
            return
        dialog = RemoveDialog(self, len(ids))
        if dialog.exec() != QDialog.Accepted:
            return
        for ident in ids:
            account = self.vault.get(ident)
            if account is None:
                continue
            if dialog.delete_profile.isChecked() and self.launcher.delete_profile(ident):
                log.info(tr("log_profile_deleted", name=account["username"]))
            self.vault.remove(ident)
            log.success(tr("log_removed", name=account["username"]))
        self.vault.save()
        self.refresh()

    def copy_password(self):
        account = self.selected_account()
        if account is None:
            return
        if not account["password"]:
            self.warn("warn_nopw_title", "warn_nopw")
            return
        QApplication.clipboard().setText(account["password"])
        self.clip_value = account["password"]
        self.clip_timer.start(config.CLIPBOARD_SECONDS * 1000)
        log.success(
            tr("log_pw_copied", name=account["username"], n=config.CLIPBOARD_SECONDS)
        )

    def clear_clipboard(self):
        self.clip_timer.stop()
        if not self.clip_value:
            return
        clipboard = QApplication.clipboard()
        if clipboard.text() == self.clip_value:
            clipboard.clear()
        self.clip_value = ""
        log.info(tr("log_clip_cleared"))

    def show_password(self):
        account = self.selected_account()
        if account is None:
            return
        if not ask_master(self, self.vault, self.settings):
            return
        account = self.vault.get(account["id"])
        log.info(tr("log_pw_shown", name=account["username"]))
        SecretDialog(
            self, tr("dlg_secret_title", name=account["username"]),
            account["password"] or tr("pw_none"),
        ).exec()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("import_title"), str(Path.home()), tr("import_filter")
        )
        if not path:
            return
        log.info(tr("log_import_read", path=path))
        self._import(importer.load_file(Path(path)))

    def import_text(self):
        dialog = PasteDialog(self)
        if dialog.exec() != QDialog.Accepted:
            dialog.clear()
            return
        text = dialog.text()
        dialog.clear()
        log.info(tr("log_import_text"))
        self._import(importer.parse_text(text))

    def _import(self, parsed):
        for number, key in parsed.invalid[:MAX_LISTED_LINES]:
            log.warn(tr("log_import_line", n=number, why=tr(key)))
        hidden = len(parsed.invalid) - MAX_LISTED_LINES
        if hidden > 0:
            log.warn(tr("log_import_more", n=hidden))
        if not parsed.entries:
            log.warn(tr("log_import_none"))
            QMessageBox.information(self, tr("import_title"), tr("log_import_none"))
            return
        overwrite = False
        clashes = importer.conflicts(self.vault, parsed.entries)
        if clashes:
            answer = QMessageBox.question(
                self, tr("ask_overwrite_title"), tr("ask_overwrite", n=clashes),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No,
            )
            if answer == QMessageBox.Cancel:
                return
            overwrite = answer == QMessageBox.Yes
        report = importer.apply(self.vault, parsed.entries, overwrite)
        self.vault.save()
        self.refresh()
        summary = tr(
            "log_import_done",
            added=report.added,
            updated=report.updated,
            skipped=report.skipped,
            duplicated=report.duplicated,
            invalid=len(parsed.invalid),
        )
        log.success(summary)
        QMessageBox.information(self, tr("import_title"), summary)

    def export_file(self):
        if not len(self.vault):
            raise VaultError("err_no_accounts")
        answer = QMessageBox.question(self, tr("export_title"), tr("ask_export"))
        if answer != QMessageBox.Yes:
            return
        if not ask_master(self, self.vault, self.settings):
            return
        ensure_private_dir(config.EXPORTS_DIR)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default = config.EXPORTS_DIR / f"contas-{stamp}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("export_title"), str(default), tr("import_filter")
        )
        if not path:
            return
        target = Path(path)
        try:
            write_private(target, importer.export_text(self.vault).encode("utf-8"))
        except OSError as exc:
            raise VaultError("err_write", why=exc.strerror or str(exc)) from exc
        message = tr("log_export_done", n=len(self.vault), path=target)
        log.success(message)
        log.warn(tr("log_export_warn"))
        QMessageBox.information(
            self, tr("export_title"), message + "\n\n" + tr("log_export_warn")
        )

    def save_session(self):
        if self.settings["isolate_profiles"]:
            log.warn(tr("log_session_isolated"))
            return
        active = self.launcher.active()
        account = self.vault.get(active) if active else None
        if account is None:
            account = self.selected_account()
        if account is not None:
            self.launcher.save_session(account["id"])

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings, self.vault)
        result = dialog.exec()
        if dialog.wiped:
            QTimer.singleShot(0, QApplication.instance().quit)
        elif result == QDialog.Accepted:
            self.apply_settings()
            log.success(tr("log_settings_saved"))

    def show_guide(self):
        TextDialog(self, tr("guide_title"), tr("guide_text", n=config.CLIPBOARD_SECONDS)).exec()

    def show_about(self):
        QMessageBox.information(
            self, tr("about_title"), tr("about_text", version=config.read_version())
        )

    def client_ok(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            missing = client_missing(self.settings["launch_command"])
        finally:
            QApplication.restoreOverrideCursor()
        if missing:
            self.warn("client_missing_title", "client_missing", name=missing)
            return False
        return True

    def _start(self, account, uri, notify):
        log.info(tr("log_launch", name=account["username"]))
        try:
            result = self.launcher.start(account["id"], self.settings, uri)
        except ManagerError as exc:
            log.error(f"{account['username']}: {exc}")
            if notify:
                QMessageBox.warning(self, tr("warn_title"), str(exc))
            return False
        except Exception:
            log.error(
                tr("log_failed", name=account["username"]), exc_info=sys.exc_info()
            )
            return False
        command = " ".join(shlex.quote(part) for part in result.command)
        log.info(tr("log_cmd", name=account["username"], cmd=command))
        log.info(tr("log_output", path=result.log_path))
        name = account["username"]
        QTimer.singleShot(CLIENT_CHECK_MS, lambda: self._check_exit(result, name))
        return True

    def _check_exit(self, result, name):
        code = result.process.poll()
        if code not in (None, 0):
            log.error(tr("log_client_exit", name=name, code=code, path=result.log_path))

    def open_for_login(self):
        account = self.selected_account()
        if account is None or not self.client_ok():
            return
        if self._start(account, None, True):
            log.info(tr("log_login_hint"))

    def launch_selected(self):
        ids = self.selected_ids()
        if not ids:
            self.warn("warn_noacc_title", "warn_noacc")
            return
        place, job = self.place.text().strip(), self.job.text().strip()
        try:
            validate_game(place, job)
        except ManagerError as exc:
            QMessageBox.warning(self, tr("warn_game_title"), str(exc))
            return
        limit = self.settings["max_batch"]
        if len(ids) > limit:
            self.warn("warn_many_title", "warn_many", n=limit)
            return
        if not self.settings["isolate_profiles"] and len(ids) > 1:
            self.warn("warn_many_title", "warn_swap_one")
            return
        if len(ids) > 3:
            answer = QMessageBox.question(
                self, tr("ask_many_title"), tr("ask_many", n=len(ids))
            )
            if answer != QMessageBox.Yes:
                return
        if not self.client_ok():
            return
        uri = game_uri(place, job)
        self.settings["last_place"] = place
        self.settings.save()
        self.queue = [(ident, uri) for ident in ids]
        self.batch_size = len(ids)
        self.launch_btn.setEnabled(False)
        self.next_launch()

    def next_launch(self):
        if not self.queue:
            self.launch_btn.setEnabled(True)
            log.success(tr("log_done"))
            return
        ident, uri = self.queue.pop(0)
        account = self.vault.get(ident)
        if account and self._start(account, uri, self.batch_size == 1):
            self.vault.touch(ident, time.strftime(STAMP_FORMAT))
            self.vault.save()
            self.refresh()
        if self.queue:
            QTimer.singleShot(self.delay.value() * 1000, self.next_launch)
        else:
            self.next_launch()

    def closeEvent(self, event):
        self.clear_clipboard()
        log.remove_listener(self._on_log)
        log.info(tr("log_exit"))
        super().closeEvent(event)


def open_vault(settings):
    path = config.VAULT_FILE
    if not path.exists():
        dialog = CreateVaultDialog()
        if dialog.exec() != QDialog.Accepted:
            dialog.clear()
            return None
        password = dialog.password()
        dialog.clear()
        vault, migrated = storage.create_vault(path, password, config.LEGACY_FILE)
        log.success(tr("log_vault_created"))
        if migrated:
            log.info(tr("log_migrated", n=migrated))
        return vault
    opened = {}

    def check(password):
        try:
            opened["vault"] = Vault.open(path, password)
        except WrongPassword:
            return False
        return True

    if UnlockDialog(settings, check).exec() != QDialog.Accepted:
        return None
    vault = opened["vault"]
    log.success(tr("log_vault_unlocked", n=len(vault)))
    return vault


def install_excepthook():
    def hook(exc_type, exc, tb):
        log.error(tr("log_unhandled", path=config.LOG_FILE), exc_info=(exc_type, exc, tb))
        try:
            QMessageBox.critical(None, tr("err_title"), tr("err_generic", path=config.LOG_FILE))
        except Exception:
            pass

    sys.excepthook = hook


def run(settings, qt_args):
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(config.APP_NAME)
    app.setDesktopFileName(config.APP_NAME)
    app.setStyle("Fusion")
    install_excepthook()
    appearance = Appearance(app)
    appearance.apply(settings["theme"], settings["font"])
    try:
        vault = open_vault(settings)
    except ManagerError as exc:
        log.error(str(exc))
        QMessageBox.critical(None, tr("err_title"), str(exc))
        return 1
    if vault is None:
        return 0
    window = MainWindow(settings, vault, appearance)
    window.show()
    if not settings["seen_guide"]:
        settings["seen_guide"] = True
        settings.save()
        QTimer.singleShot(300, window.show_guide)
    return app.exec()
