"""
 If installing cetk on Windows, and receiving error message
'Could not find the GDAL library', then run this script and modify
"C:\OSGeo4W\apps\Python312\Lib\site-packages\django\contrib\gis\gdal\libgdal.py"
such that lib_names if os.name == "nt" includes the gdal version you have installed,
for example by adding "gdal309", on line 25.
"""

import glob

pattern = r"c:\osgeo4w\bin\gdal*.dll"
matching_files = glob.glob(pattern)
print(matching_files)
