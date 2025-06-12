package gr.uoa.di.ai.validators;

import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class NeighborsValidator {
    public HashMap<String,Integer> mappingsMap;
    public HashMap<String,String> names;

    public NeighborsValidator(){
        this.mappingsMap = new HashMap<>();
        this.names = new HashMap<>();
    }

    public void validate(String mappings, String countries, String neighbors) throws IOException {
        //Read country codes
        BufferedReader reader = new BufferedReader(new FileReader(countries));
        reader.readLine();

        String line = reader.readLine();
        while(line!=null){
            String[] tokens = line.split(",");
            this.names.put(tokens[1],tokens[0]);
            line = reader.readLine();
        }
        HashMap<String,String> uri2Names = new HashMap<>();


        //Parse initial triple file and build map
        FileInputStream is = new FileInputStream(mappings);
        NxParser nxp = new NxParser();
        nxp.parse(is);

        for (Node[] nx : nxp) {
            String s = nx[0].toString();
            String p = nx[1].toString();
            String o = nx[2].toString();

            if(p.contains("http://www.opengis.net/ont/geosparql#sfTouches")){
                int sCount = countDigits(s);
                int oCount = countDigits(o);

                if((sCount==3 && oCount==3)) {
                    Integer num = mappingsMap.get(o);
                    if (num == null) num = 0;
                    num++;
                    mappingsMap.put(o, num);

                    if(!uri2Names.containsKey(o)){
                        for(Map.Entry<String,String> entry: names.entrySet()){
                            if(o.contains(entry.getKey().toLowerCase())) {
                                uri2Names.put(o, entry.getValue());
                                uri2Names.put(entry.getValue(),o);
                            }
                        }
                    }
                }
            }
        }

        BufferedReader neighborsReader = new BufferedReader(new FileReader(neighbors));
        neighborsReader.readLine();
        line = neighborsReader.readLine();
        int count1 = 0;
        int count2 = 0;
        while(line!=null){
            String[] tokens = line.split(",");

            String name = tokens[0];
            String[] Ns = tokens[1].split("\\|");

            if(!tokens[1].equals("None")) {
                int i1 = this.mappingsMap.get(uri2Names.get(name));
                int i2 = Ns.length;
                count1 += i1;
                count2 += i2;
                System.out.println(name);

                if (!Objects.equals(i1, i2)) {
                    System.out.println(uri2Names.get(name) + " " + i1 + " " + i2 + " " + tokens[1]);
                }
            }
            System.out.println(count1 + "/" +count2);

            line = neighborsReader.readLine();
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
