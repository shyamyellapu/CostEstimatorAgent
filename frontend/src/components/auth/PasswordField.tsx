import { forwardRef, useId, useState } from 'react'
import type { InputHTMLAttributes } from 'react'
import { Eye, EyeOff } from 'lucide-react'

interface PasswordFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
}

/** Password input with a show/hide toggle, styled with the existing form-input classes. */
const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(function PasswordField(
  { label, id, ...rest },
  ref
) {
  const [visible, setVisible] = useState(false)
  const generatedId = useId()
  const inputId = id ?? generatedId

  return (
    <div className="form-group">
      <label className="form-label" htmlFor={inputId}>{label}</label>
      <div className="password-field-wrap">
        <input
          {...rest}
          ref={ref}
          id={inputId}
          type={visible ? 'text' : 'password'}
          className="form-input"
          style={{ paddingRight: '2.25rem' }}
        />
        <button
          type="button"
          className="password-toggle-btn"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          tabIndex={-1}
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  )
})

export default PasswordField
