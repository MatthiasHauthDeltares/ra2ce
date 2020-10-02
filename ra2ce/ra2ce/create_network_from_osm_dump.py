# create graph from OSM
import os as os
import geopandas as gpd
from shapely.wkb import loads
import ogr
import numpy as np
import networkx as nx
import osmnx
import fiona
from shapely.geometry import shape
import geopandas as gpd
from pathlib import Path
import os
import sys
from numpy import object as np_object
import time
import filecmp
from utils import load_config

### Overrule the OSMNX default settings to get the additional metadata such as street lighting (lit)
osmnx.config(log_console=True, use_cache=True, useful_tags_path = osmnx.settings.useful_tags_path + ['lit'])
sys.setrecursionlimit(10**5)

def get_graph_from_polygon(PathShp, NetworkType, RoadTypes=None):
    """
    Get an OSMnx graph from a shapefile (input = path to shapefile).

    Args:
        PathShp [string]: path to shapefile (polygon) used to download from OSMnx the roads in that polygon
        NetworkType [string]: one of the network types from OSM, e.g. drive, drive_service, walk, bike, all
        RoadTypes [string]: formatted like "motorway|primary", one or multiple road types from OSM (highway)

    Returns:
        G [networkx multidigraph]
    """
    with fiona.open(PathShp) as source:
        for r in source:
            if 'geometry' in r:  # added this line to not take into account "None" geometry
                polygon = shape(r['geometry'])

    if RoadTypes == RoadTypes:
        # assuming the empty cell in the excel is a numpy.float64 nan value
        G = osmnx.graph_from_polygon(polygon=polygon, network_type=NetworkType, infrastructure='way["highway"~"{}"]'.format(RoadTypes))
    else:
        G = osmnx.graph_from_polygon(polygon=polygon, network_type=NetworkType)

    # we want to use undirected graphs, so turn into an undirected graph
    if type(G) == nx.classes.multidigraph.MultiDiGraph:
        G = G.to_undirected()

    return G

def fetch_roads(region, osm_pbf_path, **kwargs):
    """
    Function to extract all roads from OpenStreetMap for the specified region.

    Arguments:
        *osm_data* (string) -- string of data path where the OSM extracts (.osm.pbf) are located.
        *region* (string) -- NUTS3 code of region to consider.

        *log_file* (string) OPTIONAL -- string of data path where the log details should be written to

    Returns:
        *Geodataframe* -- Geopandas dataframe with all roads in the specified **region**.

    """

    ## LOAD FILE

    driver = ogr.GetDriverByName('OSM')
    data = driver.Open(osm_pbf_path)

    ## PERFORM SQL QUERY
    sql_lyr = data.ExecuteSQL("SELECT osm_id,highway,other_tags FROM lines WHERE highway IS NOT NULL")

    log_file = kwargs.get('log_file', None)  # if no log_file is provided when calling the function, no log will be made

    if log_file is not None:  # write to log file
        file = open(log_file, mode="a")
        file.write("\n\nRunning fetch_roads for region: {} at time: {}\n".format(region, time.strftime(
            "%a, %d %b %Y %H:%M:%S +0000", time.gmtime())))
        file.close()

    ## EXTRACT ROADS
    roads = []
    for feature in sql_lyr:  # Loop over all highway features
        if feature.GetField('highway') is not None:
            osm_id = feature.GetField('osm_id')
            shapely_geo = loads(feature.geometry().ExportToWkb())  # changed on 14/10/2019
            if shapely_geo is None:
                continue
            highway = feature.GetField('highway')
            try:
                other_tags = feature.GetField('other_tags')
                dct = OSM_dict_from_other_tags(other_tags)  # convert the other_tags string to a dict

                if 'lanes' in dct:  # other metadata can be drawn similarly
                    try:
                        # lanes = int(dct['lanes'])
                        lanes = int(round(float(dct['lanes']), 0))
                        # Cannot directly convert a float that is saved as a string to an integer;
                        # therefore: first integer to float; then road float, then float to integer
                    except:
                        if log_file is not None:  # write to log file
                            file = open(log_file, mode="a")
                            file.write(
                                "\nConverting # lanes to integer did not work for region: {} OSM ID: {} with other tags: {}".format(
                                    region, osm_id, other_tags))
                            file.close()
                        lanes = np.NaN  # added on 20/11/2019 to fix problem with UKH35
                else:
                    lanes = np.NaN

                if 'bridge' in dct:  # other metadata can be drawn similarly
                    bridge = dct['bridge']
                else:
                    bridge = np.NaN

                if 'lit' in dct:
                    lit = dct['lit']
                else:
                    lit = np.NaN

            except Exception as e:
                if log_file is not None:  # write to log file
                    file = open(log_file, mode="a")
                    file.write(
                        "\nException occured when reading metadata from 'other_tags', region: {}  OSM ID: {}, Exception = {}\n".format(
                            region, osm_id, e))
                    file.close()
                lanes = np.NaN
                bridge = np.NaN
                lit = np.NaN

            # roads.append([osm_id,highway,shapely_geo,lanes,bridge,other_tags]) #include other_tags to see all available metata
            roads.append([osm_id, highway, shapely_geo, lanes, bridge,
                          lit])  # ... but better just don't: it could give extra errors...
    ## SAVE TO GEODATAFRAME
    if len(roads) > 0:
        return gpd.GeoDataFrame(roads,columns=['osm_id','infra_type','geometry','lanes','bridge','lit'],crs={'init': 'epsg:4326'})
    else:
        print('No roads in {}'.format(region))
        if log_file is not None:
            file = open(log_file, mode="a")
            file.write('No roads in {}'.format(region))
            file.close()

