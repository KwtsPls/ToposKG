package gr.uoa.di.ai.connectors;

import gr.uoa.di.ai.Constants;
import gr.uoa.di.ai.connectors.util.GeospatialGraph;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.*;

public class Osm2GAULConnector {

    HashMap<String, List<Pair<String,String>>> gaulMap;
    HashMap<String, List<Pair<String,String>>> osmMap;
    HashMap<String, Pair<String,String>> geoMap;
    HashMap<String,String> levelsMap;
    HashMap<String,HashSet<String>> osmLevelGroup;
    HashMap<String,HashSet<String>> gaulLevelGroup;
    HashMap<String,String> linkedEntities;

    //Mirror maps (osm->gaul) (gaul->osm)
    HashMap<String,String> osm2gaulMap;
    HashMap<String,String> gaul2osmMap;

    //Input files
    String type;
    String osmFile;
    String gaulFile;
    String osmLevelsFile;
    String[] linkingFiles;

    //Output directory
    File country;



    public Osm2GAULConnector(String[] args, File country){
        this.gaulMap = new HashMap<>();
        this.osmMap = new HashMap<>();
        this.osm2gaulMap = new HashMap<>();
        this.gaul2osmMap = new HashMap<>();
        this.geoMap = new HashMap<>();
        this.levelsMap = new HashMap<>();
        this.osmLevelGroup = new HashMap<>();
        this.gaulLevelGroup = new HashMap<>();
        this.linkedEntities = new HashMap<>();

        this.type = args[0];
        this.osmFile = args[1];

        this.linkingFiles = new String[3];
        this.linkingFiles[0] = args[2];
        if(type.equals("normal") || type.equals("one_adm:1")) {
            this.linkingFiles[1] = args[3];
            this.linkingFiles[2] = args[4];
        }
        else if(type.equals("one_adm")){
            this.linkingFiles[1] = args[3];
            this.linkingFiles[2] = null;
        }
        else{
            this.linkingFiles[1] = null;
            this.linkingFiles[2] = null;
        }

        this.osmLevelsFile = args[5];
        this.gaulFile = args[6];

        //OSM directory
        this.country = country;
    }


    /***
     * TODO:
     * 1) Connect osm and gaul through the csv file
     * 2) Begin a recursive process to properly index lower osm levels with gaul. This has three steps:
     *      - First find using intersection threshold where admin units with no wikidata link belong
     *      - Intersect all current level administrative units with their neighbours so they all touch instead of overlapping
     *      - After the geometries are corrected locally, correct them with the upper unit, so that all current units belonging to
     *      a higher level upper unit are completely covered by it
     * 3) Do the above process recursively, beginning with the highest osm level not present in gaul
     * and finishing when no more osm levels are present
     * 4) Combine all the osm and gaul knowledge alongside the corrected geometries to create a complete administrative mapping of the country
    ***/

    //Step 0 - preprocessing
    //Collect all gaul and osm triples and create the geometry maps
    public void process(){
        collectOSMTriples();
        collectGAULTriples();
        loadMappings(this.linkingFiles);
        resolveMappings();
        integrate();
    }


