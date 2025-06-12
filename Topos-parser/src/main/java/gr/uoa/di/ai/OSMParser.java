package gr.uoa.di.ai;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import gr.uoa.di.ai.transformers.GeoJsonToWktTransformer;
import org.apache.commons.lang3.StringUtils;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import java.io.*;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;

public class OSMParser {
    GeoJsonToWktTransformer transformer;

    public OSMParser(){
        transformer = new GeoJsonToWktTransformer();
    }

    public void parse(String path, String output, String prefix){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String id = "osm_" + prefix + "_" + i;
                String triples = parse(geoItem,id);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private String parse(JSONObject jo, String id) throws JsonProcessingException {
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        ObjectMapper mapper = new ObjectMapper();
        JsonNode propertiesNode = mapper.readTree(properties.toJSONString());

        if (propertiesNode != null && propertiesNode.isObject()) {
            Iterator<Map.Entry<String, JsonNode>> fields = propertiesNode.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();

                if(field.getKey().toString().equals("admin_level"))
                    builder.append(createStringTriple(Constants.RESOURCE + id,Constants.URI+"hasOSMLevel", field.getValue().asText()));
                else if(field.getKey().toString().equals("wikidata"))
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikidataLink","http://www.wikidata.org/entity/"+field.getValue().asText()));
                else if(field.getKey().toString().equals("wikipedia")) {
                    String[] tokens = field.getValue().asText().split(":");
                    String locale;
                    String entity;
                    if(tokens.length>1) {
                        locale = tokens[0];
                        entity = tokens[1].replaceAll(" ","_");
                    }
                    else{
                        locale = "en";
                        entity = field.getValue().asText().replaceAll("\"","'").replaceAll(" ","_");
                    }
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikipediaURL", "https://"+locale+".wikipedia.org/wiki/"+entity));
                }
                else{

                    String key = field.getKey();
                    String[] tokens = key.split(":");
                    StringBuilder uriKey = new StringBuilder("has");
                    for(String token:tokens){
                        uriKey.append(token.substring(0, 1).toUpperCase()).append(token.substring(1));
                    }
                    builder.append(createStringTriple(Constants.RESOURCE + id,Constants.URI + uriKey,field.getValue().asText().replaceAll("\"","'")));
                }

            }
        }

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            builder.append(createDoubleTriple(Constants.RESOURCE + id,Constants.URI+"hasArea", String.valueOf(area)));

            String wkt = transformer.transformGeoJson(geometry,4326);
            builder.append(createGeometry(id,wkt));
        }

