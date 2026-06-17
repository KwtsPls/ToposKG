package gr.uoa.di.ai.connectors.util;

import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;
import org.locationtech.jts.geom.*;
import org.locationtech.jts.io.ParseException;
import org.locationtech.jts.io.WKTReader;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.util.*;
import java.util.concurrent.*;

public class GeospatialGraph {
    public HashMap<String, HashSet<String>> getGraph() {
        return graph;
    }

    HashMap<String, HashSet<String>> graph;

    public HashMap<String, String> getDiscovered() {
        return discovered;
    }

    HashMap<String,String> discovered;

    public GeospatialGraph(){
        this.graph = new HashMap<>();
        this.discovered = new HashMap<>();
    }

    public void buildForNeighbors(HashMap<String, HashSet<String>> osmLevelGroup,
                                  String jedaiSpatialMappings, String level){
        //Get the current level
        HashSet<String> group = osmLevelGroup.get(level);

        FileInputStream is = null;
        try {
            is = new FileInputStream(jedaiSpatialMappings);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(p.contains("sfIntersects") || p.contains("sfTouches"))
                    addNeighborEdge(s,o,group);
            }
        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }
    }


    public HashMap<String, Pair<String,String>> correctNeighbors(HashMap<String, Pair<String,String>> geoMap){
        WKTReader wktReader = new WKTReader();

        for(Map.Entry<String, HashSet<String>> entry: this.graph.entrySet()){
            Pair<String,String> g1Pair = geoMap.get(entry.getKey());
            String g1String = g1Pair.getRight();
            g1String = g1String.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                    .replaceAll("\"", "");
            try {
                Geometry g1 = wktReader.read(g1String);
                for(String neighbor: entry.getValue()){
                    Pair<String,String> g2Pair = geoMap.get(neighbor);
                    String g2String = g2Pair.getRight();
                    g2String = g2String.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                            .replaceAll("\"", "");
                    Geometry g2 = wktReader.read(g2String);

                    if(!g1.covers(g2) && !g2.covers(g1) && (!g1.touches(g2) && g1.overlaps(g2))) {
                        Geometry g1Trimmed = g1.difference(g2);
                        Geometry g2Trimmed = g2.difference(g1);

                        // Optional: Snap them to touch if needed
                        Geometry g1Touched = g1Trimmed.union(g1Trimmed.getBoundary().intersection(g2Trimmed.getBoundary()));
                        Geometry g2Touched = g2Trimmed.union(g2Trimmed.getBoundary().intersection(g1Trimmed.getBoundary()));

                        geoMap.put(neighbor, new ImmutablePair<>(g2Pair.getLeft(),g2Touched.toText()));
                        g1 = g1Touched;
                    }
                }
                geoMap.put(entry.getKey(), new ImmutablePair<>(g1Pair.getLeft(),g1.toText()));

            } catch (ParseException e) {
                e.printStackTrace();
            }
        }

        return geoMap;
    }


    // Helper Methods

    //Method to add an edge in the graph between entities of the same level
    private void addNeighborEdge(String key, String value, HashSet<String> group){
        if(key.equals(value)) return;

        if(group.contains(key) && group.contains(value)) {
            HashSet<String> set = graph.get(key);
            if (set == null) {
                set = new HashSet<>();
                set.add(value);
                this.graph.put(key, set);
            }
            else{
                HashSet<String> setValue = graph.get(value);
                if(setValue==null || !setValue.contains(key)){
                    set.add(value);
                    this.graph.put(key, set);
                }
            }
        }
    }


