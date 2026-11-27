//! External-framework execution identity and lifecycle.
//!
//! A framework reporting success is not a Goshikq verification. `VERIFIED` is reachable
//! only from `AWAITING_VERIFICATION`, and only through [`verify_outcome`], which rejects
//! evidence whose source is the framework itself.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use utoipa::ToSchema;
use uuid::Uuid;

/// Lifecycle of one external framework execution coordinated by Goshikq.
///
/// Names are stable wire values. Do not collapse `EXTERNAL_COMPLETED` into `VERIFIED`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, JsonSchema, ToSchema)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExternalLifecycle {
    NotDispatched,
    DispatchInProgress,
    DispatchOutcomeUnknown,
    ExternalRunning,
    ExternalSuspended,
    ExternalCompleted,
    ExternalFailed,
    ReconciliationRequired,
    AwaitingVerification,
    Verified,
    VerificationFailed,
    VerificationInconclusive,
    CancelRequested,
    Cancelled,
}

impl ExternalLifecycle {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::NotDispatched => "NOT_DISPATCHED",
            Self::DispatchInProgress => "DISPATCH_IN_PROGRESS",
            Self::DispatchOutcomeUnknown => "DISPATCH_OUTCOME_UNKNOWN",
            Self::ExternalRunning => "EXTERNAL_RUNNING",
            Self::ExternalSuspended => "EXTERNAL_SUSPENDED",
            Self::ExternalCompleted => "EXTERNAL_COMPLETED",
            Self::ExternalFailed => "EXTERNAL_FAILED",
            Self::ReconciliationRequired => "RECONCILIATION_REQUIRED",
            Self::AwaitingVerification => "AWAITING_VERIFICATION",
            Self::Verified => "VERIFIED",
            Self::VerificationFailed => "VERIFICATION_FAILED",
            Self::VerificationInconclusive => "VERIFICATION_INCONCLUSIVE",
            Self::CancelRequested => "CANCEL_REQUESTED",
            Self::Cancelled => "CANCELLED",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        serde_json::from_value(Value::String(value.to_string())).ok()
    }

    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            Self::Verified
                | Self::VerificationFailed
                | Self::VerificationInconclusive
                | Self::Cancelled
        )
    }
}

/// What the adapter actually observed. `Unknown` must not be treated as success.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExternalObservationKind {
    Unknown,
    Running,
    Suspended,
    Completed,
    Failed,
    CancelConfirmed,
}

impl ExternalObservationKind {
    pub fn to_lifecycle(self) -> ExternalLifecycle {
        match self {
            Self::Unknown => ExternalLifecycle::DispatchOutcomeUnknown,
            Self::Running => ExternalLifecycle::ExternalRunning,
            Self::Suspended => ExternalLifecycle::ExternalSuspended,
            Self::Completed => ExternalLifecycle::ExternalCompleted,
            Self::Failed => ExternalLifecycle::ExternalFailed,
            Self::CancelConfirmed => ExternalLifecycle::Cancelled,
        }
    }
}

/// Legal lifecycle edges. Unsupported jumps return false; callers must not persist them.
pub fn allow_transition(from: ExternalLifecycle, to: ExternalLifecycle) -> bool {
    use ExternalLifecycle::*;
    if from == to {
        return true;
    }
    if to == Verified || to == VerificationFailed || to == VerificationInconclusive {
        return false;
    }
    matches!(
        (from, to),
        (NotDispatched, DispatchInProgress)
            | (DispatchInProgress, ExternalRunning)
            | (DispatchInProgress, ExternalSuspended)
            | (DispatchInProgress, ExternalCompleted)
            | (DispatchInProgress, ExternalFailed)
            | (DispatchInProgress, DispatchOutcomeUnknown)
            | (DispatchInProgress, ReconciliationRequired)
            | (DispatchOutcomeUnknown, ReconciliationRequired)
            | (DispatchOutcomeUnknown, ExternalRunning)
            | (DispatchOutcomeUnknown, ExternalSuspended)
            | (DispatchOutcomeUnknown, ExternalCompleted)
            | (DispatchOutcomeUnknown, ExternalFailed)
            | (ExternalRunning, ExternalSuspended)
            | (ExternalRunning, ExternalCompleted)
            | (ExternalRunning, ExternalFailed)
            | (ExternalRunning, DispatchOutcomeUnknown)
            | (ExternalRunning, ReconciliationRequired)
            | (ExternalRunning, CancelRequested)
            | (ExternalSuspended, ExternalRunning)
            | (ExternalSuspended, ExternalCompleted)
            | (ExternalSuspended, ExternalFailed)
            | (ExternalSuspended, ReconciliationRequired)
            | (ExternalSuspended, CancelRequested)
            | (ExternalCompleted, AwaitingVerification)
            | (ExternalFailed, ReconciliationRequired)
            | (ReconciliationRequired, ExternalRunning)
            | (ReconciliationRequired, ExternalSuspended)
            | (ReconciliationRequired, ExternalCompleted)
            | (ReconciliationRequired, ExternalFailed)
            | (ReconciliationRequired, DispatchOutcomeUnknown)
            | (ReconciliationRequired, AwaitingVerification)
            | (CancelRequested, Cancelled)
            | (CancelRequested, ReconciliationRequired)
            | (CancelRequested, ExternalRunning)
            | (CancelRequested, ExternalFailed)
    )
}

