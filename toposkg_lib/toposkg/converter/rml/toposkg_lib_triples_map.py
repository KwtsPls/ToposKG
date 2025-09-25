import os

class TriplesMap():
    def __init__(self, ontology_uri, resource_uri, name=None):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        self.name = name
        self.logicalSource = None
        self.subjectMap = None
        self.refObjectMaps = []
        self.predicateObjectMaps = []

    def add_logical_source(self, input_data_source, reference_formulation, iterator=None):
        if self.name == None:
            self.name = self.clean_filename(input_data_source)
        self.logicalSource = (input_data_source, reference_formulation, iterator)

    def add_subject_map(self, id_field, subject_class=None, graph=None):
        self.subjectMap = (id_field, subject_class, graph)

    #Simple predicateObjectMap for any literal
    def add_predicate_object_map(self, predicate_name, reference, datatype=None, prefix=None):
        self.predicateObjectMaps += [("simple",predicate_name, reference, datatype, prefix)]

    #Add predicateObjectMap for a join between two triples maps
    def add_predicate_object_map_on_join(self, predicate_name, foreign_map, child, parent):
        self.predicateObjectMaps += [("join",predicate_name, foreign_map, child, parent)]

    #Add predicateObjectMap with explicit RefObjectMap
    def add_predicate_object_map_on_reference(self, predicate_name, refObjectMap):
        self.predicateObjectMaps += [("reference",predicate_name, refObjectMap)]

    #Add predicateObjectMap with template
    def add_predicate_object_map_with_template(self, predicate_name, template, prefix=None):
        self.predicateObjectMaps += [("template", predicate_name, template, prefix)]

    #Add a RefObjectMap
    def add_ref_object_map(self, name, parentMap, child, parent):
        self.refObjectMaps += [(name, parentMap, child, parent)]

    def export_as_string(self):
        if self.logicalSource==None:
            raise Exception("Logical Source is not initiliazed")
        if self.subjectMap==None:
            raise Exception("No subjectMap in TriplesMap")
        
        triples_map_str = "<#" + self.name + ">  a rr:TriplesMap;\n"
        logical_source_str = self.get_logical_source_string()
        subject_map_str = self.get_subject_map_string()
        predicate_object_map_str = self.get_predicate_object_map_str()
        ref_object_map_str = self.get_ref_object_map_str()

        result = triples_map_str + logical_source_str + subject_map_str + predicate_object_map_str
        if ref_object_map_str!=None:
                result += str(ref_object_map_str)
        return result

    #Helper functions
    def get_logical_source_string(self):
        input_data_source, reference_formulation, iterator = self.logicalSource
        logical_source_str = ""
        if iterator==None:
            logical_source_str = """rml:logicalSource [
        rml:source \"{}\";
        rml:referenceFormulation \"{}\";
];\n""".format(input_data_source,reference_formulation)
        else:
            logical_source_str = """rml:logicalSource [
        rml:source \"{}\";
        rml:iterator \"{}\";
        rml:referenceFormulation {};
];\n""".format(input_data_source,iterator,reference_formulation)
        
        return logical_source_str

    def get_subject_map_string(self):
        (id_field, subject_class, graph) = self.subjectMap
        subject_map_str = """rr:subjectMap [
    rr:template \"{}\";\n""".format(self.resource_uri+"{"+id_field+"}")
        if subject_class != None:
            subject_map_str += "\trr:class {};\n".format("onto:"+subject_class)
        if graph != None:
            subject_map_str += "\trr:graphMap [ rr:constant \"{}\"];\n".format(graph)
        subject_map_str += "];\n\n"
        return subject_map_str

    def get_predicate_object_map_str(self):
        maps_str = ""
        for i,predicateObjectMap in enumerate(self.predicateObjectMaps):
            if predicateObjectMap[0] == "simple" :
                maps_str += self.simple_predicate_object_map_string(predicateObjectMap)
            elif predicateObjectMap[0] == "join":
                maps_str += self.join_predicate_object_map_string(predicateObjectMap)
            elif predicateObjectMap[0] == "reference":
                maps_str += self.reference_predicate_object_map_string(predicateObjectMap)
            else:
                maps_str += self.template_predicate_object_map_string(predicateObjectMap)

            if i==len(self.predicateObjectMaps)-1:
                maps_str += "."
            else:
                maps_str += ";\n"
        return maps_str

    def get_ref_object_map_str(self):
        if self.refObjectMaps==None:
            return ""
        ref_map_str="\n\n"
        for ref_map in self.refObjectMaps:
            (_, name, parentMap, child, parent) = ref_map
            ref_map_str += "<#{}> a rr:RefObjectMap ;\n".format(name)
            ref_map_str += "rr:parentTriplesMap <#{}> ;\n".format(parentMap.name)
            ref_map_str += "rr:joinCondition [\n"
            ref_map_str += "\trr:child  \"{}\" ;\n".format(child)
            ref_map_str += "\trr:parent \"{}\" ;\n".format(parent)
            ref_map_str += "].\n"
        return ref_map_str


    def reference_predicate_object_map_string(self, predicateObjectMap):
        (_, predicate_name, refObjectMap) = predicateObjectMap
        predicate_object_map_string = "rr:predicateObjectMap [\n"
        predicate_object_map_string += "\trr:predicate  onto:{} ;\n".format(predicate_name)
        predicate_object_map_string += "\trr:objectMap <#{}>\n".format(refObjectMap)
        predicate_object_map_string += "]"
        return predicate_object_map_string

    def join_predicate_object_map_string(self, predicateObjectMap):
        (_, predicate_name, foreign_map, child, parent) = predicateObjectMap
        predicate_object_map_string = "rr:predicateObjectMap [\n"
        predicate_object_map_string += "\trr:predicate  onto:{} ;\n".format(predicate_name)
        predicate_object_map_string += "\trr:objectMap [\n"
        predicate_object_map_string += "\t\trr:parentTriplesMap <#{}>;\n".format(foreign_map.name)
        predicate_object_map_string += "\t\trr:joinCondition [\n"
        predicate_object_map_string += "\t\t\trr:child  \"{}\" ;\n".format(child)
        predicate_object_map_string += "\t\t\trr:parent \"{}\" ;\n".format(parent)
        predicate_object_map_string += "\t\t];\n\t];\n]"
        return predicate_object_map_string

    def simple_predicate_object_map_string(self, predicateObjectMap):
        (_, predicate_name, reference, datatype, prefix) = predicateObjectMap
        predicate_object_map_string = "rr:predicateObjectMap [\n"
        if prefix==None:
            predicate_object_map_string += "\trr:predicate  onto:{} ;\n".format(predicate_name)
        else:
            predicate_object_map_string += "\trr:predicate  {}:{} ;\n".format(prefix,predicate_name)
        predicate_object_map_string += "\trr:objectMap [\n"
        predicate_object_map_string += "\t\trml:reference \"{}\";\n".format(reference)
        if datatype!=None:
            datatype_str = ""
            if datatype == "bool":
                datatype_str = "xsd:boolean"
            elif datatype == "int":
                datatype_str = "xsd:integer"
            elif datatype ==  "float":
                datatype_str = "xsd:double"
            elif datatype == "wkt":
                datatype_str = "ogc:wktLiteral"
            else:
                datatype_str = "xsd:string"
            predicate_object_map_string += "\t\trr:datatype {};\n".format(datatype_str)
        predicate_object_map_string += "\t];\n]"
        return predicate_object_map_string

    def template_predicate_object_map_string(self,predicateObjectMap):
        (_, predicate_name, template, prefix) = predicateObjectMap
        predicate_object_map_string = "rr:predicateObjectMap [\n"
        if prefix==None:
            predicate_object_map_string += "\trr:predicate  onto:{} ;\n".format(predicate_name)
        else:
            predicate_object_map_string += "\trr:predicate  {}:{} ;\n".format(prefix,predicate_name)
        predicate_object_map_string += "\trr:objectMap [\n"
        predicate_object_map_string += "\t\trr:template \"{}\";\n".format(template)
        predicate_object_map_string += "\t];\n]"
        return predicate_object_map_string

    def clean_filename(self, file_path: str) -> str:
        # Extract just the file name
        filename = os.path.basename(file_path)
        
        # Remove all extensions (e.g. .tar.gz -> just "file")
        while '.' in filename:
            filename = os.path.splitext(filename)[0]
        
        # Replace spaces with underscores
        filename = filename.replace(" ", "_")
        
        return filename