from email.message import EmailMessage

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.overrides.raw_ingest import ingest_raw, sync_mailboxes
from helpdesk.test_utils import make_hd_customer, make_raw_email as _mail

BOX = "inbox-test@example.com"
BOX2 = "inbox-test-2@example.com"
SYNC_BOXES = ["sync-rt-a@example.com", "sync-rt-b@example.com"]


class TestRawIngest(FrappeTestCase):
    def tearDown(self):
        # ingest_raw hace commit (como el receive() nativo), así que el rollback del test no limpia.
        for t in frappe.get_all("HD Ticket", {"raised_by": ["like", "%.test"]}, pluck="name"):
            frappe.delete_doc("HD Ticket", t, force=1)
        for c in frappe.get_all("Communication", {"message_id": ["like", "%@x.test"]}, pluck="name"):
            frappe.delete_doc("Communication", c, force=1, ignore_permissions=True)
        for r in frappe.get_all("HD Raw Email", {"source_id": ["like", "rt-src-%"]}, pluck="name"):
            frappe.delete_doc("HD Raw Email", r, force=1)
        for c in frappe.get_all("HD Customer", {"customer_name": ["like", "RT Cliente%"]}, pluck="name"):
            frappe.delete_doc("HD Customer", c, force=1)
        for a in frappe.get_all("Email Account", {"email_id": ["in", [BOX2, *SYNC_BOXES]]}, pluck="name"):
            frappe.delete_doc("Email Account", a, force=1)
        frappe.db.commit()

    def test_html_cid_thread_dedupe_and_sent(self):
        first = _mail(
            "rt1@x.test", "Pedido RT", "Ana <ana@cliente.test>", BOX, "hola",
            html='<p>Hola <b>mundo</b></p><img src="cid:logo1"><script>alert(1)</script>', inline=True,
        )
        r1 = ingest_raw(first, BOX, "rt-src-1")
        self.assertEqual(r1["status"], "Processed")
        comm = frappe.get_doc("Communication", r1["communication"])
        self.assertIn("<b>mundo</b>", comm.content)  # html, no el text/plain
        self.assertNotIn("cid:logo1", comm.content)  # cid -> URL del File
        self.assertNotIn("<script", comm.content)  # sanitizado

        # idempotente por source_id y por Message-ID
        self.assertEqual(ingest_raw(first, BOX, "rt-src-1")["status"], "Duplicate")

        # respuesta enviada (Sent) y respuesta del cliente caen en el mismo ticket
        sent = _mail("rt2@x.test", "Re: Pedido RT", f"V <{BOX}>", "ana@cliente.test", "ok", in_reply_to="rt1@x.test")
        r2 = ingest_raw(sent, BOX, "rt-src-2", direction="Sent", notify=False)
        reply = _mail("rt3@x.test", "Re: Pedido RT", "ana@cliente.test", BOX, "ñandú acentuado", in_reply_to="rt2@x.test")
        r3 = ingest_raw(reply, BOX, "rt-src-3", notify=False)
        self.assertEqual({r1["reference_name"], r2["reference_name"], r3["reference_name"]}, {r1["reference_name"]})
        self.assertIn("ñandú", frappe.db.get_value("Communication", r3["communication"], "text_content"))

    def test_sent_without_thread_is_skipped(self):
        sent = _mail("rt9@x.test", "Saliente suelto", f"V <{BOX}>", "z@cliente.test", "x")
        self.assertEqual(ingest_raw(sent, BOX, "rt-src-9", direction="Sent")["reason"], "sent_sin_hilo")

    def test_broken_attachment_does_not_lose_the_mail(self):
        m = EmailMessage()
        m["From"], m["To"], m["Subject"], m["Message-ID"] = "b@cliente.test", BOX, "Adjunto roto", "<rt8@x.test>"
        m.set_content("cuerpo")
        m.add_attachment(b"%PDF-1.4 truncado", maintype="application", subtype="pdf", filename="roto.pdf")
        r = ingest_raw(m.as_bytes(), BOX, "rt-src-8", notify=False)
        self.assertEqual(r["status"], "Processed")

    def test_customer_by_domain_returns_odoo_partner_id(self):
        customer = make_hd_customer("RT Cliente Dominio", domain="dominio-rt.test", odoo_partner_id=424242)
        mail = _mail("rt20@x.test", "Con partner", "Eva <eva@dominio-rt.test>", BOX, "hola")
        r = ingest_raw(mail, BOX, "rt-src-20", notify=False)
        self.assertEqual(r["status"], "Processed")
        self.assertEqual(r["customer"], customer.name)
        self.assertEqual(r["odoo_partner_id"], 424242)

    def test_customer_without_partner_id_omits_it(self):
        make_hd_customer("RT Cliente Sin Partner", domain="sinpartner-rt.test")
        r = ingest_raw(_mail("rt21@x.test", "Sin partner", "eva@sinpartner-rt.test", BOX, "hola"), BOX, "rt-src-21", notify=False)
        self.assertEqual(r["customer"], "RT Cliente Sin Partner")
        self.assertNotIn("odoo_partner_id", r)

    def test_same_mail_in_two_mailboxes_is_merged(self):
        raw = _mail("rt30@x.test", "Cc a dos buzones", "ana@cliente.test", f"{BOX}, {BOX2}", "hola")
        r1 = ingest_raw(raw, BOX, "rt-src-30a", notify=False)
        r2 = ingest_raw(raw, BOX2, "rt-src-30b", notify=False)
        self.assertEqual(r1["status"], "Processed")
        self.assertEqual((r2["status"], r2["of"]), ("Duplicate", "Processed"))
        self.assertEqual(r2["communication"], r1["communication"])
        self.assertEqual(r2["reference_name"], r1["reference_name"])
        self.assertEqual(frappe.db.count("Communication", {"message_id": "<rt30@x.test>"}), 1)
        second = frappe.get_doc("HD Raw Email", {"source_id": "rt-src-30b"})
        self.assertEqual((second.status, second.skip_reason), ("Skipped", "fusionado_con_otro_buzon"))
        self.assertEqual(second.communication, r1["communication"])

    def test_sent_dedupe_stays_per_account(self):
        first = _mail("rt40@x.test", "Hilo", "ana@cliente.test", BOX, "hola")
        r1 = ingest_raw(first, BOX, "rt-src-40", notify=False)
        sent = _mail("rt41@x.test", "Re: Hilo", f"V <{BOX}>", "ana@cliente.test", "ok", in_reply_to="rt40@x.test")
        self.assertEqual(ingest_raw(sent, BOX, "rt-src-41", direction="Sent", notify=False)["status"], "Processed")
        # el mismo enviado visto desde otro buzón no se fusiona: Sent deduplica por cuenta
        other = ingest_raw(sent, BOX2, "rt-src-42", direction="Sent", notify=False)
        self.assertNotEqual(other.get("reason"), "fusionado_con_otro_buzon")
        self.assertEqual(r1["status"], "Processed")

    def test_sync_mailboxes_is_idempotent(self):
        first = sync_mailboxes(SYNC_BOXES + [SYNC_BOXES[0].upper()])
        second = sync_mailboxes(frappe.as_json(SYNC_BOXES))
        self.assertEqual([a["email_id"] for a in first], SYNC_BOXES)
        self.assertEqual(first, second)
        for name in (a["name"] for a in first):
            account = frappe.get_doc("Email Account", name)
            self.assertEqual((account.enable_incoming, account.use_imap, account.enable_outgoing), (0, 0, 0))
