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
            if (data.features && data.features.length > 0) {
                this.showAutocompleteResults(data.features, inputElement);
                return data.features;
            }
            return [];
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
        }
        
        dropdown.innerHTML = '';
        features.forEach(feature => {
            const li = document.createElement('li');
            li.textContent = feature.properties.label;
            li.addEventListener('click', () => {
                inputElement.value = feature.properties.label;
                const [lng, lat] = feature.geometry.coordinates;
                this.updateLocationFields(inputElement.id, lat, lng);
                dropdown.style.display = 'none';
            });
            dropdown.appendChild(li);
        });
        
        dropdown.style.display = features.length > 0 ? 'block' : 'none';
    }

    async calculateRoute(points) {
        try {
            const payload = {
                coordinates: points.map(point => [point[1], point[0]]) // Convert [lat,lng] to [lng,lat]
            };
            
            console.log('Request payload:', payload);
            
            const response = await fetch('https://api.openrouteservice.org/v2/directions/driving-car/geojson', {
                method: 'POST',
                headers: {
                    'Authorization': this.apiKey,
                    'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
                    'Content-Type': 'application/json; charset=utf-8'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            console.log('API Response:', data);

            if (!response.ok) {
                // Check for specific error codes
                if (data.error?.code === 2010) {
                    throw new Error('One or more locations are not accessible by car. Please choose locations closer to roads.');
                }
                throw new Error(data.error?.message || 'Route calculation failed');
            }

            if (!data.features || !data.features[0]) {
                throw new Error('Invalid response format from API');
            }

            // Extract total distance and duration from properties
            const properties = data.features[0].properties;
            const segments = properties.segments[0];
            const distanceInKm = segments.distance / 1000;
            const durationInMin = segments.duration / 60;

            return {
                route: data.features[0].geometry,
                distance: distanceInKm,
                duration: durationInMin
            };
        } catch (error) {
            console.error('Route calculation failed:', error);
            this.showError(error.message || 'Unable to calculate route. Please try different locations.');
            throw error;
        }
    }

    async updateRoute() {
        try {
            // Collect all points in order: pickup -> stops -> dropoff
            const points = [];
            
            // Add pickup point
            const pickupLat = parseFloat(document.getElementById('pickup_lat').value);
            const pickupLng = parseFloat(document.getElementById('pickup_lng').value);
            if (pickupLat && pickupLng) {
                points.push([pickupLat, pickupLng]);
            }
            
            // Add intermediate stops
            const stopEntries = document.querySelectorAll('.stop-entry');
            for (let entry of stopEntries) {
                const lat = parseFloat(entry.querySelector('.stop-lat').value);
                const lng = parseFloat(entry.querySelector('.stop-lng').value);
                if (!isNaN(lat) && !isNaN(lng)) {
                    points.push([lat, lng]);
                }
            }
            
            // Add dropoff point
            const dropoffLat = parseFloat(document.getElementById('dropoff_lat').value);
            const dropoffLng = parseFloat(document.getElementById('dropoff_lng').value);
            if (dropoffLat && dropoffLng) {
                points.push([dropoffLat, dropoffLng]);
            }

            if (points.length >= 2) { // Need at least pickup and dropoff
                this.clearMarkers();
                
                // Add markers for all points
                points.forEach((point, index) => {
                    const label = index === 0 ? 'Pickup' : 
                                index === points.length - 1 ? 'Drop-off' : 
                                `Stop ${index}`;
                    this.addMarker(point[0], point[1], label);
                });

                // Calculate and display route
                const routeData = await this.calculateRoute(points);
                this.displayRoute(routeData.route);
                this.updateDistanceAndFare(routeData.distance);
                
                // Store route data for form submission
                document.getElementById('route_data').value = JSON.stringify(routeData.route);
                document.getElementById('bookButton').disabled = false;
            }
        } catch (error) {
            console.error('Error updating route:', error);
            this.showError(error.message || 'Unable to calculate route. Please try different locations.');
            document.getElementById('bookButton').disabled = true;
        }
    }

    updateLocationFields(inputId, lat, lng) {
        const type = inputId.includes('pickup') ? 'pickup' : 'dropoff';
        document.getElementById(`${type}_lat`).value = lat;
        document.getElementById(`${type}_lng`).value = lng;
        this.updateRoute();
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
        
        const fare = (distance * 2) + 5;  // $2 per km + $5 base fare
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
            errorDiv.scrollIntoView({ behavior: 'smooth' });
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 10000); // Show error for 10 seconds
        }
    }
}