def convert_osm(osm_convert_path, pbf, o5m):
    """
    Convers an osm PBF file to o5m
    Args:
        osm_convert_path:
        pbf:
        o5m:

    Returns:

    """

    command = '""{}"  "{}" --complete-ways -o="{}""'.format(osm_convert_path, pbf, o5m)
    os.system(command)

def filter_osm(osm_filter_path, o5m, filtered_o5m):
    """Filters an o5m OSM file to only motorways, trunks, primary and secondary roads
    """
    command = '""{}"  "{}" --keep="highway=motorway =motorway_link =primary =primary_link =secondary =secondary_link =trunk =trunk_link" > "{}""'.format(osm_filter_path, o5m, filtered_o5m)
    os.system(command)

def graph_to_gdf(G):
    """Takes in a networkx graph object and outputs shapefiles at the paths indicated by edge_shp and node_shp
    Arguments:
        G []: networkx graph object to be converted
        edge_shp [str]: output path including extension for edges shapefile
        node_shp [str]: output path including extension for nodes shapefile
    Returns:
        None
    """
    # now only multidigraphs and graphs are used
    if type(G) == nx.classes.graph.Graph:
        G = nx.MultiGraph(G)

    nodes, edges = osmnx.graph_to_gdfs(G)

    dfs = [edges, nodes]
    for df in dfs:
        for col in df.columns:
            if df[col].dtype == np_object and col != df.geometry.name:
                df[col] = df[col].astype(str)

    return edges, nodes

def create_network_from_osm_dump(o5m, o5m_filtered, osm_filter_exe, **kwargs):
    """
    Filters and generates a graph from an osm.pbf file
    Args:
        pbf: path object for .pbf file
        o5m: path for o5m file function object for filtering infrastructure from osm pbf file
        **kwargs: all kwargs to osmnx.graph_from_file method. Use simplify=False and retain_all=True to preserve max
        complexity when generating graph

    Returns:
        G: graph object
        nodes: geodataframe representing graph nodes
        edges: geodataframe representing graph edges
    """

    filter_osm(osm_filter_exe, o5m, o5m_filtered)
    G = osmnx.graph_from_file(o5m_filtered, **kwargs)
    G = G.to_undirected()
    edges, nodes = graph_to_gdf(G)

    return G, edges, nodes

def compare_files(ref_files, test_files):
    for ref_file, test_file in zip(ref_files, test_files):
        if str(test_file).endswith('nodes.geojson'):
            pass
        else:
            assert filecmp.cmp(ref_file, test_file), '{} and {} do are not the same'.format(str(ref_file), str(test_file))
        os.remove(test_file)

if __name__=='__main__':

    # run function
    root = Path(__file__).parents[2]
    test_output_dir = Path(load_config()['paths']['test_output'])
    test_input_osm_dumps_dir = Path(load_config()['paths']['test_OSM_dumps'])

    osm_filter_exe = root / 'osmfilter.exe'
    osm_convert_exe = root / 'osmconvert64.exe'
    pbf = test_input_osm_dumps_dir / r"NL332.osm.pbf"
    o5m = test_output_dir / r"NL332.o5m"
    o5m_filtered = test_output_dir / 'NL332_filtered.o5m'

    convert_osm(osm_convert_exe, pbf, o5m)
    filter_osm(osm_filter_exe, o5m,  o5m_filtered)
    G, edges, nodes = create_network_from_osm_dump(o5m, o5m_filtered, osm_filter_exe, simplify=True, retain_all=True)

    edges.to_file(test_output_dir / 'NL332_edges_simplified_retained.shp')
    nodes.to_file(test_output_dir / 'NL332_nodes_simplified_retained.shp')

    G, edges, nodes = create_network_from_osm_dump(o5m, o5m_filtered, osm_filter_exe, simplify=False, retain_all=False)

    edges.to_file(test_output_dir / 'NL332_edges.shp')
    nodes.to_file(test_output_dir / 'NL332_nodes.shp')

    G, edges, nodes = create_network_from_osm_dump(o5m, o5m_filtered, osm_filter_exe, simplify=False, retain_all=True)

    edges.to_file(test_output_dir / 'NL332_edges_retained.shp')
    nodes.to_file(test_output_dir / 'NL332_nodes_retained.shp')

    G, edges, nodes = create_network_from_osm_dump(o5m, o5m_filtered, osm_filter_exe, simplify=True, retain_all=False)

    edges.to_file(test_output_dir / 'NL332_edges_simplified.shp')
    nodes.to_file(test_output_dir / 'NL332_nodes_simplified.shp')
