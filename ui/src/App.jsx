import { useState, useEffect, useCallback } from 'react';
import './App.css';
import { fetchTours, fetchStatus, syncTour } from './api';
import StatusBar from './components/StatusBar';
import RouteCard from './components/RouteCard';

const FILTERS = ['all', 'unsynced', 'synced'];

export default function App() {
  const [tours, setTours] = useState([]);
  const [stats, setStats] = useState({});
  const [selected, setSelected] = useState(new Set());
  const [syncing, setSyncing] = useState(new Set());
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toasts, setToasts] = useState([]);

  // ── Data fetching ──────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [toursData, statsData] = await Promise.all([
        fetchTours(),
        fetchStatus(),
      ]);
      setTours(toursData);
      setStats(statsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Toasts ─────────────────────────────────────────────

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  // ── Selection ──────────────────────────────────────────

  const unsyncedTours = tours.filter((t) => !t.synced);

  const toggleSelect = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (selected.size === unsyncedTours.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(unsyncedTours.map((t) => t.id)));
    }
  }, [selected.size, unsyncedTours]);

  // ── Sync ───────────────────────────────────────────────

  const handleSync = useCallback(async () => {
    const toSync = [...selected];
    if (toSync.length === 0) return;

    setSelected(new Set());
    let successCount = 0;
    let failCount = 0;

    for (const tourId of toSync) {
      setSyncing((prev) => new Set(prev).add(tourId));
      try {
        await syncTour(tourId);
        successCount++;
        // Immediately mark as synced in local state
        setTours((prev) =>
          prev.map((t) => (t.id === tourId ? { ...t, synced: true } : t))
        );
      } catch {
        failCount++;
      } finally {
        setSyncing((prev) => {
          const next = new Set(prev);
          next.delete(tourId);
          return next;
        });
      }
    }

    if (successCount > 0) {
      addToast(`✓ Synced ${successCount} route${successCount > 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      addToast(`✗ ${failCount} route${failCount > 1 ? 's' : ''} failed`, 'error');
    }

    // Refresh stats
    try {
      const statsData = await fetchStatus();
      setStats(statsData);
    } catch {
      // silent
    }
  }, [selected, addToast]);

  // ── Filtering ──────────────────────────────────────────

  const filteredTours = tours
    .filter((t) => {
      if (filter === 'synced') return t.synced;
      if (filter === 'unsynced') return !t.synced;
      return true;
    })
    .map((t, i) => ({ ...t, _index: i }));

  // ── Render ─────────────────────────────────────────────

  return (
    <>
      {/* Header */}
      <header className="app-header fade-in">
        <h1 className="app-title">Komoot → Hammerhead</h1>
        <p className="app-subtitle">Select routes to sync to your Karoo</p>
      </header>

      {/* Stats */}
      <StatusBar stats={stats} loading={loading} />

      {/* Error */}
      {error && (
        <div className="error-banner">
          <span>⚠</span> {error}
        </div>
      )}

      {/* Toolbar */}
      {!loading && tours.length > 0 && (
        <div className="toolbar fade-in">
          <div className="toolbar-left">
            <button className="select-all-btn" onClick={selectAll}>
              {selected.size === unsyncedTours.length && unsyncedTours.length > 0
                ? 'Deselect All'
                : 'Select All'}
            </button>
            {selected.size > 0 && (
              <span className="selected-count">
                {selected.size} selected
              </span>
            )}
          </div>
          <div className="toolbar-left">
            <button
              className="sync-btn"
              disabled={selected.size === 0 || syncing.size > 0}
              onClick={handleSync}
            >
              {syncing.size > 0 && <span className="spinner" />}
              {syncing.size > 0
                ? `Syncing (${syncing.size})…`
                : `Sync ${selected.size > 0 ? `(${selected.size})` : ''}`}
            </button>
            <button
              className={`refresh-btn${loading ? ' loading' : ''}`}
              onClick={loadData}
              title="Refresh"
            >
              ↻
            </button>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      {!loading && tours.length > 0 && (
        <div className="filter-tabs fade-in">
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`filter-tab${filter === f ? ' active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all'
                ? `All (${tours.length})`
                : f === 'unsynced'
                  ? `Unsynced (${unsyncedTours.length})`
                  : `Synced (${tours.length - unsyncedTours.length})`}
            </button>
          ))}
        </div>
      )}

      {/* Route list */}
      {loading ? (
        <div className="route-list">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton-card" style={{ animationDelay: `${i * 100}ms` }} />
          ))}
        </div>
      ) : filteredTours.length === 0 ? (
        <div className="empty-state fade-in">
          <div className="empty-state-icon">🗺️</div>
          <div className="empty-state-text">
            {tours.length === 0
              ? 'No planned routes found in the last few days'
              : 'No routes match this filter'}
          </div>
        </div>
      ) : (
        <div className="route-list">
          {filteredTours.map((tour) => (
            <RouteCard
              key={tour.id}
              tour={tour}
              selected={selected.has(tour.id)}
              syncing={syncing.has(tour.id)}
              onToggle={toggleSelect}
            />
          ))}
        </div>
      )}

      {/* Toasts */}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map((t) => (
            <div key={t.id} className={`toast ${t.type}`}>
              {t.message}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
