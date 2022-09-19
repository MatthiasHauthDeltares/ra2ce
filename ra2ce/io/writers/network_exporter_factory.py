import logging
import pickle
from pathlib import Path
from typing import Any, List, Optional, Union

import geopandas as gpd
import networkx as nx

from ra2ce.io.writers.ra2ce_exporter_protocol import Ra2ceExporterProtocol

MULTIGRAPH_TYPE = Union[
    nx.classes.multigraph.MultiGraph, nx.classes.multidigraph.MultiDiGraph
]
NETWORK_TYPE = Union[gpd.GeoDataFrame, MULTIGRAPH_TYPE]


class NetworkExporterProtocol(Ra2ceExporterProtocol):
    _export_types: List[str] = ["pickle"]

    def export_to_shp(self, output_dir: Path, export_data: NETWORK_TYPE) -> None:
        pass

    def export_to_pickle(self, output_dir: Path, export_data: NETWORK_TYPE) -> None:
        pass

    def export(self, export_path: Path, export_data: Any) -> None:
        """
        Exports the given data to the specified types.
        TODO: I do not particularly like this approach, but at least gives better clarity on what the export options at the moment are.

        Args:
            export_path (Path): Path to the output directory where to export the data.
            export_data (Any): Data that needs to be exported.
        """
        if "pickle" in self._export_types:
            self.export_to_pickle(export_path, export_data)

        if "shp" in self._export_types:
            self.export_to_shp(export_path, export_data)


class MultiGraphNetworkExporter(NetworkExporterProtocol):
    pickle_path: Optional[Path]

    def __init__(self, basename: str, export_types: List[str]) -> None:
        self._basename = basename
        self._export_types = export_types
        self.pickle_path = None

    def export_to_shp(self, output_dir: Path, export_data: MULTIGRAPH_TYPE) -> None:
        if not output_dir.is_dir():
            output_dir.mkdir(parents=True)

        # graph_to_shp(
        #     export_data,
        #     output_folder / (self._basename + "_edges.shp"),
        #     output_folder / (self._basename + "_nodes.shp"),
        # )
        logging.info(
            f"Saved {self._basename + '_edges.shp'} and {self._basename + '_nodes.shp'} in {output_dir}."
        )

    def export_to_pickle(self, output_dir: Path, export_data: MULTIGRAPH_TYPE) -> None:
        self.pickle_path = output_dir / (self._basename + ".p")
        with open(self.pickle_path, "wb") as f:
            pickle.dump(export_data, f, protocol=4)
        logging.info(
            f"Saved {self.pickle_path.stem} in {self.pickle_path.resolve().parent}."
        )


class GeoDataFrameNetworkExporter(NetworkExporterProtocol):
    def __init__(self, basename: str, export_types: List[str]) -> None:
        self._basename = basename
        self._export_types = export_types
        self.pickle_path = None

    def export_to_shp(self, output_dir: Path, export_data: gpd.GeoDataFrame) -> None:
        _output_shp_path = output_dir / (self._basename + ".shp")
        export_data.to_file(
            _output_shp_path, index=False
        )  # , encoding='utf-8' -Removed the encoding type because this causes some shapefiles not to save.
        logging.info(f"Saved {_output_shp_path.stem} in {output_dir}.")

    def export_to_pickle(self, output_dir: Path, export_data: gpd.GeoDataFrame) -> None:
        self.pickle_path = output_dir / (self._basename + ".feather")
        export_data.to_feather(self.pickle_path, index=False)
        logging.info(f"Saved {self.pickle_path.stem} in {output_dir}.")


class NetworkExporterFactory:
    @staticmethod
    def get_exporter(network: NETWORK_TYPE) -> NetworkExporterProtocol:
        _network_type = type(network)
        if _network_type == gpd.GeoDataFrame:
            pass
        elif _network_type in [
            nx.classes.multigraph.MultiGraph,
            nx.classes.multidigraph.MultiDiGraph,
        ]:
            pass
