//! External framework execution identity. Verification is a separate call and
//! rejects evidence that comes from the framework itself.

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use chrono::Utc;
use goshikq_protocol::{
    allow_transition, verify_outcome, ExternalLifecycle, RegisterExternalExecutionRequest,
    TransitionExternalExecutionRequest, VerifyExternalExecutionRequest,
};
use goshikq_storage::ExternalExecutionRow;
use serde::Serialize;
use serde_json::{json, Value};
use utoipa::ToSchema;
use uuid::Uuid;

use crate::auth::{Permission, Scope};
use crate::error::ApiError;
use crate::state::AppState;

#[derive(Debug, Serialize, ToSchema)]
pub struct RegisterExternalExecutionResponse {
    pub execution: ExternalExecutionRow,
    pub reused: bool,
}

#[utoipa::path(
    post,
    path = "/api/v1/runs/{id}/external-executions",
    tag = "integrations",
    request_body = RegisterExternalExecutionRequest,
    params(("id" = Uuid, Path)),
    responses(
        (status = 201, body = RegisterExternalExecutionResponse),
        (status = 200, body = RegisterExternalExecutionResponse),
        (status = 400, body = crate::error::ErrorBody)
    )
)]
pub async fn register_external_execution(
    State(st): State<AppState>,
    scope: Scope,
    Path(run_id): Path<Uuid>,
    Json(req): Json<RegisterExternalExecutionRequest>,
) -> Result<(StatusCode, Json<RegisterExternalExecutionResponse>), ApiError> {
    scope.require(Permission::RunWrite)?;
    if req.framework.trim().is_empty() || req.idempotency_key.trim().is_empty() {
        return Err(ApiError::bad_request(
            "framework and idempotency_key are required",
        ));
    }
    st.db.get_run(scope.project_id, run_id).await?;
    if let Some(existing) = st
        .db
        .find_external_execution_by_idempotency(scope.project_id, &req.idempotency_key)
        .await?
    {
        if existing.run_id != run_id {
            return Err(ApiError::conflict(
                "idempotency_key is already bound to a different run",
            ));
        }
        return Ok((
            StatusCode::OK,
            Json(RegisterExternalExecutionResponse {
                execution: existing,
                reused: true,
            }),
        ));
    }
    let now = Utc::now();
    let row = ExternalExecutionRow {
        id: Uuid::now_v7(),
        project_id: scope.project_id,
        run_id,
        parent_run_id: req.parent_run_id,
        task_id: req.task_id,
        tenant_id: req.tenant_id,
        framework: req.framework,
        adapter_version: req.adapter_version,
        framework_version: req.framework_version,
        external_run_id: None,
        external_thread_id: None,
        correlation_id: req.correlation_id,
        trace_id: req.trace_id,
        idempotency_key: req.idempotency_key,
        dispatch_id: req
            .dispatch_id
            .unwrap_or_else(|| Uuid::now_v7().to_string()),
        lifecycle: ExternalLifecycle::NotDispatched.as_str().to_string(),
        capabilities: if req.capabilities.is_null() {
            json!({})
        } else {
            req.capabilities
        },
        evidence: json!({}),
        result: None,
        error: None,
        created_at: now,
        updated_at: now,
    };
    let execution = st.db.insert_external_execution(&row).await?;
    Ok((
        StatusCode::CREATED,
        Json(RegisterExternalExecutionResponse {
            execution,
            reused: false,
        }),
    ))
}

#[utoipa::path(
    get,
    path = "/api/v1/runs/{id}/external-executions",
    tag = "integrations",
    params(("id" = Uuid, Path)),
    responses((status = 200, body = Vec<ExternalExecutionRow>))
)]
pub async fn list_external_executions(
    State(st): State<AppState>,
    scope: Scope,
    Path(run_id): Path<Uuid>,
) -> Result<Json<Vec<ExternalExecutionRow>>, ApiError> {
    scope.require(Permission::RunRead)?;
    st.db.get_run(scope.project_id, run_id).await?;
    Ok(Json(
        st.db
            .list_external_executions(scope.project_id, run_id)
            .await?,
    ))
}

