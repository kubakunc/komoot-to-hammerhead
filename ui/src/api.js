const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY || '';

const headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json',
};

export async function fetchTours() {
    const res = await fetch(`${API_URL}/tours`, { headers });
    if (!res.ok) throw new Error(`Failed to fetch tours: ${res.status}`);
    return res.json();
}

export async function syncTour(tourId, force = false) {
    const baseUrl = API_URL.startsWith('http') ? API_URL : window.location.origin;
    const path = API_URL.startsWith('http') ? `/sync/${tourId}` : `${API_URL}/sync/${tourId}`;
    const url = new URL(path, baseUrl);
    if (force) url.searchParams.append('force', 'true');

    const res = await fetch(url, {
        method: 'POST',
        headers,
    });
    if (!res.ok) throw new Error(`Failed to sync tour ${tourId}: ${res.status}`);
    return res.json();
}

export async function fetchStatus() {
    const res = await fetch(`${API_URL}/status`, { headers });
    if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`);
    return res.json();
}

export async function fetchRoutes(limit = 500) {
    const res = await fetch(`${API_URL}/routes?limit=${limit}`, { headers });
    if (!res.ok) throw new Error(`Failed to fetch routes: ${res.status}`);
    return res.json();
}

export async function fetchTourData(tourId) {
    const baseUrl = API_URL.startsWith('http') ? API_URL : window.location.origin;
    const path = API_URL.startsWith('http') ? `/tours/${tourId}/data` : `${API_URL}/tours/${tourId}/data`;
    const url = new URL(path, baseUrl);
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`Failed to fetch tour data: ${res.status}`);
    return res.json();
}
