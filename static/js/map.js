const ORS_API_KEY = 'YOUR_API_KEY'; // Will be injected from backend

class MapManager {
    constructor(mapId) {
        this.map = L.map(mapId).setView([0, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(this.map);
        this.routeLayer = null;
        this.markers = [];
    }

    async geocodeAddress(address) {
        const response = await fetch(`https://api.openrouteservice.org/geocode/search?api_key=${ORS_API_KEY}&text=${encodeURIComponent(address)}`);
        const data = await response.json();
        if (data.features && data.features.length > 0) {
            return data.features[0].geometry.coordinates;
        }
        throw new Error('Address not found');
    }

    async calculateRoute(start, end) {
        const response = await fetch(`https://api.openrouteservice.org/v2/directions/driving-car`, {
            method: 'POST',
            headers: {
                'Authorization': ORS_API_KEY,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                coordinates: [start, end]
            })
        });
        const data = await response.json();
        return {
            route: data.features[0].geometry,
            distance: data.features[0].properties.summary.distance
        };
    }

    displayRoute(routeGeometry) {
        if (this.routeLayer) {
            this.map.removeLayer(this.routeLayer);
        }
        this.routeLayer = L.geoJSON(routeGeometry).addTo(this.map);
        this.map.fitBounds(this.routeLayer.getBounds());
    }

    addMarker(lat, lng, title) {
        const marker = L.marker([lat, lng], {title}).addTo(this.map);
        this.markers.push(marker);
        return marker;
    }

    clearMarkers() {
        this.markers.forEach(marker => this.map.removeLayer(marker));
        this.markers = [];
    }
}
