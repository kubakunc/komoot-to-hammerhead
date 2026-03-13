export default function StatusBar({ stats, loading }) {
    if (loading) {
        return (
            <div className="stats-bar">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="stat-card">
                        <div className="stat-value" style={{ opacity: 0.3 }}>—</div>
                        <div className="stat-label">Loading</div>
                    </div>
                ))}
            </div>
        );
    }

    return (
        <div className="stats-bar fade-in">
            <div className="stat-card">
                <div className="stat-value accent">{stats.total ?? 0}</div>
                <div className="stat-label">Total Synced</div>
            </div>
            <div className="stat-card">
                <div className="stat-value success">{stats.success ?? 0}</div>
                <div className="stat-label">Successful</div>
            </div>
            <div className="stat-card">
                <div className="stat-value error">{stats.failed ?? 0}</div>
                <div className="stat-label">Failed</div>
            </div>
        </div>
    );
}
