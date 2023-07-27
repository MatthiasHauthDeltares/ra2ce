from pathlib import Path
import pytest

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point, MultiLineString

from tests import test_data
from ra2ce.graph.shp_network_wrapper.vector_network_wrapper import VectorNetworkWrapper

_test_dir = test_data / "vector_network_wrapper"


class TestVectorNetworkWrapper:
    @pytest.fixture
    def points_gdf(self) -> gpd.GeoDataFrame:
        points = [Point(-122.3, 47.6), Point(-122.2, 47.5), Point(-122.1, 47.6)]
        return gpd.GeoDataFrame(geometry=points, crs=4326)

    @pytest.fixture
    def lines_gdf(self) -> gpd.GeoDataFrame:
        points = [Point(-122.3, 47.6), Point(-122.2, 47.5), Point(-122.1, 47.6)]
        lines = [LineString([points[0], points[1]]), LineString([points[1], points[2]])]
        return gpd.GeoDataFrame(geometry=lines, crs=4326)

    @pytest.fixture
    def mock_graph(self):
        points = [(-122.3, 47.6), (-122.2, 47.5), (-122.1, 47.6)]
        lines = [(points[0], points[1]), (points[1], points[2])]

        graph = nx.Graph(crs=4326)
        for point in points:
            graph.add_node(point, geometry=Point(point))
        for line in lines:
            graph.add_edge(
                line[0], line[1], geometry=LineString([Point(line[0]), Point(line[1])])
            )

        return graph

    def test_init_without_crs_sts_default(self):
        # 1. Define test data.
        _primary_files = [Path("dummy_primary")]
        _region = Path("dummy_region")
        _crs_value = ""

        # 2. Run test.
        _wrapper = VectorNetworkWrapper(_primary_files, _region, _crs_value, False)

        # 3. Verify expectations.
        assert isinstance(_wrapper, VectorNetworkWrapper)
        assert _wrapper.primary_files == _primary_files
        assert _wrapper.region_path == _region
        assert str(_wrapper.crs) == "epsg:4326"

    @pytest.fixture
    def _valid_wrapper(self) -> VectorNetworkWrapper:
        _network_dir = _test_dir.joinpath("static", "network")
        yield VectorNetworkWrapper(
            primary_files=[_network_dir.joinpath("_test_lines.geojson")],
            region_path=None,
            crs_value=4326,
            is_directed=False,
        )

    def test_read_vector_to_project_region_and_crs(
        self, _valid_wrapper: VectorNetworkWrapper
    ):
        # Given
        assert not _valid_wrapper.directed

        # When
        vector = _valid_wrapper._read_vector_to_project_region_and_crs()

        # Then
        assert isinstance(vector, gpd.GeoDataFrame)

    def test_read_vector_to_project_region_and_crs_with_region(
        self, _valid_wrapper: VectorNetworkWrapper
    ):
        # Given
        _valid_wrapper.region_path = _test_dir / "_test_polygon.geojson"
        _expected_region = gpd.read_file(_valid_wrapper.region_path)
        assert isinstance(_expected_region, gpd.GeoDataFrame)

        # When
        vector = _valid_wrapper._read_vector_to_project_region_and_crs()

        # Then
        assert vector.crs == _expected_region.crs
        assert _expected_region.covers(vector.unary_union).all()

    @pytest.mark.parametrize(
        "region_path",
        [
            pytest.param(None, id="No region"),
            pytest.param(_test_dir / "_test_polygon.geojson", id="With region"),
        ],
    )
    def test_get_network_from_vector(
        self, _valid_wrapper: VectorNetworkWrapper, region_path: Path
    ):
        # Given
        _valid_wrapper.region_path = region_path

        # When
        graph, edges = _valid_wrapper.get_network_from_vector()

        # Then
        assert isinstance(graph, nx.MultiGraph)
        assert isinstance(edges, gpd.GeoDataFrame)

    def test_clean_vector(self, lines_gdf: gpd.GeoDataFrame):
        # Given
        gdf1 = VectorNetworkWrapper.explode_and_deduplicate_geometries(lines_gdf)

        # When
        gdf2 = VectorNetworkWrapper.clean_vector(
            lines_gdf
        )  # for now cleanup only does the above

        # Then
        assert gdf1.equals(gdf2)

    def test_get_indirect_graph_from_vector(self, lines_gdf: gpd.GeoDataFrame):
        # When
        graph = VectorNetworkWrapper.get_indirect_graph_from_vector(lines_gdf)

        # Then
        assert graph.nodes(data="geometry") is not None
        assert graph.edges(data="geometry") is not None
        assert graph.graph["crs"] == lines_gdf.crs
        assert isinstance(graph, nx.Graph) and not isinstance(graph, nx.DiGraph)

    def test_get_direct_graph_from_vector(self, lines_gdf: gpd.GeoDataFrame):
        # When
        graph = VectorNetworkWrapper.get_direct_graph_from_vector(lines_gdf)

        # Then
        assert isinstance(graph, nx.DiGraph)

    def test_get_network_edges_and_nodes_from_graph(
        self, mock_graph, points_gdf, lines_gdf
    ):
        # When
        edges, nodes = VectorNetworkWrapper.get_network_edges_and_nodes_from_graph(
            mock_graph
        )

        # Then
        assert edges.geometry.equals(lines_gdf.geometry)
        assert nodes.geometry.equals(points_gdf.geometry)
        assert set(["node_A", "node_B", "edge_fid"]).issubset(edges.columns)
        assert set(["node_fid"]).issubset(nodes.columns)

    def test_explode_and_deduplicate_geometries(self, lines_gdf):
        # Given
        multi_lines = lines_gdf.geometry.apply(lambda x: MultiLineString([x]))

        # When
        gdf = VectorNetworkWrapper.explode_and_deduplicate_geometries(multi_lines)

        # Then
        assert isinstance(gdf.geometry.iloc[0], LineString)
