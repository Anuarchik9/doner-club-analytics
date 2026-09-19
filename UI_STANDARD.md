# Doner Club Analytics — canonical UI standard

The canonical visual reference for every main Analytics page is:

`static/staff.html` — «Сотрудники и табелирование».

All pages in the burger menu must use the same visual scale. Page-specific layouts may differ, but typography, content width, control sizing and card/panel scale must follow this standard.

## Desktop — canonical Staff scale (>= 1100px)

- Main content width: `max-width: 1880px`
- Horizontal page padding: `46px`
- Bottom page padding: `84px`
- Base body font: `17px`
- Sticky top bar height: `98px`
- Logo: `58 × 58px`
- Brand title: `18px`
- Brand subtitle: `13px`
- Status/source pill: `13px`

### Hero

- Hero top/bottom padding: `56px / 34px`
- Eyebrow: `13px`
- Main H1: `clamp(66px, 5.2vw, 94px)`
- Hero description: `17px`
- Hero description max width: about `1220px`

### Filters and controls

- Filter block padding: `22px`
- Gap between controls: `16px`
- Field label: `12px`
- Date/select/input height: `60px`
- Input text: `16px`
- Primary button height: `60px`
- Primary button text: `15px`
- Quick-period pills: `13px`, padding `9px 15px`

### Sections, cards and panels

- Section spacing: `40px 0 16px`
- Section H2: `27px`
- Section secondary text: `14px`
- Card/panel gap: `17px`
- KPI card minimum height: `190px`
- KPI card padding: `26px`
- KPI label: `14px`
- KPI main value: `41px`
- KPI supporting text: `12.5px`
- Panel padding: `26px`
- Panel H3: `21px`

### Tables and detail UI

- Table header: `12px`
- Table body: `14px`
- Table cell vertical padding: `16–17px`
- Search field: `48px` high, `14px` text
- Secondary action buttons: about `13px`
- Modal max width: up to `1450px`
- Modal padding: `34px`
- Modal title: `42px`
- Modal KPI/value text: about `22px`

## Behaviour standard

- The large desktop sizing must exist in the initial CSS/HTML. Never enlarge the page after load with JavaScript. This prevents the visible “small -> large” jump on refresh.
- Main reporting pages should not load heavy iiko data automatically on entry unless the page explicitly requires live data.
- Use a primary `Показать` / `Проверить iiko` action for manual reports.
- Long requests use an inline `0–100%` progress block inside the page, never a blocking full-screen loading modal.
- Date/month inputs use the Analytics dark style; clicking anywhere inside the full field should open the picker.
- Desktop and mobile layouts remain responsive; the desktop scale above is the visual reference, not a forced mobile size.
- Do not expose technical/internal API fields as management KPIs unless they have a clear business meaning.
- Partial, archived, stale or ambiguous source data must be labelled explicitly rather than shown as current fact.

## Pages covered by this standard

- `static/dashboard-v2.html` — Продажи и аналитика
- `static/revisions.html` — Ревизии
- `static/procurement.html` — Закупки
- `static/staff.html` — Персонал и табелирование

When creating a new burger-menu page, start from the `staff.html` scale above rather than the older compact `1420px / 14px` layout.
