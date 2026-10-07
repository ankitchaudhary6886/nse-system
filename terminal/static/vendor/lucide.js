/*!
 * lucide icons (`icon(name, attrs)`) — 1.52.0 — ISC
 * https://lucide.dev | vendored icon BODIES generated from
 * node_modules/lucide-static/icons/*.svg by the project's npm tooling.
 *
 * Bundles 15 curated icons as inline SVG strings so the terminal
 * needs no icon font, no sprite request and no CDN:
 *   search, refresh-cw, menu, x, chevron-down, info, line-chart, activity, alert-triangle, trending-up, trending-down, layers, sliders-horizontal, external-link, check
 *
 * Every emitted SVG is 24x24 by default with fill="none", stroke="currentColor",
 * stroke-width="2", stroke-linecap="round", stroke-linejoin="round" and
 * aria-hidden="true" (unless a `title`/`aria-label` is supplied, in which case
 * it becomes role="img" + aria-label for screen readers).
 *
 * Usage:  import { icon } from './vendor/lucide.js';
 *         icon('search');                                  // 24x24
 *         icon('search', { size: 16, class: 'shrink-0' }); // 16x16 + extra class
 *         icon('x', { title: 'Close' });                   // labelled
 * Unknown names return '' so callers can safely interpolate into innerHTML.
 */

/** name -> inner SVG markup (paths/shapes only; the <svg> wrapper is built per call). */
const ICONS = {
  "search": "<path d=\"m21 21-4.34-4.34\" /><circle cx=\"11\" cy=\"11\" r=\"8\" />",
  "refresh-cw": "<path d=\"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8\" /><path d=\"M21 3v5h-5\" /><path d=\"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16\" /><path d=\"M8 16H3v5\" />",
  "menu": "<path d=\"M4 5h16\" /><path d=\"M4 12h16\" /><path d=\"M4 19h16\" />",
  "x": "<path d=\"M18 6 6 18\" /><path d=\"m6 6 12 12\" />",
  "chevron-down": "<path d=\"m6 9 6 6 6-6\" />",
  "info": "<circle cx=\"12\" cy=\"12\" r=\"10\" /><path d=\"M12 16v-4\" /><path d=\"M12 8h.01\" />",
  "line-chart": "<path d=\"M3 3v16a2 2 0 0 0 2 2h16\" /><path d=\"m19 9-5 5-4-4-3 3\" />",
  "activity": "<path d=\"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2\" />",
  "alert-triangle": "<path d=\"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3\" /><path d=\"M12 9v4\" /><path d=\"M12 17h.01\" />",
  "trending-up": "<path d=\"M16 7h6v6\" /><path d=\"m22 7-8.5 8.5-5-5L2 17\" />",
  "trending-down": "<path d=\"M16 17h6v-6\" /><path d=\"m22 17-8.5-8.5-5 5L2 7\" />",
  "layers": "<path d=\"M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z\" /><path d=\"M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12\" /><path d=\"M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17\" />",
  "sliders-horizontal": "<path d=\"M10 5H3\" /><path d=\"M12 19H3\" /><path d=\"M14 3v4\" /><path d=\"M16 17v4\" /><path d=\"M21 12h-9\" /><path d=\"M21 19h-5\" /><path d=\"M21 5h-7\" /><path d=\"M8 10v4\" /><path d=\"M8 12H3\" />",
  "external-link": "<path d=\"M15 3h6v6\" /><path d=\"M10 14 21 3\" /><path d=\"M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6\" />",
  "check": "<path d=\"M20 6 9 17l-5-5\" />",
};

/** Curated icon names, in the order declared above. */
export const iconNames = Object.freeze(Object.keys(ICONS));

const ATTR_NAME = /^[a-zA-Z][a-zA-Z0-9_:.-]*$/;

/** Escape a value for use inside a double-quoted HTML attribute. */
function esc(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Render a curated lucide icon as an inline SVG string.
 * @param {string} name  one of `iconNames`
 * @param {object} [attrs] optional overrides: size, class, strokeWidth, fill,
 *   stroke, title, plus any extra HTML / data-* / aria-* attributes.
 * @returns {string} SVG markup, or '' when `name` is not curated.
 */
export function icon(name, attrs) {
  const key = String(name == null ? '' : name).trim().toLowerCase();
  const inner = Object.prototype.hasOwnProperty.call(ICONS, key) ? ICONS[key] : null;
  if (inner === null) return '';

  const o = attrs && typeof attrs === 'object' ? attrs : {};
  const size = o.size === undefined || o.size === null ? 24 : o.size;
  const strokeWidth = o.strokeWidth === undefined || o.strokeWidth === null ? 2 : o.strokeWidth;
  const fill = o.fill === undefined || o.fill === null ? 'none' : o.fill;
  const stroke = o.stroke === undefined || o.stroke === null ? 'currentColor' : o.stroke;
  const label = o.title === undefined || o.title === null ? o['aria-label'] : o.title;

  let cls = 'lucide lucide-' + key;
  if (typeof o.class === 'string' && o.class.trim() !== '' && o.class.trim() !== cls) {
    cls += ' ' + o.class.trim();
  }

  const parts = [
    'class="' + esc(cls) + '"',
    'xmlns="http://www.w3.org/2000/svg"',
    'width="' + esc(size) + '"',
    'height="' + esc(size) + '"',
    'viewBox="0 0 24 24"',
    'fill="' + esc(fill) + '"',
    'stroke="' + esc(stroke) + '"',
    'stroke-width="' + esc(strokeWidth) + '"',
    'stroke-linecap="round"',
    'stroke-linejoin="round"',
  ];

  if (label === undefined || label === null || label === '') {
    parts.push('aria-hidden="true"');
  } else {
    parts.push('role="img"');
    parts.push('aria-label="' + esc(label) + '"');
  }

  const handled = new Set(['size', 'class', 'strokeWidth', 'fill', 'stroke', 'title', 'aria-label']);
  for (const k of Object.keys(o)) {
    if (handled.has(k)) continue;
    if (!ATTR_NAME.test(k)) continue;
    const v = o[k];
    if (v === undefined || v === null || v === false) continue;
    if (v === true) { parts.push(k); continue; }
    parts.push(k + '="' + esc(v) + '"');
  }

  const titleTag = label === undefined || label === null || label === '' ? '' : '<title>' + esc(label) + '</title>';
  return '<svg ' + parts.join(' ') + '>' + titleTag + inner + '</svg>';
}

export default icon;
