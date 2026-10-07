/*!
 * tailwind-merge v3.7.0 — MIT — https://github.com/dcastil/tailwind-merge
 * ESM re-export shim. The implementation is vendored verbatim at
 * ./lib/tailwind-merge.mjs (copied from node_modules/tailwind-merge/dist/bundle-mjs.mjs)
 * so the browser needs no bundler and no bare module specifier.
 */
export {
  createTailwindMerge,
  extendTailwindMerge,
  fromTheme,
  getDefaultConfig,
  mergeConfigs,
  twJoin,
  twMerge,
  validators,
} from './lib/tailwind-merge.mjs';
export { twMerge as default } from './lib/tailwind-merge.mjs';
