export default function Modal({ open, title, onClose, children, className = '' }) {
  if (!open) return null

  return (
    <div className="modal-shell" role="dialog" aria-modal="true">
      <div className={`modal-card ${className}`.trim()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button type="button" className="button ghost" onClick={onClose}>
            Fechar
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
