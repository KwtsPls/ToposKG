package gr.uoa.di.ai;

import gr.uoa.di.ai.connectors.DirectoryParsing;
import gr.uoa.di.ai.connectors.Osm2GAULConnector;
import gr.uoa.di.ai.connectors.SimpleOsmEntityLinker;
import gr.uoa.di.ai.transformers.GeometryAggregator;
import gr.uoa.di.ai.transformers.IntersectionConnector;
import gr.uoa.di.ai.transformers.Nt2Csv;
import gr.uoa.di.ai.validators.*;
import org.locationtech.jts.io.ParseException;

import java.io.IOException;
import java.nio.file.Path;

public class Manager {
    public static void main(String[] args) {
        switch (args[0]) {
            case "create" -> {
                GAULParser gaulParser = new GAULParser();
                gaulParser.parse(args[1],
                        args[2], Integer.parseInt(args[3]));
            }
            case "osm" -> {
                OSMParser osmParser = new OSMParser();
                osmParser.parse(args[1], args[2], args[3]);
            }
            case "water" -> {
                OSMParser osmParser = new OSMParser();
                osmParser.parseWater(args[1], args[2], args[3]);
            }
            case "poi" -> {
                OSMParser osmParser = new OSMParser();
                osmParser.parsePoi(args[1], args[2], args[3]);
            }
            case "forest" -> {
                OSMParser osmParser = new OSMParser();
                osmParser.parseForest(args[1], args[2], args[3]);
            }
            case "fix" -> {
                GeometryAggregator aggregator = new GeometryAggregator(args[1],
                        args[2], args[3]);
                try {
                    aggregator.aggregateOnUpperLevel();
                } catch (IOException | ParseException e) {
                    e.printStackTrace();
                }
            }
            case "fix_level" -> {
                GeometryAggregator aggregator = new GeometryAggregator(args[1],
                        args[2], args[3]);
                try {
                    aggregator.aggregateOnLevelOne();
                } catch (IOException | ParseException e) {
                    e.printStackTrace();
                }
            }
            case "validate_level" -> {
                LevelValidator levelValidator = new LevelValidator();
                try {
                    levelValidator.validate(args[1], args[2]);
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
            case "validate_neighbor" -> {
                NeighborsValidator neighborsValidator = new NeighborsValidator();
                try {
                    neighborsValidator.validate(args[1], args[2], args[3]);
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
            case "validate_triples" -> {
                try {
                    TripleValidator.fix_triples(args[1],args[2]);
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
            case "validate_iris" -> {
                try {
                    RdfIriInplaceFixer.fixInPlace(Path.of(args[1]),false,false,false);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
            /*** 1st step in the OSM integration pipeline
             * args[1] = wikidata uri for country
             * args[2] = osm input file
             * args[3] = wikidata hierarchy file
             * args[4] = .csv file with gaul->osm level mappings
             * args[5] = output file
            ***/
            case "osm_hierarchy" ->{
                OSMCollectBoundaries osmCollectBoundaries = new OSMCollectBoundaries(args[1],args[2],args[3],args[4],args[5]);
                osmCollectBoundaries.collect();
            }
            case "osm_collect_missing" -> {
                OSMMissingCollector osmMissingCollector = new OSMMissingCollector(args[1], args[2], args[3], args[4], args[5]);
                osmMissingCollector.collect();
            }
            /*** Part of the OSM pipeline. Discover missing upperAdminUnits relationships based on intersections
             * args[1] = osm input file
             * args[2] = materialized mapping file
             * args[3] = output file
             ***/
            case "rank_intersections" ->{
                IntersectionConnector intersectionConnector = new IntersectionConnector(args[1]);
                intersectionConnector.connectUpperAdminUnits(args[2],args[3]);
            }
            case "prepare_for_linking" ->{
                if(args[1].equals("OSM")){
                    try {
                        Nt2Csv.prepareOSM(args[2],args[3],args[4]);
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                }
                else if(args[1].equals("GAUL")){
                    try {
                        Nt2Csv.prepareGAUL(args[2],args[3],args[4]);
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                }
                else if(args[1].equals("General")){
                    try {
                        Nt2Csv.prepareGeneral(args[2],args[3]);
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                }
            }
            case "connection" ->{
                DirectoryParsing parser = new DirectoryParsing(args[1],args[2]);
                parser.process();
            }
            case "relink" ->{
                Path countryLinkingDir = Path.of(args[1]);
                Path newOsmNtFile = Path.of(args[2]);
                Path outputDir = Path.of(args[3]);

                SimpleOsmEntityLinker linker = new SimpleOsmEntityLinker();
                try {
                    SimpleOsmEntityLinker.RelinkReport report =
                            linker.relink(countryLinkingDir, newOsmNtFile, outputDir);
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            }
            case "geoquestions" ->{
                OSMGeoQ201Parser parser = new OSMGeoQ201Parser();
                parser.parse(args[1], args[2], args[3]);
            }
        }
    }
}
