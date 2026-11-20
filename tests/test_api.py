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
# SQLite by default. TEST_DATABASE_URL runs the suite on another database (a scratch PostgreSQL database:
# the tests drop and recreate every table in it).
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{Path(_tmpdir, 'test.db').as_posix()}"
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


class PublicTrackingTests(ApiTestCase):
    def test_ticket_gets_unique_tracking_code(self):
        a = self.create_ticket(self.client_a, self.company_a)
        b = self.create_ticket(self.client_a, self.company_a)
        self.assertEqual(len(a["tracking_code"]), 10)
        self.assertNotEqual(a["tracking_code"], b["tracking_code"])

    def test_track_without_login_hides_internal_data(self):
        ticket = self.create_ticket(self.client_a, self.company_a)
        url = f"/api/tickets/{ticket['id']}/comments"
        self.client.post(url, json={"content": "Public reply"}, headers=self.agent)
        self.client.post(url, json={"content": "Secret note", "is_internal": True}, headers=self.agent)

        r = self.client.get(f"/api/public/tickets/{ticket['tracking_code']}")  # no auth header
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["title"], "Printer broken")
        self.assertEqual([c["content"] for c in body["comments"]], ["Public reply"])
        self.assertNotIn("@", r.text)  # no e-mail addresses leak

    def test_track_accepts_formatted_code(self):
        code = self.create_ticket(self.client_a, self.company_a)["tracking_code"]
        r = self.client.get(f"/api/public/tickets/{code[:5].lower()}-{code[5:].lower()}")
        self.assertEqual(r.status_code, 200)

    def test_track_unknown_code_404(self):
        self.assertEqual(self.client.get("/api/public/tickets/ABCDEFGHJK").status_code, 404)
        self.assertEqual(self.client.get("/api/public/tickets/1").status_code, 404)

    def test_unassigned_and_open_only_filters(self):
        t1 = self.create_ticket(self.client_a, self.company_a)
        t2 = self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t1['id']}/assign", json={"assignee_id": self.agent_id}, headers=self.agent)
        self.client.put(f"/api/tickets/{t2['id']}/status", json={"status": "cancelled"}, headers=self.client_a)

        queue = self.client.get("/api/tickets?unassigned=true&open_only=true", headers=self.agent).json()
        self.assertEqual(queue["total"], 0)
        unassigned = self.client.get("/api/tickets?unassigned=true", headers=self.agent).json()
        self.assertEqual([t["id"] for t in unassigned["items"]], [t2["id"]])

    def test_portal_pages_served(self):
        for path in ("/", "/login", "/dashboard", "/perfil", "/abrir-chamado", "/acompanhar", "/tecnico"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn("portal.js", r.text)


class SearchAndStyleTests(ApiTestCase):
    def test_search_treats_like_wildcards_literally(self):
        # "%" and "_" must match themselves, not "anything"
        self.client.post("/api/tickets", headers=self.admin, json={
            "title": "Disk 100% full", "company_id": self.company_a, "priority": "low", "category": "technical"})
        self.create_ticket(self.admin, self.company_a)  # "Printer broken"
        for term, expected in (("100%", 1), ("%", 1), ("_", 0), ("Printer", 1)):
            r = self.client.get("/api/tickets", params={"search": term}, headers=self.admin)
            self.assertEqual(r.json()["total"], expected, term)
        users = self.client.get("/api/users", params={"search": "_"}, headers=self.admin).json()
        self.assertEqual(users["total"], 0)
        companies = self.client.get("/api/companies", params={"search": "%"}, headers=self.admin).json()
        self.assertEqual(companies["total"], 0)

    def test_admin_panel_login_card_is_hidden_by_default(self):
        css = self.client.get("/static/style.css").text
        # #login-screen must not force display:flex, or it shows up above the panel on /painel
        rule = next(line for line in css.splitlines() if line.startswith("#login-screen {"))
        self.assertNotIn("display", rule)
        self.assertIn("#login-screen.screen.active { display: flex; }", css)


class StaffOverviewTests(ApiTestCase):
    def test_overview_staff_only_and_counts_workload(self):
        t = self.create_ticket(self.client_a, self.company_a)
        self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t['id']}/assign", json={"assignee_id": self.agent_id}, headers=self.agent)

        self.assertEqual(self.client.get("/api/dashboard/overview", headers=self.client_a).status_code, 403)
        r = self.client.get("/api/dashboard/overview", headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["unassigned_open"], 1)
        self.assertEqual([(w["user_id"], w["open"]) for w in body["workload"]], [(self.agent_id, 1)])
        self.assertEqual(body["by_company"][0], {"name": "Company A", "total": 2, "open": 2})
        self.assertIsNotNone(body["avg_first_response_hours"])  # assignment set first_response_at

    def test_root_is_login_page(self):
        r = self.client.get("/")
        self.assertIn("login-form", r.text)
        self.assertIn("app.js", self.client.get("/painel").text)


@unittest.skipUnless(engine.dialect.name == "sqlite", "recreates a pre-v2.1 SQLite table")
class MigrationTests(unittest.TestCase):
    def test_legacy_database_gets_tracking_codes(self):
        from sqlalchemy import text
        from database import init_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            # Recreate tickets as it was before v2.1 (no tracking_code column)
            conn.execute(text("DROP TABLE tickets"))
            conn.execute(text("CREATE TABLE tickets (id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, "
                              "description TEXT, status VARCHAR(19) NOT NULL, priority VARCHAR(8) NOT NULL, "
                              "category VARCHAR(15) NOT NULL, company_id INTEGER NOT NULL, "
                              "creator_id INTEGER NOT NULL, "
                              "assignee_id INTEGER, sla_due_at DATETIME, first_response_at DATETIME, "
                              "resolved_at DATETIME, sla_warning_notified_at DATETIME, "
                              "sla_breach_notified_at DATETIME, created_at DATETIME, updated_at DATETIME, "
                              "closed_at DATETIME)"))
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("INSERT INTO tickets (id, title, status, priority, category, company_id, creator_id) "
                              "VALUES (1, 'old', 'OPEN', 'MEDIUM', 'OTHER', 1, 1)"))
        init_db()
        with engine.connect() as conn:
            code = conn.execute(text("SELECT tracking_code FROM tickets WHERE id = 1")).scalar()
        self.assertEqual(len(code), 10)
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    unittest.main()
