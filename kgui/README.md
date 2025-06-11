<div align="center">
  <h1>K-GUI</h1>
</div>

<div align="center">
  A Graphical User Interface for building Geospatial Knowledge Graphs using ToposKG.
</div>

## Overview
K-GUI is a GUI application written in Python and PySide6, created to provide easy access to the powerful functionality of ToposKG and toposkg-lib.

## Highlights
- **Ease of use.** K-GUI is a pure UI tool, no code involved.
- **Powerful.** K-GUI provides access to the powerful core functionalities of toposkg-lib.
- **Active development.** K-GUI will keep getting updates as we work on our projects.

## Getting Started

### Repository structure
The repository is organized as follows:
- `resources/` contains Natural Earth maps, used to visualize the selected data.
- `src/`contains the source code of K-GUI

### How to run
To run K-GUI first create a new virtual environment using your package manager of choice (we will use `conda` for the example).
```sh
conda create -n kgui python=3.10
conda activate kgui
```

Install the required packages.
```sh
pip install -r requirements.txt
```

Run the application from the `src/` directory.
```sh
cd src
python kgui_window.py
```
