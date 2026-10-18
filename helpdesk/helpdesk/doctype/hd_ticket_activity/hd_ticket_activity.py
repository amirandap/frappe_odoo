# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document
from frappe.utils import strip_html


class HDTicketActivity(Document):
    pass


def log_ticket_activity(ticket, action):
    return frappe.get_doc(
        {"doctype": "HD Ticket Activity", "ticket": ticket, "action": action}
    ).insert(ignore_permissions=True)


# "[Odoo chatter — sale.order S13142, 2026-09-28 21:03:16, por Desarrollos Odoo] <body>"
ODOO_CHATTER = re.compile(
    r"^\s*\[Odoo chatter\s*[—-]\s*(?P<model>[\w.]+)\s+(?P<ref>[^,\]]+),"
    r"\s*(?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\s*por\s+(?P<author>[^\]]+)\]"
    r"\s*(?P<body>.*)$",
    re.DOTALL,
)


def parse_odoo_chatter(content: str) -> dict | None:
    """Split a legacy "[Odoo chatter — …]" comment into its parts, or None if it isn't one."""
    match = ODOO_CHATTER.match(strip_html(content or "").strip())
    if not match:
        return None
    return {key: value.strip() for key, value in match.groupdict().items()}


def log_odoo_chatter(
    ticket: str, ref: str, body: str, author: str, when: str, owner: str | None = None
):
    """Record an Odoo chatter note as a system entry of the ticket timeline.

    Idempotent: the same (ticket, text, Odoo timestamp) is never logged twice, so the
    sync can be retried safely.
    """
    action = f"Odoo {ref} — {body} (por {author})"
    existing = frappe.db.exists(
        "HD Ticket Activity", {"ticket": ticket, "action": action, "creation": when}
    )
    if existing:
        return frappe.get_doc("HD Ticket Activity", existing)

    activity = log_ticket_activity(ticket, action)
    # Keep Odoo's own timestamp so the entry sorts where the event happened.
    values = {"creation": when}
    if owner:
        values["owner"] = owner
    frappe.db.set_value(
        "HD Ticket Activity", activity.name, values, update_modified=False
    )
    return activity
