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

public class OCHAParser {
    GeoJsonToWktTransformer transformer;

    public OCHAParser(){
        transformer = new GeoJsonToWktTransformer();
    }

    public void parse(String path, String output, int level){
        Object obj = null;
        try {
            BufferedWriter writer = new BufferedWriter(new FileWriter(output));

            obj = new JSONParser().parse(new FileReader(path));
            // typecasting obj to JSONObject
            JSONObject jo = (JSONObject) obj;

            JSONArray items = (JSONArray) jo.get("features");
            for(int i=0;i<items.size();i++){
                JSONObject geoItem = (JSONObject) items.get(i);
                String triples = parse(geoItem, level);
                if(triples!=null)
                    writer.write(triples);
            }

            writer.close();
        } catch (IOException | ParseException e) {
            e.printStackTrace();
        }
    }

    private String parse(JSONObject jo, int level){
        StringBuilder builder = new StringBuilder();
        JSONObject properties = (JSONObject) jo.get("properties");

        String amd0_en = (String) properties.get("ADM0_EN");
        String amd0_pcode = (String) properties.get("ADM0_PCODE");

        String id = "ocha_" + amd0_pcode.toLowerCase();

        String type;
        if(level==0)
            type = "AdminUnit_Level0";
        else if(level==1)
            type = "AdminUnit_Level1";
        else
            type = "AdminUnit_Level2";

        //Collect and add adm 0 level properties
        if(level==0) {
            builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + type));
            String localName = (String) properties.get("ADM0_" + amd0_pcode);
            builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasName", amd0_en));
            builder.append(createLanguageTriple(Constants.RESOURCE + id, Constants.URI + "hasName", localName, amd0_pcode.toLowerCase()));
        }
        else{
            String amd1_en = (String) properties.get("ADM1_EN");
            String amd1_pcode = (String) properties.get("ADM1_PCODE");

            id = "ocha_" + amd1_pcode.toLowerCase();

            if(level==1) {
                builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + type));
                String localName = (String) properties.get("ADM1_" + amd0_pcode);
                builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasName", amd1_en));
                builder.append(createLanguageTriple(Constants.RESOURCE + id, Constants.URI + "hasName", localName, amd0_pcode.toLowerCase()));
                builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasUpperAdminUnit", Constants.RESOURCE + "ocha_" + amd0_pcode.toLowerCase()));
            }
            else{
                String amd2_en = (String) properties.get("ADM2_EN");
                String amd2_pcode = (String) properties.get("ADM2_PCODE");

                id = "ocha_" + amd2_pcode.toLowerCase();
                builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + type));
                String localName = (String) properties.get("ADM2_" + amd0_pcode);
                builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasName", amd2_en));
                if(localName!=null)
                    builder.append(createLanguageTriple(Constants.RESOURCE + id, Constants.URI + "hasName", localName, amd0_pcode.toLowerCase()));
                builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasUpperAdminUnit", Constants.RESOURCE + "ocha_" + amd1_pcode.toLowerCase()));
            }
        }



        //builder.append(createTriple(Constants.RESOURCE + id, Constants.WIKIPRED, Constants.WIKILINK+id));

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
        return "<"+subject + "> <" + predicate + "> \"" + object + "\"@"+locale+" .\n";
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
