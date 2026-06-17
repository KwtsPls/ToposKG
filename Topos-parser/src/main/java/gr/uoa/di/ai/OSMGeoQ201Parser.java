package gr.uoa.di.ai;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import gr.uoa.di.ai.transformers.GeoJsonToWktTransformer;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;
import com.fasterxml.jackson.core.*;
import com.fasterxml.jackson.databind.*;

import java.io.*;
import java.util.Iterator;
import java.util.Map;

public class OSMGeoQ201Parser {
    GeoJsonToWktTransformer transformer;
    String RESOURCE = "https://www.openstreetmap.org/resource/";
    String URI = "https://www.openstreetmap.org/ontology/";

    public OSMGeoQ201Parser(){
        transformer = new GeoJsonToWktTransformer();
    }

    public void parse(String path, String output, String prefix) {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(output));
             JsonParser parser = new JsonFactory().createParser(new File(path))) {

            ObjectMapper mapper = new ObjectMapper();
            int i = 0;

            // Move to the "features" array
            while (!parser.isClosed()) {
                JsonToken token = parser.nextToken();
                if (JsonToken.FIELD_NAME.equals(token) && "features".equals(parser.getCurrentName())) {
                    parser.nextToken(); // Move to START_ARRAY
                    break;
                }
            }

            JSONParser simpleParser = new JSONParser();

            // Now iterate through array elements
            while (parser.nextToken() == JsonToken.START_OBJECT) {
                // Read one object from the stream
                JsonNode geoItem = mapper.readTree(parser);

                // Convert JsonNode → String → JSONObject
                JSONObject geoObject = null;
                try {
                    geoObject = (JSONObject) simpleParser.parse(geoItem.toString());
                } catch (ParseException e) {
                    e.printStackTrace();
                    continue; // skip malformed items
                }

                String id = "osm_" + prefix + "_" + i++;
                String triples = parse(geoObject, id); // your method using JSONObject
                if (triples != null)
                    writer.write(triples);
            }

        } catch (IOException e) {
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

                //Airport class
                if(field.getKey().toString().equals("aeroway") && field.getValue().asText().equals("aerodrome"))
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI+"Airport"));
                //Building class and subclasses
                else if(field.getKey().toString().equals("building")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Building"));
                    if(field.getValue().asText().equals("church"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Church"));
                    else if(field.getValue().asText().equals("mosque"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Mosque"));
                    else if(field.getValue().asText().equals("temple"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Temple"));
                    else if(field.getValue().asText().equals("university"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "University"));

                }
                //Waterway classes
                else if(field.getKey().toString().equals("waterway")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Waterway"));
                    if(field.getValue().asText().equals("canal"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Canal"));
                    else if(field.getValue().asText().equals("dam"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Dam"));
                    else if(field.getValue().asText().equals("river"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "River"));
                    else if(field.getValue().asText().equals("stream"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Stream"));
                }
                //Historic Classes
                else if(field.getKey().toString().equals("historic")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Historic"));
                    if(field.getValue().asText().equals("castle"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Castle"));
                    else if(field.getValue().asText().equals("memorial"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Memorial"));
                    else if(field.getValue().asText().equals("monument"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Monument"));
                    else if(field.getValue().asText().equals("archaeological_site"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Archaeological"));
                }
                //Amenity Classes
                else if(field.getKey().toString().equals("amenity")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Amenity"));
                    if(field.getValue().asText().equals("grave_yard"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Cemetery"));
                    else if(field.getValue().asText().equals("college"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "College"));
                    else if(field.getValue().asText().equals("hospital"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Hospital"));
                    else if(field.getValue().asText().equals("library"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Library"));
                    else if(field.getValue().asText().equals("prison"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Prison"));
                    else if(field.getValue().asText().equals("restaurant"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Restaurant"));
                    else if(field.getValue().asText().equals("school"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "School"));
                    else if(field.getValue().asText().equals("theatre"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Theatre"));
                    else if(field.getValue().asText().equals("parking"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Parking"));
                    else if(field.getValue().asText().equals("fuel"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Fuel"));
                    else if(field.getValue().asText().equals("cafe"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Cafe"));
                    else if(field.getValue().asText().equals("pub"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Pub"));
                    else if(field.getValue().asText().equals("pharmacy"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Pharmacy"));
                    else if(field.getValue().asText().equals("bar"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "bar"));
                }
                //Landuse classes
                else if(field.getKey().toString().equals("landuse")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Landuse"));
                    if(field.getValue().asText().equals("cemetery"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Cemetery"));
                    else if(field.getValue().asText().equals("forest"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Forest"));
                    else if(field.getValue().asText().equals("residential"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Residential"));
                }
                //Place class and subclasses
                else if(field.getKey().toString().equals("place")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Place"));
                    if(field.getValue().asText().equals("city"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "City"));
                    else if(field.getValue().asText().equals("island"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Island"));
                    else if(field.getValue().asText().equals("region"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Region"));
                    else if(field.getValue().asText().equals("town"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Town"));
                    else if(field.getValue().asText().equals("village"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Village"));
                }
                //Natural classes
                else if(field.getKey().toString().equals("natural")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Natural"));
                    if(field.getValue().asText().equals("wood"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Forest"));
                    else if(field.getValue().asText().equals("glacier"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Glacier"));
                }
                //Leisure classes
                else if(field.getKey().toString().equals("leisure")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Leisure"));
                    if(field.getValue().asText().equals("golf_course"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Golfcourse"));
                    else if(field.getValue().asText().equals("park"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Park"));
                    else if(field.getValue().asText().equals("stadium"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Stadium"));
                }
                //Tourism classes
                else if(field.getKey().toString().equals("tourism")) {
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Tourism"));
                    if(field.getValue().asText().equals("hotel"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Hotel"));
                    else if(field.getValue().asText().equals("museum"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Museum"));
                    else if(field.getValue().asText().equals("zoo"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Zoo"));
                    else if(field.getValue().asText().equals("attraction"))
                        builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI + "Attraction"));
                }
                //Railway class
                else if(field.getKey().toString().equals("railway") && field.getValue().asText().equals("station"))
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI+"Railway_Station"));
                //Tower class
                else if(field.getKey().toString().equals("man_made") && field.getValue().asText().equals("tower"))
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI+"Tower"));
                //Supermarket class
                else if(field.getKey().toString().equals("shop") && field.getValue().asText().equals("supermarket"))
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI+"Supermarket"));
                //Bridge class
                else if(field.getKey().toString().equals("bridge"))
                    builder.append(createTriple(RESOURCE + id, Constants.RDF + "type", URI+"Bridge"));


                //Name property
                if(field.getKey().toString().equals("name"))
                    builder.append(createStringTriple(RESOURCE + id, URI + "has_name", field.getValue().asText().
                            replaceAll("\"","").replaceAll("\\\\","\\\\\\\\")));

                if(field.getKey().toString().equals("wikidata"))
                    builder.append(createTriple(RESOURCE + id, URI + "hasWikidataLink","http://www.wikidata.org/entity/"+field.getValue().asText()));
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
                    builder.append(createTriple(RESOURCE + id, URI + "hasWikipediaURL", "https://"+locale+".wikipedia.org/wiki/"+entity.replaceAll("\\\\","")));
                }

            }
        }

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            if(area!=0.0)
                builder.append(createDoubleTriple(RESOURCE + id,URI+"hasArea", String.valueOf(area)));

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
        String triples = "<"+RESOURCE+id+"> <http://www.opengis.net/ont/geosparql#hasGeometry> <"+RESOURCE+"Geometry_"+id+"> .\n";
        triples += "<"+RESOURCE+"Geometry_"+id+"> <http://www.opengis.net/ont/geosparql#asWKT> " +
                "\"<http://www.opengis.net/def/crs/EPSG/0/4326> " + wkt +"\"^^<http://www.opengis.net/ont/geosparql#wktLiteral> .\n";
        return triples;
    }
}
