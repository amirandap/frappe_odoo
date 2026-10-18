# Modelo de integración: hub (vivaldi_webai) · Frappe Helpdesk · Odoo

Estado: ingesta, fusión de buzones y `odoo_partner_id` implementados; el resto es diseño. Complementa `docs/odoo-ingest-and-picker.md` (canal de ingesta y picker).

## Rol de cada pieza

| Pieza | Rol | Es dueña de |
|---|---|---|
| `vivaldi_webai` (hub, Temporal) | Automatización | Ingesta Gmail (Pub/Sub), clasificación (auto-tag), pipelines OC / cotización / facturas, **toda escritura en Odoo** (siempre en borrador) |
| `frappe_odoo` (Helpdesk) | Humano en el circuito | Estado de trabajo humano: cola/equipo, asignación, estado, validación o corrección de la IA, resolución |
| `shared-inbox-eval` | Configuración y despliegue | Custom fields, tags, equipos, vistas, `deploy.sh`, requisitos |
| Odoo | Sistema contable/comercial | Clientes (`partner_id`) y documentos (`sale.order`, `account.move`) |

Regla de convivencia: **el hub propone, el humano dispone.** Lo que la IA decide se guarda en
campos `ai_*`; lo que un agente corrige, en campos propios y nunca se sobrescribe desde el hub.

## Flujo

```
Gmail ─Pub/Sub→ gmail_history_sync → email_ingest (1×/correo)
   ① frappe_raw_ingest  ──POST raw──────────────→ Frappe: HD Raw Email → Communication → HD Ticket
        (ANTES de clasificar: todo correo existe en Frappe aunque la IA falle)
   ② router / pipelines clasifican y actúan (OC → sale.order borrador, cotización, factura, forward)
   ③ frappe_sync_outcome ──POST resultado───────→ Frappe: tag, cola, estado, custom_odoo_*, actividad
   ④ el agente valida / recategoriza en Frappe
        Frappe ──webhook firmado (cambio de tag/cola/estado)──→ hub: email_tag_log (corrección humana)
        y, si el nuevo tag dispara un pipeline, el hub lo arranca (workflowId por Message-ID = idempotente)
   ⑤ el agente responde desde Frappe; el correo Sent vuelve por Pub/Sub → ingest direction=Sent (dedupe por Message-ID)
```

El hub ya tiene el hueco para ①: `email_ingest` trae un "push a Chatwoot" escrito y desactivado.
Se reemplaza por el push a Frappe.

## Claves de identidad

| Entidad | Clave | Dónde vive el enlace |
|---|---|---|
| Correo ↔ ticket | `gmailMessageId` = `HD Raw Email.source_id` (y `Message-ID` RFC822) | tabla `frappe_ticket_links` en el hub |
| Cliente | `HD Customer.odoo_partner_id` ↔ `partner_id` | campo en Frappe; `ingest` lo devuelve al hub |
| Documento | `custom_odoo_order_id` + `custom_odoo_order_*` | campos del ticket |

## Contratos (a construir)

- **Hub → Frappe** `helpdesk.api.hub.apply_outcome`: `{message_id, tags[], confidence, outcome
  (processed|skipped|failed|needs_review), odoo_partner_id, odoo_order{id,name,url,state,amount,date},
  events[]}`. Frappe aplica tag y cola, escribe `HD Ticket Activity` ("IA: clasificó como X",
  "Odoo S13142 — creado") y los `custom_odoo_*`. Reemplaza los comentarios `[Odoo chatter — …]`.
- **Frappe → hub** `POST /api/frappe/feedback` (HMAC): `{message_id, field, old, new, user}`.
  Se registra como etiqueta humana para el aprendizaje semanal que el hub ya tiene.
- **Frappe → hub (picker)** `GET /api/odoo/documents?partner_id=&q=`: el hub es el **único
  gateway a Odoo** (ya tiene cliente, credenciales y contexto de compañía). Frappe no guarda
  credenciales de Odoo.
- Odoo → hub → Frappe: los webhooks de Odoo que el hub ya recibe (`odoo_webhook_events`)
  actualizan `custom_odoo_order_state` y el timeline, en vez de un JSON estático.

## Que nada se quede sin terminar

1. Todo correo entra a Frappe antes de clasificarse. Sin tag o con `outcome=failed|needs_review`
   → equipo **Triage** y estado "Por revisar".
2. Vistas compartidas: "Sin triar", "IA falló", "Sin respuesta > N h", por tag Funnel.
3. Conciliación diaria (Temporal Schedule, junto a los detectores del hub): Gmail del día
   vs `HD Raw Email` → alerta de correos que no llegaron; tickets abiertos sin primera respuesta
   → Slack.
4. Un ticket con `outcome=needs_review` no se cierra sin que un agente confirme o corrija.

## Fases

1. `frappe_raw_ingest` en el hub (Frappe: `odoo_partner_id` y resolución por dominio ya listos).
2. `apply_outcome` + equipos/tags/vistas + patch de los chatter históricos (#0348).
3. Feedback Frappe → hub (aprendizaje) y re-disparo de pipelines.
4. Picker (gateway del hub) y enlace manual.
5. Conciliación y alertas.

## Decisiones tomadas

1. **Salida de respuestas:** por el `gmail-client` del hub; Frappe no usa SMTP. Un solo canal
   evita mensajes duplicados al cliente.
2. **Sin umbrales en Frappe:** lo que decide Temporal (tag, cola, confianza) es la verdad;
   Frappe sólo aplica y muestra. Triage se usa por `outcome`, no por un umbral propio.
3. **Un correo en dos buzones = un ticket:** Received se deduplica por Message-ID entre todos
   los buzones sólo-ingesta; el segundo buzón queda como `HD Raw Email` `Skipped`
   (`fusionado_con_otro_buzon`).
4. **Un Email Account sólo-ingesta por buzón** monitoreado (`sync_mailboxes`); cada correo
   cuelga de su Email Account.