#[utoipa::path(
    get,
    path = "/api/v1/external-executions/{id}",
    tag = "integrations",
    params(("id" = Uuid, Path)),
    responses(
        (status = 200, body = ExternalExecutionRow),
        (status = 404, body = crate::error::ErrorBody)
    )
)]
pub async fn get_external_execution(
    State(st): State<AppState>,
    scope: Scope,
    Path(id): Path<Uuid>,
) -> Result<Json<ExternalExecutionRow>, ApiError> {
    scope.require(Permission::RunRead)?;
    Ok(Json(
        st.db.get_external_execution(scope.project_id, id).await?,
    ))
}

#[utoipa::path(
    post,
    path = "/api/v1/external-executions/{id}/transition",
    tag = "integrations",
    request_body = TransitionExternalExecutionRequest,
    params(("id" = Uuid, Path)),
    responses(
        (status = 200, body = ExternalExecutionRow),
        (status = 409, body = crate::error::ErrorBody)
    )
)]
pub async fn transition_external_execution(
    State(st): State<AppState>,
    scope: Scope,
    Path(id): Path<Uuid>,
    Json(req): Json<TransitionExternalExecutionRequest>,
) -> Result<Json<ExternalExecutionRow>, ApiError> {
    scope.require(Permission::RunWrite)?;
    if matches!(
        req.lifecycle,
        ExternalLifecycle::Verified
            | ExternalLifecycle::VerificationFailed
            | ExternalLifecycle::VerificationInconclusive
    ) {
        return Err(ApiError::bad_request(
            "verification states are recorded only by the verification endpoint",
        ));
    }
    let current = st.db.get_external_execution(scope.project_id, id).await?;
    let from = ExternalLifecycle::parse(&current.lifecycle).ok_or_else(|| {
        ApiError::conflict(format!("stored lifecycle {} is unknown", current.lifecycle))
    })?;
    if !allow_transition(from, req.lifecycle) {
        return Err(ApiError::conflict(format!(
            "cannot move {} to {}",
            from.as_str(),
            req.lifecycle.as_str()
        )));
    }
    if req.lifecycle == ExternalLifecycle::Cancelled {
        let native = current
            .capabilities
            .get("native_cancellation")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if !native {
            return Err(ApiError::bad_request(
                "this adapter does not support confirmed cancellation",
            ));
        }
    }
    let updated = st
        .db
        .update_external_execution(
            scope.project_id,
            id,
            req.lifecycle.as_str(),
            req.external_run_id.as_deref(),
            req.external_thread_id.as_deref(),
            req.result.as_ref(),
            req.error.as_deref(),
            req.evidence.as_ref(),
        )
        .await?;
    Ok(Json(updated))
}

#[utoipa::path(
    post,
    path = "/api/v1/external-executions/{id}/verify",
    tag = "verification",
    request_body = VerifyExternalExecutionRequest,
    params(("id" = Uuid, Path)),
    responses(
        (status = 200, body = ExternalExecutionRow),
        (status = 409, body = crate::error::ErrorBody)
    )
)]
pub async fn verify_external_execution(
    State(st): State<AppState>,
    scope: Scope,
    Path(id): Path<Uuid>,
    Json(req): Json<VerifyExternalExecutionRequest>,
) -> Result<Json<ExternalExecutionRow>, ApiError> {
    scope.require(Permission::RunWrite)?;
    let current = st.db.get_external_execution(scope.project_id, id).await?;
    let from = ExternalLifecycle::parse(&current.lifecycle).ok_or_else(|| {
        ApiError::conflict(format!("stored lifecycle {} is unknown", current.lifecycle))
    })?;
    let next = verify_outcome(
        from,
        req.predicate_passed,
        &req.evidence_source,
        &current.framework,
    )
    .map_err(|message| ApiError::conflict(message))?;
    let mut evidence: Value = current.evidence.clone();
    if !evidence.is_object() {
        evidence = json!({});
    }
    evidence["verification"] = json!({
        "predicate_name": req.predicate_name,
        "predicate_passed": req.predicate_passed,
        "evidence_source": req.evidence_source,
        "evidence_fingerprint": req.evidence_fingerprint,
        "framework_claim_accepted": false,
    });
    let updated = st
        .db
        .update_external_execution(
            scope.project_id,
            id,
            next.as_str(),
            None,
            None,
            None,
            None,
            Some(&evidence),
        )
        .await?;
    Ok(Json(updated))
}
