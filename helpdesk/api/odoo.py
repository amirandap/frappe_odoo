import frappe
from frappe import _

from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import (
    log_odoo_chatter,
)


@frappe.whitelist(methods=["POST"])
def log_chatter(ticket: str, ref: str, body: str, author: str, when: str) -> dict:
    """POST /api/method/helpdesk.api.odoo.log_chatter

    Entry point for the Odoo sync: an Odoo chatter note lands in the ticket timeline as a
    system entry, never as a comment or a Communication. Idempotent.
    Requires System Manager (service user with API key).
    """
    frappe.only_for("System Manager")
    if not frappe.db.exists("HD Ticket", ticket):
        frappe.throw(_("Ticket {0} not found").format(ticket), frappe.DoesNotExistError)
    activity = log_odoo_chatter(ticket, ref, body, author, when)
    return {"activity": activity.name}
