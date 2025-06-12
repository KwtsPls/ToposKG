package gr.uoa.di.ai.transformers;

import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.*;

public class Nt2Csv {
    private static final String GEOSPARQL_PREFIX = "http://www.opengis.net/ont/geosparql#";


    public static void prepareOSM(String inputFile, String outputFile, String targetLevel) throws IOException {
        Map<String, Map<String, String>> entityData = new LinkedHashMap<>();
        Set<String> allPredicates = new TreeSet<>();
        Set<String> targetEntities = new HashSet<>();

        // Map raw predicate URIs to cleaned names
        Map<String, String> predicateNameMap = new HashMap<>();

        // First pass: identify entities with the target level
        try (FileInputStream is = new FileInputStream(inputFile)) {
            NxParser nxp = new NxParser();
            nxp.parse(is);

            while (nxp.hasNext()) {
                Node[] nx = nxp.next();
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if (p.contains("hasOSMLevel") && o.contains(targetLevel)) {
                    targetEntities.add(s);
                }
            }
        }
        System.out.println(targetEntities);

        // Second pass: collect all predicates for the target entities
        try (FileInputStream is = new FileInputStream(inputFile)) {
            NxParser nxp = new NxParser();
            nxp.parse(is);

            while (nxp.hasNext()) {
                Node[] nx = nxp.next();
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString(); // Literal (quoted) or URI

                if (!targetEntities.contains(s)) continue;

                // Ignore geosparql predicates
                if (p.startsWith(GEOSPARQL_PREFIX)) continue;

                // Ignore if object is a URI (not a literal)
                if (!o.contains("\"")) continue;

                entityData.putIfAbsent(s, new HashMap<>());
                entityData.get(s).put(p, o.replaceAll("^\"|\"$", "")); // remove quotes around literals
                allPredicates.add(p);
                predicateNameMap.putIfAbsent(p, cleanPredicate(p));
            }
        }

        // Write to CSV
        try (PrintWriter writer = new PrintWriter(new FileWriter(outputFile))) {
            // Header
            writer.print("entity");
            for (String rawPred : allPredicates) {
                writer.print("," + escapeCSV(predicateNameMap.get(rawPred)));
            }
            writer.println();

            // Rows
            for (String entity : entityData.keySet()) {
                writer.print(escapeCSV(entity));
                Map<String, String> predicates = entityData.get(entity);
                for (String rawPred : allPredicates) {
                    writer.print(",");
                    writer.print(escapeCSV(predicates.getOrDefault(rawPred, "")));
                }
                writer.println();
            }
        }
    }

    public static void prepareGAUL(String inputFile, String outputFile, String targetLevel) throws IOException {
        Map<String, Map<String, String>> entityData = new LinkedHashMap<>();
        Set<String> allPredicates = new TreeSet<>();
        Set<String> targetEntities = new HashSet<>();

        // Map raw predicate URIs to cleaned names
        Map<String, String> predicateNameMap = new HashMap<>();

        // First pass: identify entities with the target level
        try (FileInputStream is = new FileInputStream(inputFile)) {
            NxParser nxp = new NxParser();
            nxp.parse(is);

            while (nxp.hasNext()) {
                Node[] nx = nxp.next();
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if (o.contains("AdminUnit_Level"+targetLevel)) {
                    targetEntities.add(s);
                }
            }
        }
        System.out.println(targetEntities);

        // Second pass: collect all predicates for the target entities
        try (FileInputStream is = new FileInputStream(inputFile)) {
            NxParser nxp = new NxParser();
            nxp.parse(is);

            while (nxp.hasNext()) {
                Node[] nx = nxp.next();
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString(); // Literal (quoted) or URI

                if (!targetEntities.contains(s)) continue;

                // Ignore geosparql predicates
                if (p.startsWith(GEOSPARQL_PREFIX)) continue;

                // Ignore if object is a URI (not a literal)
                if (!o.contains("\"")) continue;

                entityData.putIfAbsent(s, new HashMap<>());
                entityData.get(s).put(p, o.replaceAll("^\"|\"$", "")); // remove quotes around literals
                allPredicates.add(p);
                predicateNameMap.putIfAbsent(p, cleanPredicate(p));
            }
        }

        // Write to CSV
        try (PrintWriter writer = new PrintWriter(new FileWriter(outputFile))) {
            // Header
            writer.print("entity");
            for (String rawPred : allPredicates) {
                writer.print("," + escapeCSV(predicateNameMap.get(rawPred)));
            }
            writer.println();

            // Rows
            for (String entity : entityData.keySet()) {
                writer.print(escapeCSV(entity));
                Map<String, String> predicates = entityData.get(entity);
                for (String rawPred : allPredicates) {
                    writer.print(",");
                    writer.print(escapeCSV(predicates.getOrDefault(rawPred, "")));
                }
                writer.println();
            }
        }
    }


    private static String cleanPredicate(String uri) {
        uri = uri.replace("<", "").replace(">", ""); // Remove angle brackets
        int lastSlash = uri.lastIndexOf('/');
        int lastHash = uri.lastIndexOf('#');
        int pos = Math.max(lastSlash, lastHash);
        if (pos != -1 && pos < uri.length() - 1) {
            return uri.substring(pos + 1);
        }
        return uri;
    }

    private static String escapeCSV(String value) {
        if (value.contains(",") || value.contains("\"")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }

}
