from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask


def clip_tifs(tif_names, aoi_path, folder, suffix="_clipped", overwrite=False):
    """Clip several TIFFs to an AOI and save them next to the originals.

    tif_names : list of file names, e.g. ["ms_post.tif", "ms_pre.tif"]
    aoi_path  : path to the AOI file (.gpkg, .geojson, ...)
    folder    : folder containing the TIFFs (the clipped files are saved here too)
    suffix    : added to the output file name (ms_post.tif -> ms_post_clipped.tif)
    overwrite : if False, files that are already clipped are skipped
    """
    folder = Path(folder)
    aoi = gpd.read_file(aoi_path)
    out_paths = []

    for name in tif_names:
        out_path = folder / name.replace(".tif", f"{suffix}.tif")

        if out_path.exists() and not overwrite:
            print("skipping (already exists):", out_path.name)
            out_paths.append(out_path)
            continue

        print("clipping", name, flush=True)
        with rasterio.open(folder / name) as src:
            aoi_proj = aoi.to_crs(src.crs)
            out_img, out_transform = mask(src, aoi_proj.geometry, crop=True)

            meta = src.meta.copy()
            meta.update(
                height=out_img.shape[1],
                width=out_img.shape[2],
                transform=out_transform,
                compress="lzw",
            )

        with rasterio.open(out_path, "w", **meta) as dst:
            dst.write(out_img)

        del out_img
        out_paths.append(out_path)

    return out_paths