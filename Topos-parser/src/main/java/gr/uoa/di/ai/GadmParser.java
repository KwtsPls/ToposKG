package gr.uoa.di.ai;

import gr.uoa.di.ai.transformers.GeoJsonToWktTransformer;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import java.io.BufferedWriter;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;

public class GadmParser {
    GeoJsonToWktTransformer transformer;

    public GadmParser(){
        transformer = new GeoJsonToWktTransformer();
    }

    public void parseZeroLevel(String path, String output){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String triples = parseZeroLevel(geoItem);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    public void parse1stLevel(String path, String output){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String triples = parse1stLevel(geoItem);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    public void parse2ndLevel(String path, String output){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String triples = parse2ndLevel(geoItem);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private String parse2ndLevel(JSONObject jo){
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        String[] name_1_tokens = (((String) properties.get("NAME_1")).replaceAll("-","_")).split("(?=\\p{Lu})");
        String name_1 = String.join("_",name_1_tokens);

        String[] name_2_tokens = (((String) properties.get("NAME_2")).replaceAll("-","_")).split("(?=\\p{Lu})");
        String name_2 = String.join("_",name_2_tokens);

        String[] type_tokens = ((String) properties.get("TYPE_2")).split("(?=\\p{Lu})");
        String type = String.join("_",type_tokens);

        String id = name_2 + "_" + type + ",_" + name_1;

        builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "GADM_3rdOrder_AdministrativeUnit"));


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_Description", type));

        String gadm_id = (String) properties.get("GID_2");
        if(gadm_id!=null) builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_ID", gadm_id));


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_Name", name_2.replaceAll("_"," ")));
        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_NationalLevel", "3rdOrder"));

        String upperLevel = (String) properties.get("GID_1");
        if(gadm_id!=null) builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_UpperLevelUnit", upperLevel));

        builder.append(createTriple(Constants.RESOURCE + id, Constants.WIKIPRED, Constants.WIKILINK+id));

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            builder.append(createDoubleTriple(Constants.RESOURCE + id,Constants.URI+"hasArea", String.valueOf(area)));

            String wkt = transformer.transformGeoJson(geometry,4326);
            builder.append(createGeometry(id,wkt));
        }

        return builder.toString();
    }

    private String parse1stLevel(JSONObject jo){
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        String[] name_1_tokens = (((String) properties.get("NAME_1")).replaceAll("-","_")).split("(?=\\p{Lu})");
        String id = String.join("_",name_1_tokens);

        String[] type_tokens = ((String) properties.get("TYPE_1")).split("(?=\\p{Lu})");
        String type = String.join("_",type_tokens);

        builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "GADM_2ndOrder_AdministrativeUnit"));


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_Description", type));

        String gadm_id = (String) properties.get("GID_1");
        if(gadm_id!=null) builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_ID", gadm_id));


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_Name", id.replaceAll("_"," ")));
        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_NationalLevel", "2ndOrder"));

        String upperLevel = (String) properties.get("GID_0");
        if(gadm_id!=null) builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_UpperLevelUnit", upperLevel));

        builder.append(createTriple(Constants.RESOURCE + id, Constants.WIKIPRED, Constants.WIKILINK+id));

        if(jo.get("geometry")!=null){
            String geometry = jo.get("geometry").toString();

            Double area = transformer.getArea(geometry);
            builder.append(createDoubleTriple(Constants.RESOURCE + id,Constants.URI+"hasArea", String.valueOf(area)));

            String wkt = transformer.transformGeoJson(geometry,4326);
            builder.append(createGeometry(id,wkt));
        }

        return builder.toString();
    }


    private String parseZeroLevel(JSONObject jo){
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        String[] name_0_tokens = (((String) properties.get("COUNTRY")).replaceAll("-","_")).split("(?=\\p{Lu})");
        String id = String.join("_",name_0_tokens);

        builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "GADM_1stOrder_AdministrativeUnit"));


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_Description", "Country"));

        String gadm_id = (String) properties.get("GID_0");
        if(gadm_id!=null) builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_ID", gadm_id));


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_Name", id.replaceAll("_"," ")));
        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasGADM_NationalLevel", "1stOrder"));

        builder.append(createTriple(Constants.RESOURCE + id, Constants.WIKIPRED, Constants.WIKILINK+id));

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
