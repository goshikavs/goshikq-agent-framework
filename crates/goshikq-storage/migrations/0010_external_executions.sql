-- v1.1.0-dev external framework executions. Additive. Project-scoped like other run data.
-- A row's lifecycle is not a business-outcome verification.

CREATE TABLE IF NOT EXISTS external_executions (
    id                   UUID PRIMARY KEY,
    project_id           UUID NOT NULL REFERENCES projects(id),
    run_id               UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    parent_run_id        UUID REFERENCES runs(id) ON DELETE SET NULL,
    task_id              UUID,
    tenant_id            UUID,
    framework            TEXT NOT NULL,
    adapter_version      TEXT NOT NULL,
    framework_version    TEXT NOT NULL DEFAULT 'unknown',
    external_run_id      TEXT,
    external_thread_id   TEXT,
    correlation_id       TEXT NOT NULL,
    trace_id             TEXT,
    idempotency_key      TEXT NOT NULL,
    dispatch_id          TEXT NOT NULL,
    lifecycle            TEXT NOT NULL,
    capabilities         JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence             JSONB NOT NULL DEFAULT '{}'::jsonb,
    result               JSONB,
    error                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS external_executions_run_idx
    ON external_executions(project_id, run_id);
CREATE INDEX IF NOT EXISTS external_executions_thread_idx
    ON external_executions(project_id, framework, external_thread_id);
