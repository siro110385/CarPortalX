class MapManager {
    constructor(mapId) {
        this.map = L.map(mapId).setView([37.7749, -122.4194], 12); // Default to San Francisco
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(this.map);
        this.routeLayer = null;
        this.markers = [];
        this.autocompleteDropdowns = {};
    }

    async searchAddress(query, inputElement) {
        try {
            const response = await fetch(`https://api.openrouteservice.org/geocode/autocomplete`, {
                headers: {
                    'Authorization': document.querySelector('meta[name="ors-api-key"]').content
                },
                method: 'GET',
                params: {
                    'text': query,
                    'boundary.country': 'US',
                    'size': 5
                }
            });

            if (!response.ok) {
                throw new Error(`Geocoding failed: ${response.statusText}`);
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

    showAutocompleteResults(features, inputElement) {
        const dropdownId = `${inputElement.id}-dropdown`;
        let dropdown = document.getElementById(dropdownId);
        
        if (!dropdown) {
            dropdown = document.createElement('ul');
            dropdown.id = dropdownId;
            dropdown.className = 'address-dropdown';
            inputElement.parentNode.appendChild(dropdown);
            this.autocompleteDropdowns[inputElement.id] = dropdown;
        }

        dropdown.innerHTML = '';
        features.forEach(feature => {
            const li = document.createElement('li');
            li.textContent = feature.properties.label;
            li.addEventListener('click', () => {
                inputElement.value = feature.properties.label;
                const coords = feature.geometry.coordinates;
                this.updateLocationFields(inputElement.id, coords[1], coords[0]);
                dropdown.style.display = 'none';
            });
            dropdown.appendChild(li);
        });
        
        dropdown.style.display = features.length ? 'block' : 'none';
    }

    updateLocationFields(inputId, lat, lng) {
        const type = inputId.includes('pickup') ? 'pickup' : 'dropoff';
        document.getElementById(`${type}_lat`).value = lat;
        document.getElementById(`${type}_lng`).value = lng;
        this.updateMarkerAndRoute();
    }

    async calculateRoute(start, end) {
        try {
            const response = await fetch('https://api.openrouteservice.org/v2/directions/driving-car', {
                method: 'POST',
                headers: {
                    'Authorization': document.querySelector('meta[name="ors-api-key"]').content,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    coordinates: [[start[1], start[0]], [end[1], end[0]]],
                    format: 'geojson'
                })
            });

            if (!response.ok) {
                throw new Error(`Route calculation failed: ${response.statusText}`);
            }

            const data = await response.json();
            return {
                route: data.features[0].geometry,
                distance: data.features[0].properties.segments[0].distance
            };
        } catch (error) {
            console.error('Route calculation failed:', error);
            this.showError('Unable to calculate route. Please try different locations.');
            throw error;
        }
    }

    updateMarkerAndRoute() {
        const pickupLat = document.getElementById('pickup_lat').value;
        const pickupLng = document.getElementById('pickup_lng').value;
        const dropoffLat = document.getElementById('dropoff_lat').value;
        const dropoffLng = document.getElementById('dropoff_lng').value;

        if (pickupLat && pickupLng && dropoffLat && dropoffLng) {
            this.clearMarkers();
            
            // Add markers
            this.addMarker(pickupLat, pickupLng, 'Pickup');
            this.addMarker(dropoffLat, dropoffLng, 'Drop-off');

            // Calculate and display route
            this.calculateRoute([pickupLng, pickupLat], [dropoffLng, dropoffLat])
                .then(routeData => {
                    this.displayRoute(routeData.route);
                    this.updateDistanceAndFare(routeData.distance);
                })
                .catch(error => {
                    console.error('Error updating route:', error);
                });
        }
    }

    displayRoute(routeGeometry) {
        if (this.routeLayer) {
            this.map.removeLayer(this.routeLayer);
        }
        this.routeLayer = L.geoJSON(routeGeometry).addTo(this.map);
        this.map.fitBounds(this.routeLayer.getBounds());
    }

    updateDistanceAndFare(distance) {
        const distanceKm = distance / 1000;
        document.getElementById('distance').textContent = `${distanceKm.toFixed(2)} km`;
        document.getElementById('distance_value').value = distanceKm;
        
        // Calculate fare ($2 per km + $5 base fare)
        const fare = (distanceKm * 2) + 5;
        document.getElementById('fare').textContent = `$${fare.toFixed(2)}`;
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

    showError(message) {
        const errorDiv = document.getElementById('booking-error');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }
}
