#!/usr/bin/env python3

import argparse
import csv
import logging
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import geopandas as gpd


LOG = logging.getLogger("topos-update")


def read_config(config_path: Path) -> dict[str, str]:
    config = {}

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                raise ValueError(f"Invalid config line {line_no}: {line}")

            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()

    return config


def resolve_config_path(value: str, default_path: Path, config_path: Path) -> Path:
    if not value:
        return default_path

    path = Path(value)

    if path.is_absolute():
        return path

    return config_path.parent / path


def resolve_required_config_path(
    config: dict[str, str],
    key: str,
    config_path: Path,
) -> Path:
    value = config.get(key, "").strip()

    if not value:
        raise ValueError(f"Missing required config value: {key}")

    path = Path(value)

    if path.is_absolute():
        return path

    return config_path.parent / path


def resolve_tool_path(path_value: str, script_dir: Path) -> Path:
    path = Path(path_value)

    if path.is_absolute():
        return path

    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path.resolve()

    return (script_dir / path).resolve()


def safe_name(value: str) -> str:
    result = []

    for ch in value:
        if ch.isspace() or ch == "/":
            result.append("_")
        elif ch.isalnum() or ch in "._-":
            result.append(ch)
        else:
            result.append("_")

    return "".join(result)


def gaul_entries(config: dict[str, str]) -> dict[str, str]:
    entries = {}

    for key, value in config.items():
        if key.startswith("GAUL_ADMIN_") and value:
            level = key.replace("GAUL_ADMIN_", "")
            entries[level] = value

    if not entries:
        raise ValueError("No GAUL_ADMIN_* entries found in config.")

    return entries


