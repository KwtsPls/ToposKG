package gr.uoa.di.ai.connectors;

import java.io.*;
import java.util.Locale;

public class DirectoryParsing {
    String osmDirPath;
    String gaulDirPath;

    public DirectoryParsing( String osmDirPath, String gaulDirPath){
        this.osmDirPath = osmDirPath;
        this.gaulDirPath = gaulDirPath;
    }

    //For each country directory in OSM process accordingly to the format of the country specified in the stats.txt file
    //current formats:
    //normal
    //single
    //one_adm
    //one_adm:{level}
    //ignore
    public void process(){
        //Open and iterate through an osm directory
        File osmDir = new File(this.osmDirPath);
        for(File country: osmDir.listFiles()){
            if(!country.getName().equals("Ireland")) {
                System.out.println("Working on " + country.getName() + "...");
                String[] args = prepareArguments(country);
                Osm2GAULConnector connector = new Osm2GAULConnector(args, country);
                connector.process();
                System.out.println("------------------------------");
                System.out.println();
                connector = null;
            }
        }
    }

    private String[] prepareArguments(File country){
        String[] args = new String[8];
        for(File file:country.listFiles()){
            if(file.getName().equals("stats.txt"))
                args[0] = readStat(file.getAbsolutePath());
            if(file.getName().equals(country.getName().toLowerCase() + ".nt"))
                args[1] = file.getAbsolutePath();
            if(file.getName().equals("linking_admin_0.csv"))
                args[2] = file.getAbsolutePath();
            if(file.getName().equals("linking_admin_1.csv"))
                args[3] = file.getAbsolutePath();
            if(file.getName().equals("linking_admin_2.csv"))
                args[4] = file.getAbsolutePath();
            if(file.getName().endsWith("osm_levels.csv"))
                args[5] = file.getAbsolutePath();
        }
        //Get gaul file's path
        args[6] = gaulDirPath + country.getName() + "/" + country.getName() + "_fixed.nt";

        System.out.println();
        System.out.println("Arguments for " + country.getName() + ":");
        System.out.println("stats: "+args[0]);
        System.out.println("osm file: "+args[1]);
        System.out.println("levels map: "+args[5]);
        System.out.println("gaul file: "+args[6]);

        return args;
    }

    private String readStat(String path){
        try {
            BufferedReader reader = new BufferedReader(new FileReader(path));
            String stat = reader.readLine();
            reader.close();
            return stat;
        } catch (IOException e) {
            e.printStackTrace();
            return null;
        }
    }
}
