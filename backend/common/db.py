"""Database-level helpers used by migrations."""


def append_only_trigger_sql(table: str) -> tuple[str, str]:
    """SQL that forbids UPDATE/DELETE on a table (D-011). Returns (forward, reverse)."""
    fn = f"{table}_append_only"
    forward = f"""
    CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'table {table} is append-only';
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER {fn}_trg BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION {fn}();
    """
    reverse = f"DROP TRIGGER IF EXISTS {fn}_trg ON {table}; DROP FUNCTION IF EXISTS {fn}();"
    return forward, reverse
