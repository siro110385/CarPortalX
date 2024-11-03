class MapManager {
    constructor(mapId) {
        this.map = L.map(mapId).setView([37.7749, -122.4194], 12); // Default to San Francisco
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(this.map);
        this.routeLayer = null;
        this.markers = [];
        this.autocompleteDropdowns = {};
        this.currentLocationMarker = null;
    }

    async searchAddress(query, inputElement) {
        try {
            const response = await fetch(`https://api.openrouteservice.org/geocode/search?api_key=${document.querySelector('meta[name="ors-api-key"]').content}&text=${encodeURIComponent(query)}`, {
                headers: {
                    'Accept': 'application/json'
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

    async reverseGeocode(lat, lng, type) {
        try {
            const response = await fetch(`https://api.openrouteservice.org/geocode/reverse?api_key=${document.querySelector('meta[name="ors-api-key"]').content}&point.lat=${lat}&point.lon=${lng}`, {
                headers: {
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

    initGeolocation() {
        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    this.map.setView([latitude, longitude], 15);
                    if (this.currentLocationMarker) {
                        this.map.removeLayer(this.currentLocationMarker);
                    }
                    this.currentLocationMarker = L.marker([latitude, longitude], {
                        title: 'Your Location'
                    }).addTo(this.map);
                },
                (error) => {
                    console.error('Geolocation error:', error);
                    this.showError('Could not detect your location.');
                }
            );
        }
    }

    async calculateRoute(start, end) {
        try {
            const apiKey = document.querySelector('meta[name="ors-api-key"]').content;
            const response = await fetch('https://api.openrouteservice.org/v2/directions/driving-car', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json, application/geo+json',
                    'Content-Type': 'application/json',
                    'Authorization': apiKey
                },
                body: JSON.stringify({
                    coordinates: [start, end],
                    format: 'geojson'
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`Route calculation failed: ${errorData.error || response.statusText}`);
            }

            const data = await response.json();
            if (!data.features || !data.features[0]) {
                throw new Error('Invalid response format from API');
            }

            return {
                route: data.features[0].geometry,
                distance: data.features[0].properties.summary.distance
            };
        } catch (error) {
            console.error('Route calculation failed:', error);
            this.showError('Unable to calculate route. Please try different locations.');
            throw error;
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

    updateMarkerAndRoute() {
        const pickupLat = parseFloat(document.getElementById('pickup_lat').value);
        const pickupLng = parseFloat(document.getElementById('pickup_lng').value);
        const dropoffLat = parseFloat(document.getElementById('dropoff_lat').value);
        const dropoffLng = parseFloat(document.getElementById('dropoff_lng').value);

        if (pickupLat && pickupLng && dropoffLat && dropoffLng) {
            this.clearMarkers();
            
            // Add markers
            this.addMarker(pickupLat, pickupLng, 'Pickup');
            this.addMarker(dropoffLat, dropoffLng, 'Drop-off');

            // Calculate and display route
            this.calculateRoute(
                [pickupLng, pickupLat],
                [dropoffLng, dropoffLat]
            )
            .then(routeData => {
                this.displayRoute(routeData.route);
                this.updateDistanceAndFare(routeData.distance);
                document.getElementById('route_data').value = JSON.stringify(routeData.route);
                document.getElementById('bookButton').disabled = false;
            })
            .catch(error => {
                console.error('Error updating route:', error);
                document.getElementById('bookButton').disabled = true;
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
        document.getElementById('distance_value').value = distanceKm.toFixed(2);
        
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
