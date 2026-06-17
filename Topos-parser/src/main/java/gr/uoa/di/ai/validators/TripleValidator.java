package gr.uoa.di.ai.validators;

import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.util.*;

public class TripleValidator {
    public static void fix_triples(String inputFile, String outputFile) throws IOException {

        // First pass: identify entities with the target level
        try (FileInputStream is = new FileInputStream(inputFile)) {
            BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile));
            NxParser nxp = new NxParser();
            nxp.parse(is);

            while (nxp.hasNext()) {
                Node[] nx = nxp.next();
                String s = nx[0].toString();
                String p = nx[1].toString();
                String o = nx[2].toString();

                writer.write(s + " " + p + " " + o + " .\n");
            }

            writer.close();
        }
    }
}
