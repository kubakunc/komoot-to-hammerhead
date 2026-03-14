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

function formatDuration(seconds) {
    if (!seconds) return '0:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hrs}:${mins.toString().padStart(2, '0')}`;
}

function getDifficultyColor(diff) {
    const colors = {
        easy: '#34d399',
        moderate: '#fbbf24',
        hard: '#f87171',
    };
    return colors[diff] || 'var(--text-muted)';
}

import { useState, useEffect } from 'react';
import { fetchTourData } from '../api';

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
    const [expanded, setExpanded] = useState(false);
    const [vizData, setVizData] = useState(null);
    const [loadingViz, setLoadingViz] = useState(false);

    const isSynced = tour.synced;
    const canSelect = !syncing;

    useEffect(() => {
        if (expanded && !vizData && !loadingViz) {
            setLoadingViz(true);
            fetchTourData(tour.id)
                .then(data => {
                    setVizData(data);
                    setLoadingViz(false);
                })
                .catch(err => {
                    console.error('Failed to fetch viz data:', err);
                    setLoadingViz(false);
                });
        }
    }, [expanded, tour.id, vizData, loadingViz]);

    const handleCardClick = (e) => {
        // If clicking checkbox area or badge, select. Otherwise expand.
        const isActionable = e.target.closest('.route-checkbox') || e.target.closest('.status-badge');
        if (isActionable) {
            if (canSelect) onToggle(tour.id);
        } else {
            setExpanded(!expanded);
        }
    };

    const classes = [
        'route-card',
        selected && 'selected',
        isSynced && 'synced',
        expanded && 'expanded',
    ]
        .filter(Boolean)
        .join(' ');

    const calculateScale = (minLat, maxLat, minLng, maxLng, width) => {
        // Haversine-ish distance for the width of the bounding box at the center latitude
        const centerLat = (minLat + maxLat) / 2;
        const radLat = (centerLat * Math.PI) / 180;
        const degToRad = Math.PI / 180;

        // Earth radius in km
        const R = 6371;
        const dLng = (maxLng - minLng) * degToRad;

        // Horizontal distance in km across the center of the bounding box
        const distKm = R * dLng * Math.cos(radLat);

        // We want a nice round number for the scale bar (1km, 2km, 5km, 10km, etc)
        const targetWidthPx = 60; // Approximate width we want for the scale bar
        const kmPerPx = distKm / width;
        const targetKm = targetWidthPx * kmPerPx;

        // Round to nearest "nice" number
        const niceNumbers = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100];
        const scaleKm = niceNumbers.reduce((prev, curr) =>
            Math.abs(curr - targetKm) < Math.abs(prev - targetKm) ? curr : prev
        );

        const scaleWidthPx = scaleKm / kmPerPx;
        return { label: scaleKm < 1 ? `${scaleKm * 1000}m` : `${scaleKm}km`, width: scaleWidthPx };
    };

    const renderPath = () => {
        if (!vizData?.coordinates?.length) return null;
        const coords = vizData.coordinates;
        const lats = coords.map(c => c.lat);
        const lngs = coords.map(c => c.lng);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        const minLng = Math.min(...lngs);
        const maxLng = Math.max(...lngs);

        const width = 200;
        const height = 120;
        const padding = 15; // More padding for map visibility

        const scaleX = (val) => padding + ((val - minLng) / (maxLng - minLng)) * (width - 2 * padding);
        const scaleY = (val) => height - padding - ((val - minLat) / (maxLat - minLat)) * (height - 2 * padding);

        const points = coords.map(c => `${scaleX(c.lng)},${scaleY(c.lat)}`).join(' ');
        const scale = calculateScale(minLat, maxLat, minLng, maxLng, width - 2 * padding);

        return (
            <div className="viz-map-container" style={{ backgroundImage: vizData.map_url ? `url(${vizData.map_url})` : 'none' }}>
                <div className="map-overlay" />
                <svg viewBox={`0 0 ${width} ${height}`} className="viz-svg">
                    {/* Scale Indicator */}
                    <g transform={`translate(${width - scale.width - 10}, ${height - 15})`}>
                        <line x1="0" y1="0" x2={scale.width} y2="0" stroke="white" strokeWidth="1.5" />
                        <line x1="0" y1="-3" x2="0" y2="3" stroke="white" strokeWidth="1.5" />
                        <line x1={scale.width} y1="-3" x2={scale.width} y2="3" stroke="white" strokeWidth="1.5" />
                        <text x={scale.width / 2} y="-6" fill="white" fontSize="8" textAnchor="middle" fontWeight="600" style={{ textShadow: '0 1px 2px rgba(0,0,0,0.8)' }}>
                            {scale.label}
                        </text>
                    </g>
                </svg>
            </div>
        );
    };

    const renderElevation = () => {
        if (!vizData?.elevation?.length) return null;
        const el = vizData.elevation;
        const distKm = tour.distance_km;
        const minEl = Math.min(...el);
        const maxEl = Math.max(...el);
        const width = 300;
        const height = 150;
        const paddingLeft = 35;
        const paddingBottom = 20;
        const paddingTop = 20;
        const paddingRight = 10;

        const chartWidth = width - paddingLeft - paddingRight;
        const chartHeight = height - paddingTop - paddingBottom;

        const scaleX = (i) => paddingLeft + (i / (el.length - 1)) * chartWidth;
        const scaleY = (val) => paddingTop + chartHeight - ((val - minEl) / (Math.max(1, maxEl - minEl))) * chartHeight;

        const points = el.map((v, i) => `${scaleX(i)},${scaleY(v)}`);
        const pathData = `M ${paddingLeft},${paddingTop + chartHeight} ` + points.map(p => `L ${p}`).join(' ') + ` L ${paddingLeft + chartWidth},${paddingTop + chartHeight} Z`;

        const yLabels = [];
        const yStep = Math.max(25, Math.ceil((maxEl - minEl) / 3 / 25) * 25);
        for (let v = Math.floor(minEl / yStep) * yStep; v <= maxEl + 10; v += yStep) {
            yLabels.push(v);
        }

        const xLabels = [];
        const xStep = distKm > 100 ? 50 : distKm > 40 ? 20 : distKm > 15 ? 10 : 5;
        for (let d = 0; d <= distKm; d += xStep) {
            xLabels.push(d);
        }

        return (
            <div className="viz-elevation-container detail-view">
                <div className="viz-stats-overlay">
                    <div className="viz-gain-badge">+{Math.round(vizData.elevation_up)}m</div>
                    <div className="viz-loss-badge">-{Math.round(vizData.elevation_down)}m</div>
                </div>
                <svg viewBox={`0 0 ${width} ${height}`} className="viz-svg elevation-chart" preserveAspectRatio="xMidYMid meet">
                    <defs>
                        <linearGradient id="elevationGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--success)" stopOpacity="0.3" />
                            <stop offset="100%" stopColor="var(--success)" stopOpacity="0.05" />
                        </linearGradient>
                    </defs>

                    {yLabels.map(v => (
                        <g key={`y-${v}`}>
                            <line x1={paddingLeft} y1={scaleY(v)} x2={width - paddingRight} y2={scaleY(v)} stroke="rgba(255,255,255,0.05)" strokeDasharray="2,2" />
                            <text x={paddingLeft - 5} y={scaleY(v) + 3} fill="var(--text-muted)" fontSize="8" textAnchor="end">{v}m</text>
                        </g>
                    ))}

                    {xLabels.map(d => {
                        const i = Math.round((d / distKm) * (el.length - 1));
                        if (i < 0 || i >= el.length) return null;
                        return (
                            <g key={`x-${d}`}>
                                <line x1={scaleX(i)} y1={paddingTop} x2={scaleX(i)} y2={paddingTop + chartHeight} stroke="rgba(255,255,255,0.05)" strokeDasharray="2,2" />
                                <text x={scaleX(i)} y={height - 5} fill="var(--text-muted)" fontSize="8" textAnchor="middle">{d}km</text>
                            </g>
                        );
                    })}

                    <path d={pathData} className="elevation-area" fill="url(#elevationGradient)" />
                    <polyline points={points.join(' ')} fill="none" stroke="var(--success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />

                    <circle cx={scaleX(0)} cy={scaleY(el[0])} r="3" fill="#34d399" stroke="white" strokeWidth="1" />
                    <text x={scaleX(0)} y={scaleY(el[0]) - 8} fill="white" fontSize="9" fontWeight="800" textAnchor="middle">A</text>

                    <circle cx={scaleX(el.length - 1)} cy={scaleY(el[el.length - 1])} r="3" fill="#f87171" stroke="white" strokeWidth="1" />
                    <text x={scaleX(el.length - 1)} y={scaleY(el[el.length - 1]) - 8} fill="white" fontSize="9" fontWeight="800" textAnchor="middle">B</text>
                </svg>
            </div>
        );
    };

    return (
        <div
            className={classes}
            onClick={handleCardClick}
            style={{ animationDelay: `${tour._index * 40}ms` }}
        >
            <div className="expanded-header">
                <div className="route-checkbox" />
                <div className="sport-icon">{getSportIcon(tour.sport)}</div>
                <div className="route-info">
                    <div className="route-name" title={tour.name}>
                        {tour.name}
                    </div>
                    <div className="route-meta">
                        <span>{getSportLabel(tour.sport)}</span>
                        <span>📏 {tour.distance_km.toFixed(1)} km</span>
                    </div>
                </div>
                {syncing ? (
                    <span className="status-badge syncing">Syncing…</span>
                ) : isSynced ? (
                    <span className="status-badge synced">Synced</span>
                ) : (
                    <span className="status-badge unsynced">Not synced</span>
                )}
            </div>

            {expanded && (
                <>
                    <div className="expanded-content">
                        <div className="viz-box">
                            <div className="viz-label">Map View</div>
                            {loadingViz ? <div className="loading-dots">...</div> : renderPath()}
                        </div>
                        <div className="viz-box">
                            <div className="viz-label">Elevation Profile</div>
                            {loadingViz ? <div className="loading-dots">...</div> : renderElevation()}
                        </div>
                    </div>

                    {!loadingViz && vizData && (
                        <div className="route-details-grid">
                            <div className="detail-item">
                                <span className="detail-label">Duration</span>
                                <span className="detail-value">{formatDuration(vizData.duration_s)}h</span>
                            </div>
                            <div className="detail-item">
                                <span className="detail-label">Difficulty</span>
                                <span className={`detail-value difficulty-${vizData.difficulty}`} style={{ color: getDifficultyColor(vizData.difficulty) }}>
                                    {vizData.difficulty}
                                </span>
                            </div>
                            <div className="detail-item">
                                <span className="detail-label">Climb / Descent</span>
                                <span className="detail-value">+{Math.round(vizData.elevation_up)}m / -{Math.round(vizData.elevation_down)}m</span>
                            </div>
                            <div className="detail-item surfaces">
                                <span className="detail-label">Surfaces</span>
                                <div className="surface-bar">
                                    {(vizData.surfaces || []).map((s, i) => (
                                        <div
                                            key={i}
                                            className="surface-segment"
                                            style={{ width: `${s.amount * 100}%` }}
                                            title={`${s.type.replace('sb#', '')}: ${Math.round(s.amount * 100)}%`}
                                        />
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="komoot-link-container">
                        <a
                            href={`https://www.komoot.com/tour/${tour.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="komoot-link"
                            onClick={(e) => e.stopPropagation()}
                        >
                            View on Komoot ↗
                        </a>
                    </div>
                </>
            )}
        </div>
    );
}