    //Connect osm with gaul through the csv files for level1 and level2 GAUL admin levels
    public void loadMappings(String ... csvFiles){
        //Build the mapping from osm -> gaul
        for(String file:csvFiles){
            if(file!=null) {
                try {
                    BufferedReader reader = new BufferedReader(new FileReader(file));
                    reader.readLine();
                    String line = reader.readLine();
                    while (line != null) {
                        String[] columns = line.split(",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", -1);
                        osm2gaulMap.put(columns[2], columns[0]);
                        gaul2osmMap.put(columns[0], columns[2]);
                        line = reader.readLine();
                    }
                    reader.close();
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
        }
    }

    public void integrate(){
        GeospatialGraph graphHierarchy = new GeospatialGraph();
        graphHierarchy.buildForHierarchy(osmMap,osmLevelGroup,osm2gaulMap,levelsMap,geoMap);

        HashMap<String,String> discovered = graphHierarchy.getDiscovered();

        try {
            File gaulFile = new File(this.gaulFile);

            //Create file output for all data in the country
            BufferedWriter allOSMWriter = new BufferedWriter(new FileWriter(country.getAbsolutePath()+"/" + country.getName() + "_all.nt"));
            BufferedWriter allGAULWriter = new BufferedWriter(new FileWriter(gaulFile.getParentFile().getAbsolutePath() + "/" + country.getName() + "_all.nt"));

            for (Map.Entry<String, String> levelEntry : levelsMap.entrySet()) {

                //GAUL creation
                HashSet<String> gaulGroup = gaulLevelGroup.get(levelEntry.getValue());
                if(isGaulCandidate(levelEntry.getValue()) && gaulGroup!=null) {
                    BufferedWriter gaulWriter = new BufferedWriter(new FileWriter(gaulFile.getParentFile().getAbsolutePath() + "/" + country.getName() + "_" + levelEntry.getValue() + ".nt"));
                    for (String s : gaulGroup) {
                        String entity = s;

                        //If upper level unit was discovered for entity
                        if (discovered.containsKey(entity)) {
                            String o = discovered.remove(entity);
                            gaulWriter.write(entity + " <" + Constants.URI + "hasUpperAdminUnit> " + o + " .\n");
                            allGAULWriter.write(entity + " <" + Constants.URI + "hasUpperAdminUnit> " + o + " .\n");
                        }

                        List<Pair<String, String>> triples = gaulMap.remove(entity);
                        if (triples == null) {
                            triples = gaulMap.get(linkedEntities.get(s));
                            entity = linkedEntities.get(s);
                        }

                        if(triples==null && levelEntry.getValue().equals("0"))
                            continue;

                        for (Pair<String, String> pair : triples) {
                            String p = pair.getLeft();
                            String o = pair.getRight();
                            if (p.contains("hasUpperAdminUnit")) {
                                o = linkedEntities.get(entity);
                                if (o == null) o = pair.getRight();
                            }
                            gaulWriter.write(entity + " " + p + " " + o + " .\n");
                            allGAULWriter.write(entity + " " + p + " " + o + " .\n");
                        }


                        Pair<String, String> geomPair = geoMap.remove(entity);
                        if (geomPair == null) {
                            geomPair = geoMap.remove(s);
                            String geoURI = createGeometryLinkedURI(s, gaul2osmMap.get(s));
                            String geom = prepareGeometry(geomPair.getRight());

                            gaulWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geoURI + " .\n");
                            gaulWriter.write(geoURI + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");
                            allGAULWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geoURI + " .\n");
                            allGAULWriter.write(geoURI + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");
                        }
                        else {
                            String geom = prepareGeometry(geomPair.getRight());
                            gaulWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geomPair.getLeft() + " .\n");
                            gaulWriter.write(geomPair.getLeft() + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");
                            allGAULWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geomPair.getLeft() + " .\n");
                            allGAULWriter.write(geomPair.getLeft() + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");
                        }
                    }
                    gaulWriter.close();
                }

                //OSM creation
                if(type.equals("one_adm:1") && levelEntry.getValue().equals("1"))
                    continue;

                HashSet<String> osmGroup = osmLevelGroup.get(levelEntry.getKey());
                if(osmGroup==null) continue;

                BufferedWriter osmWriter = new BufferedWriter(new FileWriter(country.getAbsolutePath()+"/" + country.getName() + "_" + levelEntry.getValue() + ".nt"));
                HashSet<String> addedLevel = new HashSet<>();

                for(String s: osmGroup){
                    String entity = s;

                    //If upper level unit was discovered for entity
                    if(discovered.containsKey(entity)){
                        String o = discovered.remove(entity);
                        osmWriter.write(entity + " <" + Constants.URI + "hasUpperAdminUnit> " + o + " .\n");
                        allOSMWriter.write(entity + " <" + Constants.URI + "hasUpperAdminUnit> " + o + " .\n");
                    }

                    List<Pair<String,String>> triples = osmMap.remove(entity);
                    if(triples==null){
                        triples = osmMap.get(linkedEntities.get(s));
                        entity = linkedEntities.get(s);
                    }

                    for(Pair<String,String> pair: triples){
                        String p = pair.getLeft();
                        String o = pair.getRight();
                        if(p.contains("hasUpperAdminUnit")){
                            o = linkedEntities.get(entity);
                            if(o==null) o = pair.getRight();
                        }
                        osmWriter.write(entity + " " + p + " " + o + " .\n");
                        allOSMWriter.write(entity + " " + p + " " + o + " .\n");
                    }

                    if(Integer.parseInt(levelEntry.getValue())>=3){
                        if(!addedLevel.contains(entity)){
                            addedLevel.add(entity);
                            osmWriter.write(entity + " <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <" + Constants.URI + "AdminUnit_Level"+levelEntry.getValue()+"> .\n");
                            allOSMWriter.write(entity + " <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <" + Constants.URI + "AdminUnit_Level"+levelEntry.getValue()+"> .\n");
                        }
                    }

                    Pair<String,String> geomPair = geoMap.remove(entity);
                    if(geomPair==null){
                        geomPair = geoMap.remove(s);
                        String geoURI = createGeometryLinkedURI(osm2gaulMap.get(s),s);
                        String geom = prepareGeometry(geomPair.getRight());

                        osmWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geoURI + " .\n");
                        osmWriter.write(geoURI + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");

                        allOSMWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geoURI + " .\n");
                        allOSMWriter.write(geoURI + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");
                    }
                    else{
                        String geom = prepareGeometry(geomPair.getRight());
                        osmWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geomPair.getLeft() + " .\n");
                        osmWriter.write(geomPair.getLeft() + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");

                        allOSMWriter.write(entity + " <http://www.opengis.net/ont/geosparql#hasGeometry> " + geomPair.getLeft() + " .\n");
                        allOSMWriter.write(geomPair.getLeft() + " <http://www.opengis.net/ont/geosparql#asWKT> " + geom + " .\n");
                    }
                }

                osmWriter.close();
            }

            allGAULWriter.close();
            allOSMWriter.close();
        }
        catch (IOException e){
            e.printStackTrace();
        }
    }

    private void resolveMappings(){
        HashMap<String,String> gaulLevelsMap = GeospatialGraph.mirrorMap(levelsMap);
        String[] levels = new String[3];
        if(type.equals("normal")){
            levels[0] = "0";
            levels[1] = "1";
            levels[2] = "2";
        }
        else if(type.equals("one_adm")){
            levels[0] = "0";
            levels[1] = "1";
        }
        else if(type.equals("one_adm:1")){
            levels[0] = "0";
            levels[1] = null;
            levels[2] = "2";
        }
        else if (type.equals("single")){
            levels[0] = "0";
        }

        for(String level: levels){
            if(level!=null){
                HashSet<String> entities = gaulLevelGroup.get(level);
                for(String gaulEntity: entities){
                    //linked entities
                    String osmEntity = this.gaul2osmMap.get(gaulEntity);
                    if(osmEntity!=null) {
                        String linkedURI = createLinkedURI(gaulEntity, osmEntity);
                        this.linkedEntities.put(osmEntity, linkedURI);
                        this.linkedEntities.put(gaulEntity, linkedURI);

                        List<Pair<String, String>> gaulTriples = gaulMap.remove(gaulEntity);
                        List<Pair<String, String>> osmTriples = osmMap.remove(osmEntity);

                        if(osmTriples==null) {
                            if(level.equals("0")) continue;
                            else System.out.println(osmEntity + " " + level);
                        }


                        List<Pair<String, String>> linkedTriples = new ArrayList<>();
                        linkedTriples.addAll(gaulTriples);

                        for (Pair<String, String> pair : osmTriples) {
                            String p = pair.getLeft();
                            String o = pair.getRight();
                            if (p.contains("Name") || p.contains("name")) {
                                if (p.contains("hasName>")) linkedTriples.add(pair);
                                if (p.contains("hasNameEn>")) {
                                    p = "<" + Constants.URI + "hasName>";
                                    o = o + "@en";
                                    linkedTriples.add(new ImmutablePair<>(p, o));
                                }
                            } else
                                linkedTriples.add(pair);
                        }

                        gaulMap.put(linkedURI, linkedTriples);
                        osmMap.put(linkedURI, linkedTriples);
                    }

                }
            }
        }
    }



    /************************* HELPER METHODS **************************/

    private void collectOSMTriples(){
        try{
            BufferedReader reader = new BufferedReader(new FileReader(osmLevelsFile));
            reader.readLine();
            String line=reader.readLine();
            while(line!=null){
                String[] tokens = line.split(",");
                this.levelsMap.put(tokens[1],tokens[0]);
                line = reader.readLine();
            }
            reader.close();


            FileInputStream is = new FileInputStream(osmFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);
            HashMap<String,String> geoentityMap = new HashMap<>();
            HashSet<String> nonValidLevels = new HashSet<>();

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(p.contains("hasWikipediaURL"))
                    o = o.replaceAll(" ","_");

                if(p.contains("hasOSMLevel")){
                    //Remove non valid levels
                    if(!levelsMap.containsKey(o.replaceAll("\"",""))){
                        nonValidLevels.add(s);
                        this.geoMap.remove(s);
                        this.osmMap.remove(s);
                    }

                    //Group osm entities by their level
                    HashSet<String> value = this.osmLevelGroup.get(o.replaceAll("\"",""));
                    if(value==null){
                        value = new HashSet<>();
                    }
                    value.add(s);
                    this.osmLevelGroup.put(o.replaceAll("\"",""),value);
                }

                if(!nonValidLevels.contains(s)) {
                    if (p.contains("hasGeometry")) {
                        geoentityMap.put(o, s);
                    } else if (p.contains("asWKT")) {
                        String entity = geoentityMap.get(s);
                        this.geoMap.put(entity, new ImmutablePair<>(s, o));
                    } else {
                        List<Pair<String, String>> value = osmMap.get(s);
                        if (value == null)
                            value = new ArrayList<>();
                        value.add(new ImmutablePair<>(p, o));
                        osmMap.put(s,value);
                    }
                }

            }
        }
        catch (IOException e){
            e.printStackTrace();
        }
    }

    private void collectGAULTriples(){
        try{
            FileInputStream is = new FileInputStream(gaulFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);
            HashMap<String,String> geoentityMap = new HashMap<>();

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(o.contains("AdminUnit_Level")){
                    String key;
                    if(o.contains("0")) key = "0";
                    else if(o.contains("1")) key = "1";
                    else key= "2";

                    HashSet<String> set = this.gaulLevelGroup.get(key);
                    if(set==null)
                        set = new HashSet<>();
                    set.add(s);
                    this.gaulLevelGroup.put(key,set);

                }

                if (p.contains("hasGeometry")) {
                    geoentityMap.put(o, s);
                } else if (p.contains("asWKT")) {
                    String entity = geoentityMap.get(s);
                    this.geoMap.put(entity, new ImmutablePair<>(s, o));
                } else {
                    List<Pair<String, String>> value = gaulMap.get(s);
                    if (value == null)
                        value = new ArrayList<>();
                    value.add(new ImmutablePair<>(p, o));
                    gaulMap.put(s,value);
                }

            }
        }
        catch (IOException e){
            e.printStackTrace();
        }
    }