/// Independent verification. Framework-sourced evidence cannot satisfy the gate.
pub fn verify_outcome(
    from: ExternalLifecycle,
    predicate_passed: bool,
    evidence_source: &str,
    framework: &str,
) -> Result<ExternalLifecycle, &'static str> {
    if from != ExternalLifecycle::AwaitingVerification {
        return Err("verification requires AWAITING_VERIFICATION");
    }
    if evidence_source.trim().is_empty() {
        return Err("verification requires an evidence source");
    }
    if evidence_source.eq_ignore_ascii_case(framework) {
        return Err("framework claims are not authoritative evidence");
    }
    Ok(if predicate_passed {
        ExternalLifecycle::Verified
    } else {
        ExternalLifecycle::VerificationInconclusive
    })
}

/// Register one external execution under an existing Goshikq run.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, ToSchema)]
pub struct RegisterExternalExecutionRequest {
    pub framework: String,
    pub adapter_version: String,
    pub framework_version: String,
    pub idempotency_key: String,
    pub correlation_id: String,
    #[serde(default)]
    pub trace_id: Option<String>,
    #[serde(default)]
    pub task_id: Option<Uuid>,
    #[serde(default)]
    pub parent_run_id: Option<Uuid>,
    #[serde(default)]
    pub tenant_id: Option<Uuid>,
    #[serde(default)]
    pub dispatch_id: Option<String>,
    #[serde(default)]
    pub capabilities: Value,
}

/// Move an external execution along [`allow_transition`]. Verification states are rejected.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, ToSchema)]
pub struct TransitionExternalExecutionRequest {
    pub lifecycle: ExternalLifecycle,
    #[serde(default)]
    pub external_run_id: Option<String>,
    #[serde(default)]
    pub external_thread_id: Option<String>,
    #[serde(default)]
    pub result: Option<Value>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub evidence: Option<Value>,
}

/// Authoritative outcome gate. `evidence_source` must not be the framework name.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, ToSchema)]
pub struct VerifyExternalExecutionRequest {
    pub predicate_name: String,
    pub predicate_passed: bool,
    pub evidence_source: String,
    pub evidence_fingerprint: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn framework_completion_is_not_verified() {
        assert!(allow_transition(
            ExternalLifecycle::DispatchInProgress,
            ExternalLifecycle::ExternalCompleted
        ));
        assert!(!allow_transition(
            ExternalLifecycle::ExternalCompleted,
            ExternalLifecycle::Verified
        ));
        assert!(!allow_transition(
            ExternalLifecycle::DispatchInProgress,
            ExternalLifecycle::Verified
        ));
        assert_eq!(
            verify_outcome(
                ExternalLifecycle::AwaitingVerification,
                true,
                "langgraph",
                "langgraph"
            ),
            Err("framework claims are not authoritative evidence")
        );
    }

    #[test]
    fn unknown_observation_is_not_success() {
        assert_eq!(
            ExternalObservationKind::Unknown.to_lifecycle(),
            ExternalLifecycle::DispatchOutcomeUnknown
        );
        assert_ne!(
            ExternalObservationKind::Unknown.to_lifecycle(),
            ExternalLifecycle::ExternalCompleted
        );
    }

    #[test]
    fn independent_evidence_can_verify() {
        assert_eq!(
            verify_outcome(
                ExternalLifecycle::AwaitingVerification,
                true,
                "test-runner",
                "langgraph"
            ),
            Ok(ExternalLifecycle::Verified)
        );
        assert_eq!(
            verify_outcome(
                ExternalLifecycle::AwaitingVerification,
                false,
                "test-runner",
                "langgraph"
            ),
            Ok(ExternalLifecycle::VerificationInconclusive)
        );
        assert!(verify_outcome(
            ExternalLifecycle::ExternalCompleted,
            true,
            "test-runner",
            "langgraph"
        )
        .is_err());
    }

    #[test]
    fn cancel_requires_an_intermediate_request() {
        assert!(!allow_transition(
            ExternalLifecycle::ExternalRunning,
            ExternalLifecycle::Cancelled
        ));
        assert!(allow_transition(
            ExternalLifecycle::ExternalRunning,
            ExternalLifecycle::CancelRequested
        ));
        assert!(allow_transition(
            ExternalLifecycle::CancelRequested,
            ExternalLifecycle::Cancelled
        ));
    }
}
