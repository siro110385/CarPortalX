// Update the updateRoute method in the existing MapManager class
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
            
            // Set estimated duration in hours
            document.getElementById('estimated_duration').value = routeData.duration / 60;
            
            document.getElementById('route_data').value = JSON.stringify(routeData.route);
            document.getElementById('bookButton').disabled = false;
        }
    } catch (error) {
        console.error('Error updating route:', error);
        this.showError(error.message || 'Unable to calculate route. Please try different locations.');
        document.getElementById('bookButton').disabled = true;
    }
}
