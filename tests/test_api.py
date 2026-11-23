"""API tests against the throwaway MySQL database (see conftest.py)."""
from datetime import date, timedelta

import pytest

from conftest import ADMIN_EMAIL, ADMIN_PASSWORD, STUDENT_PASSWORD, next_weekday


# ---------------------------------------------------------------- accounts
class TestAccounts:
    def test_sign_up_then_sign_in(self, client):
        assert client.post("/signup", json={"username": "ayesha", "email": "Ayesha@Example.com", "password": STUDENT_PASSWORD}).status_code == 201
        response = client.post("/signin", json={"email": "AYESHA@example.com", "password": STUDENT_PASSWORD})
        assert response.status_code == 200
        body = response.get_json()
        assert body["role"] == "student" and body["username"] == "ayesha" and body["token"]

    def test_password_is_stored_hashed(self, client, database):
        import mysql.connector
        import config

        client.post("/signup", json={"username": "hashcheck", "email": "hashcheck@example.com", "password": STUDENT_PASSWORD})
        conn = mysql.connector.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER, password=config.DB_PASSWORD, database=config.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE email = 'hashcheck@example.com'")
        stored = cursor.fetchone()[0]
        conn.close()
        assert STUDENT_PASSWORD not in stored and stored.startswith("scrypt:")

    def test_wrong_password_and_unknown_email_look_the_same(self, client, make_student):
        make_student("known")
        wrong = client.post("/signin", json={"email": "known@example.com", "password": "not-the-password"})
        unknown = client.post("/signin", json={"email": "nobody@example.com", "password": "whatever1"})
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.get_json() == unknown.get_json()

    def test_sign_up_cannot_choose_a_role(self, client):
        client.post("/signup", json={"username": "sneaky", "email": "sneaky@example.com", "password": STUDENT_PASSWORD, "role": "admin"})
        assert client.post("/signin", json={"email": "sneaky@example.com", "password": STUDENT_PASSWORD}).get_json()["role"] == "student"

    def test_duplicates_are_refused(self, client, make_student):
        make_student("taken")
        assert client.post("/signup", json={"username": "taken", "email": "new@example.com", "password": STUDENT_PASSWORD}).status_code == 409
        assert client.post("/signup", json={"username": "new", "email": "TAKEN@example.com", "password": STUDENT_PASSWORD}).status_code == 409

    @pytest.mark.parametrize("payload", [
        {"username": "<img src=x onerror=alert(1)>", "email": "x@example.com", "password": STUDENT_PASSWORD},
        {"username": "ok name", "email": "not-an-email", "password": STUDENT_PASSWORD},
        {"username": "ok name", "email": "x@example.com", "password": "short"},
        {},
    ])
    def test_bad_sign_up_is_a_400(self, client, payload):
        assert client.post("/signup", json=payload).status_code == 400

    def test_me(self, client, make_student):
        headers = make_student("whoami")
        assert client.get("/me", headers=headers).get_json() == {"username": "whoami", "role": "student"}
        assert client.get("/me").status_code == 401
        assert client.get("/me", headers={"Authorization": "Bearer forged.token.here"}).status_code == 401


# ---------------------------------------------------------------- who may do what
class TestPermissions:
    ADMIN_ONLY = [("post", "/blocked_slots", {"resource": "Lab", "date": "2030-01-01", "time": "9-10"}), ("delete", "/blocked_slots/1", None)]

    def test_anonymous_gets_401_on_protected_routes(self, client):
        for method, path in [("get", "/bookings"), ("post", "/bookings"), ("put", "/bookings/1/status"), ("get", "/bookings/1"),
                             ("post", "/blocked_slots"), ("delete", "/blocked_slots/1"), ("get", "/notifications"),
                             ("put", "/notifications/read"), ("get", "/me")]:
            assert getattr(client, method)(path, json={}).status_code == 401, (method, path)

    def test_public_routes(self, client):
        assert client.get("/availability").status_code == 200
        assert client.get("/blocked_slots").status_code == 200

    def test_students_cannot_block_or_unblock(self, client, make_student):
        student = make_student()
        for method, path, body in self.ADMIN_ONLY:
            assert getattr(client, method)(path, json=body, headers=student).status_code == 403

    def test_admins_do_not_book(self, client, admin, book):
        assert book(admin).status_code == 403

    def test_booking_owner_comes_from_the_token_not_the_body(self, client, make_student, admin):
        student = make_student("realowner")
        response = client.post("/bookings", json={"username": "someone_else", "resource": "Lab", "date": next_weekday(), "timeSlot": "10-11"}, headers=student)
        assert response.status_code == 201
        assert {b["username"] for b in client.get("/bookings", headers=admin).get_json()} == {"realowner"}

    def test_a_student_only_sees_their_own_bookings(self, client, make_student, book):
        a, b = make_student("alice1"), make_student("bob12")
        book(a, slot="9-10")
        book(b, slot="10-11")
        assert [x["username"] for x in client.get("/bookings", headers=a).get_json()] == ["alice1"]
        assert [x["username"] for x in client.get("/bookings?username=bob12", headers=a).get_json()] == ["alice1"]

    def test_notifications_are_always_the_callers_own(self, client, make_student, book, admin, move, booking_ids):
        a, b = make_student("alice2"), make_student("bob23")
        book(a)
        move(admin, booking_ids()["alice2"], "Under Review")
        assert len(client.get("/notifications", headers=a).get_json()) == 1
        assert client.get("/notifications?username=alice2", headers=b).get_json() == []

    def test_availability_never_reveals_who_booked(self, client, make_student, book):
        book(make_student("privateperson"))
        text = client.get("/availability?resource=Lab").get_data(as_text=True)
        assert "privateperson" not in text and "username" not in text


