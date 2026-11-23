"""Pure unit tests: no database needed."""
from datetime import date, datetime, timedelta

import pytest

import validators
import workflow
from auth import hash_password, is_hashed, issue_token, read_token, verify_password


class TestPasswords:
    def test_hash_is_salted_and_not_the_password(self):
        a, b = hash_password("longenough1"), hash_password("longenough1")
        assert a != b and "longenough1" not in a and is_hashed(a)

    def test_verify(self):
        stored = hash_password("longenough1")
        assert verify_password(stored, "longenough1") == (True, False)
        assert verify_password(stored, "wrong") == (False, False)

    def test_unknown_account_is_just_false(self):
        assert verify_password(None, "anything") == (False, False)

    def test_legacy_plain_text_is_accepted_once_and_flagged_for_upgrade(self):
        assert verify_password("plainpass1", "plainpass1") == (True, True)
        assert verify_password("plainpass1", "nope") == (False, False)


class TestTokens:
    def test_round_trip(self):
        assert read_token(issue_token(42)) == 42

    @pytest.mark.parametrize("bad", ["", None, "garbage", "a.b.c"])
    def test_garbage_is_rejected(self, bad):
        assert read_token(bad) is None

    def test_tampered_token_is_rejected(self):
        token = issue_token(7)
        assert read_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb")) is None


class TestSignupRules:
    def test_ok(self):
        assert validators.validate_signup("Sara Khan", "sara@example.com", "longenough1") is None

    @pytest.mark.parametrize("username", ["", "ab", "<script>x</script>", "a" * 31, "-leading", "semi;colon"])
    def test_bad_usernames(self, username):
        assert validators.validate_signup(username, "a@b.co", "longenough1")

    @pytest.mark.parametrize("email", ["", "plain", "a@b", "a b@c.de", "x" * 100 + "@e.co"])
    def test_bad_emails(self, email):
        assert validators.validate_signup("valid name", email, "longenough1")

    @pytest.mark.parametrize("password", ["", "short", "x" * 129, None, 12345678])
    def test_bad_passwords(self, password):
        assert validators.validate_signup("valid name", "a@b.co", password)


class TestBookingRules:
    NOW = datetime(2026, 11, 23, 8, 0)  # a Monday morning

    def test_ok_tomorrow(self):
        assert validators.validate_booking("Lab", "2026-11-24", "10-11", now=self.NOW) is None

    def test_ok_later_today(self):
        assert validators.validate_booking("Lab", "2026-11-23", "10-11", now=self.NOW) is None

    def test_slot_already_started(self):
        mid_morning = datetime(2026, 11, 23, 10, 30)
        assert "already started" in validators.validate_booking("Lab", "2026-11-23", "9-10", now=mid_morning)
        assert validators.validate_booking("Lab", "2026-11-23", "11-12", now=mid_morning) is None

    def test_past_weekend_and_far_future(self):
        assert validators.validate_booking("Lab", "2026-11-20", "10-11", now=self.NOW)       # past
        assert "Monday to Friday" in validators.validate_booking("Lab", "2026-11-28", "10-11", now=self.NOW)  # Saturday
        assert validators.validate_booking("Lab", "2026-12-25", "10-11", now=self.NOW)       # too far ahead

    @pytest.mark.parametrize("resource,slot", [("Rooftop", "10-11"), ("Lab", "7-8"), (None, "10-11"), ("Lab", None)])
    def test_unknown_resource_or_slot(self, resource, slot):
        assert validators.validate_booking(resource, "2026-11-24", slot, now=self.NOW)

    @pytest.mark.parametrize("bad_date", ["", "tomorrow", "24/11/2026", "2026-13-01", None, 20261124])
    def test_garbage_dates(self, bad_date):
        assert validators.validate_booking("Lab", bad_date, "10-11", now=self.NOW)


class TestWorkflowRules:
    @pytest.mark.parametrize("current,target,roles", [
        ("Pending", "Under Review", {"admin"}),
        ("Pending", "Rejected", {"admin"}),
        ("Pending", "Cancelled", {"owner"}),
        ("Under Review", "Approved", {"admin"}),
        ("Under Review", "Rejected", {"admin"}),
        ("Under Review", "Cancelled", {"owner"}),
        ("Approved", "Cancelled", {"owner"}),
    ])
    def test_allowed_changes(self, current, target, roles):
        note = "because" if target == "Rejected" else None
        assert workflow.check_transition(current, target, roles, note) is None

    def test_approval_needs_a_review_first(self):
        assert workflow.check_transition("Pending", "Approved", {"admin"}, None)[0] == 409

    @pytest.mark.parametrize("final", ["Rejected", "Cancelled"])
    def test_final_states_do_not_change(self, final):
        for target in workflow.STATUSES:
            assert workflow.check_transition(final, target, {"admin", "owner"}, "x")[0] == 409

    def test_students_cannot_make_admin_decisions(self):
        for target in ("Under Review", "Approved", "Rejected"):
            current = "Under Review" if target in ("Approved", "Rejected") else "Pending"
            assert workflow.check_transition(current, target, {"owner"}, "x")[0] == 403

    def test_reasons(self):
        assert workflow.check_transition("Under Review", "Rejected", {"admin"}, None)[0] == 400
        assert workflow.check_transition("Under Review", "Rejected", {"admin"}, "   ")[0] == 400
        assert workflow.check_transition("Approved", "Cancelled", {"admin"}, None)[0] == 400   # admin cancelling needs one
        assert workflow.check_transition("Approved", "Cancelled", {"owner"}, None) is None     # a student does not
        assert workflow.check_transition("Under Review", "Rejected", {"admin"}, "x" * 201)[0] == 400
