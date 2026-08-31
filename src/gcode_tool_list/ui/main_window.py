"""Main window for the local desktop application."""

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gcode_tool_list.examine import filter_lines


class MainWindow(QMainWindow):
    """Application shell and legacy-compatible Examine workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("G-Code Tool List Generator")
        self.resize(900, 650)
        self._examine_source = ""

        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)

        self.main_page = self._build_main_page()
        self.examine_page = self._build_examine_page()
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.examine_page)

    def _build_main_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        heading = QLabel("G-Code Program")
        layout.addWidget(heading)

        open_button = QPushButton("Open G-Code File")
        open_button.clicked.connect(self._open_file)
        layout.addWidget(open_button)

        self.program_editor = QPlainTextEdit()
        self.program_editor.setPlaceholderText(
            "Open a G-code file or paste G-code here. "
            "Edits remain in memory and never overwrite the original file."
        )
        layout.addWidget(self.program_editor)

        mode_layout = QHBoxLayout()
        generate_button = QPushButton("Generate Tool List")
        generate_button.clicked.connect(self._show_generate_placeholder)
        examine_button = QPushButton("Use Like Examine")
        examine_button.clicked.connect(self._open_examine_page)
        mode_layout.addWidget(generate_button)
        mode_layout.addWidget(examine_button)
        layout.addLayout(mode_layout)

        return page

    def _build_examine_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        heading = QLabel("Use Like Examine")
        layout.addWidget(heading)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter literal search text")
        self.search_input.returnPressed.connect(self._filter_program)
        filter_button = QPushButton("Filter")
        filter_button.clicked.connect(self._filter_program)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(filter_button)
        layout.addLayout(search_layout)

        self.examine_output = QPlainTextEdit()
        self.examine_output.setPlaceholderText("Matching lines will appear here.")
        layout.addWidget(self.examine_output)

        back_button = QPushButton("Back")
        back_button.clicked.connect(self._show_main_page)
        layout.addWidget(back_button)

        return page

    def _open_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open G-Code File",
            "",
            "G-Code Files (*.nc *.cnc *.gcode *.tap *.txt);;All Files (*)",
        )
        if not file_name:
            return

        try:
            data = Path(file_name).read_bytes()
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("cp1252")
        except OSError as error:
            QMessageBox.critical(self, "Unable to Open File", str(error))
            return

        self.program_editor.setPlainText(text)

    def _show_generate_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "Generate Tool List",
            "Structured tool-list generation will be added in a later milestone.",
        )

    def _open_examine_page(self) -> None:
        self._examine_source = self.program_editor.toPlainText()
        self.examine_output.clear()
        self.pages.setCurrentWidget(self.examine_page)
        self.search_input.setFocus()

    def _filter_program(self) -> None:
        self.examine_output.setPlainText(
            filter_lines(self._examine_source, self.search_input.text())
        )

    def _show_main_page(self) -> None:
        self.pages.setCurrentWidget(self.main_page)
