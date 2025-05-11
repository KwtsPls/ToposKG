import sys
from PySide6.QtWidgets import QTableView, QAbstractItemView, QVBoxLayout, QWidget, QApplication, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt

from kgui_sources_model import KguiSourcesModel


class KguiStatisticsView(QTableView):
    def __init__(self, model: KguiSourcesModel):
        super().__init__()
        self.source_model = model

        # Set up the table model
        self.table_model = QStandardItemModel()
        self.table_model.setHorizontalHeaderLabels([
            "Name", "Size", "Type", "Edges", "Nodes", "Predicates", "Avg Degree", "Classes", "Country"
        ])
        self.setModel(self.table_model)

        # Configure table view
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Connect signals
        self.source_model.itemChanged.connect(self.update_table)

    def update_table(self):
        self.table_model.removeRows(0, self.table_model.rowCount())  # Clear the table

        def traverse_item(item):
            if item.checkState() == Qt.CheckState.Checked and item.metadata:
                metadata = item.metadata.to_dict()
                row = [
                    QStandardItem(str(metadata.get("name", ""))),
                    QStandardItem(str(metadata.get("size", ""))),
                    QStandardItem(str(metadata.get("type", ""))),
                    QStandardItem(str(metadata.get("edges", ""))),
                    QStandardItem(str(metadata.get("nodes", ""))),
                    QStandardItem(str(metadata.get("predicates", ""))),
                    QStandardItem(str(metadata.get("average_degree", ""))),
                    QStandardItem(str(metadata.get("classes", ""))),
                    QStandardItem(str(metadata.get("country", ""))),
                ]
                for cell in row:
                    cell.setEditable(False)
                self.table_model.appendRow(row)

            # Recursively visit children
            for row in range(item.rowCount()):
                traverse_item(item.child(row))

        # Traverse all root items
        for row in range(self.source_model.rowCount()):
            root_item = self.source_model.item(row)
            traverse_item(root_item)