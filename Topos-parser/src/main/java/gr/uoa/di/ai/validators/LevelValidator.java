package gr.uoa.di.ai.validators;

import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class LevelValidator {

    public HashMap<String,Integer> numMap;
    public HashMap<String,Integer> mappingsMap;

    public LevelValidator(){
        this.numMap = new HashMap<>();
        this.mappingsMap = new HashMap<>();
    }

    public void validate(String initialFile, String mappings) throws IOException {
        //Parse initial triple file and build map
        FileInputStream is = new FileInputStream(initialFile);
        NxParser nxp = new NxParser();
        nxp.parse(is);

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("http://spatialkg.di.uoa.gr/ontology/hasUpperAdminUnit")){
                Integer num = numMap.get(o);
                if(num==null) num=0;
                num++;
                numMap.put(o,num);
            }
        }

        //Parse mappings and collect
        is = new FileInputStream(mappings);
        nxp = new NxParser();
        nxp.parse(is);

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("http://www.opengis.net/ont/geosparql#sfWithin")){
                int sCount = countDigits(s);
                int oCount = countDigits(o);

                if((sCount>4 && oCount==4) || (sCount==4 && oCount==3)) {
                    Integer num = mappingsMap.get(o);
                    if (num == null) num = 0;
                    num++;
                    mappingsMap.put(o, num);
                }
            }
        }


        //Compare results
        for(Map.Entry<String, Integer> entry: numMap.entrySet()){
            Integer i1 = entry.getValue();
            Integer i2 = mappingsMap.get(entry.getKey());
            if(!Objects.equals(i1, i2)){
                System.out.println(entry.getKey() + " " + i1 + " " + i2);
            }
        }
    }

    int countDigits(String s){
        Matcher matcher = Pattern.compile("\\d").matcher(s);
        int count = 0;
        while (matcher.find()) {
            count++;
        }
        return count;
    }
}
