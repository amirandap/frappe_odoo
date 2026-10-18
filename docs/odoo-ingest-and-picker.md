# Ingesta de correo desde Temporal + enlaces con Odoo

Estado: **diseño** (nada de esto, salvo `raw_ingest`, está implementado).

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

Sin duplicados por dos capas: `HD Raw Email.source_id` y `Message-ID` + Email Account
(`is_exist_in_system`). Un correo enviado desde Helpdesk que vuelve por Sent se
deduplica por Message-ID.

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

Pendiente:
- `HD Customer.odoo_partner_id` (Int, único), creado por patch de este repo (hoy no existe).
- Un `custom_odoo_order_id` (Int) en `HD Ticket` para el picker (hoy el id sólo va dentro
  de la URL).
- Resolución del cliente al ingresar: dominio del remitente → `HD Customer.domain` (ya
  existe, `_set_customer_by_domain`) → `odoo_partner_id`.
- Comentarios históricos `[Odoo chatter — …]` (6 notas del #0348, migradas como
  `HD Ticket Comment`): el hook de `HDTicketComment` sólo convierte los nuevos; los
  existentes necesitan un patch único (no ejecutado).

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
