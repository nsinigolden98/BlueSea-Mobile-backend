/// Mark a pending referral's first transaction as completed.
/// Mirrors the `Referral` flag write in the purchase views and VTpass webhook.
pub async fn mark_first_transaction_completed(
    db: &sqlx::SqlitePool,
    referred_user_id: i64,
) -> Result<Option<i64>, sqlx::Error> {
    let row: Option<(i64, i64)> = sqlx::query_as(
        "SELECT id, referrer_id FROM bonus_referral
         WHERE referred_user_id = ? AND status = 'pending' AND first_transaction_completed = 0",
    )
    .bind(referred_user_id)
    .fetch_optional(db)
    .await?;
    if let Some((id, referrer_id)) = row {
        sqlx::query("UPDATE bonus_referral SET first_transaction_completed = 1 WHERE id = ?")
            .bind(id)
            .execute(db)
            .await?;
        return Ok(Some(referrer_id));
    }
    Ok(None)
}

/// Stub for `award_vtu_purchase_points` — logs until the bonus app is ported.
pub fn award_vtu_purchase_points(user_id: i64, purchase_cents: i64, reference: &str) {
    tracing::debug!(
        "bonus stub: award_vtu_purchase_points user={user_id} amount_cents={purchase_cents} ref={reference}"
    );
}

/// Stub for `award_referral_bonus` — logs until the bonus app is ported.
pub fn award_referral_bonus(referrer_id: i64, referred_user_id: i64) {
    tracing::debug!(
        "bonus stub: award_referral_bonus referrer={referrer_id} referred={referred_user_id}"
    );
}
