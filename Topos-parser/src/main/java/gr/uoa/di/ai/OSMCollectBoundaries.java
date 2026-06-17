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
    String countryLevels;
    String outputFile;
    HashSet<String> candidates;
    HashMap<String, List<String>> hierarchy;
    HashMap<String, String> upperLevel;
    HashMap<String, String> osm2wiki;
    // Level maps
    HashMap<String, String> levelMap;
    HashMap<String, String> osm2gaulLevels;

    public OSMCollectBoundaries(String uri, String osmFile, String wikidataFile, String countryLevels, String outputFile) {
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

    public void collect() {
        System.out.println("Mapping osm to wikidata...");
        collectOSM2Wikidata();

        System.out.println("Creating Hierarchies...");
        collectLinks();

        System.out.println("Building candidates...");
        discoverEntities(uri);

        System.out.println("Generating results...");

        try {
            FileInputStream is = new FileInputStream(omsFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile));

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                writer.write(s + " " + p + " " + o + " .\n");
                if (this.candidates.contains(s)) {

                    String upper = this.upperLevel.remove(s);
                    if (upper != null) {
                        writer.write(s + " <" + Constants.URI + "hasUpperAdminUnit" + "> " + upper + " .\n");
                    }

                    if (p.contains("hasGeometry")) {
                        this.candidates.add(o);
                    }
                }
            }

            writer.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void discoverEntities(String rootUri) {
        if (rootUri == null) {
            return;
        }

        Deque<String> stack = new ArrayDeque<>();
        Set<String> visited = new HashSet<>();

        visited.add(rootUri);
        stack.push(rootUri);

        while (!stack.isEmpty()) {
            String wikidataUri = stack.pop();


            String osmURI = this.osm2wiki.get(wikidataUri);
            if (osmURI != null) {
                this.candidates.add(osmURI);
            }

            List<String> lowerLevels = this.hierarchy.get(wikidataUri);
            if (lowerLevels == null) {
                continue;
            }

            String upperLevel = osmURI == null ? null : this.levelMap.get(osmURI);

            for (String lower : lowerLevels) {
                if (lower == null) {
                    continue;
                }

                String lowerOsmURI = this.osm2wiki.get(lower);

                if (osmURI != null && lowerOsmURI != null) {
                    String lowerLevel = this.levelMap.get(lowerOsmURI);

                    if (lowerLevel != null &&
                            upperLevel != null &&
                            this.osm2gaulLevels.containsKey(lowerLevel) &&
                            this.osm2gaulLevels.containsKey(upperLevel)) {

                        int gaulUpperLevel = Integer.parseInt(this.osm2gaulLevels.get(upperLevel));
                        int gaulLowerLevel = Integer.parseInt(this.osm2gaulLevels.get(lowerLevel));

                        if (gaulLowerLevel - gaulUpperLevel == 1) {
                            this.upperLevel.put(lowerOsmURI, osmURI);
                        }
                    }
                }

                // Critical fix:
                // Only push a Wikidata entity once.
                // This prevents cycles, duplicates, and explosive stack growth.
                if (visited.add(lower)) {
                    stack.push(lower);
                }
            }

            if (visited.size() % 100_000 == 0) {
                System.out.println("Visited: " + visited.size() + ", stack: " + stack.size());
            }
        }

        System.out.println("Discovery finished. Visited Wikidata entities: " + visited.size());
        System.out.println("OSM candidate entities: " + this.candidates.size());
    }

    private void discoverEntitiesR(String uri) {
        discoverEntitiesR(uri, new HashSet<>());
    }

    private void discoverEntitiesR(String uri, Set<String> visited) {
        if (uri == null || !visited.add(uri)) {
            return;
        }

        String osmURI = this.osm2wiki.get(uri);
        if (osmURI != null) {
            this.candidates.add(osmURI);
        }

        List<String> lowerLevels = hierarchy.get(uri);
        if (lowerLevels != null) {
            String upperLevel = osmURI == null ? null : this.levelMap.get(osmURI);

            for (String lower : lowerLevels) {
                String lowerOsmURI = this.osm2wiki.get(lower);

                if (osmURI != null && lowerOsmURI != null) {
                    String lowerLevel = this.levelMap.get(lowerOsmURI);

                    if (lowerLevel != null &&
                            upperLevel != null &&
                            this.osm2gaulLevels.containsKey(lowerLevel) &&
                            this.osm2gaulLevels.containsKey(upperLevel)) {

                        int gaulUpperLevel = Integer.parseInt(this.osm2gaulLevels.get(upperLevel));
                        int gaulLowerLevel = Integer.parseInt(this.osm2gaulLevels.get(lowerLevel));

                        if (gaulLowerLevel - gaulUpperLevel == 1) {
                            this.upperLevel.put(lowerOsmURI, osmURI);
                        }
                    }
                }

                discoverEntitiesR(lower, visited);
            }
        }
    }

    private void collectOSM2Wikidata() {
        try {
            BufferedReader reader = new BufferedReader(new FileReader(countryLevels));
            reader.readLine();

            String line = reader.readLine();
            while (line != null) {
                String[] tokens = line.split(",");

                if (tokens.length >= 2) {
                    this.osm2gaulLevels.put(tokens[1], tokens[0]);
                }

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

                if (p.contains("http://toposkg.di.uoa.gr/ontology/hasWikidataLink")) {
                    this.osm2wiki.put(o, s);
                }

                if (p.contains("hasOSMLevel")) {
                    this.levelMap.put(s, o.replaceAll("\"", ""));
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // Collect administrative links from wikidata
    private void collectLinks() {
        try {
            FileInputStream is = new FileInputStream(wikidataFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            int totalLinks = 0;

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                /*
                 * Important:
                 * If wikidataFile contains only administrative parent-child links,
                 * this is okay.
                 *
                 * If wikidataFile contains mixed Wikidata triples, uncomment and adapt
                 * the predicate filter below, otherwise the hierarchy can become enormous.
                 */

                /*
                if (!p.contains("P131") &&
                        !p.contains("located in the administrative territorial entity")) {
                    continue;
                }
                */

                addToHierarchy(o, s);
                totalLinks++;
            }

            System.out.println("Hierarchy parent entries: " + this.hierarchy.size());
            System.out.println("Hierarchy total links: " + totalLinks);

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void addToHierarchy(String key, String value) {
        if (key == null || value == null) {
            return;
        }

        List<String> list = this.hierarchy.get(key);
        if (list == null) {
            list = new ArrayList<>();
            this.hierarchy.put(key, list);
        }

        list.add(value);
    }
}