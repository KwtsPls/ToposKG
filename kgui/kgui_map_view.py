import sys
import geopandas as gpd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

from kgui_sources_model import KguiSourcesModel
from toposkg.utils import get_relative_path


class KguiMapCanvas(FigureCanvas):

    def __init__(self):
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

        # Load the shapefile
        self._map_data = gpd.read_file(get_relative_path('./resources/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp'))
        self._highlight_countries = []

        for name in self._map_data['NAME']:
            print(name)

        # print(self._map_data['NAME'])

    def set_countries(self, countries):
        print(countries)
        self._highlight_countries = countries
        self.generate_map()

    def generate_map(self):
        # Clear the axes before plotting again
        self.ax.clear()
        self.ax.set_position([0, 0, 1, 1])

        # Plot the world countries
        self._map_data.plot(ax=self.ax, color='lightgrey', edgecolor='black')

        # Highlight selected countries
        if self._highlight_countries:
            self._map_data[self._map_data['NAME'].isin(self._highlight_countries)].plot(ax=self.ax, color='orange')

        # Remove axes for better visualization
        self.ax.axis('off')

        # Adjust plot limits to fit the data properly
        # self.ax.set_xlim([-180, 180])
        # self.ax.set_ylim([-90, 90])

        # Redraw the canvas
        self.draw()


class KguiMapView(QWidget):
    def __init__(self, model: KguiSourcesModel):
        super().__init__()
        self.setWindowTitle("Interactive Map")
        self.model = model

        # Create the map canvas and layout
        self.map_canvas = KguiMapCanvas()
        self.map_canvas.generate_map()

        # Add the toolbar
        toolbar = NavigationToolbar2QT(self.map_canvas, self)

        layout = QVBoxLayout()
        layout.addWidget(toolbar)  # <-- Add toolbar
        layout.addWidget(self.map_canvas)  # <-- Add canvas

        self.setLayout(layout)
        self.show()

        # signals
        self.model.itemChanged.connect(self.on_item_changed)

    def on_item_changed(self):
        def traverse_item(item, items):
            if item.checkState() == Qt.CheckState.Checked:
                if item.metadata is not None and item.metadata.country is not None:
                    items.add(item.metadata.country)

            # Recursively visit all children
            for row in range(item.rowCount()):
                child_item = item.child(row)
                traverse_item(child_item, items)

        all_items = set()
        # Traverse from the root items
        for row in range(self.model.rowCount()):
            root_item = self.model.item(row)
            traverse_item(root_item, all_items)

        all_items = list(all_items)
        self.map_canvas.set_countries(all_items)

        return all_items


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KguiMapView()
    sys.exit(app.exec())
