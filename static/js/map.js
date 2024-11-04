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

    async reverseGeocode(lat, lng, type) {
        try {
            const response = await fetch(`https://api.openrouteservice.org/geocode/reverse?point.lat=${lat}&point.lon=${lng}`, {
                method: 'GET',
                headers: {
                    'Authorization': this.apiKey,
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`Reverse geocoding failed: ${response.statusText}`);
            }

            const data = await response.json();
            if (data.features && data.features.length > 0) {
                const address = data.features[0].properties.label;
                document.getElementById(type).value = address;
                this.updateLocationFields(type, lat, lng);
                return address;
            }
            throw new Error('No address found');
        } catch (error) {
            console.error('Reverse geocoding failed:', error);
            this.showError('Could not get address for location.');
            return null;
        }
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

    // ... rest of the MapManager class methods remain the same ...
}
