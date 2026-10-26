/**
 * DotText — renders text in the dot-matrix display font.
 * Map names, scores and big numerals use this typeface.
 * `as` picks the tag (default `span`); `keepCase` preserves casing
 * (e.g. `de_dust2`) — by default the text lowercases.
 *
 * Rendered via createElement (not a `<Tag>` JSX tag) so that
 * no-unused-vars sees the dynamic tag as used.
 */
import { createElement } from 'react'

export default function DotText({ as = 'span', className = '', keepCase = false, children, ...rest }) {
  return createElement(
    as,
    { className: `${keepCase ? 'font-dot' : 'dot-text'} ${className}`, ...rest },
    children
  )
}
