from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QPushButton, QStackedWidget,
    QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
import sys
import os

from kgui_map_view import KguiMapView
from kgui_materializations_editor import KguiMaterializationsEditor
from kgui_sources_model import KguiSourcesModel
from kgui_sources_view import KguiSourcesView
from kgui_statistics_view import KguiStatisticsView
from kgui_translations_editor import KguiTranslationsEditor
from toposkg.toposkg_lib_core import KnowledgeGraphSourcesManager


class KguiWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window settings
        self.setWindowTitle("K-GUI")
        self.setGeometry(100, 100, 800, 600)

        # Model
        sources_manager = KnowledgeGraphSourcesManager(['/home/sergios/kg_sources'])
        self.model = KguiSourcesModel(sources_manager)

        # UI Creation
        self.output_dir_edit = None
        self.output_file_edit = None

        self.page_manager = QStackedWidget()

        self.sources_page = self.create_sources_page()
        self.materialization_page = self.create_materialization_page()
        self.translation_page = self.create_translation_page()
        self.construction_page = self.create_construction_page()

        self.page_manager.addWidget(self.sources_page)
        self.page_manager.addWidget(self.materialization_page)
        self.page_manager.addWidget(self.translation_page)
        self.page_manager.addWidget(self.construction_page)

        self.page_manager.setCurrentIndex(0)

        self.setCentralWidget(self.page_manager)

    def change_to_sources_page(self):
        self.page_manager.setCurrentIndex(0)

    def change_to_materialization_page(self):
        self.page_manager.setCurrentIndex(1)

    def change_to_translation_page(self):
        self.page_manager.setCurrentIndex(2)

    def change_to_construction_page(self):
        self.page_manager.setCurrentIndex(3)

    def create_steps_widget(self, current_step):
        # Create step labels
        stage1 = QLabel("Data Sources")
        stage2 = QLabel("Materialization")
        stage3 = QLabel("Translation")
        stage4 = QLabel("Construction")

        # Get the application's palette
        palette = QApplication.palette()

        # Use theme-based colors
        active_color = palette.color(QPalette.Highlight)
        inactive_color = palette.color(QPalette.WindowText)

        # Highlight the current step (e.g., stage1)
        for idx, i in enumerate([stage1, stage2, stage3, stage4]):
            if idx == current_step:
                i.setStyleSheet(f"font-weight: bold; color: {active_color.name()};")
            else:
                i.setStyleSheet(f"color: {inactive_color.name()};")

        # Add separators between steps
        separator1 = QLabel("→")
        separator2 = QLabel("→")
        separator3 = QLabel("→")

        # Create layout for the progress map
        steps_layout = QHBoxLayout()
        steps_layout.addWidget(stage1)
        steps_layout.addWidget(separator1)
        steps_layout.addWidget(stage2)
        steps_layout.addWidget(separator2)
        steps_layout.addWidget(stage3)
        steps_layout.addWidget(separator3)
        steps_layout.addWidget(stage4)

        return steps_layout

    def create_navigation_buttons(self, current_page):
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        action = None
        if current_page == 1:
            action = self.change_to_sources_page
        elif current_page == 2:
            action = self.change_to_materialization_page
        elif current_page == 3:
            action = self.change_to_translation_page
        if action is not None:
            button = QPushButton("Previous")
            button.released.connect(action)
            button_layout.addWidget(button)

        action = None
        if current_page == 0:
            action = self.change_to_materialization_page
        elif current_page == 1:
            action = self.change_to_translation_page
        elif current_page == 2:
            action = self.change_to_construction_page
        if action is not None:
            button = QPushButton("Next")
            button.released.connect(action)
            button_layout.addWidget(button)

        return button_layout

    def create_sources_page(self):
        # Left sidepane
        sidepane_group = QGroupBox("Data Sources")
        sidepane_layout = QVBoxLayout(sidepane_group)

        sources_view = KguiSourcesView(self.model)
        sidepane_layout.addWidget(sources_view)

        # Create two widgets to be placed in the splitter
        top_group = QGroupBox("Map")
        top_layout = QVBoxLayout(top_group)
        top_widget = KguiMapView(self.model)
        top_layout.addWidget(top_widget)

        bottom_group = QGroupBox("Statistics")
        bottom_layout = QVBoxLayout(bottom_group)
        bototm_widget = KguiStatisticsView(self.model)
        bottom_layout.addWidget(bototm_widget)

        # Create splitters
        top_bottom_splitter = QSplitter(Qt.Orientation.Vertical)
        top_bottom_splitter.addWidget(top_group)
        top_bottom_splitter.addWidget(bottom_group)
        top_bottom_splitter.setStretchFactor(0, 1)
        top_bottom_splitter.setStretchFactor(1, 2)

        left_right_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_right_splitter.addWidget(sidepane_group)
        left_right_splitter.addWidget(top_bottom_splitter)

        # Wrap splitter in a QWidget with layout (good practice)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)  # Add margins around the layout
        layout.setSpacing(20)  # Add spacing between widgets

        # Stage viz
        steps_layout = self.create_steps_widget(0)

        # Navigation buttons
        button_layout = self.create_navigation_buttons(0)

        # layout.addWidget(progress_bar)
        layout.addLayout(steps_layout)
        layout.addWidget(left_right_splitter, stretch=1)
        layout.addLayout(button_layout)

        return container

    def create_materialization_page(self):
        # Materialization widget
        materialization_editor = KguiMaterializationsEditor(self.model)

        # Wrap splitter in a QWidget with layout (good practice)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)  # Add margins around the layout
        layout.setSpacing(20)  # Add spacing between widgets

        # Stage viz
        steps_layout = self.create_steps_widget(1)

        # Navigation buttons
        button_layout = self.create_navigation_buttons(1)

        # layout.addWidget(progress_bar)
        layout.addLayout(steps_layout)
        layout.addWidget(materialization_editor, stretch=1)
        layout.addLayout(button_layout)

        return container

    def create_translation_page(self):
        # Translation widget
        translation_editor = KguiTranslationsEditor(self.model)

        # Wrap splitter in a QWidget with layout (good practice)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)  # Add margins around the layout
        layout.setSpacing(20)  # Add spacing between widgets

        # Stage viz
        steps_layout = self.create_steps_widget(2)

        # Navigation buttons
        button_layout = self.create_navigation_buttons(2)

        # layout.addWidget(progress_bar)
        layout.addLayout(steps_layout)
        layout.addWidget(translation_editor, stretch=1)
        layout.addLayout(button_layout)

        return container

    def create_construction_page(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Step visualization
        steps_layout = self.create_steps_widget(3)
        layout.addLayout(steps_layout)

        # Output selection group
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout()
        output_layout.setSpacing(10)

        # Output directory selector
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Output Directory:")
        self.output_dir_edit = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_output_directory)

        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.output_dir_edit, stretch=1)
        dir_layout.addWidget(browse_button)

        # Output file name input
        file_layout = QHBoxLayout()
        file_label = QLabel("File Name:")
        self.output_file_edit = QLineEdit()

        file_layout.addWidget(file_label)
        file_layout.addWidget(self.output_file_edit, stretch=1)

        output_layout.addLayout(dir_layout)
        output_layout.addLayout(file_layout)
        output_group.setLayout(output_layout)

        layout.addWidget(output_group)

        # Construct button
        construct_button = QPushButton("Construct")
        construct_button.clicked.connect(self.construct_file)
        construct_button.setFixedWidth(120)
        construct_button.setStyleSheet("padding: 8px;")
        layout.addWidget(construct_button, alignment=Qt.AlignmentFlag.AlignRight)

        # Navigation buttons
        button_layout = self.create_navigation_buttons(3)
        layout.addStretch()
        layout.addLayout(button_layout)

        return container

    def browse_output_directory(self):
        dir_path = QFileDialog.getExistingDirectory(None, "Select Output Directory")
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def construct_file(self):
        output_dir = self.output_dir_edit.text()
        file_name = self.output_file_edit.text()
        if output_dir and file_name:
            full_path = os.path.join(output_dir, file_name)
            print(f"Constructing file at: {full_path}")
            # Add logic to construct and save the file
        else:
            print("Output directory or file name is missing.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KguiWindow()
    window.show()
    sys.exit(app.exec_())
