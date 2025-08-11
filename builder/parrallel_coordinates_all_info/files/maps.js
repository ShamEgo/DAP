// map.js
// ─────────────────────────────────────────────────────────────────
// 1) initialize Leaflet
var map = L.map('map').setView([-25.3, 133.8], 4);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// 2) a layer to hold tower markers
var towerLayer = L.layerGroup().addTo(map);

// 3) redraw whenever the filtered set changes
model.on('change:filtered', function(m) {
  var rows = m.get('filtered');
  towerLayer.clearLayers();

  rows.forEach(function(d) {
    var lat = +d.Latitude, lon = +d.Longitude;
    if ( !isNaN(lat) && !isNaN(lon) ) {
      L.circleMarker([lat,lon], {
        radius: 6, fillOpacity: 0.8, color: '#333', fillColor: '#FF5722'
      })
      .bindPopup(
        '<strong>' + d.SiteName + '</strong><br/>' +
        'Class: ' + d.StructureClassCode + '<br/>' +
        'Height: ' + d.Height + ' m'
      )
      .addTo(towerLayer);
    }
  });

  // fit map to markers
  var pts = rows
    .map(d => [+d.Latitude, +d.Longitude])
    .filter(p => !isNaN(p[0]));
  if (pts.length) map.fitBounds(pts, { padding: [40,40], maxZoom: 12 });
});

// 4) initial draw
updateMap = function(rows) { /* stub so code above can call */ };
model.trigger('change:filtered', model);
