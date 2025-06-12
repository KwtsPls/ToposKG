package gr.uoa.di.ai.transformers;

import org.eclipse.emf.ecore.EReference;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.io.ParseException;
import org.locationtech.jts.io.WKTReader;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;
import java.util.PriorityQueue;

class Element{
    String key;
    double value;
    public Element(String key, double value){
        this.key = key;
        this.value = value;
    }

    @Override
    public String toString() {
        return "Element{" +
                "key='" + key + '\'' +
                ", value=" + value +
                '}';
    }

    public String getKey() {
        return key;
    }

    public double getValue(){
        return value;
    }
}

public class IntersectionConnector {
    HashMap<String, Geometry> geoMap;
    String inputFile;

    public IntersectionConnector(String inputFile){
        this.geoMap = new HashMap<>();
        this.inputFile = inputFile;
    }


    public PriorityQueue<Element> rankIntersections(String entity, String output){
        collectGeometries();
        PriorityQueue<Element> priorityQueue = new PriorityQueue<>(Comparator.comparingDouble(e -> e.value));
        Geometry queryGeometry = geoMap.get(entity);
        for(Map.Entry<String,Geometry> entry: geoMap.entrySet()){
            Geometry intersection = queryGeometry.intersection(entry.getValue());
            double rank = intersection.getArea() / entry.getValue().getArea();
            if(rank>0.0)
                priorityQueue.add(new Element(entry.getKey(),rank));
        }

        if(output!=null) {
            try {
                BufferedWriter writer = new BufferedWriter(new FileWriter(output));
                for(Element element:priorityQueue){
                    if(element.getValue()>=0.9)
                        writer.write(entity + " <http://www.opengis.net/ont/geosparql#sfCovers> " + element.getKey() + " .\n");
                }

                writer.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        else{
            System.out.println(priorityQueue);
        }

        return priorityQueue;
    }

    private void collectGeometries(){
        FileInputStream is = null;
        try {
            is = new FileInputStream(inputFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);
            WKTReader wktReader = new WKTReader();
            HashMap<String,String> entity2geo = new HashMap<>();

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(p.contains("hasGeometry"))
                    entity2geo.put(o,s);
                if(p.contains("asWKT")){
                    String entity = entity2geo.get(s);
                    String geomString = o;
                    geomString = geomString.replaceAll("<http://www.opengis.net/def/crs/EPSG/0/4326>", "")
                            .replaceAll("\"", "");
                    Geometry geom = wktReader.read(geomString);
                    this.geoMap.put(entity,geom);
                }
            }

        } catch (FileNotFoundException | ParseException e) {
            e.printStackTrace();
        }
    }
}

