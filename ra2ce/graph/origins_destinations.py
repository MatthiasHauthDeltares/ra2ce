# -*- coding: utf-8 -*-
"""
Created on 30-7-2021

@author: F.C. de Groen, Deltares
@author: M. Kwant, Deltares
"""

import logging
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import rasterio.transform
import rtree
from geopy import distance
from rasterio import Affine
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import LineString, MultiLineString, Point
from tqdm import tqdm, trange

from ra2ce.graph.networks_utils import line_length, pairs

# from shapely.geometry.point import Point


def read_OD_files(
    origin_paths,
    origin_names,
    destination_paths,
    destination_names,
    od_id,
    origin_count,
    crs_,
    region_paths,
    region_var,
):

    if region_paths:
        origin = gpd.GeoDataFrame(
            columns=[od_id, "o_id", "geometry", "region"], crs=crs_
        )
        region = gpd.read_file(region_paths)
        region = region[[region_var, "geometry"]]
    else:
        origin = gpd.GeoDataFrame(columns=[od_id, "o_id", "geometry"], crs=crs_)
    destination = gpd.GeoDataFrame(columns=[od_id, "d_id", "geometry"], crs=crs_)

    if isinstance(origin_paths, str):
        origin_paths = [origin_paths]
    if isinstance(destination_paths, str):
        destination_paths = [destination_paths]
    if isinstance(origin_names, str):
        origin_names = [origin_names]
    if isinstance(destination_names, str):
        destination_names = [destination_names]

    for op, on in zip(origin_paths, origin_names):
        origin_new = gpd.read_file(op, crs=crs_)
        try:
            origin_new[od_id] * 2  # just for checking
        except:
            origin_new[od_id] = origin_new.index

        if region_paths:
            origin_new = gpd.sjoin(left_df=origin_new, right_df=region, how="left")
            origin_new["region"] = origin_new[region_var]
            origin_new = origin_new[[od_id, origin_count, "geometry", "region"]]
            origin_new["region"].fillna("Not assigned", inplace=True)
        else:
            origin_new = origin_new[[od_id, origin_count, "geometry"]]
        origin_new["o_id"] = on + "_" + origin_new[od_id].astype(str)
        origin = origin.append(origin_new, ignore_index=True, sort=False)

    for dp, dn in zip(destination_paths, destination_names):
        destination_new = gpd.read_file(dp, crs=crs_)
        try:
            assert destination_new[od_id]
        except:
            destination_new[od_id] = destination_new.index
        destination_new = destination_new[[od_id, "geometry"]]
        destination_new["d_id"] = dn + "_" + destination_new[od_id].astype(str)
        destination = destination.append(destination_new, ignore_index=True, sort=False)

    od = pd.concat([origin, destination], sort=False)

    return od


def closest_node(node, nodes):
    deltas = nodes - node
    dist_2 = np.einsum('ij,ij->i', deltas, deltas)
    return nodes[np.argmin(dist_2)]


def get_od(o_id, d_id):
    match_name = o_id
    if match_name == "nan":
        match_name = (
            np.nan
        )  # convert string nans to np.nans to be able to differentiate between origins and destinations in the next step.
    if not match_name == match_name:
        # match_name is nan, the point is not an origin but a destination
        match_name = d_id
    return match_name


def add_data_to_existing_node(graph, node, match_name):
    if "od_id" in graph.nodes[node]:
        # the node already has a origin/destination attribute
        graph.nodes[node]["od_id"] = (
                graph.nodes[node]["od_id"] + "," + match_name
        )
    else:
        graph.nodes[node]["od_id"] = match_name
    return graph


