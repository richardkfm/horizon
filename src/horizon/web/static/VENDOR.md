# Vendored frontend libraries

horizon serves its JS locally so the UI works fully offline. Download these
once during setup and place the minified files in this directory:

- `htmx.min.js`  — https://unpkg.com/htmx.org/dist/htmx.min.js
- `alpine.min.js` — https://unpkg.com/alpinejs/dist/cdn.min.js

The placeholder `.js` files in this directory are empty stubs so the scaffold
runs without 404s; replace them with the real libraries before building the UI.
A small fetch step will be added to the Dockerfile / setup in the Web UI step.
