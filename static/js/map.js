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
            const response = await fetch(`https://api.openrouteservice.org/geocode/search?text=${encodeURIComponent(query)}&size=5`, {
                method: 'GET',
                headers: {
                    'Authorization': this.apiKey,
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

    async calculateRouteWithStops(points) {
        try {
            const payload = {
                coordinates: points  // points are already in [longitude,latitude] format
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
                throw new Error(`Route calculation failed: ${errorData.error || response.statusText}`);
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
            this.showError('Unable to calculate route. Please try different locations.');
            throw error;
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

    initStops() {
        const addStopBtn = document.getElementById('addStop');
        const stopsContainer = document.getElementById('stops-list');
        const template = document.getElementById('stop-template');

        addStopBtn.addEventListener('click', () => {
            const stopEntry = template.content.cloneNode(true);
            stopsContainer.appendChild(stopEntry);
            
            const input = stopsContainer.lastElementChild.querySelector('.stop-input');
            this.setupAddressInput(input);
            
            const removeBtn = stopsContainer.lastElementChild.querySelector('.remove-stop');
            removeBtn.addEventListener('click', (e) => {
                e.target.closest('.stop-entry').remove();
                this.updateRoute();
            });
        });
    }

    setupAddressInput(input) {
        input.addEventListener('input', () => {
            clearTimeout(this.debounceTimeout);
            this.debounceTimeout = setTimeout(() => {
                const query = input.value.trim();
                if (query.length >= 3) {
                    this.searchAddress(query, input);
                }
            }, 300);
        });
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
                if (inputElement.classList.contains('stop-input')) {
                    const stopEntry = inputElement.closest('.stop-entry');
                    stopEntry.querySelector('.stop-lat').value = coords[1];
                    stopEntry.querySelector('.stop-lng').value = coords[0];
                    stopEntry.querySelector('.stop-address').value = feature.properties.label;
                } else {
                    this.updateLocationFields(inputElement.id, coords[1], coords[0]);
                }
                dropdown.style.display = 'none';
                this.updateRoute();
            });
            dropdown.appendChild(li);
        });
        
        dropdown.style.display = features.length ? 'block' : 'none';
    }

    updateLocationFields(inputId, lat, lng) {
        const type = inputId.includes('pickup') ? 'pickup' : 'dropoff';
        document.getElementById(`${type}_lat`).value = lat;
        document.getElementById(`${type}_lng`).value = lng;
        this.updateRoute();
    }

    async updateRoute() {
        const pickupLat = parseFloat(document.getElementById('pickup_lat').value);
        const pickupLng = parseFloat(document.getElementById('pickup_lng').value);
        const dropoffLat = parseFloat(document.getElementById('dropoff_lat').value);
        const dropoffLng = parseFloat(document.getElementById('dropoff_lng').value);

        if (pickupLat && pickupLng && dropoffLat && dropoffLng) {
            this.clearMarkers();
            
            // Collect all stops
            const stops = Array.from(document.querySelectorAll('.stop-entry')).map(entry => {
                const lat = parseFloat(entry.querySelector('.stop-lat').value);
                const lng = parseFloat(entry.querySelector('.stop-lng').value);
                return [lng, lat];  // ORS expects [longitude, latitude]
            }).filter(coords => !isNaN(coords[0]) && !isNaN(coords[1]));

            // Prepare all points in order
            const points = [[pickupLng, pickupLat], ...stops, [dropoffLng, dropoffLat]];
            
            try {
                const routeData = await this.calculateRouteWithStops(points);
                this.displayRoute(routeData.route);
                this.updateDistanceAndFare(routeData.distance);
                document.getElementById('route_data').value = JSON.stringify(routeData.route);
                document.getElementById('bookButton').disabled = false;

                // Add markers for all points
                this.addMarker(pickupLat, pickupLng, 'Pickup');
                stops.forEach((stop, index) => {
                    this.addMarker(stop[1], stop[0], `Stop ${index + 1}`);
                });
                this.addMarker(dropoffLat, dropoffLng, 'Drop-off');
            } catch (error) {
                console.error('Error updating route:', error);
                this.showError('Unable to calculate route. Please try different locations.');
                document.getElementById('bookButton').disabled = true;
            }
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
        document.getElementById('distance').textContent = `${distance.toFixed(2)} km`;
        document.getElementById('distance_value').value = distance.toFixed(2);
        
        // Calculate fare ($2 per km + $5 base fare)
        const fare = (distance * 2) + 5;
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
