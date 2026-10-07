# pip install rasterio

from contextlib import ExitStack
from pathlib import Path

import rasterio
from rasterio.merge import merge


def merge_tifs(input_files, output_file, nodata="auto", overwrite=False, verbose=True):
    """Merge adjacent/overlapping GeoTIFFs into one mosaic.

    input_files : list of paths (2 or more)
    output_file : path of the merged tif
    nodata      : "auto" = use the nodata value of the first file,
                  or pass a number (e.g. 0) if your files have none
    overwrite   : replace output_file if it already exists
    Returns the output path.
    """
    input_files = [str(p) for p in input_files]
    output_file = Path(output_file)

    if len(input_files) < 2:
        raise ValueError(f"Need at least 2 files, got {len(input_files)}: {input_files}")
    if output_file.exists() and not overwrite:
        if verbose:
            print(f"Skipping (already exists): {output_file}")
        return output_file
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with ExitStack() as stack:
        srcs = [stack.enter_context(rasterio.open(p)) for p in input_files]
        ref = srcs[0]

        # sanity checks: these must match for a clean merge
        for p, s in zip(input_files, srcs):
            if s.crs != ref.crs:
                raise ValueError(f"CRS mismatch in {p}: {s.crs} vs {ref.crs}")
            if s.count != ref.count:
                raise ValueError(f"Band count mismatch in {p}: {s.count} vs {ref.count}")
            if s.dtypes[0] != ref.dtypes[0]:
                raise ValueError(f"Dtype mismatch in {p}: {s.dtypes[0]} vs {ref.dtypes[0]}")
            if verbose and abs(s.res[0] - ref.res[0]) > 1e-9:
                print(f"  Warning: pixel size differs in {p}: {s.res} vs {ref.res}")

        nd = ref.nodata if nodata == "auto" else nodata

        
        opts = {"compress": "deflate", "tiled": True, "BIGTIFF": "IF_SAFER"}

        # JPEG-compressed RGBs are stored as YCbCr, which GDAL only allows with JPEG compression.
        # Check every place GDAL might report it.
        struct = ref.tags(ns="IMAGE_STRUCTURE")
        is_ycbcr = (
            "ycbcr" in " ".join(str(v).lower() for v in struct.values())
            or str(ref.profile.get("photometric", "")).lower() == "ycbcr"
            )
        if is_ycbcr:
            opts["photometric"] = "RGB"

        try:
            # rasterio >= 1.4: writes straight to disk (memory-friendly)
            merge(srcs, nodata=nd, dst_path=str(output_file), dst_kwds=opts)
        except TypeError:
            # older rasterio: mosaic in memory, then write
            mosaic, transform = merge(srcs, nodata=nd)
            profile = ref.profile.copy()
            profile.update(driver="GTiff", height=mosaic.shape[1], width=mosaic.shape[2],
                           transform=transform, nodata=nd, **opts)
            with rasterio.open(output_file, "w", **profile) as dst:
                dst.write(mosaic)

    if verbose:
        with rasterio.open(output_file) as out:
            print(f"Done: {output_file}  ({out.width}x{out.height}, {out.count} bands)")
    return output_file

