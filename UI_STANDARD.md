# Doner Club Analytics — UI standard

This file records the default visual sizing for new management pages in the Analytics project.

## Desktop (>= 1100px)

- Main content width: `max-width: 1880px`
- Page horizontal padding: `46px`
- Base body font: `17px`
- Sticky top bar height: `98px`
- Logo size: `58px`
- Main H1: `clamp(66px, 5.2vw, 94px)`
- Hero description: `17px`
- Section H2: `27px`
- KPI card minimum height: `190px`
- KPI card / panel padding: `26px`
- KPI label: `14px`
- KPI value: `41px`
- KPI supporting text: `12.5px`
- Panel H3: `21px`
- Form controls / buttons: `60px` high
- Control text: `15–16px`
- Table headers: `12px`
- Table body: `14px`

## Behaviour standard for new Analytics pages

- Sizing must be present in the initial CSS. Do not enlarge the page later with JavaScript; this prevents the visible “small -> large” jump on refresh.
- Data must not auto-load on page entry unless the page specifically requires live data.
- For manually loaded reports, use a primary “Показать” / “Проверить iiko” action.
- Long loads should display an inline 0–100% progress block on the page, not a blocking full-screen modal.
- Date/month controls should use the Analytics dark design and the entire input area must be clickable to open the native picker.
- Desktop and mobile layouts must be responsive.
- Do not surface technical/internal fields as management KPIs unless they have a clear business meaning.
- If source data is partial, historical, stale, or ambiguous, label that state explicitly instead of presenting it as current fact.

The current large desktop reference implementation is `static/staff.html`.
