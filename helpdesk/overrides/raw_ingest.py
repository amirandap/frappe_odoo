"""Ingesta de correo crudo (RFC822) que reemplaza al conector IMAP de Frappe.

El origen (Gmail API + Pub/Sub, un bridge de IMAP, un .eml cualquiera) sólo
entrega los bytes del mensaje. Todo lo demás lo hace el pipeline NATIVO de
Frappe, el mismo que usaría `EmailAccount.receive()`:

  - `InboundMail` parsea MIME: html > text, adjuntos, `cid:` -> URL del File,
    sanitiza el HTML, decodifica asunto/remitente/fecha.
  - dedupe de Received por Message-ID entre todos los buzones sólo-ingesta (un correo
    en dos buzones es un solo ticket); de Sent, por Message-ID + Email Account.
  - hilo por In-Reply-To (+ References, ver `CustomInboundMail`).
  - crea el HD Ticket si el correo no tiene padre (`append_to`).

Lo que se agrega acá es sólo lo que el IMAP de Frappe no tenía:
  - `HD Raw Email`: los bytes originales, idempotencia por `source_id`.
  - reproceso de un correo guardado sin volver al buzón.
  - correos enviados (carpeta Sent) colgados de su hilo.
"""

import base64
import binascii

import frappe
from frappe import _
from frappe.email.receive import SentEmailInInboxError
from frappe.utils import cint, now_datetime

from helpdesk.overrides.email_account import CustomInboundMail

APPEND_TO = "HD Ticket"
RAW_DOCTYPE = "HD Raw Email"


class RawInboundMail(CustomInboundMail):
    """InboundMail que sabe si el correo salió (Sent) o entró (Inbox)."""

    def __init__(self, *args, direction: str = "Received", **kwargs):
        super().__init__(*args, **kwargs)
        self.direction = direction
        self.failed_attachments: list[str] = []

    def save_attachments_in_doc(self, doc):
        """Un adjunto roto (PDF truncado, nombre inválido) no debe costar el correo.

        El nativo propaga cualquier excepción que no sea tamaño/duplicado, y
        eso tira abajo el mensaje entero. Acá se aísla cada adjunto con un
        savepoint y se registra cuál falló.
        """
        saved, all_attachments = [], self.attachments
        try:
            for attachment in all_attachments:
                self.attachments = [attachment]
                frappe.db.savepoint("hd_raw_attachment")
                try:
                    saved += super().save_attachments_in_doc(doc)
                except Exception:
                    frappe.db.rollback(save_point="hd_raw_attachment")
                    self.failed_attachments.append(attachment["fname"])
                    frappe.log_error(
                        title="HD raw ingest: adjunto descartado",
                        message=f"{attachment['fname']}\n{frappe.get_traceback()}",
                    )
        finally:
            self.attachments = all_attachments
        return saved

    def as_dict(self):
        data = super().as_dict()
        data["sent_or_received"] = self.direction
        return data

    def _create_reference_document(self, doctype):
        name = super()._create_reference_document(doctype)
        if name and doctype == APPEND_TO:
            self._set_customer_by_domain(name)
        return name

    def _set_customer_by_domain(self, ticket: str):
        """Mismo criterio con que se agruparon los tickets migrados: HD Customer.domain."""
        if frappe.db.get_value(APPEND_TO, ticket, "customer"):
            return
        domain = (self.from_email or "").rpartition("@")[2].lower()
        if not domain:
            return
        customer = frappe.db.get_value("HD Customer", {"domain": domain})
        if customer:
            frappe.db.set_value(APPEND_TO, ticket, "customer", customer, update_modified=False)

    def is_sender_same_as_receiver(self):
        # En Sent el remitente ES el buzón; no es un rebote.
        if self.direction == "Sent":
            return False
        return super().is_sender_same_as_receiver()

    def is_exist_in_system(self):
        from frappe.core.doctype.communication.communication import Communication

        if not self.message_id:
            return None
        accounts = self.email_account.name
        if self.direction == "Received":
            # El mismo correo llega a cada buzón al que iba dirigido; debe ser un solo ticket.
            accounts = ["in", [*get_ingest_only_accounts(), self.email_account.name]]
        return Communication.find_one_by_filters(
            message_id=self.message_id,
            email_account=accounts,
            sent_or_received=self.direction,
            order_by="creation DESC",
        )


def get_ingest_only_accounts() -> list[str]:
    """Email Accounts que Frappe no consulta: sólo reciben lo que entrega `ingest`."""
    return frappe.get_all("Email Account", {"enable_incoming": 0, "use_imap": 0}, pluck="name")


def customer_payload(reference_doctype: str | None, reference_name: str | None) -> dict:
    """`customer` y `odoo_partner_id` del ticket, para que el hub conozca el id de Odoo."""
    if reference_doctype != APPEND_TO or not reference_name:
        return {}
    customer = frappe.db.get_value(APPEND_TO, reference_name, "customer")
    if not customer:
        return {}
    payload = {"customer": customer}
    partner_id = frappe.db.get_value("HD Customer", customer, "odoo_partner_id")
    if partner_id:
        payload["odoo_partner_id"] = partner_id
    return payload


