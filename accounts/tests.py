from django.test import TestCase

from accounts.crypto import encrypt_pin
from accounts.models import Profile
from accounts.pin_security import verify_pin_with_lockout


class TransactionPinSecurityTestCase(TestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            email="pintest@example.com",
            phone="08022223333",
            surname="Pin",
            other_names="Test",
            role="user",
        )

    def test_set_pin_is_hashed_not_plaintext(self):
        self.user.set_transaction_pin(encrypt_pin("1234"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.pin_is_set)
        self.assertNotEqual(self.user.transaction_pin, "1234")
        self.assertTrue(self.user.transaction_pin.startswith("pbkdf2_"))

    def test_verify_correct_and_wrong_encrypted_pin(self):
        self.user.set_transaction_pin(encrypt_pin("1234"))
        self.assertTrue(self.user.verify_transaction_pin(encrypt_pin("1234")))
        self.assertFalse(self.user.verify_transaction_pin(encrypt_pin("0000")))
        # Malformed ciphertext must not raise and must fail verification.
        self.assertFalse(self.user.verify_transaction_pin("not-valid-base64!!"))

    def test_lockout_after_five_failures(self):
        self.user.set_transaction_pin(encrypt_pin("1234"))

        last = None
        for _ in range(5):
            last = verify_pin_with_lockout(self.user, encrypt_pin("0000"))
            self.assertFalse(last.ok)
        # After the 5th failure the account is locked.
        self.assertTrue(last.locked)
        self.assertEqual(last.attempts_remaining, 0)

        # While locked, even the correct PIN is rejected.
        locked = verify_pin_with_lockout(self.user, encrypt_pin("1234"))
        self.assertTrue(locked.locked)
        self.assertFalse(locked.ok)

    def test_success_resets_failure_counter(self):
        self.user.set_transaction_pin(encrypt_pin("1234"))
        verify_pin_with_lockout(self.user, encrypt_pin("0000"))  # 1 failure
        result = verify_pin_with_lockout(self.user, encrypt_pin("1234"))
        self.assertTrue(result.ok)
        self.user.refresh_from_db()
        self.assertEqual(self.user.pin_failed_attempts, 0)
        self.assertIsNone(self.user.pin_locked_until)

    def test_expired_lock_is_cleared_on_next_attempt(self):
        self.user.set_transaction_pin(encrypt_pin("1234"))
        self.user.pin_failed_attempts = 5
        self.user.pin_locked_until = self.user.pin_locked_until  # keep None path
        from django.utils import timezone

        self.user.pin_locked_until = timezone.now() - timezone.timedelta(minutes=1)
        self.user.save()

        result = verify_pin_with_lockout(self.user, encrypt_pin("1234"))
        self.assertTrue(result.ok)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.pin_locked_until)
