package gr.uoa.di.ai.transformers;

import org.locationtech.jts.geom.*;
import org.locationtech.jts.geom.util.PolygonExtracter;
import org.locationtech.jts.io.ParseException;
import org.locationtech.jts.io.WKTReader;
import org.locationtech.jts.operation.union.CascadedPolygonUnion;
import org.locationtech.jts.operation.union.UnaryUnionOp;
import org.locationtech.jts.operation.union.UnionInteracting;
import org.locationtech.jts.precision.GeometryPrecisionReducer;
import org.locationtech.jts.simplify.TopologyPreservingSimplifier;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.*;

public class GeometryAggregator {

    String path;
    String output;
    String aggrType;
    HashMap<String, String> geometryMap;
    HashMap<String, List<String>> groups;
    HashSet<String> upperLevelSet;
    HashSet<String> lowerLevelSet;


    public GeometryAggregator(String path, String output, String aggrType){
        this.path = path;
        this.output = output;
        this.aggrType = aggrType;
        this.geometryMap = new HashMap<>();
        this.upperLevelSet = new HashSet<>();
        this.lowerLevelSet = new HashSet<>();
        this.groups = new HashMap<>();
    }

    public void aggregateOnUpperLevel() throws IOException, ParseException {
        BufferedWriter writer = new BufferedWriter(new FileWriter(output));

        //Find entities with geometries
        collectADM2Entities();
        WKTReader wktReader = new WKTReader();

        List<Polygon> countryGeoms = new ArrayList<>();

        String country = null;
        for(Map.Entry<String, List<String>> entry : groups.entrySet()){
            String upper = entry.getKey();
            List<String> lowerGroup = entry.getValue();

            List<Polygon> geometries = new ArrayList<>();

            for(String lower : lowerGroup){
                if(!this.upperLevelSet.contains(lower)) {

                    String geomString = this.geometryMap.get(lower);
                    geomString = geomString.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                            .replaceAll("\"", "");
                    Geometry geom = wktReader.read(geomString).buffer(0);

                    if(geom instanceof Polygon p) {
                        geometries.add(p);
                        countryGeoms.add(p);
                    }
                    else if(geom instanceof MultiPolygon mp){
                        int numGeometries = mp.getNumGeometries();
                        for (int i = 0; i < numGeometries; i++) {
                            geometries.add((Polygon) geom.getGeometryN(i));
                            countryGeoms.add((Polygon) geom.getGeometryN(i));
                        }
                    }

                }
                else{
                    country = upper;
                }
            }

            Geometry geometry = CascadedPolygonUnion.union(geometries);

            if(geometry!=null){
                geometry = geometry.buffer(0);
                this.geometryMap.put(upper,"\"<http://www.opengis.net/def/crs/EPSG/0/4326> " + geometry.toText()
                        + "\"^^<http://www.opengis.net/ont/geosparql#wktLiteral>");
            }
        }

        Geometry countryGeom = CascadedPolygonUnion.union(countryGeoms);

        System.out.println(country);
        this.geometryMap.put(country,"\"<http://www.opengis.net/def/crs/EPSG/0/4326> " + countryGeom
                + "\"^^<http://www.opengis.net/ont/geosparql#wktLiteral>");


        FileInputStream is = new FileInputStream(path);
        NxParser nxp = new NxParser();
        nxp.parse(is);
        HashMap<String,String> entity2geo = new HashMap<>();

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("hasGeometry")){
                entity2geo.put(o,s);
            }
            else if(p.contains("asWKT")){
                String entity = entity2geo.get(s);
                o = this.geometryMap.get(entity);
            }


            if(o.endsWith("<http://www"))
                o = o.replaceAll("<http://www","<http://www.opengis.net/ont/geosparql#wktLiteral>");
            if(o.endsWith("<http://www.opengis"))
                o = o.replaceAll("<http://www.opengis","<http://www.opengis.net/ont/geosparql#wktLiteral>");
            if(o.contains("<http://www.opengis.net/ont/geosparql#wktLiteral>.net/def/crs/EPSG/0/4326>"))
                o = o.replaceAll("<http://www.opengis.net/ont/geosparql#wktLiteral>.net/def/crs/EPSG/0/4326>","<http://www.opengis.net/def/crs/EPSG/0/4326>");
            if(o.contains("<http://www.opengis.net/ont/geosparql#wktLiteral>.opengis.net/def/crs/EPSG/0/4326>"))
                o = o.replaceAll("<http://www.opengis.net/ont/geosparql#wktLiteral>.opengis.net/def/crs/EPSG/0/4326>","<http://www.opengis.net/def/crs/EPSG/0/4326>");

