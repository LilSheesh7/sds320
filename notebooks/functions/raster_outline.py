"""
Create a polygon (GeoPackage) of the outline of the valid, non-black area of a raster.

Usage in the notebook:
    from functions.raster_outline import raster_outline

    raster_outline("../data/processed/rgb_pre_clipped.tif",
                   "../GIS/aoi_clipped.gpkg", layer="aoi_pre")
"""
from pathlib import Path

import numpy as np
import rasterio
import geopandas as gpd
from rasterio.enums import MaskFlags
from rasterio.features import shapes
from scipy.ndimage import binary_fill_holes
from shapely.geometry import shape, box
from shapely.ops import unary_union


def raster_outline(raster_path, out_gpkg=None, layer="outline",
                   background_value=0, fill_holes=True, min_area=0,
                   save_extent=False):
    """
    Polygon of the area of a raster that contains data.

    A pixel counts as "empty" if it is nodata (when the raster has a nodata value)
    or if it equals `background_value` (default 0 = black) in every band.

    Parameters
    ----------
    raster_path : str or Path
        Input raster (.tif).
    out_gpkg : str or Path, optional
        Output GeoPackage. If None, nothing is written, only returned.
    layer : str
        Layer name in the GeoPackage.
    background_value : int or float or None
        Value that counts as empty in all bands (0 = black).
        None = use only the nodata value / internal mask of the raster.
    fill_holes : bool
        Fill holes inside the outline (e.g. black roofs or shadows).
    min_area : float
        Drop polygon parts smaller than this (in CRS units², e.g. m²).
        Useful against single stray pixels.
    save_extent : bool
        Also write the rectangle of the raster extent as layer "<layer>_extent".
        Needed if you want to rebuild a clip with exactly the same pixel grid.

    Returns
    -------
    geopandas.GeoDataFrame with one (Multi)Polygon and its area.
    """
    raster_path = Path(raster_path)

    with rasterio.open(raster_path) as src:
        # 1) mask of pixels with data (band by band to save memory)
        if background_value is None:
            inside = np.ones((src.height, src.width), dtype=bool)
        else:
            inside = np.zeros((src.height, src.width), dtype=bool)
            for b in range(1, src.count + 1):
                inside |= src.read(b) != background_value

        # respect nodata value / internal mask, if the raster has one
        if MaskFlags.all_valid not in src.mask_flag_enums[0]:
            inside &= src.dataset_mask() > 0

        if fill_holes:
            inside = binary_fill_holes(inside)

        if not inside.any():
            raise ValueError(f"{raster_path.name}: no non-empty pixels found")

        # 2) vectorize the mask
        polys = [shape(geom) for geom, val in
                 shapes(inside.astype("uint8"), mask=inside, transform=src.transform)
                 if val == 1]
        crs, bounds = src.crs, src.bounds

    geom = unary_union(polys)

    # 3) remove tiny parts
    if min_area > 0 and geom.geom_type == "MultiPolygon":
        parts = [p for p in geom.geoms if p.area >= min_area]
        geom = unary_union(parts) if parts else geom

    gdf = gpd.GeoDataFrame({"source": [raster_path.name]}, geometry=[geom], crs=crs)
    gdf["area_m2"] = gdf.area if crs and crs.is_projected else np.nan

    # 4) write
    if out_gpkg is not None:
        out_gpkg = Path(out_gpkg)
        out_gpkg.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_gpkg, layer=layer, driver="GPKG")
        if save_extent:
            ext = gpd.GeoDataFrame({"source": [raster_path.name]},
                                   geometry=[box(*bounds)], crs=crs)
            ext.to_file(out_gpkg, layer=f"{layer}_extent", driver="GPKG")
        n_parts = len(geom.geoms) if geom.geom_type == "MultiPolygon" else 1
        print(f"{raster_path.name} -> {out_gpkg.name} (layer '{layer}'), "
              f"{n_parts} part(s), area {gdf['area_m2'].iloc[0]:.0f} m²")

    return gdf