def decode_raw(value: str | bytes) -> bytes:
    """Acepta bytes, base64 estándar o base64url (lo que devuelve Gmail `format=raw`)."""
    if isinstance(value, bytes):
        return value
    text = "".join(value.split())
    text += "=" * (-len(text) % 4)
    try:
        return base64.b64decode(text, altchars=b"-_", validate=False)
    except (binascii.Error, ValueError) as e:
        frappe.throw(_("raw no es base64 válido: {0}").format(e))


def get_or_create_account(address: str):
    """Email Account sólo-ingesta (sin IMAP ni SMTP) por buzón.

    `InboundMail` necesita un Email Account para `email_id`, el dedupe y los
    permisos; no necesita que Frappe se conecte a nada.
    """
    address = (address or "").strip().lower()
    if not address:
        frappe.throw(_("mailbox es obligatorio"))
    name = frappe.db.get_value("Email Account", {"email_id": address})
    if name:
        return frappe.get_doc("Email Account", name)
    doc = frappe.get_doc(
        {
            "doctype": "Email Account",
            "email_account_name": address,
            "email_id": address,
            "append_to": APPEND_TO,
            "enable_incoming": 0,
            "enable_outgoing": 0,
            "create_contact": 1,
            "use_imap": 0,
        }
    )
    doc.flags.ignore_validate = True
    doc.insert(ignore_permissions=True)
    return doc


def _store_raw(raw: bytes, source_id: str, account, direction: str, message_id: str):
    row = frappe.get_doc(
        {
            "doctype": RAW_DOCTYPE,
            "source_id": source_id,
            "email_account": account.name,
            "direction": direction,
            "status": "Pending",
            "message_id": message_id,
            "received_at": now_datetime(),
            "raw_size": len(raw),
        }
    ).insert(ignore_permissions=True)
    file = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"{source_id}.eml",
            "attached_to_doctype": RAW_DOCTYPE,
            "attached_to_name": row.name,
            "attached_to_field": "raw_file",
            "is_private": 1,
            "content": raw,
        }
    ).insert(ignore_permissions=True)
    row.db_set("raw_file", file.file_url, update_modified=False)
    return row


def _raw_bytes(row) -> bytes:
    file_name = frappe.db.get_value("File", {"file_url": row.raw_file})
    # Bytes del disco, nunca `File.get_content()`: éste devuelve `str` cuando puede
    # decodificar, y un .eml en 8bit/utf-8 pasaría por message_from_string perdiendo acentos.
    with open(frappe.get_doc("File", file_name).get_full_path(), "rb") as f:
        return f.read()


def _finish(row, status: str, communication=None, reason: str = "", error: str = ""):
    row.db_set(
        {
            "status": status,
            "communication": communication.name if communication else None,
            "skip_reason": reason[:140],
            "error": error,
        },
        update_modified=True,
    )


def process_row(row, notify: bool = True) -> dict:
    """Corre el pipeline nativo de Frappe sobre un `HD Raw Email` guardado."""
    account = frappe.get_doc("Email Account", row.email_account)
    raw = _raw_bytes(row)
    try:
        mail = RawInboundMail(
            raw,
            account,
            uid=None,  # Communication.uid es Int; la identidad del origen es HD Raw Email.source_id
            seen_status=1,
            append_to=APPEND_TO,
            direction=row.direction,
        )
        if mail.mail.get("X-Auto-Generated"):
            _finish(row, "Skipped", reason="x_auto_generated")
            return {"status": "Skipped", "reason": "x_auto_generated"}
        if row.direction == "Sent" and not mail.parent_communication():
            # Un enviado sin hilo conocido abriría un ticket a nombre de nosotros mismos.
            _finish(row, "Skipped", reason="sent_sin_hilo")
            return {"status": "Skipped", "reason": "sent_sin_hilo"}

        if row.direction == "Received":
            merged = mail.is_exist_in_system()
            if merged and merged.email_account != account.name:
                _finish(row, "Skipped", merged, reason="fusionado_con_otro_buzon")
                return {
                    "status": "Duplicate",
                    "of": "Processed",
                    "communication": merged.name,
                    "reference_doctype": merged.reference_doctype,
                    "reference_name": merged.reference_name,
                    **customer_payload(merged.reference_doctype, merged.reference_name),
                }

        communication = mail.process()
        frappe.db.commit()
        is_new = bool(communication and mail.flags.get("is_new_communication"))
        if is_new and notify and row.direction == "Received":
            if account.enable_auto_reply:
                account.send_auto_reply(communication, mail)
            communication.send_email(is_inbound_mail_communcation=True)
        note = ""
        if mail.failed_attachments:
            note = "Adjuntos descartados: " + ", ".join(mail.failed_attachments)
        _finish(row, "Processed", communication, error=note)
        frappe.db.commit()
        return {
            "status": "Processed",
            "communication": communication.name,
            "reference_doctype": communication.reference_doctype,
            "reference_name": communication.reference_name,
            "is_new": is_new,
            "failed_attachments": mail.failed_attachments,
            **customer_payload(communication.reference_doctype, communication.reference_name),
        }
    except SentEmailInInboxError:
        frappe.db.rollback()
        _finish(row, "Skipped", reason="remitente_igual_al_buzon")
        frappe.db.commit()
        return {"status": "Skipped", "reason": "remitente_igual_al_buzon"}
    except Exception:
        frappe.db.rollback()
        tb = frappe.get_traceback()
        frappe.log_error(title="HD raw ingest", message=tb)
        _finish(row, "Failed", error=tb)
        frappe.db.commit()
        return {"status": "Failed", "error": tb.strip().splitlines()[-1]}


