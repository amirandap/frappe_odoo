import base64
from email.message import EmailMessage

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.overrides.raw_ingest import ingest_raw

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
BOX = "inbox-test@example.com"


def _mail(msg_id, subject, sender, to, body, in_reply_to=None, html=None, inline=False):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = sender, to, subject, f"<{msg_id}>"
    if in_reply_to:
        m["In-Reply-To"] = m["References"] = f"<{in_reply_to}>"
    m.set_content(body)
    if html:
        m.add_alternative(html, subtype="html")
        if inline:
            m.get_payload()[1].add_related(PNG, "image", "png", cid="<logo1>", filename="logo.png")
    return m.as_bytes()


class TestRawIngest(FrappeTestCase):
    def tearDown(self):
        # ingest_raw hace commit (como el receive() nativo), así que el rollback del test no limpia.
        for t in frappe.get_all("HD Ticket", {"raised_by": ["like", "%@cliente.test"]}, pluck="name"):
            frappe.delete_doc("HD Ticket", t, force=1)
        for c in frappe.get_all("Communication", {"message_id": ["like", "%@x.test"]}, pluck="name"):
            frappe.delete_doc("Communication", c, force=1, ignore_permissions=True)
        for r in frappe.get_all("HD Raw Email", {"source_id": ["like", "rt-src-%"]}, pluck="name"):
            frappe.delete_doc("HD Raw Email", r, force=1)
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
