# Implementation Plan

## 0. Current Analysis

### Figma access check

- Status: blocked.
- Requested file: `https://www.figma.com/make/LJEL5myKt3XrAROPdxKgK8/Интернет-магазин-упаковочных-материалов?t=Mz7qTzX0xM5wQpMg-1`
- Available MCP/tooling check:
  - Tool discovery still does not expose a callable Figma MCP tool in this running Codex session.
  - MCP resources list contains `codex_apps` resources for templates and Sites only.
  - Global Codex config contains an enabled `mcp_servers.figma` section and an authorization header.
  - Fixed global Codex config: removed disabled Figma plugin entry.
  - Fixed global Codex config: changed MCP URL from `URL: https://mcp.figma.com/mcp` to `https://mcp.figma.com/mcp`.
  - Fixed global Codex config: changed header from `Authorization` to `X-Figma-Token`, as required by the Figma MCP endpoint for `figd_` tokens.
  - Low-level MCP initialize request to `https://mcp.figma.com/mcp` still returns HTTP 401 `Unauthorized`.
  - Tool discovery after config changes still returns no callable Figma tools in this running session.
  - No callable tool is available in this session for reading Figma pages, layers, components, prototype transitions, images, SVGs, or design tokens.
- Direct Figma REST API check:
  - The token was used without printing it.
  - Request to `https://api.figma.com/v1/files/LJEL5myKt3XrAROPdxKgK8?depth=1` returned HTTP 400.
  - Response: `File type not supported by this endpoint`.
  - This suggests the provided `/make/` link is not readable as a normal Figma design file through the standard Files API.
- Data available from Figma right now:
  - The URL only.
  - No pages, frames, layers, components, assets, measurements, colors, fonts, images, states, or prototype links are available through MCP in this session.
- Required to continue exact visual transfer:
  - Verify the Figma token has access to the file and is accepted by the Figma MCP endpoint, then restart/reload Codex so callable Figma tools are exposed in-session, or
  - Provide a regular Figma design file link that the Files API/MCP can read, or
  - Provide a Figma file export with frames/assets/design tokens, or
  - Provide screenshots for every desktop/tablet/mobile screen plus exported images/SVGs and prototype notes.

### Project analysis

- Workspace: `/mnt/c/Users/alepi/OneDrive/Рабочий стол/Вова`
- Current files: no application files were found in the workspace root.
- Existing directories: `.git`, `.agents`, `.codex`.
- No existing `frontend`, `package.json`, `src`, Vite config, React app, or AGENTS.md was found in the visible project tree.
- No existing user files need removal or migration at this stage.

## 1. Implementation Rules

- Do not invent or approximate the Figma visual design while the Figma file is unavailable.
- Do not treat prototype links as real business logic.
- Separate documented Figma behavior from code-only application behavior.
- Preserve all existing files unless a change is strictly necessary.
- Keep implementation in `frontend/`.
- Use React, TypeScript, Vite, and React Router.
- Use React Context plus `localStorage` for cart persistence in the first version.
- Store catalog data outside UI components.
- Keep pages, reusable components, services, hooks, context, types, assets, and styles in separate folders.

## 2. Figma Extraction Checklist

Status: blocked until Figma MCP, a readable regular Figma file, or equivalent export is available.

- [ ] Confirm MCP can open the Figma file.
- [ ] List all pages in the file.
- [ ] List all top-level frames/screens per page.
- [ ] Identify desktop, tablet, and mobile variants.
- [ ] Identify reusable components and variants.
- [ ] Identify hover, pressed, focused, disabled, loading, empty, and error states.
- [ ] Identify modals, menus, dropdowns, forms, and validation states.
- [ ] Identify prototype transitions and distinguish them from business logic.
- [ ] Extract colors, typography, spacing, radii, borders, shadows, and grid rules.
- [ ] Export images and SVG icons into `frontend/src/assets/`.
- [ ] Document all Figma-derived behavior separately from code-only behavior.

## 3. Frontend Scaffold

Status: pending. This can begin only after either Figma assets are available or the user explicitly approves a non-final scaffold without visual implementation.

- [ ] Create `frontend/package.json`.
- [ ] Add Vite, React, TypeScript, React Router dependencies.
- [ ] Add `frontend/index.html`.
- [ ] Add `frontend/vite.config.ts`.
- [ ] Add `frontend/tsconfig.json` and `frontend/tsconfig.node.json`.
- [ ] Create `frontend/src/main.tsx`.
- [ ] Create `frontend/src/App.tsx`.
- [ ] Create the requested folder structure.

## 4. Design System

Status: blocked by unavailable Figma data.

- [ ] Create `frontend/src/styles/tokens.css`.
- [ ] Create `frontend/src/styles/global.css`.
- [ ] Map Figma colors to CSS variables.
- [ ] Map Figma typography to CSS variables.
- [ ] Map spacing, radii, shadows, borders, and breakpoints.
- [ ] Add focus, hover, active, disabled, loading, and error styling rules.

## 5. Data And Services

Status: pending.

- [ ] Create product TypeScript types with `id`, `name`, `category`, `subcategory`, `description`, `price`, `oldPrice`, `images`, `specifications`, `availability`, `sku`, `minQuantity`, and `unit`.
- [ ] Create category and order types.
- [ ] Create catalog test data only if real Figma/API data is absent.
- [ ] Create catalog service for search, filtering, sorting, category lookup, and product lookup.
- [ ] Create order service stub for checkout submission.

## 6. Shared Components

Status: pending.

- [ ] Implement layout shell.
- [ ] Implement header and navigation from Figma.
- [ ] Implement menu behavior from Figma.
- [ ] Implement search input and suggestions.
- [ ] Implement buttons, links, inputs, selects, checkboxes, counters, badges, loaders, alerts, empty states, modals, and dropdowns.
- [ ] Implement responsive behavior for desktop, tablet, and mobile.

## 7. Pages

Status: pending.

- [ ] Home page.
- [ ] Catalog page.
- [ ] Category page.
- [ ] Subcategory page.
- [ ] Product detail page.
- [ ] Search results page.
- [ ] Cart page.
- [ ] Checkout page.
- [ ] Success/confirmation page.
- [ ] Not found page.

## 8. Application Logic

Status: pending.

- [ ] Add routing with React Router.
- [ ] Add real catalog search.
- [ ] Add filters and sorting.
- [ ] Add cart context.
- [ ] Persist cart state in `localStorage`.
- [ ] Add quantity changes with minimum quantity constraints.
- [ ] Add cart item removal.
- [ ] Add checkout form state and validation.
- [ ] Add submission loading and error states.
- [ ] Add empty states for search, catalog, cart, and checkout.

## 9. Validation

Status: pending.

- [ ] Run dependency install.
- [ ] Run TypeScript build.
- [ ] Run Vite dev server.
- [ ] Check all routes.
- [ ] Check browser console.
- [ ] Check desktop layout.
- [ ] Check tablet layout.
- [ ] Check mobile layout.
- [ ] Compare implementation against Figma.
- [ ] Fix visual differences after comparison.

## 10. Current Decision

Implementation of the visual interface is paused because the Figma MCP is not available in this session. Starting visual work now would require inventing the design, which conflicts with the requirement to transfer the Figma layout exactly.
