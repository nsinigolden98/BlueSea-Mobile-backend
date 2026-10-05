//! Transactions app — wallet ledger.
//! Django layout mirrored (`transactions/models.py`).
//! Only `WalletTransaction` ships in this pass (wallet's credit/debit need
//! it); `FundWallet`/`AccountName` and the funding views land with the
//! transactions app port.

pub mod models;