def update_edges_with_new_node(graph, edge_data, node_a, node_b, k, line_a, line_b, new_node_id, graph_crs, inverse_vertices_dict):
    # Check which line is connected to which node. There can be 8 different combinations and there should be two
    # edges added to the graph.
    cnt = 0

    if Point(graph.nodes[node_a]["geometry"].coords[0]).almost_equals(Point(line_b.coords[-1])):
        edge_data.update(length=line_length(line_b, graph_crs), geometry=line_b)
        graph.add_edge(node_a, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_a, new_node_id, 0) for p in set(list(line_b.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_b]["geometry"].coords[0]).almost_equals(Point(line_b.coords[0])):
        edge_data.update(length=line_length(line_b, graph_crs), geometry=line_b)
        graph.add_edge(node_b, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_b, new_node_id, 0) for p in set(list(line_b.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_a]["geometry"].coords[0]).almost_equals(Point(line_b.coords[0])):
        edge_data.update(length=line_length(line_b, graph_crs), geometry=line_b)
        graph.add_edge(node_a, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_a, new_node_id, 0) for p in set(list(line_b.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_b]["geometry"].coords[0]).almost_equals(Point(line_b.coords[-1])):
        edge_data.update(length=line_length(line_b, graph_crs), geometry=line_b)
        graph.add_edge(node_b, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_b, new_node_id, 0) for p in set(list(line_b.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_b]["geometry"].coords[0]).almost_equals(Point(line_a.coords[0])):
        edge_data.update(length=line_length(line_a, graph_crs), geometry=line_a)
        graph.add_edge(node_b, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_b, new_node_id, 0) for p in set(list(line_a.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_a]["geometry"].coords[0]).almost_equals(Point(line_a.coords[-1])):
        edge_data.update(length=line_length(line_a, graph_crs), geometry=line_a)
        graph.add_edge(node_a, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_a, new_node_id, 0) for p in set(list(line_a.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_b]["geometry"].coords[0]).almost_equals(Point(line_a.coords[-1])):
        edge_data.update(length=line_length(line_a, graph_crs), geometry=line_a)
        graph.add_edge(node_b, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_b, new_node_id, 0) for p in set(list(line_a.coords[1:-1]))})

        cnt += 1

    if Point(graph.nodes[node_a]["geometry"].coords[0]).almost_equals(Point(line_a.coords[0])):
        edge_data.update(length=line_length(line_a, graph_crs), geometry=line_a)
        graph.add_edge(node_a, new_node_id, 0, **edge_data)

        # Update the inverse vertices dict
        inverse_vertices_dict.update(
            {p: (node_a, new_node_id, 0) for p in set(list(line_a.coords[1:-1]))})

        cnt += 1

    try:
        assert cnt == 2
    except AssertionError:
        logging.warning("No combination of nodes/road segments found for the OD assignment.")

    # remove the edge that is split in two from the graph
    graph.remove_edge(node_a, node_b, k)

    return graph, inverse_vertices_dict


