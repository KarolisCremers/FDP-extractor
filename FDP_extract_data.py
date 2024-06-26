"""
FDP data extraction script (start)
Author: Karolis Cremers https://github.com/KarolisCremers
ORCID: https://orcid.org/0000-0002-1756-3905
"""

import requests
from rdflib import Graph, URIRef
import os
import re

# get relative path:
cwd = os.getcwd()
# Resource type filtering dictionary, the value lists allow for popping one-by-one to
# efficiently generate a generic directory structure using the deprecated generate_path function.
path_dictionary = {'https://w3id.org/fdp/fdp-o#MetadataService': ["not target"],
    "https://w3id.org/fdp/fdp-o#FAIRDataPoint": ["FDP"], 
        "http://www.w3.org/ns/dcat#Catalog":["Catalog","FDP"],
        "http://www.w3.org/ns/dcat#Dataset":["Dataset","Catalog","FDP"],
        "http://www.w3.org/ns/dcat#Distribution":["Distribution","Dataset","Catalog","FDP"],
        "http://www.w3.org/ns/dcat#Resource": ["not target"],
        "http://www.w3.org/ns/dcat#DataService":["not target"]}

unimportant = ('https://w3id.org/fdp/fdp-o#MetadataService', "http://www.w3.org/ns/dcat#Resource",
                  "http://www.w3.org/ns/dcat#DataService", )

def get_title(g, url):
    """
    This function extract the name of a given resource
    g = graph
    url = url associated with resource
    returns the first title object found in the graph.
    """
    query = """PREFIX dcterms: <http://purl.org/dc/terms/> 
    SELECT ?o WHERE {
    ?url dcterms:title ?o .
    }"""
    qres = g.query(query, initBindings={'url': url})
    return re.sub('\W+','', str(qres.bindings[0]["o"])[:20])


def write_to_disk(g, url, dirpath):
    """
    Writes the graph in turtule format to the approriate path.
    """
    filepath = os.path.join(dirpath, get_title(g, url))
    g.serialize(destination="{}.ttl".format(filepath), format="turtle")

# deprecated:
# def generate_path(path_sequence, title, cwd):
#     """
#     This function generates a folder based on the
#     information in the FDP.
#     """
#     dirpath = os.path.join(cwd, path_sequence.pop())
#     while len(dirpath) > 0:
#         os.path.join(dirpath, path_sequence.pop())
#     filepath = os.path.join(dirpath, title)
#     return dirpath, filepath


def directories(g, url, path):
    """
    This function sets the path sequence for a given resource
    based on the standard FDP structure.
    """
    # extract the current resource type:
    query = """prefix dcat: <http://www.w3.org/ns/dcat#> 
SELECT ?value WHERE {
?url a ?value .
}
    """
    dcat = g.query(query, initBindings={'url': url})
    for attribute in dcat:
        uri = str(attribute[0])
        # if we're at the FDP level we have to make sure to add the relative path:
        if uri == "https://w3id.org/fdp/fdp-o#FAIRDataPoint":
            current_path = os.path.join(cwd, "FDP_" + get_title(g,url).rstrip(" ").replace(" ", "_"))
            break
            # otherwise we extend path to include new resource
            # this path fails if we start from a non FDP url without setting 
            # a relative path associated with the resource
        if uri not in unimportant:
            resource_type = uri.split('#')
            if len(resource_type) < 2:
                resource_type = uri.split('/')
            dir_name = resource_type.pop() + "_" + get_title(g,url).replace(" ", "_")
            current_path = os.path.join(path, dir_name)
    path_exists = os.path.isdir(current_path)
    if not path_exists:
        os.mkdir(current_path)
    return current_path

def traverse_fdp(url, path=str):
    """
    Recursive function that walk the FDP tree from
    the starting URL.
    Path variable MUST be set to the appropriate directory when
    not starting at a FDP url.
    returns: a merged graph containing all resource information available
    in the FDP tree.
    """
    #print("querying: {}".format(str(url)))
    url = URIRef(url)
    resp = requests.get(str(url+"/?format=ttl"), params={"format":"ttl"})
    # currently not possible to know if a child resource is draft from the parent
    # so we just jump up when we encounter one:
    if resp.text == "You are not allow to view this record in state DRAFT":
        #print("Draft found, skipping!")
        return Graph()
    g = Graph()
    # use data= because Graph.parse assumes input to be a filepath at default:
    g.parse(data=resp.text, format="ttl")
    # obtain ldp objects, ldp is used as pointers within the FDP datastructure
    qres = g.query(
    """SELECT ?o WHERE {
        ?s ?p ?o .
        FILTER (?p = <http://www.w3.org/ns/ldp#contains>)
        }"""
    )
    # setup directory for current resource:
    path = directories(g, url, path)
    # if qres is empty, we are at a leaf node:
    if len(qres) == 0:
        write_to_disk(g, url, path)
        return g
    # move to branch:
    for resource in qres:
        g2 = traverse_fdp(resource.o, path)
        g = g + g2
    # write starting resource
    write_to_disk(g, url, path)
    return g

def get_resource(url, destination):
    #FDP url when using /?format=ttl postfix:
    graph = traverse_fdp()
    # write merged graph to turtle file
    graph.serialize(destination=destination, format="turtle")

if __name__ == '__main__':
    get_resource('https://w3id.org/ejp-rd/fairdatapoints/orphanet-catalog-fdp', "orpha-fdp.ttl")