def ingest_raw(
    raw: bytes,
    mailbox: str,
    source_id: str,
    direction: str = "Received",
    notify: bool = True,
) -> dict:
    """Punto único de entrada. Idempotente por `source_id`."""
    if direction not in ("Received", "Sent"):
        frappe.throw(_("direction debe ser Received o Sent"))
    if not source_id:
        frappe.throw(_("source_id es obligatorio"))
    if not raw:
        frappe.throw(_("raw vacío"))

    existing = frappe.db.get_value(
        RAW_DOCTYPE, {"source_id": source_id}, ["name", "status", "communication"], as_dict=True
    )
    if existing and existing.status in ("Processed", "Skipped"):
        return {"status": "Duplicate", "of": existing.status, "communication": existing.communication}
    if existing:  # Pending/Failed: reintento con los mismos bytes ya guardados
        return process_row(frappe.get_doc(RAW_DOCTYPE, existing.name), notify)

    import email

    message_id = (email.message_from_bytes(raw).get("Message-ID") or "").strip("<> \r\n")[:140]
    account = get_or_create_account(mailbox)
    row = _store_raw(raw, source_id, account, direction, message_id)
    frappe.db.commit()
    return process_row(row, notify)


@frappe.whitelist(methods=["POST"])
def ingest(
    mailbox: str,
    source_id: str,
    raw_b64: str = "",
    direction: str = "Received",
    notify: int = 1,
) -> dict:
    """POST /api/method/helpdesk.overrides.raw_ingest.ingest

    `raw_b64`: el RFC822 completo en base64 o base64url (Gmail `format=raw`).
    Alternativa para adjuntos grandes: multipart con el archivo en el campo `raw`.
    Requiere rol System Manager (usar un usuario de servicio con API key).
    """
    frappe.only_for("System Manager")
    if raw_b64:
        raw = decode_raw(raw_b64)
    else:
        upload = frappe.request.files.get("raw") if frappe.request else None
        raw = upload.stream.read() if upload else b""
    result = ingest_raw(raw, mailbox, source_id, direction, bool(cint(notify)))
    # el pipeline nativo deja msgprints internos (p.ej. "ticket por asunto no encontrado"); no son para el caller
    frappe.clear_messages()
    return result


@frappe.whitelist(methods=["POST"])
def sync_mailboxes(mailboxes: list[str]) -> list[dict]:
    """POST /api/method/helpdesk.overrides.raw_ingest.sync_mailboxes

    Asegura un Email Account sólo-ingesta por cada buzón que monitorea Temporal.
    Idempotente; no borra cuentas que dejen de venir en la lista.
    """
    frappe.only_for("System Manager")
    if isinstance(mailboxes, str):
        mailboxes = frappe.parse_json(mailboxes)
    if not isinstance(mailboxes, list):
        frappe.throw(_("mailboxes debe ser una lista"))
    seen = dict.fromkeys((m or "").strip().lower() for m in mailboxes)
    accounts = [get_or_create_account(address) for address in seen]
    return [{"name": a.name, "email_id": a.email_id} for a in accounts]


@frappe.whitelist(methods=["POST"])
def reprocess(source_id: str, notify: int = 0) -> dict:
    """Re-corre el parser sobre los bytes guardados (sin tocar el buzón).

    Sólo para filas Failed/Pending, o tras borrar a mano la Communication derivada.
    """
    frappe.only_for("System Manager")
    name = frappe.db.get_value(RAW_DOCTYPE, {"source_id": source_id})
    if not name:
        frappe.throw(_("No existe {0}").format(source_id), frappe.DoesNotExistError)
    row = frappe.get_doc(RAW_DOCTYPE, name)
    if row.communication and frappe.db.exists("Communication", row.communication):
        frappe.throw(_("Ya tiene Communication {0}; borrala antes de reprocesar").format(row.communication))
    return process_row(row, bool(cint(notify)))


def ingest_eml_file(path: str, mailbox: str, source_id: str | None = None, direction: str = "Received"):
    """bench --site X execute helpdesk.overrides.raw_ingest.ingest_eml_file --kwargs "{...}" """
    import hashlib

    with open(path, "rb") as f:
        raw = f.read()
    sid = source_id or "eml-" + hashlib.sha256(raw).hexdigest()[:24]
    return ingest_raw(raw, mailbox, sid, direction, notify=False)
