/**
 * MicroLabel — small uppercase, letter-spaced label used for
 * eyebrows, section headings, and meta text. `as` picks the tag
 * (default `span`).
 *
 * Rendered via createElement (not a `<Tag>` JSX tag) so that
 * no-unused-vars sees the dynamic tag as used.
 */
import { createElement } from 'react'

export default function MicroLabel({ as = 'span', className = '', children, ...rest }) {
  return createElement(as, { className: `micro-label ${className}`, ...rest }, children)
}
