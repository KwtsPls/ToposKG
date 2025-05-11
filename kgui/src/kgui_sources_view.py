import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QTreeView

from kgui_sources_model import KguiSourcesModel

class KguiSourcesView(QTreeView):
    def __init__(self, model: KguiSourcesModel):
        super().__init__()

        # Set up tree view
        self.setModel(model)
        self.setHeaderHidden(True)
        self.expandToDepth(1)