        return builder.toString();
    }


    // WATERBODIES PARSING
    public void parseWater(String path, String output, String prefix){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String id = "osm_water_" + prefix + "_" + i;
                String triples = parseWater(geoItem,id);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private String parseWater(JSONObject jo, String id) throws JsonProcessingException {
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        ObjectMapper mapper = new ObjectMapper();
        JsonNode propertiesNode = mapper.readTree(properties.toJSONString());

        if (propertiesNode != null && propertiesNode.isObject()) {
            Iterator<Map.Entry<String, JsonNode>> fields = propertiesNode.fields();
            builder.append(createTriple(Constants.RESOURCE + id,"http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "Waterbody" ));
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();

                if(field.getKey().toString().equals("water"))
                    builder.append(createTriple(Constants.RESOURCE + id,"http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + StringUtils.capitalize(field.getValue().asText())) );
                else if(field.getKey().toString().equals("wikidata"))
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikidataLink","http://www.wikidata.org/entity/"+field.getValue().asText()));
                else if(field.getKey().toString().equals("wikipedia")) {
                    String[] tokens = field.getValue().asText().split(":");
                    String locale;
                    String entity;
                    if(tokens.length>1) {
                        locale = tokens[0];
                        entity = tokens[1].replaceAll(" ","_");
                    }
                    else{
                        locale = "en";
                        entity = field.getValue().asText().replaceAll("\"","'").replaceAll(" ","_");
                    }
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikipediaURL", "https://"+locale+".wikipedia.org/wiki/"+entity));
                }
                else{

                    String key = field.getKey();
                    String[] tokens = key.split("[:_]+");
                    StringBuilder uriKey = new StringBuilder("has");
                    for(String token:tokens){
                        if(token.length()>1)
                            uriKey.append(token.substring(0, 1).toUpperCase()).append(token.substring(1));
                    }

                    String entryKey = uriKey.toString().toLowerCase();
                    if(entryKey.contains("name") || entryKey.contains("natural")){
                        if(entryKey.equals("hasname"))
                            builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'")));
                        if(entryKey.equals("hasnameen"))
                            builder.append(createLanguageTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'"), "en"));
                    }
                    else {
                        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'")));
                    }
                }

            }
        }

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            builder.append(createDoubleTriple(Constants.RESOURCE + id,Constants.URI+"hasArea", String.valueOf(area)));

            String wkt = transformer.transformGeoJson(geometry,4326);
            builder.append(createGeometry(id,wkt));
        }

        return builder.toString();
    }


    // PARSING FOR POIS
    public void parsePoi(String path, String output, String prefix){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String id = "osm_poi_" + prefix + "_" + i;
                String triples = parsePoi(geoItem,id);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private String parsePoi(JSONObject jo, String id) throws JsonProcessingException {
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        ObjectMapper mapper = new ObjectMapper();
        JsonNode propertiesNode = mapper.readTree(properties.toJSONString());

        if (propertiesNode != null && propertiesNode.isObject()) {
            Iterator<Map.Entry<String, JsonNode>> fields = propertiesNode.fields();
            builder.append(createTriple(Constants.RESOURCE + id,"http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "POI" ));
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();

                if(field.getKey().toString().equals("amenity"))
                    builder.append(createTriple(Constants.RESOURCE + id,"http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + StringUtils.capitalize(field.getValue().asText())) );
                else if(field.getKey().toString().equals("wikidata"))
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikidataLink","http://www.wikidata.org/entity/"+field.getValue().asText()));
                else if(field.getKey().toString().equals("wikipedia")) {
                    String[] tokens = field.getValue().asText().split(":");
                    String locale;
                    String entity;
                    if(tokens.length>1) {
                        locale = tokens[0];
                        entity = tokens[1].replaceAll(" ","_");
                    }
                    else{
                        locale = "en";
                        entity = field.getValue().asText().replaceAll("\"","'").replaceAll(" ","_");
                    }
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikipediaURL", "https://"+locale+".wikipedia.org/wiki/"+entity));
                }
                else{

                    String key = field.getKey();
                    String[] tokens = key.split("[:_]+");
                    StringBuilder uriKey = new StringBuilder("has");
                    for(String token:tokens){
                        if(token.length()>1)
                            uriKey.append(token.substring(0, 1).toUpperCase()).append(token.substring(1));
                    }

                    String entryKey = uriKey.toString().toLowerCase();
                    if(entryKey.contains("name")){
                        if(entryKey.equals("hasname"))
                            builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'")));
                        if(entryKey.equals("hasnameen"))
                            builder.append(createLanguageTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'"), "en"));
                    }
                    else {
                        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'")));
                    }
                }

            }
        }

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            builder.append(createDoubleTriple(Constants.RESOURCE + id,Constants.URI+"hasArea", String.valueOf(area)));

            String wkt = transformer.transformGeoJson(geometry,4326);
            builder.append(createGeometry(id,wkt));
        }

        return builder.toString();
    }


    // PARSING FOR FORESTS
    public void parseForest(String path, String output, String prefix){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String id = "osm_forest_" + prefix + "_" + i;
                String triples = parseForest(geoItem,id);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private String parseForest(JSONObject jo, String id) throws JsonProcessingException {
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        ObjectMapper mapper = new ObjectMapper();
        JsonNode propertiesNode = mapper.readTree(properties.toJSONString());

        if (propertiesNode != null && propertiesNode.isObject()) {
            Iterator<Map.Entry<String, JsonNode>> fields = propertiesNode.fields();
            builder.append(createTriple(Constants.RESOURCE + id,"http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "Forest" ));
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();

                if(field.getKey().toString().equals("wikidata"))
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikidataLink","http://www.wikidata.org/entity/"+field.getValue().asText()));
                else if(field.getKey().toString().equals("wikipedia")) {
                    String[] tokens = field.getValue().asText().split(":");
                    String locale;
                    String entity;
                    if(tokens.length>1) {
                        locale = tokens[0];
                        entity = tokens[1].replaceAll(" ","_");
                    }
                    else{
                        locale = "en";
                        entity = field.getValue().asText().replaceAll("\"","'").replaceAll(" ","_");
                    }
                    builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasWikipediaURL", "https://"+locale+".wikipedia.org/wiki/"+entity));
                }
                else{

                    String key = field.getKey();
                    String[] tokens = key.split("[:_]+");
                    StringBuilder uriKey = new StringBuilder("has");
                    for(String token:tokens){
                        if(token.length()>1)
                            uriKey.append(token.substring(0, 1).toUpperCase()).append(token.substring(1));
                    }

                    String entryKey = uriKey.toString().toLowerCase();
                    if(entryKey.contains("name")){
                        if(entryKey.equals("hasname"))
                            builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'")));
                        if(entryKey.equals("hasnameen"))
                            builder.append(createLanguageTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'"), "en"));
                    }
                    else {
                        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + uriKey, field.getValue().asText().replaceAll("\"", "'")));
                    }
                }

            }
        }

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            builder.append(createDoubleTriple(Constants.RESOURCE + id,Constants.URI+"hasArea", String.valueOf(area)));

            String wkt = transformer.transformGeoJson(geometry,4326);
            builder.append(createGeometry(id,wkt));
        }

        return builder.toString();
    }




    private String createTriple(String subject, String predicate, String object){
        return "<"+subject + "> <" + predicate + "> <" + object + "> .\n";
    }

    private String createStringTriple(String subject, String predicate, String object){
        return "<"+subject + "> <" + predicate + "> \"" + object + "\" .\n";
    }

    private String createLanguageTriple(String subject, String predicate, String object, String locale){
        return "<"+subject + "> <" + predicate + "> \"" + object + "\"@" + locale + " .\n";
    }

    private String createIntTriple(String subject, String predicate, String object){
        return "<"+subject + "> <" + predicate + "> \"" + object + "\"^^<http://www.w3.org/2001/XMLSchema#integer> .\n";
    }

    private String createDoubleTriple(String subject, String predicate, String object){
        return "<"+subject + "> <" + predicate + "> \"" + object + "\"^^<http://www.w3.org/2001/XMLSchema#double> .\n";
    }

    private String createGeometry(String id, String wkt){
        String triples = "<"+Constants.RESOURCE+id+"> <http://www.opengis.net/ont/geosparql#hasGeometry> <"+Constants.RESOURCE+"Geometry_"+id+"> .\n";
        triples += "<"+Constants.RESOURCE+"Geometry_"+id+"> <http://www.opengis.net/ont/geosparql#asWKT> " +
                "\"<http://www.opengis.net/def/crs/EPSG/0/4326> " + wkt +"\"^^<http://www.opengis.net/ont/geosparql#wktLiteral> .\n";
        return triples;
    }
}
