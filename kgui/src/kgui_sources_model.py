from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt

from toposkg.toposkg_lib_core import KnowledgeGraphSourcesManager, KnowledgeGraphDataSource


class KguiSourceItem(QStandardItem):
    def __init__(self, name: str, data_source: KnowledgeGraphDataSource):
        super().__init__(name)
        self.setCheckable(True)
        self.setEditable(False)
        self.data_source = data_source
        self.metadata = data_source.metadata


class KguiSourcesModel(QStandardItemModel):

    def __init__(self, source_manager: KnowledgeGraphSourcesManager, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["Resources"])
        self.setColumnCount(1)
        self.setRowCount(0)

        # Populate the model with the directory structure
        for data_source in source_manager.get_sources_as_tree():
            self.add_items(self.invisibleRootItem(), data_source)

        # signals
        self.itemChanged.connect(self.on_item_changed)

    @staticmethod
    def on_item_changed(item: KguiSourceItem):
        for row in range(item.rowCount()):
            child_item = item.child(row)
            child_item.setCheckState(item.checkState())  # on_item_changed will be called for each child item

    def add_items(self, parent_item, data_source: KnowledgeGraphDataSource):
        item = KguiSourceItem(data_source.name, data_source)
        parent_item.appendRow(item)
        for child in data_source.children:
            self.add_items(item, child)

    def get_all_items(self):
        def traverse_item(item, items):
            items.append(item)
            # Recursively visit all children
            for row in range(item.rowCount()):
                child_item = item.child(row)
                traverse_item(child_item, items)

        all_items = []
        # Traverse from the root items
        for row in range(self.rowCount()):
            root_item = self.item(row)
            traverse_item(root_item, all_items)

        return all_items

    def get_selected_items(self):
        items = self.get_all_items()
        selected_items = []
        for item in items:
            if item.checkState() == Qt.CheckState.Checked:
                selected_items.append(item)
        return selected_items