            writer.write(s + " " + p + " " + o + " .\n");
        }

        writer.close();
    }

    private void collectADM2Entities() throws IOException{

        FileInputStream is = new FileInputStream(path);
        NxParser nxp = new NxParser();
        nxp.parse(is);

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("hasGeometry")){
                //Entry with WKT appeared before geometry
                if(this.geometryMap.containsKey(o)){
                    String wkt = this.geometryMap.get(o);
                    this.geometryMap.remove(o);
                    this.geometryMap.put(s,wkt);
                }
                else if(!this.geometryMap.containsKey(s)){
                    this.geometryMap.put(o,s);
                }
            }
            else if(p.contains("asWKT")){
                //Entry with WKT appeared before geometry
                if(!this.geometryMap.containsKey(s)){
                    this.geometryMap.put(s,o);
                }
                else{
                    String entity = this.geometryMap.get(s);
                    this.geometryMap.remove(s);
                    this.geometryMap.put(entity,o);
                }
            }
            else if(o.contains("AdminUnit_Level1") || o.contains("AdminUnit_Level0")){
                this.upperLevelSet.add(s);
            }
            else if(p.contains("hasUpperAdminUnit")){
                this.addToMap(s,o);
            }
        }

        for(String upperLevel: this.upperLevelSet){
            this.geometryMap.remove(upperLevel);
        }
    }


    public void aggregateOnLevelOne() throws IOException, ParseException {
        BufferedWriter writer = new BufferedWriter(new FileWriter(output));

        //Find entities with geometries
        collectADM1Entities();
        WKTReader wktReader = new WKTReader();

        List<Polygon> countryGeoms = new ArrayList<>();

        String country = null;
        for(Map.Entry<String, List<String>> entry : groups.entrySet()){
            country = entry.getKey();
            List<String> lowerGroup = entry.getValue();

            for(String lower : lowerGroup){
                String geomString = this.geometryMap.get(lower);
                geomString = geomString.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                        .replaceAll("\"", "");
                Geometry geom = wktReader.read(geomString).buffer(0);

                if(geom instanceof Polygon p) {
                    countryGeoms.add(p);
                }
                else if(geom instanceof MultiPolygon mp){
                    int numGeometries = mp.getNumGeometries();
                    for (int i = 0; i < numGeometries; i++) {
                        countryGeoms.add((Polygon) geom.getGeometryN(i));
                    }
                }

            }
        }

        Geometry countryGeom = CascadedPolygonUnion.union(countryGeoms);

        this.geometryMap.put(country,"\"<http://www.opengis.net/def/crs/EPSG/0/4326> " + countryGeom
                + "\"^^<http://www.opengis.net/ont/geosparql#wktLiteral>");


        FileInputStream is = new FileInputStream(path);
        NxParser nxp = new NxParser();
        nxp.parse(is);
        HashMap<String,String> entity2geo = new HashMap<>();

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("hasGeometry")){
                entity2geo.put(o,s);
            }
            else if(p.contains("asWKT")){
                String entity = entity2geo.get(s);
                o = this.geometryMap.get(entity);
            }


            if(o.endsWith("<http://www"))
                o = o.replaceAll("<http://www","<http://www.opengis.net/ont/geosparql#wktLiteral>");
            if(o.endsWith("<http://www.opengis"))
                o = o.replaceAll("<http://www.opengis","<http://www.opengis.net/ont/geosparql#wktLiteral>");
            if(o.contains("<http://www.opengis.net/ont/geosparql#wktLiteral>.net/def/crs/EPSG/0/4326>"))
                o = o.replaceAll("<http://www.opengis.net/ont/geosparql#wktLiteral>.net/def/crs/EPSG/0/4326>","<http://www.opengis.net/def/crs/EPSG/0/4326>");
            if(o.contains("<http://www.opengis.net/ont/geosparql#wktLiteral>.opengis.net/def/crs/EPSG/0/4326>"))
                o = o.replaceAll("<http://www.opengis.net/ont/geosparql#wktLiteral>.opengis.net/def/crs/EPSG/0/4326>","<http://www.opengis.net/def/crs/EPSG/0/4326>");

            writer.write(s + " " + p + " " + o + " .\n");
        }

        writer.close();
    }


    private void collectADM1Entities() throws IOException {
        FileInputStream is = new FileInputStream(path);
        NxParser nxp = new NxParser();
        nxp.parse(is);

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("hasGeometry")){
                //Entry with WKT appeared before geometry
                if(this.geometryMap.containsKey(o)){
                    String wkt = this.geometryMap.get(o);
                    this.geometryMap.remove(o);
                    this.geometryMap.put(s,wkt);
                }
                else if(!this.geometryMap.containsKey(s)){
                    this.geometryMap.put(o,s);
                }
            }
            else if(p.contains("asWKT")){
                //Entry with WKT appeared before geometry
                if(!this.geometryMap.containsKey(s)){
                    this.geometryMap.put(s,o);
                }
                else{
                    String entity = this.geometryMap.get(s);
                    this.geometryMap.remove(s);
                    this.geometryMap.put(entity,o);
                }
            }
            else if(o.contains("AdminUnit_Level2")){
                this.lowerLevelSet.add(s);
            }
            else if(o.contains("AdminUnit_Level0")){
                this.upperLevelSet.add(s);
            }
            else if(p.contains("hasUpperAdminUnit")){
                this.addToMap(s,o);
            }
        }

        for(String lowerLevel: this.lowerLevelSet) {
            this.geometryMap.remove(lowerLevel);
        }
        for(String upperLevel: this.upperLevelSet){
            this.geometryMap.remove(upperLevel);
        }
    }

    private void addToMap(String lower, String upper){
        List<String> group = this.groups.get(upper);
        if(group==null)
            group = new ArrayList<>();
        group.add(lower);
        this.groups.put(upper,group);
    }
}
