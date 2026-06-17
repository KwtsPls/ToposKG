# Topos Update Tool

This tool automates the preparation and update workflow for ToposKG administrative and OSM-derived geospatial data.

It currently supports the following pipeline:

1. Download GAUL archives.
2. Extract GAUL shapefiles and convert them to GeoJSON.
3. Split GAUL GeoJSON files by country.
4. Convert GAUL country GeoJSON files to N-Triples.
5. Download OSM administrative boundary data from Geofabrik.
6. Convert OSM administrative GeoJSON files to N-Triples.
7. Copy precomputed GAUL–OSM linking metadata into the OSM country directories.
8. Discover and materialize OSM administrative hierarchy/boundary relationships.
9. Relink OSM data using the updated `linking_admin_*.csv` files.
10. Connect GAUL and OSM outputs.
11. Download and extract non-administrative OSM features: water, forests, and POIs.
12. Convert non-administrative OSM features to N-Triples.
13. Clean and group the final outputs.

The main entry point is:

```bash
python3 topos_update_tool.py --config topos-update.config --workdir data
```

---

## 1. Directory layout

A typical project directory should look like this before a full run:

```text
topos-update-tool/
├── topos_update_tool.py
├── topos-update.config
├── world.csv
├── parser.jar
├── fixer.py
├── split_gaul_country.sh
├── create_country_nt.sh
├── prepare_osm_country.sh
├── create_osm_country_nt.sh
├── discover_osm_boundaries.sh
├── prepare_osm_non_admin_country.sh
├── jedai_spatial_pipeline.sh
├── jedai_map.sh
├── geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar
├── linking_dir/
│   ├── Greece/
│   │   ├── greece_osm_levels.csv
│   │   ├── linking_admin_0.csv
│   │   ├── linking_admin_1.csv
│   │   ├── linking_admin_2.csv
│   │   └── stats.txt
│   └── ...
└── wikidata_upper_file.nt
```

The output directory is controlled by `--workdir`. With `--workdir data`, outputs are written under:

```text
data/
├── gaul/
│   └── countries/
└── osm/
    ├── countries/
    ├── pois/
    ├── water/
    └── forests/
```

---

## 2. Configuration file

The tool reads a simple key-value configuration file. The default filename is:

```text
topos-update.config
```

Example:

```text
GAUL_ADMIN_L0=https://mars.jrc.ec.europa.eu/asap/files/gaul0_asap.zip
GAUL_ADMIN_L1=https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L2.zip
GAUL_ADMIN_L2=https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L2.zip

COUNTRIES_CSV=world.csv
PARSER_JAR_PATH=parser.jar
WIKIDATA_UPPER_PATH=wikidata_upper_file.nt
LINKING_DIR_PATH=linking_dir
```

### Config keys

| Key | Required for full run? | Description |
|---|---:|---|
| `GAUL_ADMIN_L0` | Yes | Download URL for GAUL level 0 data. |
| `GAUL_ADMIN_L1` | Yes | Download URL for GAUL level 1 data. |
| `GAUL_ADMIN_L2` | Yes | Download URL for GAUL level 2 data. |
| `COUNTRIES_CSV` | No, but strongly recommended | Path to the country metadata CSV. If empty, the tool expects `world.csv` next to `topos_update_tool.py`. |
| `PARSER_JAR_PATH` | No, but strongly recommended | Path to the parser JAR. If empty, the tool expects `parser.jar` next to `topos_update_tool.py`. |
| `WIKIDATA_UPPER_PATH` | Yes, unless boundary discovery is skipped | Path to the Wikidata hierarchy/upper administrative file used during OSM hierarchy materialization. |
| `LINKING_DIR_PATH` | No, but strongly recommended | Path to the directory containing `linking_admin_*.csv` and `*_osm_levels.csv` files. If empty, the tool expects `linking_dir/` next to `topos_update_tool.py`. |

Relative paths are resolved relative to the directory containing `topos-update.config`.

For example, if your config is:

```text
COUNTRIES_CSV=metadata/world.csv
PARSER_JAR_PATH=jars/parser.jar
```

and the config file is located at:

```text
/home/kwts/Desktop/topos-update-tool/topos-update.config
```

then the tool resolves these as:

```text
/home/kwts/Desktop/topos-update-tool/metadata/world.csv
/home/kwts/Desktop/topos-update-tool/jars/parser.jar
```

---

## 3. Country CSV format

The country CSV must contain at least these columns:

```csv
country,uri,code,geofabrik_cont
Greece,<http://www.wikidata.org/entity/Q41>,grc,europe
Algeria,<http://www.wikidata.org/entity/Q262>,dza,africa
```

### Column descriptions

| Column | Description |
|---|---|
| `country` | Human-readable country name. This is also used for country directory names. |
| `uri` | Wikidata URI of the country, usually wrapped in `<...>`. |
| `code` | Country code used as the parser prefix, for example `grc`, `dza`, `ago`. |
| `geofabrik_cont` | Geofabrik continent/subregion path component, for example `europe`, `africa`, `asia`. |