def filename_from_url(url: str, fallback: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name

    if not name:
        return fallback

    if not name.endswith(".zip"):
        return f"{name}.zip"

    return name


def download_file(url: str, output_path: Path, force: bool = False) -> None:
    if output_path.exists() and not force:
        LOG.info("Already downloaded: %s", output_path)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    LOG.info("Downloading %s", url)
    LOG.info("Destination: %s", output_path)

    with urllib.request.urlopen(url) as response:
        total = response.headers.get("Content-Length")
        total = int(total) if total is not None else None

        downloaded = 0
        chunk_size = 1024 * 1024

        with tmp_path.open("wb") as f:
            while True:
                chunk = response.read(chunk_size)

                if not chunk:
                    break

                f.write(chunk)
                downloaded += len(chunk)

                if total:
                    percent = downloaded * 100 / total
                    print(
                        f"\rDownloaded {downloaded / 1_000_000:.1f} MB "
                        f"of {total / 1_000_000:.1f} MB "
                        f"({percent:.1f}%)",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\rDownloaded {downloaded / 1_000_000:.1f} MB",
                        end="",
                        flush=True,
                    )

    print()
    tmp_path.replace(output_path)


def safe_unzip(zip_path: Path, output_dir: Path, force: bool = False) -> None:
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        LOG.info("Already extracted: %s", output_dir)
        return

    if output_dir.exists() and force:
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    LOG.info("Extracting %s", zip_path)

    output_root = output_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target_path = (output_dir / member.filename).resolve()

            if not str(target_path).startswith(str(output_root)):
                raise RuntimeError(f"Unsafe zip entry detected: {member.filename}")

            zf.extract(member, output_dir)


def find_shapefiles(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.shp"))


def convert_shp_to_geojson(
    shp_path: Path,
    output_path: Path,
    force: bool = False,
    reproject_to_wgs84: bool = True,
) -> None:
    if output_path.exists() and not force:
        LOG.info("Already converted: %s", output_path)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    LOG.info("Converting %s -> %s", shp_path, output_path)

    gdf = gpd.read_file(shp_path)

    if gdf.crs is None:
        LOG.warning("No CRS found for %s. Writing as-is.", shp_path)
    elif reproject_to_wgs84 and gdf.crs.to_epsg() != 4326:
        LOG.info("Reprojecting %s from %s to EPSG:4326", shp_path, gdf.crs)
        gdf = gdf.to_crs("EPSG:4326")

    gdf.to_file(output_path, driver="GeoJSON")


def prepare_gaul(config: dict[str, str], workdir: Path, force: bool = False) -> None:
    entries = gaul_entries(config)

    gaul_dir = workdir / "gaul"
    raw_dir = gaul_dir / "raw"
    extracted_dir = gaul_dir / "extracted"
    geojson_dir = gaul_dir / "geojson"

    for level, url in sorted(entries.items()):
        LOG.info("Processing GAUL level: %s", level)

        zip_name = filename_from_url(url, fallback=f"{level}.zip")
        zip_path = raw_dir / f"{level}_{zip_name}"

        level_extract_dir = extracted_dir / level
        level_geojson_dir = geojson_dir / level

        download_file(url, zip_path, force=force)
        safe_unzip(zip_path, level_extract_dir, force=force)

        shapefiles = find_shapefiles(level_extract_dir)

        if not shapefiles:
            LOG.warning("No .shp files found for %s in %s", level, level_extract_dir)
            continue

        for shp_path in shapefiles:
            relative_name = shp_path.relative_to(level_extract_dir).with_suffix(".geojson")
            output_path = level_geojson_dir / relative_name

            convert_shp_to_geojson(
                shp_path=shp_path,
                output_path=output_path,
                force=force,
            )

    LOG.info("GAUL preparation complete.")
    LOG.info("GAUL GeoJSON directory: %s", geojson_dir)


def read_country_records(countries_csv: Path) -> list[dict[str, str]]:
    if not countries_csv.exists():
        raise FileNotFoundError(f"Countries CSV not found: {countries_csv}")

    records = []

    with countries_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or "country" not in reader.fieldnames:
            raise ValueError(
                f"CSV file {countries_csv} must contain a 'country' column."
            )

        for row in reader:
            country = row.get("country", "").strip()

            if not country:
                continue

            records.append(
                {
                    "country": country,
                    "code": row.get("code", "").strip(),
                    "uri": row.get("uri", "").strip(),
                    "geofabrik_cont": row.get("geofabrik_cont", "").strip(),
                }
            )

    if not records:
        raise ValueError(f"No countries found in {countries_csv}")

    return records


def countries_csv_from_config(config: dict[str, str], config_path: Path) -> Path:
    default_csv = Path(__file__).resolve().parent / "world.csv"

    return resolve_config_path(
        value=config.get("COUNTRIES_CSV", ""),
        default_path=default_csv,
        config_path=config_path,
    )


def read_countries(countries_csv: Path) -> list[str]:
    return [record["country"] for record in read_country_records(countries_csv)]


def split_gaul_by_country(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
    split_script_path: Path,
) -> None:
    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    gaul_geojson_root = workdir / "gaul" / "geojson"
    countries_output_root = workdir / "gaul" / "countries"

    if not gaul_geojson_root.exists():
        raise FileNotFoundError(
            f"GAUL GeoJSON directory does not exist: {gaul_geojson_root}. "
            f"Run the GAUL preparation step first."
        )

    if not split_script_path.exists():
        raise FileNotFoundError(f"Country split script not found: {split_script_path}")

    countries_output_root.mkdir(parents=True, exist_ok=True)

    LOG.info("Splitting GAUL GeoJSON files by country.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("GAUL GeoJSON root: %s", gaul_geojson_root)
    LOG.info("Country output root: %s", countries_output_root)

    for index, record in enumerate(country_records, start=1):
        country = record["country"]
        iso3_code = record["code"]

        LOG.info(
            "[%d/%d] Processing country: %s, iso3_code=%s",
            index,
            len(country_records),
            country,
            iso3_code if iso3_code else "<empty>",
        )

        subprocess.run(
            [
                "bash",
                str(split_script_path),
                country,
                str(gaul_geojson_root),
                str(countries_output_root),
                iso3_code,
            ],
            check=True,
        )

    LOG.info("Country splitting complete.")


def resolve_parser_jar(config: dict[str, str], config_path: Path) -> Path:
    default_parser_jar = Path(__file__).resolve().parent / "parser.jar"

    return resolve_config_path(
        value=config.get("PARSER_JAR_PATH", ""),
        default_path=default_parser_jar,
        config_path=config_path,
    )


def create_country_nt_files(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
    nt_script_path: Path,
) -> None:
    countries_csv = countries_csv_from_config(config, config_path)

    parser_jar = resolve_parser_jar(
        config=config,
        config_path=config_path,
    )

    countries = read_countries(countries_csv)

    countries_root = workdir / "gaul" / "countries"

    if not countries_root.exists():
        raise FileNotFoundError(
            f"Country GeoJSON directory does not exist: {countries_root}. "
            f"Run the country split step first."
        )

    if not nt_script_path.exists():
        raise FileNotFoundError(f"NT creation script not found: {nt_script_path}")

    if not parser_jar.exists():
        raise FileNotFoundError(
            f"Parser jar not found: {parser_jar}. "
            f"Set PARSER_JAR_PATH in topos-update.config or place parser.jar next to the tool."
        )

    LOG.info("Creating country GAUL NT files.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("Countries root: %s", countries_root)
    LOG.info("Parser jar: %s", parser_jar)

    for index, country in enumerate(countries, start=1):
        LOG.info("[%d/%d] Creating GAUL NT for country: %s", index, len(countries), country)

        subprocess.run(
            [
                "bash",
                str(nt_script_path),
                country,
                str(countries_root),
                str(parser_jar),
            ],
            check=True,
        )

    LOG.info("Country GAUL NT creation complete.")


def prepare_osm_data(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
    osm_script_path: Path,
) -> None:
    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    if not osm_script_path.exists():
        raise FileNotFoundError(f"OSM preparation script not found: {osm_script_path}")

    osm_countries_root = workdir / "osm" / "countries"
    osm_countries_root.mkdir(parents=True, exist_ok=True)

    LOG.info("Preparing OSM data from Geofabrik.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("OSM script: %s", osm_script_path)
    LOG.info("OSM countries output root: %s", osm_countries_root)

    for index, record in enumerate(country_records, start=1):
        country = record["country"]
        continent = record["geofabrik_cont"]

        if not continent:
            raise ValueError(
                f"Missing geofabrik_cont for country '{country}' in {countries_csv}"
            )

        LOG.info(
            "[%d/%d] Preparing OSM for country: %s, continent=%s",
            index,
            len(country_records),
            country,
            continent,
        )

        subprocess.run(
            [
                "bash",
                str(osm_script_path),
                continent,
                country,
            ],
            check=True,
            cwd=str(osm_countries_root),
        )

    LOG.info("OSM preparation complete.")


def create_osm_nt_files(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
    osm_nt_script_path: Path,
    fixer_script_path: Path,
) -> None:
    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    parser_jar = resolve_parser_jar(
        config=config,
        config_path=config_path,
    )

    osm_countries_root = workdir / "osm" / "countries"

    if not osm_countries_root.exists():
        raise FileNotFoundError(
            f"OSM countries directory does not exist: {osm_countries_root}. "
            f"Run the OSM preparation step first."
        )

    if not osm_nt_script_path.exists():
        raise FileNotFoundError(f"OSM NT creation script not found: {osm_nt_script_path}")

    if not parser_jar.exists():
        raise FileNotFoundError(
            f"Parser jar not found: {parser_jar}. "
            f"Set PARSER_JAR_PATH in topos-update.config or place parser.jar next to the tool."
        )

    if not fixer_script_path.exists():
        raise FileNotFoundError(
            f"fixer.py not found: {fixer_script_path}. "
            f"Place fixer.py next to the tool or pass --fixer-script."
        )

    LOG.info("Creating OSM NT files.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("OSM countries root: %s", osm_countries_root)
    LOG.info("Parser jar: %s", parser_jar)
    LOG.info("Fixer script: %s", fixer_script_path)

    for index, record in enumerate(country_records, start=1):
        country = record["country"]
        prefix = record["code"] or safe_name(country).lower()

        LOG.info(
            "[%d/%d] Creating OSM NT for country: %s, prefix=%s",
            index,
            len(country_records),
            country,
            prefix,
        )

        subprocess.run(
            [
                "bash",
                str(osm_nt_script_path),
                country,
                prefix,
                str(osm_countries_root),
                str(parser_jar),
                str(fixer_script_path),
            ],
            check=True,
        )

    LOG.info("OSM NT creation complete.")




def resolve_linking_dir(config: dict[str, str], config_path: Path) -> Path:
    """
    Resolve LINKING_DIR_PATH.

    If LINKING_DIR_PATH is empty, default to:
      <directory of this Python tool>/linking_dir
    """

    default_linking_dir = Path(__file__).resolve().parent / "linking_dir"

    return resolve_config_path(
        value=config.get("LINKING_DIR_PATH", ""),
        default_path=default_linking_dir,
        config_path=config_path,
    )


def normalize_spaces_to_underscores(path: Path) -> None:
    """
    Normalize spaces to underscores inside a copied *_osm_levels.csv file.
    """

    content = path.read_text(encoding="utf-8")
    normalized = content.replace(" ", "_")

    if normalized != content:
        path.write_text(normalized, encoding="utf-8")


def find_linking_country_dir(linking_dir: Path, country: str) -> Path | None:
    """
    Find the source directory for a country inside LINKING_DIR_PATH.

    Preferred source:
      LINKING_DIR_PATH/<country>

    Fallbacks support already-normalized country directory names.
    """

    candidates = [
        linking_dir / country,
        linking_dir / safe_name(country),
        linking_dir / country.replace(" ", "_"),
        linking_dir / country.replace(" ", "-"),
        linking_dir / country.lower(),
        linking_dir / safe_name(country).lower(),
        linking_dir / country.replace(" ", "_").lower(),
        linking_dir / country.replace(" ", "-").lower(),
    ]

    seen: set[Path] = set()

    for candidate in candidates:
        if candidate in seen:
            continue

        seen.add(candidate)

        if candidate.is_dir():
            return candidate

    return None


def copy_linking_metadata(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
) -> None:
    """
    Copy per-country linking metadata into:
      <workdir>/osm/countries/<country>/

    Source directory:
      LINKING_DIR_PATH/<country>/

    If LINKING_DIR_PATH is empty, the default is:
      <tool_dir>/linking_dir/

    Special handling:
      Every copied file whose name ends with '_osm_levels.csv' is normalized
      by replacing spaces with underscores.
    """

    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    linking_dir = resolve_linking_dir(config, config_path)
    osm_countries_root = workdir / "osm" / "countries"

    if not linking_dir.exists():
        raise FileNotFoundError(
            f"LINKING_DIR_PATH does not exist: {linking_dir}. "
            f"Set LINKING_DIR_PATH in topos-update.config or place linking_dir next to the tool."
        )

    if not osm_countries_root.exists():
        raise FileNotFoundError(
            f"OSM countries directory does not exist: {osm_countries_root}. "
            f"Run the OSM preparation step first."
        )

    LOG.info("Copying linking metadata into OSM country directories.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("Linking metadata root: %s", linking_dir)
    LOG.info("OSM countries root: %s", osm_countries_root)

    for index, record in enumerate(country_records, start=1):
        country = record["country"]

        source_country_dir = find_linking_country_dir(linking_dir, country)
        target_country_dir = osm_countries_root / country

        if source_country_dir is None:
            LOG.warning(
                "[%d/%d] Linking metadata directory not found for country '%s'. Skipping.",
                index,
                len(country_records),
                country,
            )
            continue

        if not target_country_dir.exists():
            LOG.warning(
                "[%d/%d] OSM country directory not found for country '%s': %s. Skipping.",
                index,
                len(country_records),
                country,
                target_country_dir,
            )
            continue

        LOG.info(
            "[%d/%d] Copying linking metadata for country: %s",
            index,
            len(country_records),
            country,
        )
        LOG.info("Source: %s", source_country_dir)
        LOG.info("Target: %s", target_country_dir)

        for source_path in source_country_dir.iterdir():
            target_path = target_country_dir / source_path.name

            if source_path.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)

                shutil.copytree(source_path, target_path)

            elif source_path.is_file():
                shutil.copy2(source_path, target_path)

                if target_path.name.endswith("_osm_levels.csv"):
                    LOG.info("Normalizing spaces to underscores in: %s", target_path)
                    normalize_spaces_to_underscores(target_path)

        LOG.info("Finished copying linking metadata for: %s", country)

    LOG.info("Linking metadata copy complete.")


def discover_osm_boundaries(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
    boundary_script_path: Path,
) -> None:
    countries_csv = countries_csv_from_config(config, config_path)
    osm_countries_root = workdir / "osm" / "countries"

    wikidata_upper_path = resolve_required_config_path(
        config=config,
        key="WIKIDATA_UPPER_PATH",
        config_path=config_path,
    )

    parser_jar = resolve_parser_jar(
        config=config,
        config_path=config_path,
    )

    if not countries_csv.exists():
        raise FileNotFoundError(f"Countries CSV not found: {countries_csv}")

    if not osm_countries_root.exists():
        raise FileNotFoundError(
            f"OSM countries directory does not exist: {osm_countries_root}. "
            f"Run OSM preparation and OSM NT creation first."
        )

    if not wikidata_upper_path.exists():
        raise FileNotFoundError(f"Wikidata hierarchy file not found: {wikidata_upper_path}")

    if not parser_jar.exists():
        raise FileNotFoundError(
            f"Parser jar not found: {parser_jar}. "
            f"Set PARSER_JAR_PATH in topos-update.config or place parser.jar next to the tool."
        )

    if not boundary_script_path.exists():
        raise FileNotFoundError(f"OSM boundary discovery script not found: {boundary_script_path}")

    LOG.info("Running OSM boundary discovery.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("OSM countries root: %s", osm_countries_root)
    LOG.info("Wikidata hierarchy: %s", wikidata_upper_path)
    LOG.info("Parser jar: %s", parser_jar)
    LOG.info("Boundary discovery script: %s", boundary_script_path)

    subprocess.run(
        [
            "bash",
            str(boundary_script_path),
            str(countries_csv),
            str(osm_countries_root),
            str(wikidata_upper_path),
            str(parser_jar),
        ],
        check=True,
    )

    LOG.info("OSM boundary discovery complete.")






def promote_new_linking_admin_files(country_dir: Path) -> None:
    """
    After parser relinking, replace old linking_admin files with the new ones.

    Example:
      linking_admin_0.csv      -> removed
      linking_admin_0_new.csv  -> linking_admin_0.csv

    This is done for every file matching:
      linking_admin_*_new.csv
    """

    new_files = sorted(country_dir.glob("linking_admin_*_new.csv"))

    if not new_files:
        LOG.warning("No new linking_admin files found in: %s", country_dir)
        return

    for new_path in new_files:
        old_name = new_path.name.replace("_new.csv", ".csv")
        old_path = country_dir / old_name

        if old_path.exists():
            LOG.info("Removing old linking file: %s", old_path)
            old_path.unlink()

        LOG.info("Renaming %s -> %s", new_path.name, old_name)
        new_path.rename(old_path)


def relink_osm_data(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
) -> None:
    """
    Relink OSM data using the parser's relink command.

    For each country in COUNTRIES_CSV, run:

      java -jar parser.jar relink \
        <workdir>/osm/countries/<country> \
        <workdir>/osm/countries/<country>/<country_lower>_final.nt \
        <workdir>/osm/countries/<country>

    The parser jar path comes from PARSER_JAR_PATH, or defaults to parser.jar
    next to this tool.
    """

    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    parser_jar = resolve_parser_jar(
        config=config,
        config_path=config_path,
    )

    osm_countries_root = workdir / "osm" / "countries"

    if not parser_jar.exists():
        raise FileNotFoundError(
            f"Parser jar not found: {parser_jar}. "
            f"Set PARSER_JAR_PATH in topos-update.config or place parser.jar next to the tool."
        )

    if not osm_countries_root.exists():
        raise FileNotFoundError(
            f"OSM countries directory does not exist: {osm_countries_root}. "
            f"Run the OSM pipeline first."
        )

    LOG.info("Relinking OSM data.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("OSM countries root: %s", osm_countries_root)
    LOG.info("Parser jar: %s", parser_jar)

    for index, record in enumerate(country_records, start=1):
        country = record["country"]
        country_lower = country.lower()

        country_dir = osm_countries_root / country
        country_final_nt = country_dir / f"{country_lower}_final.nt"

        if not country_dir.exists():
            LOG.warning(
                "[%d/%d] OSM country directory not found for country '%s': %s. Skipping.",
                index,
                len(country_records),
                country,
                country_dir,
            )
            continue

        if not country_final_nt.exists():
            LOG.warning(
                "[%d/%d] Final OSM NT file not found for country '%s': %s. Skipping.",
                index,
                len(country_records),
                country,
                country_final_nt,
            )
            continue

        LOG.info(
            "[%d/%d] Relinking OSM data for country: %s",
            index,
            len(country_records),
            country,
        )

        subprocess.run(
            [
                "java",
                "-jar",
                str(parser_jar),
                "relink",
                str(country_dir),
                str(country_final_nt),
                str(country_dir),
            ],
            check=True,
        )

        promote_new_linking_admin_files(country_dir)

    LOG.info("OSM relinking complete.")




def connect_gaul_osm(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
) -> None:
    """
    Connect GAUL and OSM outputs using the parser's connection command.

    Runs:

      java -jar parser.jar connection \
        <workdir>/osm/countries \
        <workdir>/gaul/countries

    The parser jar path comes from PARSER_JAR_PATH, or defaults to parser.jar
    next to this tool.
    """

    parser_jar = resolve_parser_jar(
        config=config,
        config_path=config_path,
    )

    osm_countries_root = workdir / "osm" / "countries"
    gaul_countries_root = workdir / "gaul" / "countries"

    if not parser_jar.exists():
        raise FileNotFoundError(
            f"Parser jar not found: {parser_jar}. "
            f"Set PARSER_JAR_PATH in topos-update.config or place parser.jar next to the tool."
        )

    if not osm_countries_root.exists():
        raise FileNotFoundError(
            f"OSM countries directory does not exist: {osm_countries_root}. "
            f"Run the OSM pipeline first."
        )

    if not gaul_countries_root.exists():
        raise FileNotFoundError(
            f"GAUL countries directory does not exist: {gaul_countries_root}. "
            f"Run the GAUL pipeline first."
        )

    LOG.info("Connecting GAUL and OSM data.")
    LOG.info("Parser jar: %s", parser_jar)
    LOG.info("OSM countries root: %s", osm_countries_root)
    LOG.info("GAUL countries root: %s", gaul_countries_root)

    # The parser's connection command concatenates the root path with
    # country directory names internally, so both root paths must end with "/".
    osm_countries_root_arg = str(osm_countries_root) + "/"
    gaul_countries_root_arg = str(gaul_countries_root) + "/"

    subprocess.run(
        [
            "java",
            "-jar",
            str(parser_jar),
            "connection",
            osm_countries_root_arg,
            gaul_countries_root_arg,
        ],
        check=True,
    )

    LOG.info("GAUL/OSM connection complete.")




def prepare_osm_non_admin_data(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
    osm_non_admin_script_path: Path,
) -> None:
    """
    Download and group non-admin OSM data per country.

    This runs the non-admin OSM shell script once per country with cwd set to:

      <workdir>/osm/countries

    Therefore outputs are written under:

      <workdir>/osm/countries/<country>/

    Expected GeoJSON outputs per country:
      <country_lower>_water.geojson
      <country_lower>_forest.geojson
      <country_lower>_poi.geojson
    """

    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    if not osm_non_admin_script_path.exists():
        raise FileNotFoundError(
            f"Non-admin OSM preparation script not found: {osm_non_admin_script_path}"
        )

    osm_countries_root = workdir / "osm" / "countries"
    osm_countries_root.mkdir(parents=True, exist_ok=True)

    LOG.info("Preparing non-admin OSM data.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("Non-admin OSM script: %s", osm_non_admin_script_path)
    LOG.info("OSM countries root: %s", osm_countries_root)

    for index, record in enumerate(country_records, start=1):
        country = record["country"]
        continent = record["geofabrik_cont"]

        if not continent:
            raise ValueError(
                f"Missing geofabrik_cont for country '{country}' in {countries_csv}"
            )

        LOG.info(
            "[%d/%d] Preparing non-admin OSM data for country: %s, continent=%s",
            index,
            len(country_records),
            country,
            continent,
        )

        subprocess.run(
            [
                "bash",
                str(osm_non_admin_script_path),
                continent,
                country,
            ],
            check=True,
            cwd=str(osm_countries_root),
        )

    LOG.info("Non-admin OSM preparation complete.")


def create_osm_non_admin_nt_files(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
) -> None:
    """
    Convert non-admin OSM GeoJSON files to NT.

    For each country, run:

      java -jar parser.jar water <country_lower>_water.geojson  <country_lower>_water.nt  <code>
      java -jar parser.jar water <country_lower>_forest.geojson <country_lower>_forest.nt <code>
      java -jar parser.jar water <country_lower>_poi.geojson    <country_lower>_poi.nt    <code>

    The command name is intentionally 'water' for all three categories, matching
    the existing parser interface requested by the pipeline.
    """

    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    parser_jar = resolve_parser_jar(
        config=config,
        config_path=config_path,
    )

    osm_countries_root = workdir / "osm" / "countries"

    if not parser_jar.exists():
        raise FileNotFoundError(
            f"Parser jar not found: {parser_jar}. "
            f"Set PARSER_JAR_PATH in topos-update.config or place parser.jar next to the tool."
        )

    if not osm_countries_root.exists():
        raise FileNotFoundError(
            f"OSM countries directory does not exist: {osm_countries_root}. "
            f"Run OSM preparation first."
        )

    LOG.info("Creating non-admin OSM NT files.")
    LOG.info("Countries CSV: %s", countries_csv)
    LOG.info("OSM countries root: %s", osm_countries_root)
    LOG.info("Parser jar: %s", parser_jar)

    categories = ["water", "forest", "poi"]

    for index, record in enumerate(country_records, start=1):
        country = record["country"]
        code = record["code"]
        country_lower = country.lower()
        country_dir = osm_countries_root / country

        if not code:
            raise ValueError(f"Missing code for country '{country}' in {countries_csv}")

        if not country_dir.exists():
            LOG.warning(
                "[%d/%d] OSM country directory not found for country '%s': %s. Skipping.",
                index,
                len(country_records),
                country,
                country_dir,
            )
            continue

        LOG.info(
            "[%d/%d] Creating non-admin OSM NT files for country: %s, code=%s",
            index,
            len(country_records),
            country,
            code,
        )

        for category in categories:
            input_geojson = country_dir / f"{country_lower}_{category}.geojson"
            output_nt = country_dir / f"{country_lower}_{category}.nt"

            if not input_geojson.exists():
                LOG.warning(
                    "Input GeoJSON not found for country '%s', category '%s': %s. Skipping.",
                    country,
                    category,
                    input_geojson,
                )
                continue

            subprocess.run(
                [
                    "java",
                    "-jar",
                    str(parser_jar),
                    "water",
                    str(input_geojson),
                    str(output_nt),
                    code,
                ],
                check=True,
            )

    LOG.info("Non-admin OSM NT creation complete.")




def country_name_variants(country: str) -> list[str]:
    """
    Return filename variants that may exist because earlier stages use either
    the CSV country name, lowercase country name, or safe filesystem name.
    """

    variants = [
        country,
        country.lower(),
        safe_name(country),
        safe_name(country).lower(),
    ]

    deduped = []

    for value in variants:
        if value not in deduped:
            deduped.append(value)

    return deduped


def should_keep_final_country_file(file_name: str, country: str) -> bool:
    """
    Decide whether a file should survive the final cleanup.

    Keep:
      <Country>_all.nt
      <Country>_0.nt
      <Country>_1.nt
      <Country>_2.nt
      ...

    Also keep lowercase/safe-name variants produced by earlier stages.
    """

    for variant in country_name_variants(country):
        if file_name == f"{variant}_all.nt":
            return True

        prefix = f"{variant}_"
        suffix = ".nt"

        if file_name.startswith(prefix) and file_name.endswith(suffix):
            level = file_name[len(prefix):-len(suffix)]

            if level.isdigit():
                return True

    return False


def remove_all_except_final_country_files(country_dir: Path, country: str) -> None:
    """
    Remove every file/directory in country_dir except final country NT files:

      <Country>_all.nt
      <Country>_<admin_level>.nt

    where <admin_level> is numeric, for example 0, 1, 2, 3, ...
    """

    if not country_dir.exists():
        return

    for path in country_dir.iterdir():
        if path.is_file() and should_keep_final_country_file(path.name, country):
            continue

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def find_existing_country_dir(root: Path, country: str) -> Path | None:
    """
    Find a country directory under root. Prefer exact country name, but fall
    back to safe/lowercase variants.
    """

    candidates = [
        root / country,
        root / safe_name(country),
        root / country.lower(),
        root / safe_name(country).lower(),
    ]

    seen: set[Path] = set()

    for candidate in candidates:
        if candidate in seen:
            continue

        seen.add(candidate)

        if candidate.is_dir():
            return candidate

    return None


def move_osm_category_nt(
    country: str,
    country_dir: Path,
    osm_root: Path,
    category: str,
    target_group_dir_name: str,
) -> None:
    """
    Move one non-admin OSM category NT file into its grouped directory.

    Example:
      data/osm/countries/Greece/greece_poi.nt
        -> data/osm/pois/Greece/Greece.nt
    """

    source_candidates = []

    for variant in country_name_variants(country):
        source_candidates.append(country_dir / f"{variant}_{category}.nt")

    source_path = None

    for candidate in source_candidates:
        if candidate.exists():
            source_path = candidate
            break

    if source_path is None:
        LOG.warning(
            "No %s NT file found for country '%s' in %s",
            category,
            country,
            country_dir,
        )
        return

    target_dir = osm_root / target_group_dir_name / country
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / f"{country}.nt"

    if target_path.exists():
        LOG.info("Removing existing grouped file: %s", target_path)
        target_path.unlink()

    LOG.info("Moving %s -> %s", source_path, target_path)
    shutil.move(str(source_path), str(target_path))


def cleanup_outputs(
    config: dict[str, str],
    config_path: Path,
    workdir: Path,
) -> None:
    """
    Final destructive cleanup/grouping stage.

    GAUL:
      - remove <workdir>/gaul/extracted
      - remove <workdir>/gaul/geojson
      - remove <workdir>/gaul/raw
      - inside each country dir, keep only <Country>_x.nt and <Country>_all.nt

    OSM:
      - move each country *_poi.nt to <workdir>/osm/pois/<Country>/<Country>.nt
      - move each country *_water.nt to <workdir>/osm/water/<Country>/<Country>.nt
      - move each country *_forest.nt to <workdir>/osm/forests/<Country>/<Country>.nt
      - inside each country dir, keep only <Country>_x.nt and <Country>_all.nt
    """

    countries_csv = countries_csv_from_config(config, config_path)
    country_records = read_country_records(countries_csv)

    gaul_root = workdir / "gaul"
    gaul_countries_root = gaul_root / "countries"

    osm_root = workdir / "osm"
    osm_countries_root = osm_root / "countries"

    LOG.info("Starting final cleanup/grouping stage.")

    # GAUL cleanup of intermediate directories.
    for dir_name in ["extracted", "geojson", "raw"]:
        path = gaul_root / dir_name

        if path.exists():
            LOG.info("Removing GAUL intermediate directory: %s", path)
            shutil.rmtree(path)

    # GAUL country cleanup.
    if gaul_countries_root.exists():
        for record in country_records:
            country = record["country"]
            country_dir = find_existing_country_dir(gaul_countries_root, country)

            if country_dir is None:
                LOG.warning("GAUL country directory not found for cleanup: %s", country)
                continue

            LOG.info("Cleaning GAUL country directory: %s", country_dir)
            LOG.info("Keeping only: %s_all.nt and %s_<numeric_admin_level>.nt", country, country)
            remove_all_except_final_country_files(country_dir, country)
    else:
        LOG.warning("GAUL countries directory not found during cleanup: %s", gaul_countries_root)

    # OSM category grouping and country cleanup.
    if osm_countries_root.exists():
        for record in country_records:
            country = record["country"]
            country_dir = find_existing_country_dir(osm_countries_root, country)

            if country_dir is None:
                LOG.warning("OSM country directory not found for cleanup: %s", country)
                continue

            move_osm_category_nt(
                country=country,
                country_dir=country_dir,
                osm_root=osm_root,
                category="poi",
                target_group_dir_name="pois",
            )

            move_osm_category_nt(
                country=country,
                country_dir=country_dir,
                osm_root=osm_root,
                category="water",
                target_group_dir_name="water",
            )

            move_osm_category_nt(
                country=country,
                country_dir=country_dir,
                osm_root=osm_root,
                category="forest",
                target_group_dir_name="forests",
            )

            LOG.info("Cleaning OSM country directory: %s", country_dir)
            LOG.info("Keeping only: %s_all.nt and %s_<numeric_admin_level>.nt", country, country)
            remove_all_except_final_country_files(country_dir, country)
    else:
        LOG.warning("OSM countries directory not found during cleanup: %s", osm_countries_root)

    LOG.info("Final cleanup/grouping stage complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Topos KG update tool."
    )

    parser.add_argument(
        "--config",
        default="topos-update.config",
        help="Path to the Topos update config file.",
    )

    parser.add_argument(
        "--workdir",
        default="data",
        help="Working directory where generated files will be stored.",
    )

    parser.add_argument(
        "--split-script",
        default="split_gaul_country.sh",
        help="Path to the country-level GAUL splitting shell script.",
    )

    parser.add_argument(
        "--nt-script",
        default="create_country_nt.sh",
        help="Path to the shell script that creates GAUL NT files for one country.",
    )

    parser.add_argument(
        "--osm-script",
        default="prepare_osm_country.sh",
        help="Path to the shell script that downloads and prepares OSM data for one country.",
    )

    parser.add_argument(
        "--osm-nt-script",
        default="create_osm_country_nt.sh",
        help="Path to the shell script that creates OSM NT files for one country.",
    )

    parser.add_argument(
        "--osm-boundary-script",
        default="discover_osm_boundaries.sh",
        help="Path to the shell script that discovers OSM admin boundaries.",
    )

    parser.add_argument(
        "--osm-non-admin-script",
        default="prepare_osm_non_admin_country.sh",
        help="Path to the shell script that downloads and prepares non-admin OSM data for one country.",
    )

    parser.add_argument(
        "--fixer-script",
        default="fixer.py",
        help="Path to fixer.py used after OSM NT creation.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload, re-extract, and reconvert existing GAUL files.",
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip GAUL download/unzip/shapefile conversion step.",
    )

    parser.add_argument(
        "--skip-country-split",
        action="store_true",
        help="Skip country-level GAUL GeoJSON creation step.",
    )

    parser.add_argument(
        "--skip-nt-creation",
        action="store_true",
        help="Skip country-level GAUL NT creation step.",
    )

    parser.add_argument(
        "--skip-osm",
        action="store_true",
        help="Skip OSM/Geofabrik download and GeoJSON creation step.",
    )

    parser.add_argument(
        "--skip-osm-nt-creation",
        action="store_true",
        help="Skip country-level OSM NT creation step.",
    )

    parser.add_argument(
        "--skip-linking-metadata",
        action="store_true",
        help="Skip copying linking metadata into OSM country directories.",
    )

    parser.add_argument(
        "--skip-osm-boundary-discovery",
        action="store_true",
        help="Skip OSM boundary discovery/materialization step.",
    )

    parser.add_argument(
        "--skip-osm-relink",
        action="store_true",
        help="Skip OSM relinking step.",
    )

    parser.add_argument(
        "--skip-gaul-osm-connection",
        action="store_true",
        help="Skip final GAUL/OSM connection step.",
    )

    parser.add_argument(
        "--skip-osm-non-admin",
        action="store_true",
        help="Skip non-admin OSM download and GeoJSON grouping step.",
    )

    parser.add_argument(
        "--skip-osm-non-admin-nt-creation",
        action="store_true",
        help="Skip non-admin OSM NT creation step.",
    )

    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip final cleanup/grouping stage.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    script_dir = Path(__file__).resolve().parent

    config_path = Path(args.config).resolve()
    workdir = Path(args.workdir).resolve()

    split_script_path = resolve_tool_path(args.split_script, script_dir)
    nt_script_path = resolve_tool_path(args.nt_script, script_dir)
    osm_script_path = resolve_tool_path(args.osm_script, script_dir)
    osm_nt_script_path = resolve_tool_path(args.osm_nt_script, script_dir)
    osm_boundary_script_path = resolve_tool_path(args.osm_boundary_script, script_dir)
    osm_non_admin_script_path = resolve_tool_path(args.osm_non_admin_script, script_dir)
    fixer_script_path = resolve_tool_path(args.fixer_script, script_dir)

    config = read_config(config_path)

    if not args.skip_download:
        prepare_gaul(
            config=config,
            workdir=workdir,
            force=args.force,
        )

    if not args.skip_country_split:
        split_gaul_by_country(
            config=config,
            config_path=config_path,
            workdir=workdir,
            split_script_path=split_script_path,
        )

    if not args.skip_nt_creation:
        create_country_nt_files(
            config=config,
            config_path=config_path,
            workdir=workdir,
            nt_script_path=nt_script_path,
        )

    if not args.skip_osm:
        prepare_osm_data(
            config=config,
            config_path=config_path,
            workdir=workdir,
            osm_script_path=osm_script_path,
        )

    if not args.skip_osm_nt_creation:
        create_osm_nt_files(
            config=config,
            config_path=config_path,
            workdir=workdir,
            osm_nt_script_path=osm_nt_script_path,
            fixer_script_path=fixer_script_path,
        )

    if not args.skip_linking_metadata:
        copy_linking_metadata(
            config=config,
            config_path=config_path,
            workdir=workdir,
        )

    if not args.skip_osm_boundary_discovery:
        discover_osm_boundaries(
            config=config,
            config_path=config_path,
            workdir=workdir,
            boundary_script_path=osm_boundary_script_path,
        )

    if not args.skip_osm_relink:
        relink_osm_data(
            config=config,
            config_path=config_path,
            workdir=workdir,
        )

    if not args.skip_gaul_osm_connection:
        connect_gaul_osm(
            config=config,
            config_path=config_path,
            workdir=workdir,
        )

    if not args.skip_osm_non_admin:
        prepare_osm_non_admin_data(
            config=config,
            config_path=config_path,
            workdir=workdir,
            osm_non_admin_script_path=osm_non_admin_script_path,
        )

    if not args.skip_osm_non_admin_nt_creation:
        create_osm_non_admin_nt_files(
            config=config,
            config_path=config_path,
            workdir=workdir,
        )

    if not args.skip_cleanup:
        cleanup_outputs(
            config=config,
            config_path=config_path,
            workdir=workdir,
        )


if __name__ == "__main__":
    main()
