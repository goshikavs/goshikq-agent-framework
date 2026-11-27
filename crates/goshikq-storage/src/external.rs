//! Project-scoped external framework execution records.
//!
//! Queries always filter on `project_id`. A missing row and a row owned by another
//! project are both `NotFound`.

use chrono::Utc;
use serde_json::Value;
use uuid::Uuid;

use crate::{Db, DbResult, ExternalExecutionRow, StorageError};

impl Db {
    pub async fn find_external_execution_by_idempotency(
        &self,
        project_id: Uuid,
        idempotency_key: &str,
    ) -> DbResult<Option<ExternalExecutionRow>> {
        Ok(sqlx::query_as::<_, ExternalExecutionRow>(
            r#"SELECT * FROM external_executions
                WHERE project_id = $1 AND idempotency_key = $2"#,
        )
        .bind(project_id)
        .bind(idempotency_key)
        .fetch_optional(&self.pool)
        .await?)
    }

    pub async fn insert_external_execution(
        &self,
        row: &ExternalExecutionRow,
    ) -> DbResult<ExternalExecutionRow> {
        Ok(sqlx::query_as::<_, ExternalExecutionRow>(
            r#"INSERT INTO external_executions
                 (id, project_id, run_id, parent_run_id, task_id, tenant_id, framework,
                  adapter_version, framework_version, external_run_id, external_thread_id,
                  correlation_id, trace_id, idempotency_key, dispatch_id, lifecycle,
                  capabilities, evidence, result, error, created_at, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
               RETURNING *"#,
        )
        .bind(row.id)
        .bind(row.project_id)
        .bind(row.run_id)
        .bind(row.parent_run_id)
        .bind(row.task_id)
        .bind(row.tenant_id)
        .bind(&row.framework)
        .bind(&row.adapter_version)
        .bind(&row.framework_version)
        .bind(&row.external_run_id)
        .bind(&row.external_thread_id)
        .bind(&row.correlation_id)
        .bind(&row.trace_id)
        .bind(&row.idempotency_key)
        .bind(&row.dispatch_id)
        .bind(&row.lifecycle)
        .bind(&row.capabilities)
        .bind(&row.evidence)
        .bind(&row.result)
        .bind(&row.error)
        .bind(row.created_at)
        .bind(row.updated_at)
        .fetch_one(&self.pool)
        .await?)
    }

    pub async fn get_external_execution(
        &self,
        project_id: Uuid,
        id: Uuid,
    ) -> DbResult<ExternalExecutionRow> {
        sqlx::query_as::<_, ExternalExecutionRow>(
            "SELECT * FROM external_executions WHERE project_id = $1 AND id = $2",
        )
        .bind(project_id)
        .bind(id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or_else(|| StorageError::NotFound(format!("external execution {id}")))
    }

    pub async fn list_external_executions(
        &self,
        project_id: Uuid,
        run_id: Uuid,
    ) -> DbResult<Vec<ExternalExecutionRow>> {
        Ok(sqlx::query_as::<_, ExternalExecutionRow>(
            r#"SELECT * FROM external_executions
                WHERE project_id = $1 AND run_id = $2
                ORDER BY created_at ASC"#,
        )
        .bind(project_id)
        .bind(run_id)
        .fetch_all(&self.pool)
        .await?)
    }

    pub async fn update_external_execution(
        &self,
        project_id: Uuid,
        id: Uuid,
        lifecycle: &str,
        external_run_id: Option<&str>,
        external_thread_id: Option<&str>,
        result: Option<&Value>,
        error: Option<&str>,
        evidence: Option<&Value>,
    ) -> DbResult<ExternalExecutionRow> {
        let updated = sqlx::query_as::<_, ExternalExecutionRow>(
            r#"UPDATE external_executions SET
                 lifecycle = $3,
                 external_run_id = COALESCE($4, external_run_id),
                 external_thread_id = COALESCE($5, external_thread_id),
                 result = COALESCE($6, result),
                 error = COALESCE($7, error),
                 evidence = COALESCE($8, evidence),
                 updated_at = $9
               WHERE project_id = $1 AND id = $2
               RETURNING *"#,
        )
        .bind(project_id)
        .bind(id)
        .bind(lifecycle)
        .bind(external_run_id)
        .bind(external_thread_id)
        .bind(result)
        .bind(error)
        .bind(evidence)
        .bind(Utc::now())
        .fetch_optional(&self.pool)
        .await?;
        updated.ok_or_else(|| StorageError::NotFound(format!("external execution {id}")))
    }
}
