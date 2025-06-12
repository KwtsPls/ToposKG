package gr.uoa.di.ai;

import gr.uoa.di.ai.connectors.DirectoryParsing;
import gr.uoa.di.ai.connectors.Osm2GAULConnector;
import gr.uoa.di.ai.transformers.GeometryAggregator;
import gr.uoa.di.ai.transformers.IntersectionConnector;
import gr.uoa.di.ai.transformers.Nt2Csv;
import gr.uoa.di.ai.validators.LevelValidator;
import gr.uoa.di.ai.validators.NeighborsValidator;
import gr.uoa.di.ai.validators.OSMMissingCollector;
import org.locationtech.jts.io.ParseException;

import java.io.IOException;

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
            /*** 1st step in the OSM integration pipeline
             * args[0] = wikidata uri for country
             * args[1] = osm input file
             * args[2] = wikidata hierarchy file
             * args[3] = .csv file with gaul->osm level mappings
             * args[4] = output file
            ***/
            case "osm_hierarchy" ->{
                OSMCollectBoundaries osmCollectBoundaries = new OSMCollectBoundaries(args[1],args[2],args[3],args[4],args[5]);
                osmCollectBoundaries.collect();
            }
            case "osm_collect_missing" -> {
                OSMMissingCollector osmMissingCollector = new OSMMissingCollector(args[1], args[2], args[3], args[4], args[5]);
                osmMissingCollector.collect();
            }
            case "rank_intersections" ->{
                IntersectionConnector intersectionConnector = new IntersectionConnector(args[2]);
                if(args.length==4)
                    intersectionConnector.rankIntersections(args[1],args[3]);
                else
                    intersectionConnector.rankIntersections(args[1],null);
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
            }
            case "connection" ->{
                DirectoryParsing parser = new DirectoryParsing(args[1],args[2]);
                parser.process();
            }
        }
    }
}
