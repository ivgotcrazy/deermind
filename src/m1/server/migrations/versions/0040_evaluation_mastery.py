"""Create the evidence and mastery projections."""

from alembic import op

revision = "0040_evaluation_mastery"
down_revision = "0039_evaluation_interpretation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation.evidence (
            evidence_id uuid PRIMARY KEY,
            input_ref uuid NOT NULL REFERENCES evaluation.evaluation_input(input_id),
            interpretation_ref uuid NOT NULL
                REFERENCES evaluation.interpretation(interpretation_id),
            scope_id uuid NOT NULL,
            claim_id uuid NOT NULL,
            claim_revision bigint NOT NULL,
            method_id uuid NOT NULL,
            method_version bigint NOT NULL CHECK (method_version > 0),
            aspect_code text NOT NULL CHECK (
                aspect_code IN ('independent', 'understanding', 'transfer', 'retention')
            ),
            source_kind text NOT NULL CHECK (source_kind IN ('answer', 'teaching')),
            source_id uuid NOT NULL,
            execution_checks jsonb NOT NULL,
            rule_ref jsonb NOT NULL,
            condition_facts jsonb NOT NULL,
            source_spans jsonb NOT NULL,
            source_refs jsonb NOT NULL DEFAULT '[]',
            qualification text NOT NULL CHECK (
                qualification IN ('eligible', 'ineligible', 'unknown')
            ),
            verdict text CHECK (verdict IN ('positive', 'negative')),
            reason_codes jsonb NOT NULL,
            reason text NOT NULL,
            limitations jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            CHECK ((verdict IS NOT NULL) = (qualification='eligible' AND source_kind='answer')),
            FOREIGN KEY (claim_id, claim_revision)
                REFERENCES evaluation.claim_version(claim_id, revision),
            UNIQUE (
                scope_id, claim_id, claim_revision, method_id, method_version, aspect_code,
                source_kind, source_id
            )
        );
        CREATE INDEX evaluation_evidence_input ON evaluation.evidence(input_ref);
        CREATE INDEX evaluation_evidence_event ON evaluation.evidence(source_event_id);

        CREATE TABLE evaluation.belief_revision (
            belief_revision_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            claim_id uuid NOT NULL,
            claim_revision bigint NOT NULL,
            method_id uuid NOT NULL,
            method_version bigint NOT NULL CHECK (method_version > 0),
            aspect_code text NOT NULL CHECK (
                aspect_code IN ('independent', 'understanding', 'transfer', 'retention')
            ),
            previous_revision_id uuid REFERENCES evaluation.belief_revision(belief_revision_id),
            evidence_ref uuid NOT NULL UNIQUE REFERENCES evaluation.evidence(evidence_id),
            update_kind text NOT NULL CHECK (update_kind IN ('observation','learning_transition')),
            p_obs_before double precision CHECK (p_obs_before BETWEEN 0 AND 1),
            p_current_before double precision NOT NULL CHECK (p_current_before BETWEEN 0 AND 1),
            p_obs_after double precision CHECK (p_obs_after BETWEEN 0 AND 1),
            p_current_after double precision NOT NULL CHECK (p_current_after BETWEEN 0 AND 1),
            last_observed_at timestamptz,
            parameter_ref text NOT NULL,
            algorithm_ref text NOT NULL,
            reason_codes jsonb NOT NULL,
            trigger_event_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            FOREIGN KEY (claim_id, claim_revision)
                REFERENCES evaluation.claim_version(claim_id, revision)
        );
        CREATE INDEX evaluation_belief_event ON evaluation.belief_revision(source_event_id);
        CREATE INDEX evaluation_belief_previous
            ON evaluation.belief_revision(previous_revision_id);
        CREATE INDEX evaluation_belief_history ON evaluation.belief_revision (
            scope_id, claim_id, claim_revision, method_id, method_version, aspect_code, created_at
        );

        CREATE TABLE evaluation.belief_current (
            scope_id uuid NOT NULL,
            claim_id uuid NOT NULL,
            claim_revision bigint NOT NULL,
            method_id uuid NOT NULL,
            method_version bigint NOT NULL,
            aspect_code text NOT NULL,
            current_revision_ref uuid NOT NULL REFERENCES evaluation.belief_revision,
            p_obs double precision CHECK (p_obs BETWEEN 0 AND 1),
            p_current double precision NOT NULL CHECK (p_current BETWEEN 0 AND 1),
            last_observed_at timestamptz,
            FOREIGN KEY (claim_id, claim_revision)
                REFERENCES evaluation.claim_version(claim_id, revision),
            PRIMARY KEY (scope_id, claim_id, claim_revision, method_id, method_version, aspect_code)
        );
        CREATE TABLE evaluation.mastery_snapshot (
            snapshot_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            publication_seq bigint NOT NULL CHECK (publication_seq > 0),
            items jsonb NOT NULL,
            coverage jsonb NOT NULL,
            result_coverage jsonb NOT NULL DEFAULT '[]',
            published_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (scope_id, publication_seq)
        );
        CREATE INDEX evaluation_mastery_event ON evaluation.mastery_snapshot(source_event_id);
        CREATE TABLE evaluation.mastery_head (
            scope_id uuid PRIMARY KEY,
            current_snapshot_ref uuid REFERENCES evaluation.mastery_snapshot(snapshot_id),
            publication_seq bigint NOT NULL DEFAULT 0 CHECK (publication_seq >= 0),
            CHECK ((current_snapshot_ref IS NULL) = (publication_seq = 0))
        );
        GRANT SELECT, INSERT ON evaluation.evidence, evaluation.belief_revision,
            evaluation.mastery_snapshot TO deermind_app;
        GRANT SELECT, INSERT, UPDATE ON evaluation.belief_current, evaluation.mastery_head
            TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
