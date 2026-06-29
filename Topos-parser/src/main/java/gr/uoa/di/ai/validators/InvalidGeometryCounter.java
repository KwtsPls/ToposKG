package gr.uoa.di.ai.validators;

import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.io.ParseException;
import org.locationtech.jts.io.WKTReader;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class InvalidGeometryCounter {

    private static final Pattern CRS_PREFIX = Pattern.compile("^<[^>]+>\\s*");
    private static final Pattern SRID_PREFIX = Pattern.compile("(?i)^SRID=\\d+;\\s*");

    private static final Pattern GEOMETRY_TYPE_PATTERN = Pattern.compile(
            "(?i)^(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\\b"
    );

    private static final String GEOSPARQL_AS_WKT =
            "http://www.opengis.net/ont/geosparql#asWKT";

    private static final String GEOSPARQL_WKT_LITERAL =
            "http://www.opengis.net/ont/geosparql#wktLiteral";

    private InvalidGeometryCounter() {
        // Utility class.
    }

    public static void countInvalidGeometries(
            Path inputDir,
            int mode,
            Path perCountryCsv,
            Path totalCsv
    ) throws IOException {

        validateInput(inputDir, mode);

        List<CountryResult> results = evaluate(inputDir, mode);

        writePerCountryCsv(results, perCountryCsv);
        writeTotalCsv(results, totalCsv);
    }

    public static List<CountryResult> evaluate(Path inputDir, int mode) throws IOException {
        validateInput(inputDir, mode);

        List<CountryResult> results = new ArrayList<>();

        try (var dirs = Files.list(inputDir)) {
            List<Path> countryDirs = dirs
                    .filter(Files::isDirectory)
                    .sorted(Comparator.comparing(p -> p.getFileName().toString()))
                    .toList();

            for (Path countryDir : countryDirs) {
                String country = countryDir.getFileName().toString();

                Path ntFile = getExpectedFile(countryDir, country, mode);

                if (!Files.exists(ntFile)) {
                    System.err.println("[WARN] Missing expected file for country "
                            + country + ": " + ntFile);
                    continue;
                }

                CountryResult result = evaluateCountryFile(country, ntFile);
                results.add(result);
            }
        }

        return results;
    }

    private static void validateInput(Path inputDir, int mode) {
        if (!Files.isDirectory(inputDir)) {
            throw new IllegalArgumentException(
                    "Input directory does not exist or is not a directory: " + inputDir
            );
        }

        if (mode != 1 && mode != 2) {
            throw new IllegalArgumentException(
                    "Mode must be 1 or 2. Mode 1 checks Country_all.nt. Mode 2 checks Country.nt."
            );
        }
    }

    private static Path getExpectedFile(Path countryDir, String country, int mode) {
        if (mode == 1) {
            return countryDir.resolve(country + "_all.nt");
        }

        return countryDir.resolve(country + ".nt");
    }

    private static CountryResult evaluateCountryFile(String country, Path ntFile) throws IOException {
        CountryResult result = new CountryResult(country);
        WKTReader reader = new WKTReader();

        long lineNumber = 0;

        try (BufferedReader br = Files.newBufferedReader(ntFile, StandardCharsets.UTF_8)) {
            String line;

            while ((line = br.readLine()) != null) {
                lineNumber++;

                if (!isPotentialWktTriple(line)) {
                    continue;
                }

                String literal = extractFirstLiteral(line);
                if (literal == null) {
                    continue;
                }

                literal = literal.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                        .replace("\"", "");
                String wkt = normalizeWktLiteral(literal);
                if (wkt.isBlank()) {
                    continue;
                }

                String inferredType = inferGeometryType(wkt);

                try {
                    Geometry geometry = reader.read(wkt);

                    String geometryType = geometry.getGeometryType();
                    boolean invalid = !geometry.isValid();

                    result.getCounts(geometryType).addParsed(invalid);

                } catch (ParseException | IllegalArgumentException e) {
                    result.getCounts(inferredType).addParseError();

                    System.err.println(
                            "[WARN] Could not parse WKT in "
                                    + ntFile
                                    + " at line "
                                    + lineNumber
                                    + " inferredType="
                                    + inferredType
                    );
                }
            }
        }

        return result;
    }

    private static boolean isPotentialWktTriple(String line) {
        return line.contains(GEOSPARQL_AS_WKT)
                || line.contains(GEOSPARQL_WKT_LITERAL)
                || line.contains("asWKT")
                || line.contains("wktLiteral");
    }

    private static String extractFirstLiteral(String line) {
        int start = line.indexOf('"');
        if (start < 0) {
            return null;
        }

        StringBuilder literal = new StringBuilder();
        boolean escaped = false;

        for (int i = start + 1; i < line.length(); i++) {
            char c = line.charAt(i);

            if (escaped) {
                literal.append(unescapeChar(c));
                escaped = false;
                continue;
            }

            if (c == '\\') {
                escaped = true;
                continue;
            }

            if (c == '"') {
                return literal.toString();
            }

            literal.append(c);
        }

        return null;
    }

    private static char unescapeChar(char c) {
        return switch (c) {
            case 't' -> '\t';
            case 'b' -> '\b';
            case 'n' -> '\n';
            case 'r' -> '\r';
            case 'f' -> '\f';
            case '"' -> '"';
            case '\'' -> '\'';
            case '\\' -> '\\';
            default -> c;
        };
    }

    private static String normalizeWktLiteral(String literal) {
        String wkt = literal.trim();

        // GeoSPARQL WKT literals may begin with a CRS URI:
        // <http://www.opengis.net/def/crs/EPSG/0/4326> POLYGON(...)
        wkt = CRS_PREFIX.matcher(wkt).replaceFirst("");

        // Also support common non-GeoSPARQL form:
        // SRID=4326;POLYGON(...)
        wkt = SRID_PREFIX.matcher(wkt).replaceFirst("");

        return wkt.trim();
    }

    private static String inferGeometryType(String wkt) {
        Matcher matcher = GEOMETRY_TYPE_PATTERN.matcher(wkt.trim());

        if (matcher.find()) {
            return matcher.group(1).toUpperCase();
        }

        return "UNKNOWN";
    }

    public static void writePerCountryCsv(
            List<CountryResult> results,
            Path out
    ) throws IOException {

        try (BufferedWriter writer = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
            writer.write("country,geometry_type,invalid_geometry_count,parsed_geometry_count,parse_error_count");
            writer.newLine();

            for (CountryResult result : results) {
                List<String> geometryTypes = result.countsByGeometryType.keySet()
                        .stream()
                        .sorted()
                        .toList();

                for (String geometryType : geometryTypes) {
                    Counts counts = result.countsByGeometryType.get(geometryType);

                    writer.write(csv(result.country));
                    writer.write(",");
                    writer.write(csv(geometryType));
                    writer.write(",");
                    writer.write(Long.toString(counts.invalidGeometryCount));
                    writer.write(",");
                    writer.write(Long.toString(counts.parsedGeometryCount));
                    writer.write(",");
                    writer.write(Long.toString(counts.parseErrorCount));
                    writer.newLine();
                }

                Counts all = sumCounts(result.countsByGeometryType);

                writer.write(csv(result.country));
                writer.write(",");
                writer.write("ALL_TYPES");
                writer.write(",");
                writer.write(Long.toString(all.invalidGeometryCount));
                writer.write(",");
                writer.write(Long.toString(all.parsedGeometryCount));
                writer.write(",");
                writer.write(Long.toString(all.parseErrorCount));
                writer.newLine();
            }
        }
    }

    public static void writeTotalCsv(
            List<CountryResult> results,
            Path out
    ) throws IOException {

        Map<String, Counts> totals = new HashMap<>();

        for (CountryResult result : results) {
            for (Map.Entry<String, Counts> entry : result.countsByGeometryType.entrySet()) {
                String geometryType = entry.getKey();
                Counts counts = entry.getValue();

                totals.computeIfAbsent(geometryType, k -> new Counts()).add(counts);
            }
        }

        Counts all = sumCounts(totals);

        try (BufferedWriter writer = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
            writer.write("geometry_type,invalid_geometry_count,parsed_geometry_count,parse_error_count");
            writer.newLine();

            List<String> geometryTypes = totals.keySet()
                    .stream()
                    .sorted()
                    .toList();

            for (String geometryType : geometryTypes) {
                Counts counts = totals.get(geometryType);

                writer.write(csv(geometryType));
                writer.write(",");
                writer.write(Long.toString(counts.invalidGeometryCount));
                writer.write(",");
                writer.write(Long.toString(counts.parsedGeometryCount));
                writer.write(",");
                writer.write(Long.toString(counts.parseErrorCount));
                writer.newLine();
            }

            writer.write("ALL_TYPES");
            writer.write(",");
            writer.write(Long.toString(all.invalidGeometryCount));
            writer.write(",");
            writer.write(Long.toString(all.parsedGeometryCount));
            writer.write(",");
            writer.write(Long.toString(all.parseErrorCount));
            writer.newLine();
        }
    }

    private static Counts sumCounts(Map<String, Counts> countsByType) {
        Counts all = new Counts();

        for (Counts counts : countsByType.values()) {
            all.add(counts);
        }

        return all;
    }

    private static String csv(String value) {
        if (value == null) {
            return "";
        }

        boolean needsQuotes = value.contains(",")
                || value.contains("\"")
                || value.contains("\n")
                || value.contains("\r");

        if (!needsQuotes) {
            return value;
        }

        return "\"" + value.replace("\"", "\"\"") + "\"";
    }

    public static final class CountryResult {
        private final String country;
        private final Map<String, Counts> countsByGeometryType = new HashMap<>();

        private CountryResult(String country) {
            this.country = country;
        }

        private Counts getCounts(String geometryType) {
            return countsByGeometryType.computeIfAbsent(geometryType, k -> new Counts());
        }

        public String getCountry() {
            return country;
        }

        public Map<String, Counts> getCountsByGeometryType() {
            return countsByGeometryType;
        }
    }

    public static final class Counts {
        private long parsedGeometryCount = 0;
        private long invalidGeometryCount = 0;
        private long parseErrorCount = 0;

        private void addParsed(boolean invalid) {
            parsedGeometryCount++;

            if (invalid) {
                invalidGeometryCount++;
            }
        }

        private void addParseError() {
            parseErrorCount++;
        }

        private void add(Counts other) {
            this.parsedGeometryCount += other.parsedGeometryCount;
            this.invalidGeometryCount += other.invalidGeometryCount;
            this.parseErrorCount += other.parseErrorCount;
        }

        public long getParsedGeometryCount() {
            return parsedGeometryCount;
        }

        public long getInvalidGeometryCount() {
            return invalidGeometryCount;
        }

        public long getParseErrorCount() {
            return parseErrorCount;
        }
    }
}