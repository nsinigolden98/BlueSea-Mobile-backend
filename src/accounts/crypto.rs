use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
use rsa::{Oaep, RsaPrivateKey};
use sha2::Sha256;

#[derive(Debug)]
pub struct PinDecryptionError(pub String);

impl std::fmt::Display for PinDecryptionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "PIN decryption failed: {}", self.0)
    }
}
impl std::error::Error for PinDecryptionError {}

fn load_private_key(b64_or_pem: &str) -> Result<RsaPrivateKey, PinDecryptionError> {
    let trimmed = b64_or_pem.trim();
    if trimmed.is_empty() {
        return Err(PinDecryptionError("PIN_RSA_PRIVATE_KEY is not configured".into()));
    }
    if std::path::Path::new(trimmed).exists() {
        let pem = std::fs::read(trimmed).map_err(|e| PinDecryptionError(e.to_string()))?;
        return parse_pem(&pem);
    }
    if trimmed.contains("-----BEGIN") {
        return parse_pem(trimmed.as_bytes());
    }
    let pem = B64.decode(trimmed).map_err(|_| PinDecryptionError("not valid base64 or PEM".into()))?;
    parse_pem(&pem)
}

fn parse_pem(pem: &[u8]) -> Result<RsaPrivateKey, PinDecryptionError> {
    use rsa::pkcs8::DecodePrivateKey;
    let text = std::str::from_utf8(pem).map_err(|_| PinDecryptionError("bad PEM utf8".into()))?;
    if let Ok(key) = RsaPrivateKey::from_pkcs8_pem(text) {
        return Ok(key);
    }
    use rsa::pkcs1::DecodeRsaPrivateKey;
    RsaPrivateKey::from_pkcs1_pem(text)
        .map_err(|e| PinDecryptionError(format!("Failed to load PIN_RSA_PRIVATE_KEY: {e}")))
}

/// Decrypt base64 RSA-OAEP-SHA256 ciphertext → plaintext PIN/BVN.
pub fn decrypt_pin(ciphertext_b64: &str, key_b64_or_pem: &str) -> Result<String, PinDecryptionError> {
    if ciphertext_b64.is_empty() {
        return Err(PinDecryptionError("Empty ciphertext".into()));
    }
    let cipher_bytes = B64.decode(ciphertext_b64).map_err(|_| PinDecryptionError("not valid base64".into()))?;
    let key = load_private_key(key_b64_or_pem)?;
    let padding = Oaep::new::<Sha256>();
    let plain = key.decrypt(padding, &cipher_bytes).map_err(|_| PinDecryptionError("Failed to decrypt PIN".into()))?;
    String::from_utf8(plain).map_err(|_| PinDecryptionError("not valid text".into()))
}

/// Test/backend tooling helper: encrypt with the public key derived from the private key.
pub fn encrypt_pin(plain: &str, key_b64_or_pem: &str) -> Result<String, PinDecryptionError> {
    use rand::thread_rng;
    let key = load_private_key(key_b64_or_pem)?;
    let pub_key = rsa::RsaPublicKey::from(&key);
    let padding = Oaep::new::<Sha256>();
    let mut rng = thread_rng();
    let cipher = pub_key.encrypt(&mut rng, padding, plain.as_bytes())
        .map_err(|e| PinDecryptionError(e.to_string()))?;
    Ok(B64.encode(cipher))
}
