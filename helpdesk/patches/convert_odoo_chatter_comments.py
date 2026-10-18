import frappe

from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import (
    log_odoo_chatter,
    parse_odoo_chatter,
)


def execute():
    comments = frappe.get_all(
        "HD Ticket Comment",
        filters={"content": ["like", "%Odoo chatter%"]},
        fields=["name", "content", "reference_ticket", "owner"],
    )
    for comment in comments:
        chatter = parse_odoo_chatter(comment.content)
        if not chatter:
            continue
        log_odoo_chatter(
            comment.reference_ticket,
            chatter["ref"],
            chatter["body"],
            chatter["author"],
            chatter["when"],
            owner=comment.owner,
        )
        frappe.delete_doc("HD Ticket Comment", comment.name, force=True)
