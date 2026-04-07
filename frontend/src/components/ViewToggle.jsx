import { LayoutGrid, Rows3 } from 'lucide-react'

export default function ViewToggle({ mode, setMode }) {
  return (
    <div className="view-toggle">
      <button type="button" className={mode === 'cards' ? 'active' : ''} onClick={() => setMode('cards')}>
        <LayoutGrid size={16} />
        Cards
      </button>
      <button type="button" className={mode === 'list' ? 'active' : ''} onClick={() => setMode('list')}>
        <Rows3 size={16} />
        Lista
      </button>
    </div>
  )
}
