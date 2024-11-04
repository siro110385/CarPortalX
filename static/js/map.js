class MapManager {
    constructor(mapId) {
        this.map = L.map(mapId).setView([37.7749, -122.4194], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(this.map);
        this.routeLayer = null;
        this.markers = [];
        this.autocompleteDropdowns = {};
        this.currentLocationMarker = null;
        this.apiKey = document.querySelector('meta[name="ors-api-key"]').content;
    }

    async searchAddress(query, inputElement) {
        try {
            const response = await fetch(`https://api.openrouteservice.org/geocode/search?text=${encodeURIComponent(query)}&size=5&boundary.country=US`, {
                method: 'GET',
                headers: {
                    'Authorization': this.apiKey,
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                console.error('API Error:', errorData);
                throw new Error(`Geocoding failed: ${JSON.stringify(errorData)}`);
            }

            const data = await response.json();
            this.showAutocompleteResults(data.features, inputElement);
            return data.features;
        } catch (error) {
            console.error('Address search failed:', error);
            this.showError('Address search failed. Please try again.');
            return [];
        }
    }

    async calculateRouteWithStops(points) {
        try {
            console.log('Calculating route with points:', points);
            
            // Validate coordinates
            for (const [lng, lat] of points) {
                if (!this.isValidCoordinate(lat, lng)) {
                    throw new Error('Invalid coordinates detected');
                }
            }

            const payload = {
                coordinates: points,
                radiuses: Array(points.length).fill(500), // Increase search radius to 500m
                geometry_simplify: false,
                instructions: true,
                preference: "recommended"
            };
            
            const response = await fetch('https://api.openrouteservice.org/v2/directions/driving-car', {
                method: 'POST',
                headers: {
                    'Authorization': this.apiKey,
                    'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
                    'Content-Type': 'application/json; charset=utf-8'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                console.error('API Error:', errorData);
                throw new Error(`Route calculation failed: ${errorData.error?.message || 'Unknown error'}`);
            }

            const data = await response.json();
            if (!data.features || !data.features[0]) {
                throw new Error('Invalid response format from API');
            }

            const totalDistance = data.features[0].properties.segments.reduce(
                (acc, segment) => acc + segment.distance, 0
            ) / 1000;  // Convert to km

            return {
                route: data.features[0].geometry,
                distance: totalDistance
            };
        } catch (error) {
            console.error('Route calculation failed:', error);
            this.showError(`Unable to calculate route: ${error.message}`);
            throw error;
        }
    }

    isValidCoordinate(lat, lng) {
        return (
            typeof lat === 'number' && 
            typeof lng === 'number' && 
            lat >= -90 && lat <= 90 && 
            lng >= -180 && lng <= 180 &&
            !isNaN(lat) && !isNaN(lng)
        );
    }

    async updateRoute() {
        try {
            const pickupLat = parseFloat(document.getElementById('pickup_lat').value);
            const pickupLng = parseFloat(document.getElementById('pickup_lng').value);
            const dropoffLat = parseFloat(document.getElementById('dropoff_lat').value);
            const dropoffLng = parseFloat(document.getElementById('dropoff_lng').value);

            if (!this.isValidCoordinate(pickupLat, pickupLng)) {
                throw new Error('Invalid pickup coordinates');
            }
            if (!this.isValidCoordinate(dropoffLat, dropoffLng)) {
                throw new Error('Invalid dropoff coordinates');
            }

            this.clearMarkers();
            
            // Collect all stops
            const stops = Array.from(document.querySelectorAll('.stop-entry')).map(entry => {
                const lat = parseFloat(entry.querySelector('.stop-lat').value);
                const lng = parseFloat(entry.querySelector('.stop-lng').value);
                if (!this.isValidCoordinate(lat, lng)) {
                    throw new Error('Invalid stop coordinates');
                }
                return [lng, lat];  // ORS expects [longitude, latitude]
            }).filter(coords => !isNaN(coords[0]) && !isNaN(coords[1]));

            // Add markers
            this.addMarker(pickupLat, pickupLng, 'Pickup');
            stops.forEach((stop, index) => {
                this.addMarker(stop[1], stop[0], `Stop ${index + 1}`);
            });
            this.addMarker(dropoffLat, dropoffLng, 'Drop-off');

            // Prepare all points in order
            const points = [[pickupLng, pickupLat], ...stops, [dropoffLng, dropoffLat]];
            console.log('Route Points:', points);
            
            const routeData = await this.calculateRouteWithStops(points);
            this.displayRoute(routeData.route);
            this.updateDistanceAndFare(routeData.distance);
            document.getElementById('route_data').value = JSON.stringify(routeData.route);
            document.getElementById('bookButton').disabled = false;
        } catch (error) {
            console.error('Error updating route:', error);
            this.showError(error.message);
            document.getElementById('bookButton').disabled = true;
        }
    }

    // ... rest of the MapManager class remains the same ...
}
