package gr.uoa.di.ai.transformers;

import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.TopologyException;
import org.locationtech.jts.io.ParseException;
import org.locationtech.jts.io.WKTReader;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.*;

class Element {
    String key;
    double value;

    public Element(String key, double value) {
        this.key = key;
        this.value = value;
    }

    public String getKey() {
        return key;
    }

    public double getValue() {
        return value;
    }
}

public class IntersectionConnector {
    HashMap<String, Geometry> geoMap;
    String inputFile;

    public IntersectionConnector(String inputFile) {
        this.geoMap = new HashMap<>();
        this.inputFile = inputFile;
    }

    public String rankIntersections(String entity, Collection<String> candidates) {
        if (geoMap.isEmpty()) {
            collectGeometries();
        }

        Geometry queryGeometry = geoMap.get(entity);

        if (queryGeometry == null || !isPolygonal(queryGeometry)) {
            return null;
        }

        double entityArea = queryGeometry.getArea();

        List<String> prunedCandidates = candidates.stream()
                .filter(candidate -> !candidate.equals(entity))
                .filter(candidate -> geoMap.containsKey(candidate))
                .filter(candidate -> isPolygonal(geoMap.get(candidate)))
                .filter(candidate -> geoMap.get(candidate).getArea() > entityArea)
                .sorted(Comparator.comparingDouble(candidate -> geoMap.get(candidate).getArea()))
                .limit(20)
                .toList();

        return prunedCandidates.parallelStream()
                .map(candidate -> {
                    Geometry candidateGeometry = geoMap.get(candidate);
                    try {
                        Geometry intersection = queryGeometry.intersection(candidateGeometry);
                        double rank = intersection.getArea() / candidateGeometry.getArea();
                        return new Element(candidate, rank);
                    }
                    catch (TopologyException e){
                        return new Element(candidate, 0.0);
                    }
                })
                .filter(element -> element.getValue() > 0.0)
                .max(
                        Comparator.comparingDouble(Element::getValue)
                                .thenComparing(Element::getKey, Comparator.reverseOrder())
                )
                .map(Element::getKey)
                .orElse(null);
    }

    public void connectUpperAdminUnits(String intersectsFile, String outputFile) {
        if (geoMap.isEmpty()) {
            collectGeometries();
        }

        HashMap<String, HashSet<String>> entity2intersections = new HashMap<>();

        try {
            FileInputStream is = new FileInputStream(intersectsFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if (p.contains("sfIntersects")) {
                    entity2intersections
                            .computeIfAbsent(s, k -> new HashSet<>())
                            .add(o);
                }
            }

            is.close();
        } catch (IOException e) {
            e.printStackTrace();
        }

        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile));

            for (Map.Entry<String, HashSet<String>> entry : entity2intersections.entrySet()) {
                String entity = entry.getKey();
                String bestCandidate = rankIntersections(entity, entry.getValue());

                if (bestCandidate != null) {
                    writer.write(entity
                            + " <http://toposkg.di.uoa.gr/ontology/hasUpperAdminUnit> "
                            + bestCandidate
                            + " .\n");
                }
            }

            writer.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void collectGeometries() {
        FileInputStream is = null;
        try {
            is = new FileInputStream(inputFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);
            WKTReader wktReader = new WKTReader();
            HashMap<String, String> entity2geo = new HashMap<>();

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if (p.contains("hasGeometry"))
                    entity2geo.put(o, s);

                if (p.contains("asWKT")) {
                    String entity = entity2geo.get(s);
                    String geomString = o;
                    geomString = geomString.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                            .replaceAll("\"", "");
                    Geometry geom = wktReader.read(geomString);
                    this.geoMap.put(entity, geom);
                }
            }

            is.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private boolean isPolygonal(Geometry geometry) {
        return geometry != null &&
                (geometry.getGeometryType().equals("Polygon")
                        || geometry.getGeometryType().equals("MultiPolygon"));
    }
}