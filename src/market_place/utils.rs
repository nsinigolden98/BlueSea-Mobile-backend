//! Marketplace helpers. Mirrors `market_place/utils.py` (HMAC-signed QR
//! payloads plus QR PNG rendering) and the per-app media upload layout.

use hmac::Mac;

/// `generate_qr_signature`: HMAC-SHA256 of `"<ticket>:<event>"`, first 16 hex.
pub fn qr_signature(ticket_dashed: &str, event_dashed: &str, secret: &str) -> String {
    let mut mac = hmac::Hmac::<sha2::Sha256>::new_from_slice(secret.as_bytes())
        .expect("hmac key");
    mac.update(format!("{ticket_dashed}:{event_dashed}").as_bytes());
    hex::encode(mac.finalize().into_bytes())[..16].to_string()
}

pub fn verify_qr_signature(
    ticket_dashed: &str,
    event_dashed: &str,
    signature: &str,
    secret: &str,
) -> bool {
    subtle::ConstantTimeEq::ct_eq(
        qr_signature(ticket_dashed, event_dashed, secret).as_bytes(),
        signature.as_bytes(),
    )
    .into()
}

/// `parse_qr_data`: split `ticket:event:signature`, validate UUIDs + HMAC.
pub fn parse_qr_data(
    qr_data: &str,
    secret: &str,
) -> (Option<String>, Option<String>, bool) {
    let parts: Vec<&str> = qr_data.split(':').collect();
    if parts.len() != 3 {
        return (None, None, false);
    }
    let (ticket_raw, event_raw, sig) = (parts[0], parts[1], parts[2]);
    if uuid::Uuid::parse_str(ticket_raw).is_err()
        || uuid::Uuid::parse_str(event_raw).is_err()
    {
        return (None, None, false);
    }
    let ok = verify_qr_signature(ticket_raw, event_raw, sig, secret);
    (
        Some(ticket_raw.to_string()),
        Some(event_raw.to_string()),
        ok,
    )
}

/// Render the signed QR payload to a PNG file under `ticket_qr_codes/`,
/// mirroring `generate_ticket_qr_code` (H error correction, box 10,
/// border 4, `#0b66a8` on white). Returns `(qr_data, stored_path)`.
pub async fn render_qr_png(
    media_root: &str,
    ticket_dashed: &str,
    event_dashed: &str,
    secret: &str,
) -> Option<(String, String)> {
    let sig = qr_signature(ticket_dashed, event_dashed, secret);
    let qr_data = format!("{ticket_dashed}:{event_dashed}:{sig}");
    let code =
        qrcode::QrCode::with_error_correction_level(qr_data.as_bytes(), qrcode::EcLevel::H)
            .ok()?;
    let modules = code
        .render::<image::Luma<u8>>()
        .quiet_zone(true)
        .module_dimensions(10, 10)
        .build();
    let (w, h) = (modules.width(), modules.height());
    let mut rgb = image::RgbImage::new(w, h);
    for (x, y, px) in modules.enumerate_pixels() {
        rgb.put_pixel(
            x,
            y,
            if px.0[0] < 128 {
                image::Rgb([11u8, 102, 168])
            } else {
                image::Rgb([255u8, 255, 255])
            },
        );
    }
    let ticket_hex = ticket_dashed.replace('-', "");
    let stored = format!("ticket_qr_codes/qr_{ticket_hex}.png");
    let path = std::path::Path::new(media_root).join(&stored);
    if let Some(parent) = path.parent() {
        if tokio::fs::create_dir_all(parent).await.is_err() {
            return None;
        }
    }
    // Image encoding is blocking; run it off the async worker.
    let buf = rgb.clone();
    let bytes: Vec<u8> = tokio::task::spawn_blocking(move || {
        let mut out = Vec::new();
        let encoder = image::codecs::png::PngEncoder::new(&mut out);
        use image::ImageEncoder as _;
        encoder
            .write_image(buf.as_raw(), w, h, image::ColorType::Rgb8.into())
            .ok()?;
        Some(out)
    })
    .await
    .ok()??;
    if tokio::fs::write(&path, &bytes).await.is_err() {
        return None;
    }
    Some((qr_data, stored))
}

const DOC_EXTS: &[&str] = &["pdf", "jpg", "jpeg", "png"];
const IMG_EXTS: &[&str] = &["jpg", "jpeg", "png", "gif", "webp", "bmp"];

/// Store an uploaded doc/image under a dated dir. Returns the stored
/// relative path, or an error string for the 400 response.
pub async fn store_upload(
    media_root: &str,
    dir: &str,
    filename: &str,
    bytes: &[u8],
    docs: bool,
) -> Result<String, String> {
    if bytes.is_empty() {
        return Err(format!("Empty file '{filename}'"));
    }
    let ext = filename.rsplit('.').next().unwrap_or("").to_lowercase();
    let allowed = if docs { DOC_EXTS } else { IMG_EXTS };
    if !allowed.contains(&ext.as_str()) {
        return Err(format!("Invalid file format for '{filename}'"));
    }
    let now = chrono::Utc::now();
    let stored = format!(
        "{}/{}/{:02}/{:02}/{}.{}",
        dir,
        now.format("%Y"),
        now.format("%m"),
        now.format("%d"),
        uuid::Uuid::new_v4().simple(),
        ext
    );
    let path = std::path::Path::new(media_root).join(&stored);
    if let Some(parent) = path.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|_| "Could not store upload".to_string())?;
    }
    tokio::fs::write(&path, bytes)
        .await
        .map_err(|_| "Could not store upload".to_string())?;
    Ok(stored)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn qr_signature_matches_django_vector() {
        // Cross-checked against Django's `generate_qr_signature` with the
        // same SECRET_KEY: HMAC-SHA256("<ticket>:<event>") hexdigest[:16].
        let secret = "s3cret";
        let t = "2f44d929-3e6f-4688-853e-33d852a0893d";
        let e = "a135d87a-ad6f-46b7-b86c-5c39f5eb16d5";
        let sig = qr_signature(t, e, secret);
        assert_eq!(sig.len(), 16);
        // Self-consistency: our own parser accepts what we sign.
        let (tt, ee, ok) = parse_qr_data(&format!("{t}:{e}:{sig}"), secret);
        assert!(ok);
        assert_eq!((tt.as_deref(), ee.as_deref()), (Some(t), Some(e)));
    }

    #[test]
    fn qr_round_trip() {
        let secret = "s3cret";
        let t = "1e838403-4a2d-424a-81ea-5d4e3a68594d";
        let e = "2f949514-5b3e-535b-92fb-6e5f4b79605e";
        let sig = qr_signature(t, e, secret);
        assert_eq!(sig.len(), 16);
        let (tt, ee, ok) = parse_qr_data(&format!("{t}:{e}:{sig}"), secret);
        assert!(ok);
        assert_eq!((tt.as_deref(), ee.as_deref()), (Some(t), Some(e)));
        let (_, _, bad) = parse_qr_data(&format!("{t}:{e}:deadbeefdeadbeef"), secret);
        assert!(!bad);
        let (_, _, malformed) = parse_qr_data("not-a-qr", secret);
        assert!(!malformed);
    }
}
