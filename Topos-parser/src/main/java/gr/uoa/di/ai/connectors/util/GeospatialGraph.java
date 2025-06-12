package gr.uoa.di.ai.connectors.util;

import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;
import org.locationtech.jts.geom.*;
import org.locationtech.jts.geom.util.GeometryCombiner;
import org.locationtech.jts.geom.util.GeometryFixer;
import org.locationtech.jts.io.ParseException;
import org.locationtech.jts.io.WKTReader;
import org.locationtech.jts.operation.overlay.snap.GeometrySnapper;
import org.locationtech.jts.operation.overlay.snap.SnapOverlayOp;
import org.locationtech.jts.operation.polygonize.Polygonizer;
import org.locationtech.jts.operation.union.CascadedPolygonUnion;
import org.locationtech.jts.operation.union.UnaryUnionOp;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileWriter;
import java.util.*;

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

    public void buildForHierarchy(HashMap<String, List<Pair<String,String>>> osmMap, HashMap<String, HashSet<String>> osmLevelGroup,
                                  HashMap<String,String> osm2gaulMap, HashMap<String,String> levelsMap,
                                  HashMap<String, Pair<String,String>> geoMap){
        //Get the current level
        HashMap<String,String> gaulLevels = mirrorMap(levelsMap);

        for(int i=1;i<gaulLevels.size();i++) {
            System.out.println("Working on level..." + i + "/" + (gaulLevels.size() - 1));
            String level = String.valueOf(i);
            String osmLevel = gaulLevels.get(level);
            String upperLevel = String.valueOf(Integer.parseInt(level) - 1);
            HashSet<String> group = osmLevelGroup.get(osmLevel);
            HashSet<String> u = osmLevelGroup.get(gaulLevels.get(upperLevel));

            if (group != null) {
                for (Map.Entry<String, List<Pair<String, String>>> entry : osmMap.entrySet()) {
                    String s = entry.getKey();
                    boolean isDiscovered = false;
                    if (group.contains(s)) {
                        for (Pair<String, String> pair : entry.getValue()) {
                            String p = pair.getLeft();
                            String o = pair.getRight();
                            if (p.contains("hasUpperAdminUnit")) {
                                isDiscovered = true;

                                String key = o;
                                if (upperLevel.equals("2")) {
                                    key = osm2gaulMap.get(o);
                                }
                                HashSet<String> set = graph.get(key);
                                if (set == null) {
                                    set = new HashSet<>();
                                }
                                set.add(s);
                                graph.put(key, set);
                            }
                        }
                    } else {
                        isDiscovered = true;
                    }

                    //Entity does not have an upper level connection - discover it
                    HashSet<String> upperGroup = osmLevelGroup.get(gaulLevels.get(upperLevel));
                    if (!isDiscovered && upperGroup!=null) {
                        try {
                            String upperAdminUnit = discoverEntity(s, upperGroup, geoMap);
                            if (upperAdminUnit != null) {
                                this.discovered.put(s, upperAdminUnit);

                                String key = upperAdminUnit;
                                if (upperLevel.equals("2")) {
                                    key = osm2gaulMap.get(upperAdminUnit);
                                }

                                HashSet<String> set = graph.get(key);
                                if (set == null) {
                                    set = new HashSet<>();
                                }
                                set.add(s);
                                graph.put(key, set);
                            }
                        } catch (ParseException e) {
                            e.printStackTrace();
                        }
                    }

                }
            }
        }
    }


    private String discoverEntity(String entity, HashSet<String> upperGroup, HashMap<String, Pair<String,String>> geoMap) throws ParseException {
        WKTReader reader = new WKTReader();
        String geomString = geoMap.get(entity).getRight();
        geomString = geomString.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                .replaceAll("\"", "");
        Geometry geom = reader.read(geomString).buffer(0).getEnvelope();

        String result = null;
        double max = 0.0;
        for(String upper:upperGroup){
            Pair<String,String> pair = geoMap.get(upper);
            String candidateString = pair.getRight();
            candidateString = candidateString.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                    .replaceAll("\"", "");
            Geometry candidate = reader.read(candidateString).buffer(0).getEnvelope();

            if(candidate.covers(geom)){
                result = upper;
                break;
            }

            Geometry intersection = geom.intersection(candidate);
            double rank = intersection.getArea() / geom.getArea();
            if(rank>max){
                max = rank;
                result = upper;
            }
        }

        return result;
    }

    public static <K, V> HashMap<V, K> mirrorMap(Map<K, V> original) {
        HashMap<V, K> mirrored = new HashMap<>();
        for (Map.Entry<K, V> entry : original.entrySet()) {
            mirrored.put(entry.getValue(), entry.getKey());
        }
        return mirrored;
    }
}
