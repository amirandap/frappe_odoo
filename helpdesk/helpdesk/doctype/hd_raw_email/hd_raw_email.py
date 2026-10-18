from frappe.model.document import Document


class HDRawEmail(Document):
    """Copia inmutable del correo RFC822 tal como llegó del origen.

    Es la fuente de verdad: Communication es un derivado y se puede
    regenerar (`reprocess`) cuando cambia el parser, sin volver al buzón.
    """

    pass