/********** HIERARCHY ALGORITHMS *****************/

    public void buildForHierarchy(
            HashMap<String, List<Pair<String, String>>> osmMap,
            HashMap<String, HashSet<String>> osmLevelGroup,
            HashMap<String, String> osm2gaulMap,
            HashMap<String, String> levelsMap,
            HashMap<String, Pair<String, String>> geoMap
    ) {
        int threads = Math.max(1, Runtime.getRuntime().availableProcessors() - 1);

        buildForHierarchyParallel(
                osmMap,
                osmLevelGroup,
                osm2gaulMap,
                levelsMap,
                geoMap,
                threads
        );
    }

    public void buildForHierarchyParallel(
            HashMap<String, List<Pair<String, String>>> osmMap,
            HashMap<String, HashSet<String>> osmLevelGroup,
            HashMap<String, String> osm2gaulMap,
            HashMap<String, String> levelsMap,
            HashMap<String, Pair<String, String>> geoMap,
            int threads
    ) {
        HashMap<String, String> gaulLevels = mirrorMap(levelsMap);

        /*
         * 1. Pre-index explicit OSM upper-admin links.
         *    This avoids scanning each entity's predicates repeatedly.
         */
        Map<String, String> explicitUpperAdmin = indexExplicitUpperAdmin(osmMap);

        /*
         * 2. Precompute geometries once.
         *    Your original discoverEntity reparses WKT for the child and every upper
         *    candidate on every call. This is usually the largest bottleneck.
         */
        Map<String, Geometry> envelopeMap = buildEnvelopeMap(geoMap);

        ExecutorService executor = Executors.newFixedThreadPool(threads);

        try {
            for (int i = 1; i < gaulLevels.size(); i++) {
                System.out.println("Working on level..." + i + "/" + (gaulLevels.size() - 1));

                String level = String.valueOf(i);
                String osmLevel = gaulLevels.get(level);

                String upperLevel = String.valueOf(i - 1);
                String upperOsmLevel = gaulLevels.get(upperLevel);

                HashSet<String> group = osmLevelGroup.get(osmLevel);
                HashSet<String> upperGroup = osmLevelGroup.get(upperOsmLevel);

                if (group == null || group.isEmpty()) {
                    continue;
                }

                if (upperGroup == null || upperGroup.isEmpty()) {
                    continue;
                }

                /*
                 * Per-level concurrent maps.
                 * We do NOT directly mutate this.graph or this.discovered inside worker threads.
                 */
                ConcurrentHashMap<String, Set<String>> levelGraph = new ConcurrentHashMap<>();
                ConcurrentHashMap<String, String> levelDiscovered = new ConcurrentHashMap<>();

                List<Callable<Void>> tasks = new ArrayList<>(group.size());

                for (String s : group) {
                    tasks.add(() -> {
                        /*
                         * Case 1: entity already has explicit hasUpperAdminUnit.
                         */
                        String explicitParent = explicitUpperAdmin.get(s);

                        if (explicitParent != null) {
                            String key = normalizeUpperKey(explicitParent, upperLevel, osm2gaulMap);

                            if (key != null) {
                                addToConcurrentGraph(levelGraph, key, s);
                            }

                            return null;
                        }

                        /*
                         * Case 2: no explicit upper admin unit, discover spatially.
                         *
                         * No coarse size pruning here. Instead, discovery uses cheap envelope
                         * intersection checks before ranking candidates.
                         */
                        String upperAdminUnit = discoverEntityFast(s, upperGroup, envelopeMap);

                        if (upperAdminUnit != null) {
                            levelDiscovered.put(s, upperAdminUnit);

                            String key = normalizeUpperKey(upperAdminUnit, upperLevel, osm2gaulMap);

                            if (key != null) {
                                addToConcurrentGraph(levelGraph, key, s);
                            }
                        }

                        return null;
                    });
                }

                /*
                 * Run all tasks for this level and wait.
                 * Levels remain sequential, but entities inside the level are parallel.
                 */
                List<Future<Void>> futures = executor.invokeAll(tasks);

                for (Future<Void> future : futures) {
                    try {
                        future.get();
                    } catch (ExecutionException e) {
                        e.getCause().printStackTrace();
                    }
                }

                /*
                 * Merge results back into the original fields sequentially.
                 * This avoids requiring graph/discovered themselves to be ConcurrentHashMaps.
                 */
                mergeLevelGraph(levelGraph);
                this.discovered.putAll(levelDiscovered);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Hierarchy construction interrupted", e);
        } finally {
            executor.shutdown();
        }
    }


    private Map<String, String> indexExplicitUpperAdmin(
            HashMap<String, List<Pair<String, String>>> osmMap
    ) {
        Map<String, String> explicitUpperAdmin = new HashMap<>();

        for (Map.Entry<String, List<Pair<String, String>>> entry : osmMap.entrySet()) {
            String child = entry.getKey();

            for (Pair<String, String> pair : entry.getValue()) {
                String p = pair.getLeft();
                String o = pair.getRight();

                if (p != null && p.contains("hasUpperAdminUnit")) {
                    explicitUpperAdmin.put(child, o);
                    break;
                }
            }
        }

        return explicitUpperAdmin;
    }

    private Map<String, Geometry> buildEnvelopeMap(
            HashMap<String, Pair<String, String>> geoMap
    ) {
        ConcurrentHashMap<String, Geometry> result = new ConcurrentHashMap<>();

        geoMap.entrySet().parallelStream().forEach(entry -> {
            String entity = entry.getKey();

            if (entity == null) {
                System.err.println("Skipping geometry entry with null entity key.");
                return;
            }

            Pair<String, String> pair = entry.getValue();

            if (pair == null) {
                System.err.println("Skipping geometry for entity " + entity + ": null pair.");
                return;
            }

            String wkt = pair.getRight();

            if (wkt == null || wkt.trim().isEmpty()) {
                System.err.println("Skipping geometry for entity " + entity + ": null or empty WKT.");
                return;
            }

            try {
                Geometry envelope = parseEnvelope(wkt);

                if (envelope == null || envelope.isEmpty()) {
                    System.err.println("Skipping geometry for entity " + entity + ": empty parsed geometry.");
                    return;
                }

                result.put(entity, envelope);

            } catch (ParseException e) {
                System.err.println("Could not parse geometry for entity: " + entity);
                System.err.println("WKT was: " + wkt);
                e.printStackTrace();
            } catch (Exception e) {
                System.err.println("Unexpected error while parsing geometry for entity: " + entity);
                System.err.println("WKT was: " + wkt);
                e.printStackTrace();
            }
        });

        return result;
    }

    private Geometry parseEnvelope(String geomString) throws ParseException {
        if (geomString == null) {
            return null;
        }

        String cleaned = geomString
                .replace("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                .replace("\"", "")
                .trim();

        if (cleaned.isEmpty()) {
            return null;
        }

        WKTReader reader = new WKTReader();
        Geometry geometry = reader.read(cleaned);

        if (geometry == null || geometry.isEmpty()) {
            return null;
        }

        return geometry.buffer(0).getEnvelope();
    }

    private String discoverEntityFast(
            String entity,
            Collection<String> upperGroup,
            Map<String, Geometry> envelopeMap
    ) {
        if (entity == null || upperGroup == null || upperGroup.isEmpty()) {
            return null;
        }

        Geometry geom = envelopeMap.get(entity);

        if (geom == null || geom.isEmpty()) {
            return null;
        }

        double geomArea = geom.getArea();

        if (geomArea == 0.0) {
            return null;
        }

        Envelope geomEnvelope = geom.getEnvelopeInternal();

        String result = null;
        double max = 0.0;

        for (String upper : upperGroup) {
            if (upper == null) {
                continue;
            }

            Geometry candidate = envelopeMap.get(upper);

            if (candidate == null || candidate.isEmpty()) {
                continue;
            }

            if (!candidate.getEnvelopeInternal().intersects(geomEnvelope)) {
                continue;
            }

            if (candidate.covers(geom)) {
                return upper;
            }

            Geometry intersection = geom.intersection(candidate);
            double rank = intersection.getArea() / geomArea;

            if (rank > max) {
                max = rank;
                result = upper;
            }
        }

        return result;
    }

    private String normalizeUpperKey(
            String upperAdminUnit,
            String upperLevel,
            HashMap<String, String> osm2gaulMap
    ) {
        if (upperAdminUnit == null) {
            return null;
        }

        /*
         * Your original code mapped level 2 parents through osm2gaulMap.
         * This version avoids producing null graph keys when the mapping is missing.
         */
        if ("2".equals(upperLevel)) {
            return osm2gaulMap.getOrDefault(upperAdminUnit, upperAdminUnit);
        }

        return upperAdminUnit;
    }

    private void addToConcurrentGraph(
            ConcurrentHashMap<String, Set<String>> levelGraph,
            String parent,
            String child
    ) {
        levelGraph
                .computeIfAbsent(parent, k -> ConcurrentHashMap.newKeySet())
                .add(child);
    }

    private void mergeLevelGraph(
            ConcurrentHashMap<String, Set<String>> levelGraph
    ) {
        for (Map.Entry<String, Set<String>> entry : levelGraph.entrySet()) {
            String parent = entry.getKey();
            Set<String> children = entry.getValue();

            HashSet<String> set = graph.get(parent);

            if (set == null) {
                set = new HashSet<>();
                graph.put(parent, set);
            }

            set.addAll(children);
        }
    }

    public static <K, V> HashMap<V, K> mirrorMap(Map<K, V> original) {
        HashMap<V, K> mirrored = new HashMap<>();

        for (Map.Entry<K, V> entry : original.entrySet()) {
            mirrored.put(entry.getValue(), entry.getKey());
        }

        return mirrored;
    }
}
