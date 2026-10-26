import { Link } from 'react-router-dom'

/**
 * LinkButton — paper & ink call to action.
 * Uppercase micro text with an arrow; solid inverts (ink bg / paper text)
 * on hover, otherwise underlines.
 */
export default function LinkButton({
  to = '#',
  children,
  solid = false,
  className = '',
  ...rest
}) {
  return (
    <Link
      to={to}
      className={`${solid ? 'link-button link-button-solid' : 'link-button'} ${className}`}
      {...rest}
    >
      <span>{children}</span>
      <span aria-hidden="true" className="link-button-arrow">→</span>
    </Link>
  )
}
