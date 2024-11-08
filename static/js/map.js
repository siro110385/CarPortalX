class MapManager {
    constructor(mapId, isEditMode = false) {
        this.map = L.map(mapId).setView([37.7749, -122.4194], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(this.map);
        this.routeLayer = null;
        this.markers = [];
        this.autocompleteDropdowns = {};
        this.currentLocationMarker = null;
        this.apiKey = document.querySelector('meta[name="ors-api-key"]').content;
        this.isEditMode = isEditMode;
    }

    async searchAddress(query, inputElement) {
        try {
            if (!query || query.length < 3) return;

            const response = await fetch(
                `https://graphhopper.com/api/1/geocode?q=${encodeURIComponent(query)}&limit=5&key=${this.apiKey}`
            );

            if (!response.ok) {
                throw new Error(`Geocoding failed: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Geocoding response:', data);

            if (data.hits && data.hits.length > 0) {
                this.showAutocompleteResults(data.hits, inputElement);
            } else {
                console.log('No results found for query:', query);
            }
        } catch (error) {
            console.error('Address search failed:', error);
            this.showError('Address search failed. Please try again.');
        }
    }

    showAutocompleteResults(hits, inputElement) {
        const dropdownId = `${inputElement.id || 'stop'}-dropdown`;
        let dropdown = document.getElementById(dropdownId);
        
        if (!dropdown) {
            dropdown = document.createElement('ul');
            dropdown.id = dropdownId;
            dropdown.className = 'address-dropdown';
            inputElement.parentNode.appendChild(dropdown);
        }
        
        dropdown.innerHTML = '';
        hits.forEach(hit => {
            const li = document.createElement('li');
            const address = [
                hit.name,
                hit.street,
                hit.city,
                hit.state,
                hit.country
            ].filter(Boolean).join(', ');
            
            li.textContent = address;
            li.addEventListener('click', () => {
                inputElement.value = address;
                
                // Handle both main inputs and stop inputs
                if (inputElement.classList.contains('stop-input')) {
                    const stopEntry = inputElement.closest('.stop-entry');
                    stopEntry.querySelector('.stop-lat').value = hit.point.lat;
                    stopEntry.querySelector('.stop-lng').value = hit.point.lng;
                } else {
                    document.getElementById(`${inputElement.id}_lat`).value = hit.point.lat;
                    document.getElementById(`${inputElement.id}_lng`).value = hit.point.lng;
                }
                
                // Add marker to map
                this.addMarker(hit.point.lat, hit.point.lng, address);
                
                dropdown.style.display = 'none';
                this.updateRoute();
            });
            dropdown.appendChild(li);
        });
        
        dropdown.style.display = 'block';
    }

    setupAddressInput(input) {
        let debounceTimeout;
        input.addEventListener('input', () => {
            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(() => {
                const query = input.value.trim();
                if (query.length >= 3) {
                    this.searchAddress(query, input);
                }
            }, 300);
        });
    }

    async calculateRoute(points) {
        try {
            const pointsParam = points.map(point => `point=${point[0]},${point[1]}`).join('&');
            const response = await fetch(`https://graphhopper.com/api/1/route?${pointsParam}&vehicle=car&key=${this.apiKey}&type=json&points_encoded=false`);

            if (!response.ok) {
                throw new Error(`Route calculation failed: ${response.statusText}`);
            }

            const data = await response.json();
            if (!data.paths || !data.paths[0]) {
                throw new Error('No route found');
            }

            const path = data.paths[0];
            const distanceInKm = path.distance / 1000;
            const durationInMin = path.time / 60000;

            return {
                route: {
                    type: 'Feature',
                    geometry: {
                        type: 'LineString',
                        coordinates: path.points.coordinates
                    },
                    properties: {}
                },
                distance: distanceInKm,
                duration: durationInMin
            };
        } catch (error) {
            console.error('Route calculation failed:', error);
            throw error;
        }
    }

    async updateRoute() {
        try {
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

            if (points.length >= 2) {
                this.clearMarkers();
                
                // Add markers for all points
                points.forEach((point, index) => {
                    const label = index === 0 ? 'Pickup' : 
                                index === points.length - 1 ? 'Drop-off' : 
                                `Stop ${index}`;
                    this.addMarker(point[0], point[1], label);
                });

                const routeData = await this.calculateRoute(points);
                this.displayRoute(routeData.route);
                this.updateDistanceAndFare(routeData.distance);
                
                // Update car availability in edit mode
                if (this.isEditMode) {
                    const contractId = document.querySelector('input[name="contract_id"]:checked')?.value;
                    if (contractId) {
                        const pickupDatetime = document.getElementById('pickup_datetime').value;
                        const params = new URLSearchParams({
                            pickup_datetime: pickupDatetime,
                            contract_id: contractId
                        });
                        
                        const response = await fetch('/book-ride?' + params);
                        if (!response.ok) throw new Error('Failed to check availability');
                        
                        const html = await response.text();
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        
                        const availableCarsSection = this.findAvailableCarsSection(doc);
                        if (availableCarsSection) {
                            const currentSection = this.findAvailableCarsSection(document);
                            if (currentSection) {
                                currentSection.innerHTML = availableCarsSection.innerHTML;
                                
                                // Re-select the previously selected contract
                                const contractInput = document.querySelector(`input[name="contract_id"][value="${contractId}"]`);
                                if (contractInput) {
                                    contractInput.checked = true;
                                }
                            }
                        }
                    }
                }
                
                document.getElementById('route_data').value = JSON.stringify(routeData.route);
                document.getElementById('bookButton').disabled = false;
            }
        } catch (error) {
            console.error('Error updating route:', error);
            this.showError(error.message || 'Unable to calculate route. Please try different locations.');
            document.getElementById('bookButton').disabled = true;
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
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }

    async reverseGeocode(lat, lng, inputId) {
        try {
            const response = await fetch(
                `https://graphhopper.com/api/1/geocode?point=${lat},${lng}&reverse=true&key=${this.apiKey}`
            );
            
            if (!response.ok) {
                throw new Error('Reverse geocoding failed');
            }
            
            const data = await response.json();
            if (data.hits && data.hits.length > 0) {
                const address = [
                    data.hits[0].name,
                    data.hits[0].street,
                    data.hits[0].city,
                    data.hits[0].state,
                    data.hits[0].country
                ].filter(Boolean).join(', ');
                
                document.getElementById(inputId).value = address;
            }
        } catch (error) {
            console.error('Reverse geocoding failed:', error);
        }
    }

    findAvailableCarsSection(element) {
        const sections = element.querySelectorAll('.mb-3');
        for (const section of sections) {
            const label = section.querySelector('label');
            if (label && label.textContent.trim() === 'Available Cars') {
                return section;
            }
        }
        return null;
    }
}
