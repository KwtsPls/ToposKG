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
import java.util.HashSet;

public class GAULParser {
    GeoJsonToWktTransformer transformer;
    HashSet<String> countries;

    public GAULParser(){
        transformer = new GeoJsonToWktTransformer();
        countries = new HashSet<>();
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
                String triples = parse(geoItem,level);
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

        String iso3Code = (String) properties.get("iso3_code");
        String mapCode = (String) properties.get("map_code");
        String continent = (String) properties.get("continent");


        String type;
        if(level==0)
            type = "AdminUnit_Level0";
        else if(level==1)
            type = "AdminUnit_Level1";
        else
            type = "AdminUnit_Level2";


        //Collect and add adm 0 level properties
        String adm0_id = "gaul_" + iso3Code.toLowerCase() + "_" + (Long) properties.get("gaul0_code");
        String id = adm0_id;

        if(level==1) {

            if(!countries.contains(adm0_id)){
                builder.append(createTriple(Constants.RESOURCE + adm0_id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + "AdminUnit_Level0"));
                builder.append(createGeometry(adm0_id,"POINT (30 10)"));
                countries.add(adm0_id);
            }

            id = "gaul_" + iso3Code.toLowerCase() + "_" + (Long) properties.get("gaul1_code");
            String name = (String) properties.get("gaul1_name");

            builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + type));
            builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasName", name));
            builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasUpperAdminUnit", Constants.RESOURCE  + adm0_id.toLowerCase()));
        }
        else if(level==2){
            String adm1_id = "gaul_" + iso3Code.toLowerCase() + "_" + (Long) properties.get("gaul1_code");
            id = "gaul_" + iso3Code.toLowerCase() + "_" + (Long) properties.get("gaul2_code");
            String name = (String) properties.get("gaul2_name");


            builder.append(createTriple(Constants.RESOURCE + id, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", Constants.URI + type));
            builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasName", name));
            builder.append(createTriple(Constants.RESOURCE + id, Constants.URI + "hasUpperAdminUnit", Constants.RESOURCE + adm1_id.toLowerCase()));
        }


        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasISO3Code", iso3Code));
        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "hasMapCode", mapCode));
        builder.append(createStringTriple(Constants.RESOURCE + id, Constants.URI + "inContinent", continent));

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