The OSM download URL is constructed as:

```text
https://download.geofabrik.de/<geofabrik_cont>/<country-name-lowercase-with-dashes>-latest.osm.pbf
```

For example:

```text
country=Greece
geofabrik_cont=europe
```

produces:

```text
https://download.geofabrik.de/europe/greece-latest.osm.pbf
```

---

## 4. External data required for a full run

A full run requires more than the Python script itself. You need the following files.

### 4.1 Parser JAR

This .jar file is simply the compilation of the Topos-parser under this repository. It is highly recommended to compile Topos-parser locally and replace parser.jar with the result. However, for ease of use, we provide the latest compilation and packaging here under the name parser.jar

```text
parser.jar
```

Configured with:

```text
PARSER_JAR_PATH=parser.jar
```

If `PARSER_JAR_PATH` is empty, the tool expects `parser.jar` next to `topos_update_tool.py`.

The parser must support the following commands:

```text
create
fix
osm
validate_iris
rank_intersections
osm_hierarchy
relink
connection
water
```

### 4.2 `fixer.py`

Required after OSM administrative NT creation:

```text
fixer.py
```

By default, the tool expects it next to `topos_update_tool.py`.

You can override the path with:

```bash
--fixer-script /path/to/fixer.py
```

### 4.3 Wikidata hierarchy file

Required for OSM boundary discovery:

```text
WIKIDATA_UPPER_PATH=/path/to/wikidata_upper_file.nt
```

This file is passed to the parser command:

```bash
java -jar parser.jar osm_hierarchy ...
```

### 4.4 Linking metadata directory

Required before OSM boundary discovery and relinking:

```text
LINKING_DIR_PATH=/path/to/linking_dir
```

Expected structure:

```text
linking_dir/
├── Greece/
│   ├── greece_osm_levels.csv
│   ├── linking_admin_0.csv
│   ├── linking_admin_1.csv
│   ├── linking_admin_2.csv
│   └── stats.txt
├── Algeria/
│   ├── algeria_osm_levels.csv
│   ├── linking_admin_0.csv
│   ├── linking_admin_1.csv
│   ├── linking_admin_2.csv
│   └── stats.txt
└── ...
```

The tool copies the metadata for each country into:

```text
data/osm/countries/<country>/
```

After copying, files ending in `_osm_levels.csv` are normalized by replacing spaces with underscores.

### 4.5 JEDAI scripts and geospatial interlinking JAR

Required for OSM boundary discovery:

```text
jedai_spatial_pipeline.sh
jedai_map.sh
geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar
```

These must be located next to:

```text
discover_osm_boundaries.sh
```

---

## 5. Zenodo resources

The linking metadata directory and Wikidata hierarchy file are available from the Zenodo repository:

```text
https://zenodo.org/records/20731058
```

After downloading/extracting the Zenodo contents, update your config accordingly, for example:

```text
LINKING_DIR_PATH=/home/kwts/Desktop/topos-update-tool/linking_dir
WIKIDATA_UPPER_PATH=/home/kwts/Desktop/topos-update-tool/wikidata_upper_file.nt
```

Adjust the filenames to match the files you extracted from Zenodo.

---

## 6. Prerequisites

The tool has system-level dependencies and Python dependencies.

The commands below assume Ubuntu/Debian.

### 6.1 Java 17

The parser and interlinking JARs require Java.

Install Java 17:

```bash
sudo apt update
sudo apt install openjdk-17-jdk
```

Verify:

```bash
java -version
```

Expected output should mention version `17`, for example:

```text
openjdk version "17..."
```

### 6.2 Python 3 and virtual environment support

Install Python tools:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install --upgrade pip
pip install geopandas pyogrio shapely
```

### 6.3 OSM tools

Install `wget` and `osmium`:

```bash
sudo apt update
sudo apt install wget osmium-tool
```

Verify:

```bash
wget --version
osmium --version
```

### 6.4 Common shell tools

The scripts use standard Unix tools such as:

```text
bash
grep
sed
awk
cat
tail
wc
mktemp
realpath
tr
```

These are normally available on Ubuntu/Debian. If needed:

```bash
sudo apt install coreutils gawk sed grep
```

---

## 7. Make scripts executable

Before running the tool, make all shell scripts executable:

```bash
chmod +x split_gaul_country.sh
chmod +x create_country_nt.sh
chmod +x prepare_osm_country.sh
chmod +x create_osm_country_nt.sh
chmod +x discover_osm_boundaries.sh
chmod +x prepare_osm_non_admin_country.sh
chmod +x jedai_spatial_pipeline.sh
chmod +x jedai_map.sh
```

---

## 8. Absolute minimum needed for a full run

To run all components without skipping any stage, you need:

```text
topos_update_tool.py
topos-update.config
world.csv or COUNTRIES_CSV
parser.jar or PARSER_JAR_PATH
fixer.py
linking_dir/ or LINKING_DIR_PATH
Wikidata hierarchy file via WIKIDATA_UPPER_PATH
jedai_spatial_pipeline.sh
jedai_map.sh
geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar
Java 17
Python venv with geopandas, pyogrio, shapely
wget
osmium-tool
Internet access to GAUL and Geofabrik download URLs
Enough disk space for GAUL and OSM intermediate files
```

A minimal full-run config should look like this:

```text
GAUL_ADMIN_L0=https://mars.jrc.ec.europa.eu/asap/files/gaul0_asap.zip
GAUL_ADMIN_L1=https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L2.zip
GAUL_ADMIN_L2=https://storage.googleapis.com/fao-maps-catalog-data/boundaries/GAUL_2024_L2.zip

