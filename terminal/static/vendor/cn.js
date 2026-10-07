/*!
 * cn() — className composer used across the terminal UI.
 *
 * Combines clsx (conditional class joining) with tailwind-merge (later
 * conflicting Tailwind utilities win). Both dependencies are vendored locally as
 * real packages under ./lib/ — see ./clsx.js and ./tailwind-merge.js.
 *
 * Usage:  import { cn } from './vendor/cn.js';
 *         cn('px-2 py-1', isActive && 'bg-sky-500', 'px-4')  // => 'py-1 bg-sky-500 px-4'
 */
import { clsx } from './clsx.js';
import { twMerge } from './tailwind-merge.js';

export const cn = (...i) => twMerge(clsx(i));
