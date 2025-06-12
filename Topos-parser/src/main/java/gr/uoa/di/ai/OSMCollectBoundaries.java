package gr.uoa.di.ai;

import com.google.common.hash.BloomFilter;
import com.google.common.hash.Funnels;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class OSMCollectBoundaries {
    String uri;
    String omsFile;
    String wikidataFile;
    String countryLevels ;
    String outputFile;
    HashSet<String> candidates;
    HashMap<String,List<String>> hierarchy;
    HashMap<String,String> upperLevel;
    HashMap<String,String> osm2wiki;
    //Level maps
    HashMap<String,String> levelMap;
    HashMap<String,String> osm2gaulLevels;

    public OSMCollectBoundaries(String uri, String osmFile, String wikidataFile, String countryLevels, String outputFile){
        this.uri = uri;
        this.omsFile = osmFile;
        this.wikidataFile = wikidataFile;
        this.outputFile = outputFile;
        this.countryLevels = countryLevels;
        this.candidates = new HashSet<>();
        this.upperLevel = new HashMap<>();
        this.hierarchy = new HashMap<>();
        this.osm2wiki = new HashMap<>();
        this.levelMap = new HashMap<>();
        this.osm2gaulLevels = new HashMap<>();
    }


    public void collect(){
        System.out.println("Mapping osm to wikidata...");
        collectOSM2Wikidata();
        System.out.println("Creating Hierarchies...");
        collectLinks();
        System.out.println("Building candidates...");
        discoverEntities(uri);
        System.out.println("Generating results...");

        try{
            FileInputStream is = new FileInputStream(omsFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);
            BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile));

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();


                if(this.candidates.contains(s)) {
                    writer.write(s + " " + p + " " + o + " .\n");
                    String upper = this.upperLevel.remove(s);
                    if(upper!=null) writer.write(s + " <" + Constants.URI + "hasUpperAdminUnit" + "> " + upper + " .\n");
                    if(p.contains("hasGeometry")){
                        this.candidates.add(o);
                    }
                }
            }

            writer.close();
        }
        catch (IOException e){
            e.printStackTrace();
        }
    }

    private void discoverEntities(String rootUri){
        Deque<String> stack = new ArrayDeque<>();
        stack.push(rootUri);

        while (!stack.isEmpty()) {
            String uri = stack.pop();
            String osmURI = this.osm2wiki.get(uri);
            this.candidates.add(osmURI);

            List<String> lower_levels = hierarchy.get(uri);
            if (lower_levels != null) {
                for (String lower : lower_levels) {
                    stack.push(lower);  // Push child to stack for future processing

                    String upperLevel = this.levelMap.get(osmURI);
                    String lowerLevel = this.levelMap.get(this.osm2wiki.get(lower));

                    if (lowerLevel != null && upperLevel != null &&
                            this.osm2gaulLevels.containsKey(lowerLevel) &&
                            this.osm2gaulLevels.containsKey(upperLevel)) {
                        int gaulUpperLevel = Integer.parseInt(this.osm2gaulLevels.get(upperLevel));
                        int gaulLowerLevel = Integer.parseInt(this.osm2gaulLevels.get(lowerLevel));

                        if (gaulLowerLevel - gaulUpperLevel == 1) {
                            this.upperLevel.put(this.osm2wiki.get(lower), osmURI);
                        }
                    }
                }
            }
        }
    }


    private void discoverEntitiesR(String uri){
        String osmURI = this.osm2wiki.get(uri);
        this.candidates.add(osmURI);
        List<String> lower_levels = hierarchy.get(uri);
        if(lower_levels!=null) {
            for (String lower : lower_levels) {
                discoverEntities(lower);

                String upperLevel = this.levelMap.get(osmURI);
                String lowerLevel = this.levelMap.get(this.osm2wiki.get(lower));

                if(lowerLevel!=null && upperLevel!=null && this.osm2gaulLevels.containsKey(lowerLevel)
                        && this.osm2gaulLevels.containsKey(upperLevel)) {
                    int gaulUpperLevel = Integer.parseInt(this.osm2gaulLevels.get(upperLevel));
                    int gaulLowerLevel = Integer.parseInt(this.osm2gaulLevels.get(lowerLevel));

                    if (gaulLowerLevel - gaulUpperLevel == 1)
                        this.upperLevel.put(this.osm2wiki.get(lower), osmURI);
                }
            }
        }
    }

    private void collectOSM2Wikidata(){
        try{
            BufferedReader reader = new BufferedReader(new FileReader(countryLevels));
            reader.readLine();
            String line=reader.readLine();
            while(line!=null){
                String[] tokens = line.split(",");
                this.osm2gaulLevels.put(tokens[1],tokens[0]);
                line = reader.readLine();
            }
            reader.close();


            FileInputStream is = new FileInputStream(omsFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(p.contains("http://spatialkg.di.uoa.gr/ontology/hasWikidataLink")) {
                    this.osm2wiki.put(o, s);
                }

                if(p.contains("hasOSMLevel")){
                    this.levelMap.put(s,o.replaceAll("\"",""));
                }
            }
        }
        catch (IOException e){
            e.printStackTrace();
        }
    }

    //Collect all administrative links from wikidata
    private void collectLinks(){
        try{
            FileInputStream is = new FileInputStream(wikidataFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String o = nx[2].toString();

                addToHierarchy(o,s);
            }

        }
        catch (IOException e){
            e.printStackTrace();
        }
    }

    private void addToHierarchy(String key, String value){
        List<String> list = this.hierarchy.get(key);
        if(list==null)
            list = new ArrayList<>();
        list.add(value);
        this.hierarchy.put(key,list);
    }

}