    private String createLinkedURI(String gaulEntity,String osmEntity){
        gaulEntity = gaulEntity.replaceAll("[<>]", "");
        osmEntity = osmEntity.replaceAll("[<>]", "");

        String[] gaulParts = gaulEntity.split("_");
        String[] osmParts = osmEntity.split("_");
        String gaulId = gaulParts[gaulParts.length-1];
        String osmID;
        if(osmParts.length==4)
            osmID = "no_" + osmParts[osmParts.length-1];
        else
            osmID = osmParts[osmParts.length-1];

        return "<" + Constants.RESOURCE + gaulParts[1] + "_" + gaulId + "_" + osmID + ">";
    }

    private String createGeometryLinkedURI(String gaulEntity,String osmEntity){
        gaulEntity = gaulEntity.substring(1,gaulEntity.length()-1);
        osmEntity = osmEntity.substring(1,osmEntity.length()-1);

        String[] gaulParts = gaulEntity.split("_");
        String[] osmParts = osmEntity.split("_");
        String gaulId = gaulParts[gaulParts.length-1];
        String osmID;
        if(osmParts.length==5)
            osmID = "no_" + osmParts[osmParts.length-1];
        else
            osmID = osmParts[osmParts.length-1];

        return "<" + Constants.RESOURCE + "Geometry_" + gaulParts[1] + "_" + gaulId + "_" + osmID + ">";
    }

