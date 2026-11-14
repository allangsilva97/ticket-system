"""
API tests. Run from the project folder:

    python -m unittest discover -s tests -v

Uses a temporary SQLite database, so the real tickets.db is never touched.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Must be set BEFORE importing the app (settings are read at import time)
_tmpdir = tempfile.mkdtemp(prefix="ticket-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmpdir, 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(Path(_tmpdir, "uploads"))
os.environ["SECRET_KEY"] = "test-only-secret-key-0123456789abcdefghijklmnop"
os.environ["SLA_MONITOR_ENABLED"] = "false"
os.environ["SMTP_HOST"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, engine  # noqa: E402
from main import app  # noqa: E402
from routers import auth as auth_router  # noqa: E402

PASSWORD = "Password123!"


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        auth_router._failures.clear()
        self.client = TestClient(app)
        self.client.__enter__()

        # First user bootstraps as admin
        r = self.client.post("/api/auth/register", json={
            "email": "admin@example.com", "password": PASSWORD, "full_name": "Admin"})
        self.assertEqual(r.status_code, 201, r.text)
        self.admin = self.login("admin@example.com")

        self.company_a = self.create_company("Company A")
        self.company_b = self.create_company("Company B")
        self.agent_id = self.create_user("agent@a.example.com", "agent", self.company_a)
        self.client_id = self.create_user("client@a.example.com", "client", self.company_a)
        self.agent = self.login("agent@a.example.com")
        self.client_a = self.login("client@a.example.com")

    def tearDown(self):
        self.client.__exit__(None, None, None)

    # ---------- helpers ----------
    def login(self, email):
        r = self.client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def create_company(self, name):
        r = self.client.post("/api/companies", json={"name": name}, headers=self.admin)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def create_user(self, email, role, company_id):
        r = self.client.post("/api/auth/register", headers=self.admin, json={
            "email": email, "password": PASSWORD, "full_name": email.split("@")[0],
            "role": role, "company_id": company_id})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def create_ticket(self, headers, company_id, priority="medium"):
        r = self.client.post("/api/tickets", headers=headers, json={
            "title": "Printer broken", "description": "It does not print",
            "company_id": company_id, "priority": priority, "category": "technical"})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()


class AuthTests(ApiTestCase):
    def test_register_requires_admin_after_bootstrap(self):
        body = {"email": "x@example.com", "password": PASSWORD, "full_name": "X", "role": "admin"}
        self.assertEqual(self.client.post("/api/auth/register", json=body).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/register", json=body, headers=self.agent).status_code, 403)

    def test_login_wrong_password(self):
        r = self.client.post("/api/auth/login", data={"username": "admin@example.com", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_login_rate_limited_after_repeated_failures(self):
        for _ in range(auth_router.MAX_FAILURES_PER_ACCOUNT):
            r = self.client.post("/api/auth/login", data={"username": "agent@a.example.com", "password": "bad"})
            self.assertEqual(r.status_code, 401)
        # Locked now, even with the correct password
        r = self.client.post("/api/auth/login", data={"username": "agent@a.example.com", "password": PASSWORD})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)
        # Other accounts are not affected
        self.login("client@a.example.com")

    def test_successful_login_resets_failure_count(self):
        for _ in range(auth_router.MAX_FAILURES_PER_ACCOUNT - 1):
            self.client.post("/api/auth/login", data={"username": "agent@a.example.com", "password": "bad"})
        self.login("agent@a.example.com")
        r = self.client.post("/api/auth/login", data={"username": "agent@a.example.com", "password": "bad"})
        self.assertEqual(r.status_code, 401)

    def test_invalid_token_rejected(self):
        r = self.client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
        self.assertEqual(r.status_code, 401)

    def test_admin_cannot_demote_self(self):
        me = self.client.get("/api/auth/me", headers=self.admin).json()
        r = self.client.put(f"/api/auth/users/{me['id']}", json={"role": "client"}, headers=self.admin)
        self.assertEqual(r.status_code, 400)

    def test_local_domain_emails_accepted(self):
        # Regression: ".local" emails could log in but every update returned 422
        uid = self.create_user("someone@corp.local", "agent", self.company_a)
        r = self.client.put(f"/api/auth/users/{uid}", headers=self.admin,
                            json={"email": "someone@corp.local", "full_name": "Renamed"})
        self.assertEqual(r.status_code, 200, r.text)

    def test_self_update_cannot_escalate_role(self):
        self.client.put("/api/auth/me", json={"role": "admin"}, headers=self.client_a)
        me = self.client.get("/api/auth/me", headers=self.client_a).json()
        self.assertEqual(me["role"], "client")


class TicketTests(ApiTestCase):
    def test_client_cannot_change_priority_but_staff_can(self):
        ticket = self.create_ticket(self.client_a, self.company_a, priority="low")
        url = f"/api/tickets/{ticket['id']}"

        r = self.client.put(url, json={"priority": "critical", "title": "Edited"}, headers=self.client_a)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["priority"], "low")
        self.assertEqual(r.json()["title"], "Edited")
        self.assertEqual(r.json()["sla_due_at"], ticket["sla_due_at"])

        r = self.client.put(url, json={"priority": "critical"}, headers=self.agent)
        self.assertEqual(r.json()["priority"], "critical")
        self.assertNotEqual(r.json()["sla_due_at"], ticket["sla_due_at"])

    def test_client_cannot_create_ticket_for_other_company(self):
        r = self.client.post("/api/tickets", headers=self.client_a, json={
            "title": "x", "company_id": self.company_b})
        self.assertEqual(r.status_code, 403)

    def test_client_cannot_see_other_company_ticket(self):
        other = self.create_ticket(self.admin, self.company_b)
        self.assertEqual(self.client.get(f"/api/tickets/{other['id']}", headers=self.client_a).status_code, 403)
        listed = self.client.get("/api/tickets", headers=self.client_a).json()
        self.assertNotIn(other["id"], [t["id"] for t in listed["items"]])

    def test_internal_comments_hidden_from_clients(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        url = f"/api/tickets/{ticket['id']}/comments"
        self.client.post(url, json={"content": "internal note", "is_internal": True}, headers=self.agent)
        self.client.post(url, json={"content": "public reply"}, headers=self.agent)

        client_view = [c["content"] for c in self.client.get(url, headers=self.client_a).json()]
        agent_view = [c["content"] for c in self.client.get(url, headers=self.agent).json()]
        self.assertEqual(client_view, ["public reply"])
        self.assertEqual(agent_view, ["internal note", "public reply"])

    def test_status_close_and_reopen_tracks_resolution(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        url = f"/api/tickets/{ticket['id']}/status"
        closed = self.client.put(url, json={"status": "closed"}, headers=self.agent).json()
        self.assertIsNotNone(closed["closed_at"])
        reopened = self.client.put(url, json={"status": "open"}, headers=self.client_a).json()
        self.assertIsNone(reopened["closed_at"])

    def test_client_cannot_close_ticket(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        r = self.client.put(f"/api/tickets/{ticket['id']}/status", json={"status": "closed"}, headers=self.client_a)
        self.assertEqual(r.status_code, 403)

    def test_only_admin_deletes_tickets(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        url = f"/api/tickets/{ticket['id']}"
        self.assertEqual(self.client.delete(url, headers=self.agent).status_code, 403)
        self.assertEqual(self.client.delete(url, headers=self.admin).status_code, 204)

    def test_attachment_upload_and_download_requires_access(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        r = self.client.post(f"/api/tickets/{ticket['id']}/attachments", headers=self.client_a,
                             files={"file": ("note.txt", b"hello", "text/plain")})
        self.assertEqual(r.status_code, 201, r.text)
        att_id = r.json()["id"]

        dl = f"/api/tickets/attachments/{att_id}/download"
        self.assertEqual(self.client.get(dl, headers=self.client_a).content, b"hello")
        self.assertEqual(self.client.get(dl).status_code, 401)

        outsider_id = self.create_user("client@b.example.com", "client", self.company_b)
        self.assertTrue(outsider_id)
        self.assertEqual(self.client.get(dl, headers=self.login("client@b.example.com")).status_code, 403)

    def test_disallowed_file_type_rejected(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        r = self.client.post(f"/api/tickets/{ticket['id']}/attachments", headers=self.client_a,
                             files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
        self.assertEqual(r.status_code, 400)


class DashboardTests(ApiTestCase):
    def test_dashboard_scoped_per_role(self):
        self.create_ticket(self.client_a, self.company_a)
        self.create_ticket(self.admin, self.company_b)
        self.assertEqual(self.client.get("/api/dashboard/stats", headers=self.admin).json()["total_tickets"], 2)
        self.assertEqual(self.client.get("/api/dashboard/stats", headers=self.client_a).json()["total_tickets"], 1)

    def test_charts_endpoints(self):
        self.create_ticket(self.client_a, self.company_a)
        r = self.client.get("/api/dashboard/charts/tickets-by-date?days=7", headers=self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sum(d["count"] for d in r.json()["data"]), 1)
        self.assertEqual(self.client.get("/api/dashboard/charts/sla-compliance", headers=self.admin).status_code, 200)


if __name__ == "__main__":
    unittest.main()
