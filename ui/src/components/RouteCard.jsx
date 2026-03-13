const SPORT_ICONS = {
    racebike: '🚴',
    touringbicycle: '🚲',
    mountainbike: '🚵',
    mtb_easy: '🚵',
    mtb_advanced: '🚵',
    e_touringbicycle: '⚡',
    e_mountainbike: '⚡',
    jogging: '🏃',
    running: '🏃',
    hiking: '🥾',
    mountaineering: '⛰️',
    nordic_walking: '🚶',
    other: '📍',
};

function getSportIcon(sport) {
    return SPORT_ICONS[sport] || '📍';
}

function getSportLabel(sport) {
    const labels = {
        racebike: 'Road',
        touringbicycle: 'Touring',
        mountainbike: 'MTB',
        mtb_easy: 'MTB Easy',
        mtb_advanced: 'MTB Advanced',
        e_touringbicycle: 'E-Touring',
        e_mountainbike: 'E-MTB',
        jogging: 'Running',
        running: 'Running',
        hiking: 'Hiking',
        mountaineering: 'Mountaineering',
        nordic_walking: 'Nordic Walk',
    };
    return labels[sport] || sport || 'Route';
}

export default function RouteCard({ tour, selected, syncing, onToggle }) {
    const isSynced = tour.synced;
    const canSelect = !isSynced && !syncing;

    const classes = [
        'route-card',
        selected && 'selected',
        isSynced && 'synced',
    ]
        .filter(Boolean)
        .join(' ');

    return (
        <div
            className={classes}
            onClick={() => canSelect && onToggle(tour.id)}
            style={{ animationDelay: `${tour._index * 40}ms` }}
        >
            {/* Checkbox */}
            <div className="route-checkbox" />

            {/* Sport icon */}
            <div className="sport-icon">{getSportIcon(tour.sport)}</div>

            {/* Info */}
            <div className="route-info">
                <div className="route-name" title={tour.name}>
                    {tour.name}
                </div>
                <div className="route-meta">
                    <span>{getSportLabel(tour.sport)}</span>
                    <span>📏 {tour.distance_km.toFixed(1)} km</span>
                </div>
            </div>

            {/* Status badge */}
            {syncing ? (
                <span className="status-badge syncing">Syncing…</span>
            ) : isSynced ? (
                <span className="status-badge synced">Synced</span>
            ) : (
                <span className="status-badge unsynced">Not synced</span>
            )}
        </div>
    );
}