def add_od_nodes(od: gpd.GeoDataFrame, graph, crs):
    """Gets from each origin and destination the closest vertice on the graph edge.
    Args:
        od [Geodataframe]: The GeoDataFrame with the origins and destinations
        graph [networkX graph]: networkX graph
        crs [string or pyproj crs]:
    Returns:
        od [Geodataframe]: The GeoDataFrame with the locations of the origins and destinations on the road vertices
        graph [networkX graph]: The networkX graph updated with origins and destinations
    """
    logging.info("Finding vertices closest to Origins and Destinations")

    # create dictionary of the roads geometries and identifyers
    edge_list = [e for e in graph.edges.data(keys=True) if "geometry" in e[-1]]
    inverse_vertices_dict = {}
    all_vertices = []
    for line in edge_list:
        # Add all vertices except the end-points as they belong to multiple edges and nodes already exist at the end-points
        inverse_vertices_dict.update(
            {p: (line[0], line[1], line[2]) for p in set(list(line[-1]["geometry"].coords[1:-1]))})

        # create list of all points to search in
        all_vertices.extend([p for p in set(list(line[-1]["geometry"].coords))])

    # Make an array from the list
    all_vertices = np.array(all_vertices)

    # Also create an inverse nodes dict of the node geometries as keys and node ID's as values
    inverse_nodes_dict = {node[-1]["geometry"].coords[0]: node[0] for node in graph.nodes.data()}

    # Get the maximum node id
    max_node_id = max([n for n in graph.nodes()])

    ODs = []
    for o_d_pointx, o_d_pointy, o_id, d_id in tqdm(list(zip(od['geometry'].x, od['geometry'].y, od['o_id'], od['d_id'])),
                          desc="Adding Origin-Destination nodes to graph"):
        match_name = get_od(o_id, d_id)

        # Find the vertice on the road that is closest to the origin or destination point
        closest_node_on_road = closest_node(np.array((o_d_pointx, o_d_pointy)), all_vertices)
        match_OD = Point(closest_node_on_road)

        # Find the road to which this vertice belongs. If the vertice is on an end-point of a road, it cannot be found
        # and it goes to the except statement.
        try:
            closest_u_v_k = inverse_vertices_dict[(closest_node_on_road[0], closest_node_on_road[1])]
            match_edge = graph.edges[closest_u_v_k]

            # Add the node to the graph edge
            match_geom = match_edge["geometry"]

            new_lines = split_line_with_points(match_geom, [match_OD])

            assert len(new_lines) == 2
            assert len([match_OD]) == 1

            line1, line2 = new_lines

            new_node_id = max_node_id + 1
            max_node_id = new_node_id

            # Add the new node to the graph
            graph.add_node(
                new_node_id,
                node_fid=new_node_id,  # Check if this attribute always exists
                y=match_OD.coords[0][1],
                x=match_OD.coords[0][0],
                geometry=match_OD,
                od_id=match_name,
            )

            # Update the inverse_nodes_dict with the new node
            inverse_nodes_dict[match_OD.coords[0]] = new_node_id

            # Delete the new node from the inverse_vertices_dict as no end-points are included here
            del inverse_vertices_dict[match_OD.coords[0]]

            # Update the graph edges and the inverse_vertices_dict
            graph, inverse_vertices_dict = update_edges_with_new_node(graph, match_edge, closest_u_v_k[0],
                                                                      closest_u_v_k[1], closest_u_v_k[2],
                                                                      line1, line2, new_node_id, crs,
                                                                      inverse_vertices_dict)

        except (KeyError, AssertionError):
            # If the vertice is at the end of the road it won't be found in the inverse_vertices_dict,
            # so search in the inverse_nodes_dict.
            match_node = inverse_nodes_dict[(closest_node_on_road[0], closest_node_on_road[1])]

            # Update the node with the OD attribute
            graph = add_data_to_existing_node(graph, match_node, match_name)

        # Save both in lists
        ODs.append(match_OD)  # save the point as a Shapely Point

    # save in dataframe
    od["OD"] = ODs

    # save the road vertices closest to the origin/destination as geometry, delete the input origin/destination point geometry
    od = gpd.GeoDataFrame(od, geometry="OD")
    od = od.drop(columns=["geometry"])

    return od, graph


def split_line_with_points(line, points):
    """Splits a line string in several segments considering a list of points."""
    segments = []
    current_line = line

    # make a list of points and its distance to the start to sort them from small to large distance
    list_dist = [current_line.project(pnt) for pnt in points]
    list_dist.sort()

    for d in list_dist:
        # cut the line at a distance d
        seg, current_line = cut(current_line, d)
        if seg:
            segments.append(seg)
    segments.append(current_line)
    return segments


def cut(line, distance):
    # Cuts a line in two at a distance from its starting point
    # This is taken from shapely manual
    if (distance <= 0.0) | (distance >= line.length):
        return [None, LineString(line)]

    if isinstance(line, LineString):
        coords = list(line.coords)
        for i, p in enumerate(coords):
            pd = line.project(Point(p))
            if pd == distance:
                return [LineString(coords[: i + 1]), LineString(coords[i:])]
            if pd > distance:
                cp = line.interpolate(distance)
                # check if the LineString contains an Z-value, if so, remove
                # only use XY because otherwise the snapping functionality doesn't work
                return [
                    LineString([xy[0:2] for xy in coords[:i]] + [(cp.x, cp.y)]),
                    LineString([(cp.x, cp.y)] + [xy[0:2] for xy in coords[i:]]),
                ]
    elif isinstance(line, MultiLineString):
        for ln in line:
            coords = list(ln.coords)
            for i, p in enumerate(coords):
                pd = ln.project(Point(p))
                if pd == distance:
                    return [LineString(coords[: i + 1]), LineString(coords[i:])]
                if pd > distance:
                    cp = ln.interpolate(distance)
                    # check if the LineString contains an Z-value, if so, remove
                    # only use XY because otherwise the snapping functionality doesn't work
                    return [
                        LineString([xy[0:2] for xy in coords[:i]] + [(cp.x, cp.y)]),
                        LineString([(cp.x, cp.y)] + [xy[0:2] for xy in coords[i:]]),
                    ]


