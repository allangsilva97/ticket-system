"""Tests for the audit trail, SLA monitor and e-mail notifications."""
from datetime import timedelta
from unittest import mock

from test_api import ApiTestCase  # sets up the temporary database first

from database import SessionLocal, utcnow
from models import Ticket
from services import email_service, sla_service


class AuditTrailTests(ApiTestCase):
    def test_ticket_lifecycle_is_audited(self):
        t = self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t['id']}/assign", json={"assignee_id": self.agent_id}, headers=self.admin)
        self.client.put(f"/api/tickets/{t['id']}/status", json={"status": "closed"}, headers=self.agent)

        r = self.client.get(f"/api/tickets/{t['id']}/history", headers=self.agent)
        self.assertEqual(r.status_code, 200, r.text)
        actions = [e["action"] for e in r.json()]
        self.assertEqual(actions, ["status_change", "assignment", "create"])
        assignment = r.json()[1]
        self.assertEqual(assignment["changes"]["assignee_id"], {"old": None, "new": self.agent_id})
        self.assertEqual(assignment["user_role"], "admin")

    def test_history_is_staff_only(self):
        t = self.create_ticket(self.client_a, self.company_a)
        r = self.client.get(f"/api/tickets/{t['id']}/history", headers=self.client_a)
        self.assertEqual(r.status_code, 403)

    def test_audit_endpoint_admin_only_and_filters(self):
        self.create_ticket(self.client_a, self.company_a)
        self.assertEqual(self.client.get("/api/audit", headers=self.agent).status_code, 403)

        r = self.client.get("/api/audit?entity_type=company", headers=self.admin)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)  # Company A and B created in setUp
        self.assertTrue(all(e["entity_type"] == "company" for e in body["items"]))

    def test_noop_update_is_not_logged(self):
        t = self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t['id']}", json={"title": t["title"]}, headers=self.admin)
        r = self.client.get(f"/api/tickets/{t['id']}/history", headers=self.admin)
        self.assertEqual([e["action"] for e in r.json()], ["create"])

    def test_audit_survives_user_deletion(self):
        uid = self.create_user("temp@a.example.com", "agent", self.company_a)
        r = self.client.delete(f"/api/auth/users/{uid}", headers=self.admin)
        self.assertEqual(r.status_code, 204, r.text)
        r = self.client.get(f"/api/audit?entity_type=user&entity_id={uid}", headers=self.admin)
        self.assertEqual([e["action"] for e in r.json()["items"]], ["delete", "create"])


class SlaTests(ApiTestCase):
    def _set_ticket_times(self, ticket_id, created_ago_h, due_in_h):
        db = SessionLocal()
        try:
            t = db.get(Ticket, ticket_id)
            now = utcnow()
            t.created_at = now - timedelta(hours=created_ago_h)
            t.sla_due_at = now + timedelta(hours=due_in_h)
            db.commit()
        finally:
            db.close()

    def test_sla_endpoint_states(self):
        t = self.create_ticket(self.client_a, self.company_a)
        r = self.client.get(f"/api/tickets/{t['id']}/sla", headers=self.client_a)
        self.assertEqual(r.json()["status"], "ok")

        self._set_ticket_times(t["id"], created_ago_h=9, due_in_h=1)   # 90% used
        self.assertEqual(self.client.get(f"/api/tickets/{t['id']}/sla", headers=self.admin).json()["status"], "warning")

        self._set_ticket_times(t["id"], created_ago_h=30, due_in_h=-2)
        body = self.client.get(f"/api/tickets/{t['id']}/sla", headers=self.admin).json()
        self.assertEqual(body["status"], "breached")
        self.assertEqual(body["overdue_by"], "2h")

    def test_monitor_sends_each_alert_once(self):
        t = self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t['id']}/assign", json={"assignee_id": self.agent_id}, headers=self.admin)
        self._set_ticket_times(t["id"], created_ago_h=9, due_in_h=1)

        with mock.patch.object(email_service, "send") as send:
            db = SessionLocal()
            try:
                self.assertEqual(sla_service.run_sla_check(db), {"warnings": 1, "breaches": 0})
                self.assertEqual(sla_service.run_sla_check(db), {"warnings": 0, "breaches": 0})
            finally:
                db.close()
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args.args[0].to, ["agent@a.example.com"])

            self._set_ticket_times(t["id"], created_ago_h=30, due_in_h=-1)
            db = SessionLocal()
            try:
                self.assertEqual(sla_service.run_sla_check(db), {"warnings": 0, "breaches": 1})
                self.assertEqual(sla_service.run_sla_check(db), {"warnings": 0, "breaches": 0})
            finally:
                db.close()
            breach_mail = send.call_args.args[0]
            self.assertIn("SLA VIOLADO", breach_mail.subject)
            self.assertIn("admin@example.com", breach_mail.to)

    def test_closed_tickets_are_ignored(self):
        t = self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t['id']}/status", json={"status": "closed"}, headers=self.admin)
        self._set_ticket_times(t["id"], created_ago_h=30, due_in_h=-1)
        db = SessionLocal()
        try:
            self.assertEqual(sla_service.run_sla_check(db), {"warnings": 0, "breaches": 0})
        finally:
            db.close()

    def test_format_delta(self):
        self.assertEqual(sla_service.format_delta(timedelta(minutes=5)), "5m")
        self.assertEqual(sla_service.format_delta(timedelta(days=1, hours=2)), "1d 2h")
        self.assertEqual(sla_service.format_delta(timedelta(seconds=-10)), "0m")


class EmailTests(ApiTestCase):
    def test_internal_comment_not_mailed_to_client(self):
        t = self.create_ticket(self.client_a, self.company_a)
        self.client.put(f"/api/tickets/{t['id']}/assign", json={"assignee_id": self.agent_id}, headers=self.admin)
        with mock.patch.object(email_service, "send") as send:
            r = self.client.post(f"/api/tickets/{t['id']}/comments",
                                 json={"content": "secret note", "is_internal": True}, headers=self.admin)
            self.assertEqual(r.status_code, 201, r.text)
            self.assertEqual(send.call_args.args[0].to, ["agent@a.example.com"])

            self.client.post(f"/api/tickets/{t['id']}/comments",
                             json={"content": "public <b>reply</b>"}, headers=self.admin)
            mail = send.call_args.args[0]
            self.assertEqual(sorted(mail.to), ["agent@a.example.com", "client@a.example.com"])
            self.assertIn("&lt;b&gt;reply&lt;/b&gt;", mail.html)  # user content is escaped

    def test_author_does_not_mail_themselves(self):
        t = self.create_ticket(self.client_a, self.company_a)
        with mock.patch.object(email_service, "send") as send:
            self.client.put(f"/api/tickets/{t['id']}/status", json={"status": "cancelled"}, headers=self.client_a)
            self.assertEqual(send.call_args.args[0].to, [])

    def test_send_without_smtp_only_logs(self):
        mail = email_service.Email(["x@example.com"], "Subject", "<p>hi</p>")
        with mock.patch("smtplib.SMTP") as smtp:
            self.assertTrue(email_service.send(mail))
            smtp.assert_not_called()