    private String prepareGeometry(String geom){
        if(!geom.contains("<http://www.opengis.net/def/crs/EPSG/0/4326>")) {
            geom = "\"<http://www.opengis.net/def/crs/EPSG/0/4326> " + geom
                    + "\"^^<http://www.opengis.net/ont/geosparql#wktLiteral>";
        }

        if(geom.endsWith("<http://www"))
            geom = geom.replaceAll("<http://www","<http://www.opengis.net/ont/geosparql#wktLiteral>");
        if(geom.endsWith("<http://www.opengis"))
            geom = geom.replaceAll("<http://www.opengis","<http://www.opengis.net/ont/geosparql#wktLiteral>");
        if(geom.contains("<http://www.opengis.net/ont/geosparql#wktLiteral>.net/def/crs/EPSG/0/4326>"))
            geom = geom.replaceAll("<http://www.opengis.net/ont/geosparql#wktLiteral>.net/def/crs/EPSG/0/4326>","<http://www.opengis.net/def/crs/EPSG/0/4326>");
        if(geom.contains("<http://www.opengis.net/ont/geosparql#wktLiteral>.opengis.net/def/crs/EPSG/0/4326>"))
            geom = geom.replaceAll("<http://www.opengis.net/ont/geosparql#wktLiteral>.opengis.net/def/crs/EPSG/0/4326>","<http://www.opengis.net/def/crs/EPSG/0/4326>");

        return geom;
    }

    private boolean isGaulCandidate(String level){
        if(type.equals("normal") || type.equals("one_adm:1") || type.equals("ignore")) {
            return (level.equals("0") || level.equals("1") || level.equals("2"));
        }
        else if(type.equals("one_adm")){
            return (level.equals("0") || level.equals("1"));
        }
        else if(type.equals("single")){
            return level.equals("0");
        }

        return false;
    }
}