COUNTRIES_CSV=/absolute/path/to/world.csv
PARSER_JAR_PATH=/absolute/path/to/parser.jar
WIKIDATA_UPPER_PATH=/absolute/path/to/wikidata_upper_file.nt
LINKING_DIR_PATH=/absolute/path/to/linking_dir
```

Then run:

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data
```

---

## 9. Pipeline outputs

After a full run and cleanup, the main outputs are:

### GAUL administrative outputs

```text
data/gaul/countries/<country>/<Country>_x.nt
data/gaul/countries/<country>/<Country>_all.nt
```

### OSM administrative outputs

```text
data/osm/countries/<country>/<Country>_x.nt
data/osm/countries/<country>/<Country>_all.nt
```

### OSM POI outputs

```text
data/osm/pois/<country>/<Country>.nt
```

### OSM water outputs

```text
data/osm/water/<country>/<Country>.nt
```

### OSM forest outputs

```text
data/osm/forests/<country>/<Country>.nt
```

---

## 10. Running selected stages

Every stage can be skipped with command-line flags. This is useful for testing or resuming the pipeline.

### Run everything

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data
```

### Run everything but keep intermediate files

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data \
  --skip-cleanup
```

### Run only cleanup

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data \
  --skip-download \
  --skip-country-split \
  --skip-nt-creation \
  --skip-osm \
  --skip-osm-nt-creation \
  --skip-linking-metadata \
  --skip-osm-boundary-discovery \
  --skip-osm-relink \
  --skip-gaul-osm-connection \
  --skip-osm-non-admin \
  --skip-osm-non-admin-nt-creation
```

### Run only OSM boundary discovery

Assuming OSM NT files and linking metadata are already available:

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data \
  --skip-download \
  --skip-country-split \
  --skip-nt-creation \
  --skip-osm \
  --skip-osm-nt-creation \
  --skip-linking-metadata \
  --skip-osm-relink \
  --skip-gaul-osm-connection \
  --skip-osm-non-admin \
  --skip-osm-non-admin-nt-creation \
  --skip-cleanup
```

### Run only OSM relinking

Assuming boundary discovery has already produced `<country_lower>_final.nt`:

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data \
  --skip-download \
  --skip-country-split \
  --skip-nt-creation \
  --skip-osm \
  --skip-osm-nt-creation \
  --skip-linking-metadata \
  --skip-osm-boundary-discovery \
  --skip-gaul-osm-connection \
  --skip-osm-non-admin \
  --skip-osm-non-admin-nt-creation \
  --skip-cleanup
```

### Run only GAUL/OSM connection

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data \
  --skip-download \
  --skip-country-split \
  --skip-nt-creation \
  --skip-osm \
  --skip-osm-nt-creation \
  --skip-linking-metadata \
  --skip-osm-boundary-discovery \
  --skip-osm-relink \
  --skip-osm-non-admin \
  --skip-osm-non-admin-nt-creation \
  --skip-cleanup
```

### Run only non-admin OSM extraction and NT creation

```bash
python3 topos_update_tool.py \
  --config topos-update.config \
  --workdir data \
  --skip-download \
  --skip-country-split \
  --skip-nt-creation \
  --skip-osm \
  --skip-osm-nt-creation \
  --skip-linking-metadata \
  --skip-osm-boundary-discovery \
  --skip-osm-relink \
  --skip-gaul-osm-connection \
  --skip-cleanup
```

---

## 11. Notes and assumptions

The OSM extraction scripts use Geofabrik filenames derived from the country name:

```text
Greece -> greece-latest.osm.pbf
Burkina Faso -> burkina-faso-latest.osm.pbf
```

For countries where the Geofabrik filename differs from this simple rule, update the country name or adapt the script.

The GeoJSON filtering scripts assume that each GeoJSON feature is written on one line. This matches the current `osmium export` and GAUL conversion workflow used by the tool.

The final cleanup step is destructive. Use:

```bash
--skip-cleanup
```

while debugging intermediate outputs.
