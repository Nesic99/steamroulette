CREATE TABLE IF NOT EXISTS spins (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    steam_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    player_avatar TEXT NOT NULL DEFAULT '',
    appid BIGINT NOT NULL,
    game_name TEXT NOT NULL,
    genres TEXT[] NOT NULL DEFAULT '{}',
    total_games INTEGER NOT NULL,
    filtered_pool INTEGER NOT NULL,
    playtime_min INTEGER NOT NULL DEFAULT 0,
    playtime_max INTEGER NOT NULL DEFAULT -1,
    modes TEXT[] NOT NULL DEFAULT '{}',
    genre_filters TEXT[] NOT NULL DEFAULT '{}',
    unplayed_only BOOLEAN NOT NULL DEFAULT FALSE,
    duration_ms INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS filter_failures (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    steam_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spins_created_at ON spins (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_spins_steam_id ON spins (steam_id);
CREATE INDEX IF NOT EXISTS idx_filter_failures_created_at ON filter_failures (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_filter_failures_reason ON filter_failures (reason);

CREATE OR REPLACE FUNCTION export_prometheus_metrics()
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    output TEXT := '';
    total_spins BIGINT := 0;
    spins_last_1h BIGINT := 0;
    avg_duration_ms NUMERIC := 0;
    filter_failures_total BIGINT := 0;
    playtime_failures BIGINT := 0;
    content_failures BIGINT := 0;
BEGIN
    SELECT COUNT(*) INTO total_spins FROM spins;
    SELECT COUNT(*) INTO spins_last_1h FROM spins WHERE created_at >= NOW() - INTERVAL '1 hour';
    SELECT COALESCE(AVG(duration_ms), 0) INTO avg_duration_ms FROM spins;

    SELECT COUNT(*) INTO filter_failures_total FROM filter_failures;
    SELECT COUNT(*) INTO playtime_failures FROM filter_failures WHERE reason = 'playtime';
    SELECT COUNT(*) INTO content_failures FROM filter_failures WHERE reason = 'content';

    output := output || '# HELP steamroulette_spins_total Total successful spins recorded' || E'\n';
    output := output || '# TYPE steamroulette_spins_total counter' || E'\n';
    output := output || 'steamroulette_spins_total ' || total_spins || E'\n';

    output := output || '# HELP steamroulette_spins_last_hour Spins completed in the last hour' || E'\n';
    output := output || '# TYPE steamroulette_spins_last_hour gauge' || E'\n';
    output := output || 'steamroulette_spins_last_hour ' || spins_last_1h || E'\n';

    output := output || '# HELP steamroulette_spin_duration_ms_avg Average spin request duration in milliseconds' || E'\n';
    output := output || '# TYPE steamroulette_spin_duration_ms_avg gauge' || E'\n';
    output := output || 'steamroulette_spin_duration_ms_avg ' || ROUND(avg_duration_ms, 2) || E'\n';

    output := output || '# HELP steamroulette_filter_failures_total Total filter failures' || E'\n';
    output := output || '# TYPE steamroulette_filter_failures_total counter' || E'\n';
    output := output || 'steamroulette_filter_failures_total ' || filter_failures_total || E'\n';

    output := output || '# HELP steamroulette_filter_failures_by_reason_total Filter failures by reason' || E'\n';
    output := output || '# TYPE steamroulette_filter_failures_by_reason_total counter' || E'\n';
    output := output || 'steamroulette_filter_failures_by_reason_total{reason="playtime"} ' || playtime_failures || E'\n';
    output := output || 'steamroulette_filter_failures_by_reason_total{reason="content"} ' || content_failures || E'\n';

    RETURN output;
END;
$$;