# ---------------------------------------------------------------- booking input checks
class TestBookingInput:
    def test_valid_booking(self, book, make_student):
        assert book(make_student()).status_code == 201

    @pytest.mark.parametrize("body", [
        {"resource": "Rooftop", "timeSlot": "10-11"},
        {"resource": "Lab", "timeSlot": "7-8"},
        {"resource": "Lab", "timeSlot": "10-11", "date": "26/11/2026"},
        {"resource": "Lab", "timeSlot": "10-11", "date": "2020-01-06"},
        {},
    ])
    def test_bad_input_is_a_400(self, client, make_student, body):
        body.setdefault("date", next_weekday())
        assert client.post("/bookings", json=body, headers=make_student()).status_code == 400

    def test_weekends_and_far_future_are_refused(self, client, make_student):
        student = make_student()
        saturday = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 or 7)
        for day in (saturday.isoformat(), (date.today() + timedelta(days=60)).isoformat()):
            assert client.post("/bookings", json={"resource": "Lab", "date": day, "timeSlot": "10-11"}, headers=student).status_code == 400

    def test_same_user_same_slot_twice_is_a_409(self, book, make_student):
        student = make_student()
        assert book(student).status_code == 201
        assert book(student).status_code == 409

    def test_cannot_book_a_blocked_slot(self, client, book, make_student, admin):
        day = next_weekday()
        assert client.post("/blocked_slots", json={"resource": "Lab", "date": day, "time": "10-11"}, headers=admin).status_code == 201
        assert book(make_student(), day=day).status_code == 400

    def test_blocks_are_validated_and_unique(self, client, admin):
        day = next_weekday()
        assert client.post("/blocked_slots", json={"resource": "Lab", "date": day, "time": "10-11"}, headers=admin).status_code == 201
        assert client.post("/blocked_slots", json={"resource": "Lab", "date": day, "time": "10-11"}, headers=admin).status_code == 409
        assert client.post("/blocked_slots", json={"resource": "Lab", "date": "2020-01-06", "time": "10-11"}, headers=admin).status_code == 400
        assert client.delete("/blocked_slots/99999", headers=admin).status_code == 404

    def test_availability_validates_its_filters(self, client):
        assert client.get("/availability?resource=Nope").status_code == 400
        assert client.get("/availability?from=yesterday").status_code == 400


