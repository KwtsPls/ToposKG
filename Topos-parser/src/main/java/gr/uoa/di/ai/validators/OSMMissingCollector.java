package gr.uoa.di.ai.validators;

import gr.uoa.di.ai.Constants;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.HashSet;

public class OSMMissingCollector {
    String countryURI;
    String mappingsFile;
    String dataFile;
    String outputFile;
    String mode;
    HashSet<String> candidates;


    public OSMMissingCollector(String countryURI, String mode, String mappingsFile, String dataFile, String outputFile){
        this.countryURI = countryURI;
        this.mappingsFile = mappingsFile;
        this.dataFile = dataFile;
        this.mode = mode;
        this.outputFile = outputFile;
        this.candidates = new HashSet<>();
    }

    public void collect(){
        collectMappings();
        FileInputStream is = null;
        try {
            is = new FileInputStream(dataFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);
            BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile));

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(this.candidates.contains(s)) {
                    writer.write(s + " " + p + " " + o + " .\n");
                    if(p.contains("hasGeometry")){
                        this.candidates.add(o);
                    }
                }

            }

            writer.close();

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void collectMappings(){
        FileInputStream is = null;
        try {
            is = new FileInputStream(mappingsFile);
            NxParser nxp = new NxParser();
            nxp.parse(is);

            for (Node[] nx : nxp) {
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                if(s.equals(countryURI)){
                    if(mode.equals("COV")) {
                        if (p.contains("sfCovers"))
                            candidates.add(o);
                    }
                    if(mode.equals("INT")) {
                        if (p.contains("sfIntersects"))
                            candidates.add(o);
                    }
                }

            }


        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }
    }
}
