from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QGroupBox, QSplitter, QScrollArea, QSpacerItem, QSizePolicy

from kgui_sources_model import KguiSourcesModel


class KguiMaterializationsEditor(QWidget):
    def __init__(self, model: KguiSourcesModel):
        super().__init__()

        self.entries = []

        self.create_ui(model)

    def get_materialization_pairs(self):
        pairs = []
        for object1, object2 in self.entries:
            if object1.currentText() and object2.currentText():
                pairs.append((object1.currentText(), object2.currentText()))
        return pairs

    def create_ui(self, model: KguiSourcesModel):
        layout = QVBoxLayout()

        # Scroll area to contain pairs
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()

        pairs_layout = QVBoxLayout(scroll_content)
        pairs_layout.setSpacing(2)

        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        pairs_layout.addItem(spacer)

        scroll_content.setLayout(pairs_layout)
        scroll_area.setWidget(scroll_content)

        def add_object_pair():
            pair_widget = QWidget()
            pair_layout = QHBoxLayout(pair_widget)

            targets = [item.data_source.path for item in model.get_selected_items() if "." in item.data_source.path]
            print(targets)

            object1 = QComboBox()
            object1.addItems(targets)

            object2 = QComboBox()
            object2.addItems(targets)

            # Delete button
            delete_button = QPushButton("X")
            delete_button.setFixedSize(24, 24)

            def remove_pair():
                self.entries.remove((object1, object2))
                pairs_layout.removeWidget(pair_widget)
                pair_widget.setParent(None)

            delete_button.clicked.connect(remove_pair)

            # Add widgets to layout
            pair_layout.addWidget(object1)
            pair_layout.addWidget(object2)
            pair_layout.addWidget(delete_button)

            pairs_layout.addWidget(pair_widget)
            self.entries.append((object1, object2))

        add_pair_button = QPushButton("Add Materialization")
        add_pair_button.clicked.connect(add_object_pair)

        layout.addWidget(scroll_area, stretch=1)
        layout.addWidget(add_pair_button)

        self.setLayout(layout)
        self.show()



