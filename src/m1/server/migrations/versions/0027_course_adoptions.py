"""Persist course checks, applications, target bases and space adoptions."""

from alembic import op

revision = "0027_course_adoptions"
down_revision = "0026_learning_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.application_check (
            check_id uuid PRIMARY KEY,
            request_ref uuid NOT NULL REFERENCES product.command_receipt(request_ref),
            base_application_ref jsonb,
            input jsonb NOT NULL,
            proposed_application jsonb NOT NULL,
            purpose_checks jsonb NOT NULL,
            blockers jsonb NOT NULL DEFAULT '[]',
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.target_basis (
            basis_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            target_id uuid NOT NULL REFERENCES product.learning_target(target_id),
            normalized_basis jsonb NOT NULL,
            digest text NOT NULL CHECK (length(digest) = 64),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (textbook_id, target_id, digest)
        );
        CREATE TABLE product.course_application (
            application_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            target_id uuid NOT NULL REFERENCES product.learning_target(target_id),
            previous_application_id uuid REFERENCES product.course_application(application_id),
            check_ref uuid NOT NULL REFERENCES product.application_check(check_id),
            content_snapshot jsonb NOT NULL,
            target_basis_ref uuid NOT NULL REFERENCES product.target_basis(basis_id),
            actor_ref jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.application_head (
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            target_id uuid NOT NULL REFERENCES product.learning_target(target_id),
            current_application_ref uuid NOT NULL REFERENCES product.course_application,
            revision bigint NOT NULL CHECK (revision > 0),
            PRIMARY KEY (textbook_id, target_id)
        );
        CREATE TABLE product.learning_space (
            space_id uuid PRIMARY KEY,
            student_id uuid NOT NULL REFERENCES product.accounts(account_id),
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            target_id uuid NOT NULL REFERENCES product.learning_target(target_id),
            current_adoption_ref uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (student_id, textbook_id, target_id)
        );
        CREATE TABLE product.space_adoption (
            adoption_id uuid PRIMARY KEY,
            space_id uuid NOT NULL REFERENCES product.learning_space(space_id),
            adoption_seq bigint NOT NULL CHECK (adoption_seq > 0),
            application_ref uuid NOT NULL REFERENCES product.course_application,
            target_basis_ref uuid NOT NULL REFERENCES product.target_basis(basis_id),
            previous_adoption_id uuid REFERENCES product.space_adoption(adoption_id),
            reason text NOT NULL,
            event_ref uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (space_id, adoption_seq),
            UNIQUE (space_id, adoption_id)
        );
        ALTER TABLE product.learning_space ADD CONSTRAINT space_current_adoption
            FOREIGN KEY (space_id, current_adoption_ref)
            REFERENCES product.space_adoption(space_id, adoption_id)
            DEFERRABLE INITIALLY DEFERRED;
        GRANT SELECT, INSERT ON product.application_check, product.target_basis,
            product.course_application, product.application_head,
            product.learning_space, product.space_adoption TO deermind_app;
        GRANT UPDATE (current_application_ref, revision) ON product.application_head
            TO deermind_app;
        GRANT UPDATE (current_adoption_ref, source_event_id) ON product.learning_space
            TO deermind_app;
        CREATE INDEX space_course ON product.learning_space(textbook_id, target_id, space_id);
        CREATE INDEX course_options_page ON product.application_head(current_application_ref);
    """)
    for relation in (
        "application_check",
        "target_basis",
        "course_application",
        "learning_space",
        "space_adoption",
    ):
        op.execute(f"CREATE INDEX {relation}_event ON product.{relation}(source_event_id)")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE product.learning_space DROP CONSTRAINT space_current_adoption;
        DROP TABLE product.space_adoption, product.learning_space, product.application_head,
            product.course_application, product.target_basis, product.application_check;
    """)
