"""Fail-fast production checks for wallet indexes, isolation, and row-lock serialization."""
from concurrent.futures import ThreadPoolExecutor
import os
import time

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")


def debit_under_lock(wallet_id: int, amount: float) -> str:
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        row = connection.execute("SELECT available_balance FROM user_wallets WHERE wallet_id = %s FOR UPDATE", (wallet_id,)).fetchone()
        if not row or row[0] < amount:
            connection.rollback()
            return "rejected"
        connection.execute("UPDATE user_wallets SET available_balance = available_balance - %s WHERE wallet_id = %s", (amount, wallet_id))
        time.sleep(0.05)
        connection.rollback()  # validation never mutates production data
        return "serialized"


def main() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        isolation = connection.execute("SHOW transaction_isolation").fetchone()[0]
        indexes = {row[0] for row in connection.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename IN ('wallet_transactions','financial_consent_logs')")}
        required = {"ix_wallet_transactions_wallet_created", "ix_financial_consent_user_created", "ix_financial_consent_order_status"}
        missing = required - indexes
        if missing:
            raise RuntimeError(f"Missing wallet indexes: {sorted(missing)}")
        wallet = connection.execute("SELECT wallet_id FROM user_wallets ORDER BY wallet_id LIMIT 1").fetchone()
        if not wallet:
            raise RuntimeError("Seed at least one wallet before concurrency validation")
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: debit_under_lock(wallet[0], 1), range(24)))
    if set(outcomes) - {"serialized", "rejected"}:
        raise RuntimeError(f"Unexpected checkout outcomes: {outcomes}")
    print(f"PostgreSQL wallet validation passed: isolation={isolation}, indexes={len(required)}, concurrent_attempts={len(outcomes)}")


if __name__ == "__main__":
    main()
