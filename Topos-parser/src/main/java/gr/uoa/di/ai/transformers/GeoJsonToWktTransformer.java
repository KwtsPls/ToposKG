package gr.uoa.di.ai.transformers;

import org.geotools.geojson.geom.GeometryJSON;
import org.geotools.geometry.jts.JTS;
import org.geotools.referencing.CRS;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.io.WKTWriter;
import org.opengis.referencing.FactoryException;
import org.opengis.referencing.crs.CoordinateReferenceSystem;
import org.opengis.referencing.operation.MathTransform;
import org.opengis.referencing.operation.TransformException;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

public class GeoJsonToWktTransformer {
    WKTWriter writer;
    public GeoJsonToWktTransformer(){
        this.writer = new WKTWriter();
    }

    public String transformGeoJson(String geojson,int EPSG){
        GeometryJSON gjson = new GeometryJSON();
        Geometry geometry = null;
        try {
            geometry = gjson.read(geojson);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }

        if(EPSG==4326){
            WKTWriter writer = new WKTWriter();
            return writer.write(geometry);
        }
        else{
            String sourceCRS = "EPSG:"+EPSG;
            String targetCRS = "EPSG:4326";

            // Parse the source and target CRS
            try {
                CoordinateReferenceSystem source = CRS.decode(sourceCRS);
                CoordinateReferenceSystem target = CRS.decode(targetCRS);
                // Get the transform from the source CRS to the target CRS
                MathTransform transform = CRS.findMathTransform(source, target);
                Geometry transformedGeometry = JTS.transform(geometry,transform);

                WKTWriter writer = new WKTWriter();
                return writer.write(transformedGeometry);
            } catch (FactoryException | TransformException e) {
                throw new RuntimeException(e);
            }
        }
    }

    public double getArea(String geojson){
        GeometryJSON gjson = new GeometryJSON();
        Geometry geometry = null;
        try {
            geometry = gjson.read(geojson);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        return geometry.getArea();
    }
}
