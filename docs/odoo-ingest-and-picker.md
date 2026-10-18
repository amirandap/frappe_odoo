# Ingesta de correo desde Temporal + enlaces con Odoo

Estado: ingesta, fusión entre buzones, `sync_mailboxes`, `HD Customer.odoo_partner_id` y chatter
están implementados; el picker y `meta` del ticket siguen pendientes.

## Objetivo

1. `vivaldi_webai` (Temporal, Gmail API + Pub/Sub) entrega cada correo a Helpdesk por el
   canal de ingesta crudo de este repo, sin segundo camino IMAP, sin duplicados.
2. El ticket queda enlazado al cliente de Odoo (`partner_id`) y, cuando se conoce, a su
   orden (`sale.order`).
3. En la UI, un picker de documentos de Odoo permite enlazar o citar documentos a mano.

## 1. Canal de ingesta (ya existe)

`helpdesk/overrides/raw_ingest.py` — `POST /api/method/helpdesk.overrides.raw_ingest.ingest`

| campo | valor |
|---|---|
| `mailbox` | buzón (`ventas@…`); crea un Email Account sólo-ingesta si no existe |
| `source_id` | id de mensaje de Gmail (idempotencia) |
| `raw_b64` | RFC822 en base64/base64url (Gmail `format=raw`) |
| `direction` | `Received` o `Sent` (carpeta Sent, sólo si hay hilo) |

Auth: usuario de servicio con rol System Manager y API key.

### Buzones = Email Accounts sólo-ingesta

Cada buzón que monitorea Temporal existe en Frappe como Email Account sin IMAP ni SMTP
(`enable_incoming=0`, `use_imap=0`, `enable_outgoing=0`) y cada correo cuelga de él.
`ingest` lo crea al vuelo; para aprovisionarlos de antemano:

`POST /api/method/helpdesk.overrides.raw_ingest.sync_mailboxes` `{"mailboxes": ["a@x", "b@x"]}`
(System Manager) -> `[{name, email_id}]`. Idempotente; no borra cuentas ausentes de la lista.

### Sin duplicados ni tickets repetidos

- `HD Raw Email.source_id`: reintentos del mismo mensaje del origen.
- **Received**: `Message-ID` entre *todas* las cuentas sólo-ingesta. El mismo correo en dos
  buzones es un solo ticket/Communication; el segundo `ingest` responde
  `{status: "Duplicate", of: "Processed", communication, reference_*}` y su fila
  `HD Raw Email` queda `Skipped` con `skip_reason = fusionado_con_otro_buzon`.
- **Sent**: `Message-ID` + Email Account (un enviado desde Helpdesk que vuelve por Sent se
  deduplica).

### Resultado

Se mantienen las claves anteriores (`status`, `communication`, `reference_*`, `is_new`,
`failed_attachments`) y se añaden, cuando el ticket tiene cliente, `customer` (HD Customer) y
`odoo_partner_id` (sólo si está definido), también en respuestas `Duplicate` por fusión.

### Reglas de diseño

- Frappe **no aplica umbrales** de confianza: la clasificación y la cola que decide Temporal
  son la verdad.
- Las respuestas salen por el `gmail-client` del hub; Frappe no usa SMTP.

## 2. Lado `vivaldi_webai` (Temporal)

Nueva activity `frappe_raw_ingest` encadenada en `gmail_history_sync`, después de
`messages.get(format=raw)`. Reintenta sola (la ingesta es idempotente). No reemplaza el
pipeline de OC; sólo duplica el correo hacia Helpdesk.

Parámetro adicional propuesto (pendiente en `ingest`): `meta` JSON opcional
`{odoo_order_id, odoo_order_name, odoo_order_url}` aplicado al ticket tras procesar.

## 3. Enlaces con Odoo en Frappe (parcialmente pendiente)

Ya existen en el site (exportados en `shared-inbox-eval/frappe-config/custom_fields.json`,
no en este repo): `HD Ticket.custom_odoo_order_name`, `_order_url` (LinkPair),
`_order_state`, `_order_date`, `_order_amount` y `_timeline_json`. **Se reutilizan**; no se
crean campos paralelos.

Implementado: `HD Customer.odoo_partner_id` (Int, "Odoo Partner ID"). La unicidad se valida en
el controlador (`validate_odoo_partner_id`) y no con `unique: 1`, porque una columna Int vale 0
y no NULL: todos los clientes sin id colisionarían. La resolución al ingresar es dominio del
remitente -> `HD Customer.domain` (`_set_customer_by_domain`) -> `odoo_partner_id`, que se
devuelve al hub en el resultado de `ingest`.

Pendiente:
- Un `custom_odoo_order_id` (Int) en `HD Ticket` para el picker (hoy el id sólo va dentro
  de la URL).
- **Chatter de Odoo como mensaje de sistema, no comentario ni Communication** (implementado):
  - `POST /api/method/helpdesk.api.odoo.log_chatter` `{ticket, ref, body, author, when}`
    (System Manager) crea una `HD Ticket Activity` "Odoo {ref} — {body} (por {author})" con la
    fecha de Odoo. Idempotente por (ticket, texto, fecha): el sync puede reintentar.
  - `HDTicketComment.after_insert`: si llega un comentario `[Odoo chatter — …]`, lo convierte
    y lo borra (red de seguridad para quien aún escriba comentarios).
  - Patch `convert_odoo_chatter_comments` convierte los comentarios históricos (6 del #0348)
    al correr `bench migrate`.

## 4. Picker de documentos de Odoo (pendiente)

Backend: `helpdesk.api.odoo.search_documents(ticket, query="", doctypes=...)` (nuevo).
Consulta Odoo por XML-RPC (`sale.order`, `account.move`) filtrado por
`odoo_partner_id` del cliente del ticket, últimos N, más búsqueda por texto.
Credenciales en `site_config` (no en el repo). Referencia del cliente:
`cos-mcp-public/src/cos_mcp_public/odoo_client.py`.

Frontend:
- Reply box: botón "Documentos de Odoo" con lista rápida de los últimos documentos del
  cliente; al elegir uno se inserta su referencia en el mensaje.
- Sidebar del ticket: "Enlazar orden de Odoo" para el caso manual; escribe
  los `custom_odoo_order_*`.
