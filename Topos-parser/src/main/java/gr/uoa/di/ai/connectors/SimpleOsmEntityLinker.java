package gr.uoa.di.ai.connectors;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class SimpleOsmEntityLinker {

    private static final Pattern INTEGER_PATTERN = Pattern.compile("-?\\d+");

    private static final Set<String> ADMIN_STOPWORDS = Set.of(
            "the", "of", "and",
            "region", "regional", "unit", "municipality", "municipal",
            "province", "prefecture", "district", "department", "county",
            "state", "administration", "administrative", "decentralized",
            "city", "community", "commune", "oblast", "raion", "governorate"
    );

    private final Config config;

    public SimpleOsmEntityLinker() {
        this(new Config());
    }

    public SimpleOsmEntityLinker(Config config) {
        this.config = Objects.requireNonNull(config);
    }

    /**
     * Relinks one country directory.
     *
     * @param countryLinkingDir directory containing *_osm_levels.csv and linking_admin_0/1/2.csv
     * @param osmNtFile newly generated OSM .nt file for that country
     * @param outputDir directory where new linking_admin_*_new.csv files will be written
     */
    public RelinkReport relink(Path countryLinkingDir, Path osmNtFile, Path outputDir) throws IOException {
        Files.createDirectories(outputDir);

        Path osmLevelsFile = findOsmLevelsFile(countryLinkingDir);
        Map<Integer, Integer> gaulToOsmLevel = readGaulToOsmLevels(osmLevelsFile);

        Set<Integer> neededOsmLevels = new HashSet<>();
        for (int adminLevel = 0; adminLevel <= 2; adminLevel++) {
            Integer osmLevel = gaulToOsmLevel.get(adminLevel);
            if (osmLevel != null) {
                neededOsmLevels.add(osmLevel);
            }
        }

        String countryName = deriveCountryName(countryLinkingDir, osmNtFile);

        OsmIndex osmIndex = buildOsmIndex(osmNtFile, neededOsmLevels);

        RelinkReport report = new RelinkReport();
        report.countryName = countryName;
        report.osmNtFile = osmNtFile.toString();
        report.osmLevelsFile = osmLevelsFile.toString();

        for (int adminLevel = 0; adminLevel <= 2; adminLevel++) {
            Integer osmLevel = gaulToOsmLevel.get(adminLevel);
            if (osmLevel == null) {
                report.warnings.add("No OSM level mapping found for GAUL/admin level " + adminLevel);
                continue;
            }

            Path inputCsv = countryLinkingDir.resolve("linking_admin_" + adminLevel + ".csv");
            if (!Files.exists(inputCsv)) {
                report.warnings.add("Missing file: " + inputCsv);
                continue;
            }

            Path outputCsv = outputDir.resolve("linking_admin_" + adminLevel + config.outputSuffix + ".csv");
            relinkAdminFile(inputCsv, outputCsv, adminLevel, osmLevel, countryName, osmIndex, report);
        }

        if (config.writeMatchReport) {
            writeMatchReport(outputDir.resolve("osm_relink_report.csv"), report);
        }

        return report;
    }

    /**
     * Convenience overload. Writes output files next to the original linking CSVs.
     */
    public RelinkReport relink(Path countryLinkingDir, Path osmNtFile) throws IOException {
        return relink(countryLinkingDir, osmNtFile, countryLinkingDir);
    }

    private void relinkAdminFile(
            Path inputCsv,
            Path outputCsv,
            int adminLevel,
            int osmLevel,
            String countryName,
            OsmIndex osmIndex,
            RelinkReport report
    ) throws IOException {

        CsvTable table = readCsv(inputCsv);

        int entityGaulIdx = findColumn(table.header, "entity_gaul");
        int nameGaulIdx = findColumn(table.header, "hasName_gaul");
        int entityOsmIdx = findColumn(table.header, "entity_osm");
        int nameOsmIdx = findColumn(table.header, "hasName_osm");
        int nameEnIdx = findColumn(table.header, "hasNameEn");

        if (entityOsmIdx < 0) {
            throw new IOException("CSV file has no entity_osm column: " + inputCsv);
        }

        try (BufferedWriter writer = Files.newBufferedWriter(outputCsv, StandardCharsets.UTF_8)) {
            writeCsvRow(writer, table.header);

            for (List<String> row : table.rows) {
                padRow(row, table.header.size());

                String oldOsmUri = valueAt(row, entityOsmIdx);
                String gaulUri = valueAt(row, entityGaulIdx);

                List<String> searchLabels = new ArrayList<>();

                addIfPresent(searchLabels, valueAt(row, nameOsmIdx));
                addIfPresent(searchLabels, valueAt(row, nameEnIdx));
                addIfPresent(searchLabels, valueAt(row, nameGaulIdx));

                // Admin 0 linking files are often sparse, so the country name is useful.
                if (adminLevel == 0) {
                    addIfPresent(searchLabels, countryName);
                }

                MatchDecision decision = findBestMatch(
                        adminLevel,
                        osmLevel,
                        searchLabels,
                        osmIndex
                );

                if (decision.matched) {
                    row.set(entityOsmIdx, asCsvUri(decision.newOsmUri));
                    report.matchedRows++;
                } else {
                    report.unmatchedRows++;

                    if (!config.keepOldOsmUriOnNoMatch) {
                        row.set(entityOsmIdx, "");
                    }
                }

                report.totalRows++;
                increment(report.rowsByAdminLevel, adminLevel);
                if (decision.matched) {
                    increment(report.matchedRowsByAdminLevel, adminLevel);
                } else {
                    increment(report.unmatchedRowsByAdminLevel, adminLevel);
                }

                report.matchLogs.add(new MatchLog(
                        adminLevel,
                        osmLevel,
                        gaulUri,
                        oldOsmUri,
                        decision.matched ? decision.newOsmUri : "",
                        decision.score,
                        decision.reason
                ));

                writeCsvRow(writer, row);
            }
        }
    }

    private MatchDecision findBestMatch(
            int adminLevel,
            int osmLevel,
            List<String> rawSearchLabels,
            OsmIndex osmIndex
    ) {
        List<OsmEntity> candidates = osmIndex.entitiesByLevel.getOrDefault(osmLevel, List.of());

        if (candidates.isEmpty()) {
            return MatchDecision.unmatched("No OSM candidates found for OSM level " + osmLevel);
        }

        List<String> normalizedSearchLabels = rawSearchLabels.stream()
                .map(SimpleOsmEntityLinker::normalizeForMatching)
                .filter(s -> !s.isBlank())
                .distinct()
                .toList();

        // Country level is usually unique inside a country-specific .nt file.
        if (adminLevel == 0 && candidates.size() == 1) {
            OsmEntity only = candidates.get(0);
            double score = normalizedSearchLabels.isEmpty()
                    ? 1.0
                    : scoreEntity(normalizedSearchLabels, only);

            return MatchDecision.matched(
                    only.uri,
                    Math.max(score, 0.95),
                    "Single country-level candidate for mapped OSM level " + osmLevel
            );
        }

        // Fast path: exact normalized-name lookup.
        LinkedHashMap<String, OsmEntity> exactMatches = new LinkedHashMap<>();
        Map<String, List<OsmEntity>> nameIndex =
                osmIndex.entitiesByLevelAndNormalizedName.getOrDefault(osmLevel, Map.of());

        for (String label : normalizedSearchLabels) {
            for (OsmEntity entity : nameIndex.getOrDefault(label, List.of())) {
                exactMatches.put(entity.uri, entity);
            }
        }

        if (!exactMatches.isEmpty()) {
            ScoredEntity best = exactMatches.values().stream()
                    .map(e -> new ScoredEntity(e, scoreEntity(normalizedSearchLabels, e)))
                    .max(scoredEntityComparator())
                    .orElseThrow();

            return MatchDecision.matched(
                    best.entity.uri,
                    Math.max(best.score, 1.0),
                    "Exact normalized label match"
            );
        }

        // Slow path: simple lexical scoring among same-level candidates.
        List<ScoredEntity> scored = new ArrayList<>();
        for (OsmEntity candidate : candidates) {
            double score = scoreEntity(normalizedSearchLabels, candidate);
            scored.add(new ScoredEntity(candidate, score));
        }

        scored.sort(scoredEntityComparator().reversed());

        ScoredEntity best = scored.get(0);
        double secondBestScore = scored.size() > 1 ? scored.get(1).score : 0.0;

        if (best.score < config.minimumScore) {
            return MatchDecision.unmatched(
                    "Best score below threshold: " + best.score + " < " + config.minimumScore
            );
        }

        if ((best.score - secondBestScore) < config.minimumScoreMargin) {
            return MatchDecision.unmatched(
                    "Ambiguous match. Best=" + best.score + ", secondBest=" + secondBestScore
            );
        }

        return MatchDecision.matched(
                best.entity.uri,
                best.score,
                "Best lexical match inside mapped OSM level " + osmLevel
        );
    }

    private static Comparator<ScoredEntity> scoredEntityComparator() {
        return Comparator
                .comparingDouble((ScoredEntity s) -> s.score)
                .thenComparing(s -> s.entity.uri);
    }

    private static double scoreEntity(List<String> normalizedSearchLabels, OsmEntity entity) {
        if (normalizedSearchLabels.isEmpty() || entity.normalizedNames.isEmpty()) {
            return 0.0;
        }

        double best = 0.0;

        for (String queryLabel : normalizedSearchLabels) {
            for (String entityLabel : entity.normalizedNames) {
                best = Math.max(best, labelSimilarity(queryLabel, entityLabel));
            }
        }

        return best;
    }

    private static double labelSimilarity(String a, String b) {
        if (a.isBlank() || b.isBlank()) {
            return 0.0;
        }

        if (a.equals(b)) {
            return 1.0;
        }

        int minLen = Math.min(a.length(), b.length());
        int maxLen = Math.max(a.length(), b.length());

        if (minLen >= 3 && (a.contains(b) || b.contains(a))) {
            return 0.82 + 0.15 * ((double) minLen / (double) maxLen);
        }

        Set<String> tokensA = contentTokens(a);
        Set<String> tokensB = contentTokens(b);

        if (tokensA.isEmpty() || tokensB.isEmpty()) {
            return 0.0;
        }

        int intersection = 0;
        for (String token : tokensA) {
            if (tokensB.contains(token)) {
                intersection++;
            }
        }

        int union = tokensA.size() + tokensB.size() - intersection;
        double jaccard = union == 0 ? 0.0 : (double) intersection / (double) union;
        double dice = (2.0 * intersection) / (tokensA.size() + tokensB.size());

        return Math.max(jaccard, dice * 0.95);
    }

    private static Set<String> contentTokens(String normalized) {
        Set<String> out = new LinkedHashSet<>();

        for (String token : normalized.split("\\s+")) {
            if (token.isBlank()) {
                continue;
            }

            if (ADMIN_STOPWORDS.contains(token)) {
                continue;
            }

            out.add(token);
        }

        return out;
    }

    private OsmIndex buildOsmIndex(Path osmNtFile, Set<Integer> neededOsmLevels) throws IOException {
        Map<String, Integer> subjectToLevel = collectRelevantOsmSubjects(osmNtFile, neededOsmLevels);

        Map<String, OsmEntity> entitiesByUri = new LinkedHashMap<>();
        for (Map.Entry<String, Integer> entry : subjectToLevel.entrySet()) {
            entitiesByUri.put(entry.getKey(), new OsmEntity(entry.getKey(), entry.getValue()));
        }

        try (BufferedReader reader = Files.newBufferedReader(osmNtFile, StandardCharsets.UTF_8)) {
            String line;

            while ((line = reader.readLine()) != null) {
                NTriple triple = parseNTriple(line);
                if (triple == null) {
                    continue;
                }

                OsmEntity entity = entitiesByUri.get(triple.subject);
                if (entity == null) {
                    continue;
                }

                String predicateLocalName = localName(triple.predicate).toLowerCase(Locale.ROOT);

                if (triple.objectLiteral && isNamePredicate(predicateLocalName)) {
                    String label = triple.objectLexical == null ? "" : triple.objectLexical.trim();

                    if (!label.isBlank()) {
                        entity.names.add(label);

                        String normalized = normalizeForMatching(label);
                        if (!normalized.isBlank()) {
                            entity.normalizedNames.add(normalized);
                        }
                    }
                }
            }
        }

        OsmIndex index = new OsmIndex();

        for (OsmEntity entity : entitiesByUri.values()) {
            index.entitiesByLevel
                    .computeIfAbsent(entity.osmLevel, ignored -> new ArrayList<>())
                    .add(entity);

            for (String normalizedName : entity.normalizedNames) {
                index.entitiesByLevelAndNormalizedName
                        .computeIfAbsent(entity.osmLevel, ignored -> new HashMap<>())
                        .computeIfAbsent(normalizedName, ignored -> new ArrayList<>())
                        .add(entity);
            }
        }

        for (List<OsmEntity> entities : index.entitiesByLevel.values()) {
            entities.sort(Comparator.comparing(e -> e.uri));
        }

        return index;
    }

    private Map<String, Integer> collectRelevantOsmSubjects(Path osmNtFile, Set<Integer> neededOsmLevels)
            throws IOException {

        Map<String, Integer> subjectToLevel = new LinkedHashMap<>();

        try (BufferedReader reader = Files.newBufferedReader(osmNtFile, StandardCharsets.UTF_8)) {
            String line;

            while ((line = reader.readLine()) != null) {
                NTriple triple = parseNTriple(line);
                if (triple == null) {
                    continue;
                }

                if (!looksLikeOsmResource(triple.subject)) {
                    continue;
                }

                String predicateLocalName = localName(triple.predicate).toLowerCase(Locale.ROOT);

                if (!isLevelPredicate(predicateLocalName)) {
                    continue;
                }

                Integer level = parseInteger(triple.objectLexical);
                if (level == null || !neededOsmLevels.contains(level)) {
                    continue;
                }

                subjectToLevel.put(triple.subject, level);
            }
        }

        return subjectToLevel;
    }

    private static boolean looksLikeOsmResource(String iri) {
        String lower = iri.toLowerCase(Locale.ROOT);
        return lower.contains("/resource/osm_")
                || lower.contains("/osm_")
                || lower.contains("resource/osm_");
    }

    private static boolean isLevelPredicate(String localNameLower) {
        String compact = localNameLower
                .replace("_", "")
                .replace("-", "");

        return compact.equals("hasosmlevel")
                || compact.equals("osmlevel")
                || compact.equals("hasadminlevel")
                || compact.equals("adminlevel")
                || compact.endsWith("osmlevel")
                || compact.endsWith("adminlevel");
    }

    private static boolean isNamePredicate(String localNameLower) {
        String compact = localNameLower
                .replace("_", "")
                .replace("-", "");

        return compact.equals("hasname")
                || compact.equals("hasnameen")
                || compact.equals("name")
                || compact.equals("nameen")
                || compact.equals("label")
                || compact.equals("preflabel")
                || compact.equals("altlabel")
                || compact.equals("officialname")
                || compact.endsWith("name");
    }

    private static Integer parseInteger(String value) {
        if (value == null) {
            return null;
        }

        Matcher matcher = INTEGER_PATTERN.matcher(value);
        if (!matcher.find()) {
            return null;
        }

        try {
            return Integer.parseInt(matcher.group());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private Map<Integer, Integer> readGaulToOsmLevels(Path osmLevelsFile) throws IOException {
        CsvTable table = readCsv(osmLevelsFile);

        int gaulIdx = findColumn(table.header, "gaul");
        int osmIdx = findColumn(table.header, "osm");

        if (gaulIdx < 0 || osmIdx < 0) {
            throw new IOException("Expected columns gaul,osm in " + osmLevelsFile);
        }

        Map<Integer, Integer> result = new HashMap<>();

        for (List<String> row : table.rows) {
            Integer gaul = parseInteger(valueAt(row, gaulIdx));
            Integer osm = parseInteger(valueAt(row, osmIdx));

            if (gaul != null && osm != null) {
                result.put(gaul, osm);
            }
        }

        return result;
    }

    private Path findOsmLevelsFile(Path countryLinkingDir) throws IOException {
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(countryLinkingDir, "*_osm_levels.csv")) {
            for (Path path : stream) {
                return path;
            }
        }

        throw new IOException("Could not find *_osm_levels.csv in " + countryLinkingDir);
    }

    private static String deriveCountryName(Path countryLinkingDir, Path osmNtFile) {
        if (countryLinkingDir != null && countryLinkingDir.getFileName() != null) {
            String name = countryLinkingDir.getFileName().toString();
            if (!name.isBlank()) {
                return cleanCountryName(name);
            }
        }

        if (osmNtFile != null && osmNtFile.getParent() != null && osmNtFile.getParent().getFileName() != null) {
            return cleanCountryName(osmNtFile.getParent().getFileName().toString());
        }

        return "";
    }

    private static String cleanCountryName(String raw) {
        return raw
                .replace("_", " ")
                .replace("-", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private static String normalizeForMatching(String value) {
        if (value == null) {
            return "";
        }

        String s = value.trim();

        if (s.startsWith("<") && s.endsWith(">")) {
            s = s.substring(1, s.length() - 1);
        }

        s = s.replace("_", " ");
        s = s.replace("-", " ");

        s = Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "");

        s = s.replaceAll("[^\\p{IsAlphabetic}\\p{IsDigit}]+", " ");
        s = s.toLowerCase(Locale.ROOT);
        s = s.replaceAll("\\s+", " ").trim();

        return s;
    }

    private static String localName(String iri) {
        int hash = iri.lastIndexOf('#');
        int slash = iri.lastIndexOf('/');
        int colon = iri.lastIndexOf(':');

        int idx = Math.max(hash, Math.max(slash, colon));

        if (idx < 0 || idx + 1 >= iri.length()) {
            return iri;
        }

        return iri.substring(idx + 1);
    }

    private static NTriple parseNTriple(String line) {
        if (line == null) {
            return null;
        }

        String trimmed = line.trim();

        if (trimmed.isBlank() || trimmed.startsWith("#")) {
            return null;
        }

        int sStart = trimmed.indexOf('<');
        if (sStart != 0) {
            return null;
        }

        int sEnd = trimmed.indexOf('>', sStart + 1);
        if (sEnd < 0) {
            return null;
        }

        int pStart = trimmed.indexOf('<', sEnd + 1);
        if (pStart < 0) {
            return null;
        }

        int pEnd = trimmed.indexOf('>', pStart + 1);
        if (pEnd < 0) {
            return null;
        }

        String subject = trimmed.substring(sStart + 1, sEnd);
        String predicate = trimmed.substring(pStart + 1, pEnd);

        String objectPart = trimmed.substring(pEnd + 1).trim();

        if (objectPart.endsWith(".")) {
            objectPart = objectPart.substring(0, objectPart.length() - 1).trim();
        }

        ParsedObject object = parseObject(objectPart);

        return new NTriple(subject, predicate, object.lexical, object.literal);
    }

    private static ParsedObject parseObject(String objectPart) {
        if (objectPart == null || objectPart.isBlank()) {
            return new ParsedObject("", false);
        }

        String trimmed = objectPart.trim();

        if (trimmed.startsWith("<")) {
            int end = trimmed.indexOf('>');
            if (end > 0) {
                return new ParsedObject(trimmed.substring(1, end), false);
            }
            return new ParsedObject(trimmed, false);
        }

        if (trimmed.startsWith("\"")) {
            StringBuilder lexical = new StringBuilder();
            boolean escaping = false;

            for (int i = 1; i < trimmed.length(); i++) {
                char c = trimmed.charAt(i);

                if (escaping) {
                    if (c == 'u' && i + 4 < trimmed.length()) {
                        String hex = trimmed.substring(i + 1, i + 5);
                        Optional<Character> decoded = decodeHexChar(hex);
                        if (decoded.isPresent()) {
                            lexical.append(decoded.get());
                            i += 4;
                        } else {
                            lexical.append(c);
                        }
                    } else if (c == 'U' && i + 8 < trimmed.length()) {
                        String hex = trimmed.substring(i + 1, i + 9);
                        Optional<Character> decoded = decodeHexChar(hex);
                        if (decoded.isPresent()) {
                            lexical.append(decoded.get());
                            i += 8;
                        } else {
                            lexical.append(c);
                        }
                    } else {
                        lexical.append(switch (c) {
                            case 't' -> '\t';
                            case 'b' -> '\b';
                            case 'n' -> '\n';
                            case 'r' -> '\r';
                            case 'f' -> '\f';
                            case '"' -> '"';
                            case '\\' -> '\\';
                            default -> c;
                        });
                    }

                    escaping = false;
                    continue;
                }

                if (c == '\\') {
                    escaping = true;
                    continue;
                }

                if (c == '"') {
                    return new ParsedObject(lexical.toString(), true);
                }

                lexical.append(c);
            }

            return new ParsedObject(lexical.toString(), true);
        }

        return new ParsedObject(trimmed, false);
    }

    private static Optional<Character> decodeHexChar(String hex) {
        try {
            int codePoint = Integer.parseUnsignedInt(hex, 16);

            if (Character.isValidCodePoint(codePoint) && codePoint <= Character.MAX_VALUE) {
                return Optional.of((char) codePoint);
            }

            return Optional.empty();
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }

    private static CsvTable readCsv(Path file) throws IOException {
        CsvTable table = new CsvTable();

        try (BufferedReader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            String line = reader.readLine();

            if (line == null) {
                return table;
            }

            table.header = parseCsvLine(line);

            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }

                table.rows.add(parseCsvLine(line));
            }
        }

        return table;
    }

    private static List<String> parseCsvLine(String line) {
        List<String> values = new ArrayList<>();
        StringBuilder current = new StringBuilder();

        boolean inQuotes = false;

        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);

            if (c == '"') {
                if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }

                continue;
            }

            if (c == ',' && !inQuotes) {
                values.add(current.toString());
                current.setLength(0);
                continue;
            }

            current.append(c);
        }

        values.add(current.toString());

        return values;
    }

    private static void writeCsvRow(BufferedWriter writer, List<String> row) throws IOException {
        for (int i = 0; i < row.size(); i++) {
            if (i > 0) {
                writer.write(',');
            }

            writer.write(escapeCsv(valueAt(row, i)));
        }

        writer.newLine();
    }

    private static String escapeCsv(String value) {
        if (value == null) {
            return "";
        }

        boolean mustQuote = value.contains(",")
                || value.contains("\"")
                || value.contains("\n")
                || value.contains("\r");

        if (!mustQuote) {
            return value;
        }

        return "\"" + value.replace("\"", "\"\"") + "\"";
    }

    private static int findColumn(List<String> header, String name) {
        String wanted = canonicalColumnName(name);

        for (int i = 0; i < header.size(); i++) {
            if (canonicalColumnName(header.get(i)).equals(wanted)) {
                return i;
            }
        }

        return -1;
    }

    private static String canonicalColumnName(String name) {
        if (name == null) {
            return "";
        }

        return name.trim()
                .toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9]", "");
    }

    private static void padRow(List<String> row, int size) {
        while (row.size() < size) {
            row.add("");
        }
    }

    private static String valueAt(List<String> row, int idx) {
        if (idx < 0 || idx >= row.size()) {
            return "";
        }

        return row.get(idx) == null ? "" : row.get(idx);
    }

    private static void addIfPresent(List<String> values, String value) {
        if (value != null && !value.isBlank()) {
            values.add(value.trim());
        }
    }

    private static void increment(Map<Integer, Integer> map, int key) {
        map.put(key, map.getOrDefault(key, 0) + 1);
    }

    private static void writeMatchReport(Path reportFile, RelinkReport report) throws IOException {
        try (BufferedWriter writer = Files.newBufferedWriter(reportFile, StandardCharsets.UTF_8)) {
            writeCsvRow(writer, List.of(
                    "admin_level",
                    "osm_level",
                    "entity_gaul",
                    "old_entity_osm",
                    "new_entity_osm",
                    "score",
                    "reason"
            ));

            for (MatchLog log : report.matchLogs) {
                writeCsvRow(writer, List.of(
                        String.valueOf(log.adminLevel),
                        String.valueOf(log.osmLevel),
                        log.entityGaul,
                        log.oldEntityOsm,
                        log.newEntityOsm,
                        String.valueOf(log.score),
                        log.reason
                ));
            }
        }
    }

    public static final class Config {
        /**
         * Minimum lexical score required for non-exact matches.
         */
        public double minimumScore = 0.72;

        /**
         * Required difference between best and second-best candidate.
         */
        public double minimumScoreMargin = 0.02;

        /**
         * If true, unmatched rows keep their old OSM URI.
         * If false, unmatched rows get an empty entity_osm value.
         */
        public boolean keepOldOsmUriOnNoMatch = true;

        /**
         * Write osm_relink_report.csv.
         */
        public boolean writeMatchReport = true;

        /**
         * Output suffix. Default creates linking_admin_0_new.csv, etc.
         */
        public String outputSuffix = "_new";
    }

    public static final class RelinkReport {
        public String countryName;
        public String osmNtFile;
        public String osmLevelsFile;

        public int totalRows;
        public int matchedRows;
        public int unmatchedRows;

        public final Map<Integer, Integer> rowsByAdminLevel = new LinkedHashMap<>();
        public final Map<Integer, Integer> matchedRowsByAdminLevel = new LinkedHashMap<>();
        public final Map<Integer, Integer> unmatchedRowsByAdminLevel = new LinkedHashMap<>();

        public final List<String> warnings = new ArrayList<>();
        public final List<MatchLog> matchLogs = new ArrayList<>();
    }

    public static final class MatchLog {
        public final int adminLevel;
        public final int osmLevel;
        public final String entityGaul;
        public final String oldEntityOsm;
        public final String newEntityOsm;
        public final double score;
        public final String reason;

        private MatchLog(
                int adminLevel,
                int osmLevel,
                String entityGaul,
                String oldEntityOsm,
                String newEntityOsm,
                double score,
                String reason
        ) {
            this.adminLevel = adminLevel;
            this.osmLevel = osmLevel;
            this.entityGaul = entityGaul;
            this.oldEntityOsm = oldEntityOsm;
            this.newEntityOsm = newEntityOsm;
            this.score = score;
            this.reason = reason;
        }
    }

    private static final class CsvTable {
        private List<String> header = new ArrayList<>();
        private final List<List<String>> rows = new ArrayList<>();
    }

    private static final class OsmIndex {
        private final Map<Integer, List<OsmEntity>> entitiesByLevel = new HashMap<>();
        private final Map<Integer, Map<String, List<OsmEntity>>> entitiesByLevelAndNormalizedName = new HashMap<>();
    }

    private static final class OsmEntity {
        private final String uri;
        private final int osmLevel;
        private final List<String> names = new ArrayList<>();
        private final Set<String> normalizedNames = new LinkedHashSet<>();

        private OsmEntity(String uri, int osmLevel) {
            this.uri = uri;
            this.osmLevel = osmLevel;
        }
    }

    private static final class ScoredEntity {
        private final OsmEntity entity;
        private final double score;

        private ScoredEntity(OsmEntity entity, double score) {
            this.entity = entity;
            this.score = score;
        }
    }

    private static final class MatchDecision {
        private final boolean matched;
        private final String newOsmUri;
        private final double score;
        private final String reason;

        private MatchDecision(boolean matched, String newOsmUri, double score, String reason) {
            this.matched = matched;
            this.newOsmUri = newOsmUri;
            this.score = score;
            this.reason = reason;
        }

        private static MatchDecision matched(String newOsmUri, double score, String reason) {
            return new MatchDecision(true, newOsmUri, score, reason);
        }

        private static MatchDecision unmatched(String reason) {
            return new MatchDecision(false, "", 0.0, reason);
        }
    }

    private static final class NTriple {
        private final String subject;
        private final String predicate;
        private final String objectLexical;
        private final boolean objectLiteral;

        private NTriple(String subject, String predicate, String objectLexical, boolean objectLiteral) {
            this.subject = subject;
            this.predicate = predicate;
            this.objectLexical = objectLexical;
            this.objectLiteral = objectLiteral;
        }
    }

    private static final class ParsedObject {
        private final String lexical;
        private final boolean literal;

        private ParsedObject(String lexical, boolean literal) {
            this.lexical = lexical;
            this.literal = literal;
        }
    }

    private static String asCsvUri(String uri) {
        if (uri == null || uri.isBlank()) {
            return "";
        }

        String trimmed = uri.trim();

        if (trimmed.startsWith("<") && trimmed.endsWith(">")) {
            return trimmed;
        }

        return "<" + trimmed + ">";
    }
}
