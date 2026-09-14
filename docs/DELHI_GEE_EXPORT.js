// Hazard Intelligence Engine — Delhi static-data exports
// CRS: EPSG:4326 | target scale: 60 metres
// Run this in https://code.earthengine.google.com (using your own project) and
// start the 33 Tasks.

var DISTRICTS = {
  central: [77.167901, 28.571167, 77.303197, 28.788141],
  east: [77.269601, 28.583839, 77.342563, 28.657921],
  new_delhi: [77.050629, 28.483932, 77.256066, 28.646095],
  north: [76.961797, 28.684401, 77.224393, 28.883500],
  north_east: [77.216027, 28.670071, 77.298273, 28.786533],
  north_west: [76.941891, 28.656122, 77.185831, 28.818183],
  shahadara: [77.249939, 28.640011, 77.332922, 28.713984],
  south: [77.110778, 28.404668, 77.252639, 28.569243],
  south_east: [77.200160, 28.480652, 77.347570, 28.608668],
  south_west: [76.838892, 28.500777, 77.106151, 28.670189],
  west: [76.953800, 28.596217, 77.181193, 28.702051]
};

var chirpsSource = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
  .filterDate('2023-01-01', '2025-12-31')
  .select('precipitation')
  .mean();
// Set these to the flood/landslide asset ids you host or subscribe to.
var gfsmSource = ee.ImageCollection('YOUR_FLOOD_IMAGE_COLLECTION_ID').mosaic();
var ilsmSource = ee.Image('YOUR_LANDSLIDE_IMAGE_ID');

Object.keys(DISTRICTS).forEach(function(key) {
  var region = ee.Geometry.Rectangle(DISTRICTS[key]);
  var exportArgs = {folder: 'sih_gee', scale: 60, crs: 'EPSG:4326', region: region, maxPixels: 1e9};
  Export.image.toDrive(Object.assign({}, exportArgs, {
    image: chirpsSource.clip(region), description: 'chirps_rainfall_' + key,
    fileNamePrefix: 'chirps_rainfall_' + key
  }));
  Export.image.toDrive(Object.assign({}, exportArgs, {
    image: gfsmSource.clip(region), description: 'flood_gfsm_' + key,
    fileNamePrefix: 'flood_gfsm_' + key
  }));
  Export.image.toDrive(Object.assign({}, exportArgs, {
    image: ilsmSource.clip(region), description: 'ilsm_' + key,
    fileNamePrefix: 'ilsm_' + key
  }));
});

print('Created 33 export tasks: CHIRPS, GFSM and ILSM for 11 Delhi districts.');