#########################################################################################
################### Code to generate origins points from raster #########################
#########################################################################################


def rescale_and_crop(path_name, gdf, outputFolderPath, res=500):

    dst_crs = rasterio.crs.CRS.from_dict(gdf.crs.to_dict())

    # Rescale and reproject raster to gdf crs
    with rasterio.open(path_name) as src:

        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        m2degree = (
            1 / 111000
        )  # approximate conversion from meter to 1 degree of EPSG:4326; TODO: make flexible depending on the input crs
        transform = Affine(
            res * m2degree,
            transform.b,
            transform.c,
            transform.d,
            -res * m2degree,
            transform.f,
        )

        # use scale, instead of absolute meter, for resolution
        # scale = 2
        # transform = Affine(transform.a * scale, transform.b, transform.c, transform.d, transform.e * scale, transform.f)
        # height = height * scale
        # width = width * scale

        kwargs = src.meta.copy()
        kwargs.update(
            {"crs": dst_crs, "transform": transform, "width": width, "height": height}
        )

        with rasterio.open(
            outputFolderPath / "origins_raster_reprojected.tif", "w", **kwargs
        ) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.sum,
                )  # Resampling.sum or Resampling.nearest

    raster = rasterio.open(outputFolderPath / "origins_raster_reprojected.tif")

    # Crop to shapefile
    out_array, out_trans = rasterio.mask.mask(
        dataset=raster, shapes=gdf.geometry, crop=True
    )

    out_meta = raster.meta.copy()
    out_meta.update(
        {
            "height": out_array.shape[1],
            "width": out_array.shape[2],
            "transform": out_trans,
        }
    )
    raster.close()
    os.remove(outputFolderPath / "origins_raster_reprojected.tif")

    return out_array, out_meta


def export_raster_to_geotiff(array, meta, path, fileName):
    Cropped_outputfile = path / fileName
    with rasterio.open(
        Cropped_outputfile, "w", **meta, compress="LZW", tiled=True
    ) as dest:
        dest.write(array)
    return Cropped_outputfile


def generate_points_from_raster(fn, out_fn):
    # Read raster coordinate centroid
    with rasterio.open(fn) as src:
        points = []
        for col in range(src.width):
            x_s, y_s = rasterio.transform.xy(
                src.transform,
                [row for row in range(src.height)],
                [col for _ in range(src.height)],
            )
            points += [Point(x, y) for x, y in zip(x_s, y_s)]

    # Put raster coordinates into geodataframe
    gdf = gpd.GeoDataFrame()
    gdf["geometry"] = points
    gdf["OBJECTID"] = [x for x in range(len(gdf))]

    # Get raster values
    temp = [gdf["geometry"].x, gdf["geometry"].y]
    coords = list(map(list, zip(*temp)))
    with rasterio.open(fn) as src:
        gdf.crs = src.crs
        gdf["values"] = [sample[0] for sample in src.sample(coords)]

    # Save non-zero cells
    gdf.loc[gdf["values"] > 0].to_file(out_fn)

    return out_fn


def origins_from_raster(outputFolderPath, mask_fn, raster_fn):
    """Makes origin points from a population raster."""
    output_fn = outputFolderPath / "origins_raster.tif"
    mask = gpd.read_file(mask_fn[0])
    res = 1000  # in meter; TODO: put in config file or in network.ini
    out_array, out_meta = rescale_and_crop(raster_fn, mask, outputFolderPath, res)
    outputfile = export_raster_to_geotiff(
        out_array, out_meta, outputFolderPath, output_fn
    )

    out_array[out_array > 0] = 1
    print(
        "There are "
        + str(out_array[~np.isnan(out_array)].sum().sum())
        + " origin points."
    )

    out_fn = outputFolderPath / "origins_points.shp"
    out_fn = generate_points_from_raster(outputfile, out_fn)

    return out_fn