# ---------------------------------------------------------------- the approval workflow
class TestWorkflow:
    def test_full_happy_path_and_history(self, client, make_student, book, admin, move, booking_ids):
        student = make_student("happy1")
        book(student)
        booking_id = booking_ids()["happy1"]
        assert move(admin, booking_id, "Under Review").status_code == 200
        assert move(admin, booking_id, "Approved").status_code == 200
        assert move(student, booking_id, "Cancelled").status_code == 200

        history = client.get(f"/bookings/{booking_id}", headers=student).get_json()["history"]
        assert [(e["fromStatus"], e["toStatus"]) for e in history] == [
            (None, "Pending"), ("Pending", "Under Review"), ("Under Review", "Approved"), ("Approved", "Cancelled")]
        assert history[-1]["actor"] == "happy1"

    def test_cannot_skip_the_review_step(self, make_student, book, admin, move, booking_ids):
        book(make_student("skip12"))
        assert move(admin, booking_ids()["skip12"], "Approved").status_code == 409

    def test_students_cannot_decide(self, make_student, book, admin, move, booking_ids):
        student = make_student("decide1")
        book(student)
        booking_id = booking_ids(slot="10-11")["decide1"]
        assert move(student, booking_id, "Under Review").status_code == 403   # only an admin starts a review
        move(admin, booking_id, "Under Review")
        assert move(student, booking_id, "Approved").status_code == 403       # ...and only an admin decides
        assert move(student, booking_id, "Rejected", "nope").status_code == 403

    def test_someone_elses_booking_looks_like_it_does_not_exist(self, client, make_student, book, move, booking_ids):
        owner, other = make_student("owner12"), make_student("other12")
        book(owner)
        booking_id = booking_ids()["owner12"]
        assert move(other, booking_id, "Cancelled").status_code == 404
        assert client.get(f"/bookings/{booking_id}", headers=other).status_code == 404

    def test_rejection_needs_a_reason_and_is_final(self, make_student, book, admin, move, booking_ids):
        book(make_student("reason1"))
        booking_id = booking_ids()["reason1"]
        assert move(admin, booking_id, "Rejected").status_code == 400
        assert move(admin, booking_id, "Rejected", "Reserved for an exam").status_code == 200
        assert move(admin, booking_id, "Under Review").status_code == 409

    def test_admin_cancelling_needs_a_reason_but_a_student_does_not(self, make_student, book, admin, move, booking_ids):
        student = make_student("cancel1")
        book(student)
        booking_id = booking_ids()["cancel1"]
        move(admin, booking_id, "Under Review")
        move(admin, booking_id, "Approved")
        assert move(admin, booking_id, "Cancelled").status_code == 400
        assert move(student, booking_id, "Cancelled").status_code == 200

    def test_approving_one_request_rejects_the_competition(self, client, make_student, book, admin, move, booking_ids):
        sara, tariq = make_student("sara12"), make_student("tariq1")
        book(sara)
        book(tariq)
        ids = booking_ids()
        move(admin, ids["sara12"], "Under Review")
        response = move(admin, ids["sara12"], "Approved")
        assert response.get_json()["alsoRejected"] == 1
        statuses = {b["username"]: b["status"] for b in client.get("/bookings", headers=admin).get_json()}
        assert statuses == {"sara12": "Approved", "tariq1": "Rejected"}
        message = client.get("/notifications", headers=tariq).get_json()[0]["message"]
        assert "rejected" in message and "another request" in message

    def test_a_cancelled_slot_can_be_booked_again(self, client, make_student, book, admin, move, booking_ids):
        first, second = make_student("first12"), make_student("second1")
        book(first)
        move(admin, booking_ids()["first12"], "Under Review")
        move(admin, booking_ids()["first12"], "Approved")
        move(first, booking_ids()["first12"], "Cancelled")
        assert book(second).status_code == 201
        assert book(first).status_code == 201  # the cancelled request no longer counts as a duplicate

    def test_a_maintenance_block_cancels_approved_and_rejects_open_bookings(self, client, make_student, book, admin, move, booking_ids):
        day = next_weekday()
        approved_student, waiting_student = make_student("appr12"), make_student("wait12")
        book(approved_student, day=day)
        book(waiting_student, day=day)
        ids = booking_ids(day=day)
        move(admin, ids["appr12"], "Under Review")
        move(admin, ids["appr12"], "Approved")  # this also rejects wait12, so make a fresh pending one below
        book(make_student("late12"), day=day)
        response = client.post("/blocked_slots", json={"resource": "Lab", "date": day, "time": "10-11"}, headers=admin)
        assert response.status_code == 201 and response.get_json()["affectedBookings"] == 2
        statuses = {b["username"]: b["status"] for b in client.get("/bookings", headers=admin).get_json()}
        assert statuses["appr12"] == "Cancelled" and statuses["late12"] == "Rejected"
        assert "maintenance" in client.get("/notifications", headers=approved_student).get_json()[0]["message"]

    def test_unknown_status_value(self, make_student, book, admin, move, booking_ids):
        book(make_student("weird12"))
        assert move(admin, booking_ids()["weird12"], "Teleported").status_code == 400

    def test_two_approved_bookings_for_one_slot_are_impossible(self, client, database, make_student, book, admin, move, booking_ids):
        """Even if the application logic were bypassed, the database refuses a second approved booking for a slot."""
        import mysql.connector
        import config

        book(make_student("dbrule1"))
        book(make_student("dbrule2"))
        ids = booking_ids()
        move(admin, ids["dbrule1"], "Under Review")
        move(admin, ids["dbrule1"], "Approved")
        conn = mysql.connector.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER, password=config.DB_PASSWORD, database=config.DB_NAME)
        cursor = conn.cursor()
        with pytest.raises(mysql.connector.IntegrityError):
            cursor.execute("UPDATE bookings SET status = 'Approved' WHERE id = %s", (ids["dbrule2"],))
        conn.close()


# ---------------------------------------------------------------- notifications
class TestNotifications:
    def test_mark_read(self, client, make_student, book, admin, move, booking_ids):
        student = make_student("notif12")
        book(student)
        move(admin, booking_ids()["notif12"], "Under Review")
        assert client.get("/notifications", headers=student).get_json()[0]["is_read"] in (0, False)
        assert client.put("/notifications/read", headers=student).status_code == 200
        assert client.get("/notifications", headers=student).get_json()[0]["is_read"] in (1, True)
