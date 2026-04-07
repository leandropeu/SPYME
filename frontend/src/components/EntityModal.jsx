import { useEffect, useState } from 'react'

import Modal from './Modal'

export default function EntityModal({
  open,
  title,
  fields,
  initialValues,
  onClose,
  onSubmit,
}) {
  const [form, setForm] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const formSeedKey = initialValues?.id != null ? `edit:${initialValues.id}` : `new:${title}`

  useEffect(() => {
    if (!open) {
      setSubmitting(false)
      setSubmitError('')
      return
    }

    setForm(initialValues || {})
    setSubmitError('')
  }, [open, formSeedKey])

  const handleChange = (name, value) => {
    setForm((current) => ({ ...current, [name]: value }))
  }

  return (
    <Modal open={open} title={title} onClose={onClose}>
      <form
        className="form-grid"
        onSubmit={async (event) => {
          event.preventDefault()
          try {
            setSubmitting(true)
            setSubmitError('')
            await onSubmit(form)
          } catch (error) {
            setSubmitError(error?.message || 'Nao foi possivel salvar os dados.')
          } finally {
            setSubmitting(false)
          }
        }}
      >
        {fields.map((field) => (
          <label key={field.name} className={field.full ? 'full' : ''}>
            <span>{field.label}</span>
            {field.type === 'select' ? (
              <select
                value={(() => {
                  const currentValue = form[field.name] ?? field.defaultValue ?? ''
                  return currentValue === '' ? '' : String(currentValue)
                })()}
                disabled={submitting}
                onChange={(event) => handleChange(field.name, event.target.value)}
              >
                <option value="">Selecione</option>
                {field.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : field.type === 'textarea' ? (
              <textarea
                rows={4}
                value={form[field.name] ?? field.defaultValue ?? ''}
                disabled={submitting}
                onChange={(event) => handleChange(field.name, event.target.value)}
              />
            ) : (
              <input
                type={field.type || 'text'}
                value={form[field.name] ?? field.defaultValue ?? ''}
                disabled={submitting}
                onChange={(event) => handleChange(field.name, event.target.value)}
              />
            )}
          </label>
        ))}

        {submitError ? <div className="alert-banner error full">{submitError}</div> : null}

        <div className="form-actions full">
          <button type="button" className="button ghost" onClick={onClose} disabled={submitting}>
            Cancelar
          </button>
          <button type="submit" className="button primary" disabled={submitting}>
            {submitting ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
