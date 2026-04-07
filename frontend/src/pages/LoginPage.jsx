import { useState } from 'react'
import { ArrowRight, KeyRound, LockKeyhole, MonitorDot, ShieldCheck, Sparkles } from 'lucide-react'

export default function LoginPage({ onLogin, loading, booting = false }) {
  const [form, setForm] = useState({
    email: 'admin@spygym.local',
    password: 'Admin@123',
  })
  const [error, setError] = useState('')

  const fillDefaultAccess = () => {
    setForm({
      email: 'admin@spygym.local',
      password: 'Admin@123',
    })
    setError('')
  }

  const submit = async (event) => {
    event.preventDefault()
    try {
      setError('')
      await onLogin(form)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-glow login-glow-a" />
      <div className="login-glow login-glow-b" />
      <div className="login-grid" />

      <div className="login-modal">
        <section className="login-side">
          <div className="brand-chip">SPYGYM Secure Access</div>

          <div className="login-copy">
            <h1>Monitoramento centralizado com acesso rápido e seguro</h1>
            <p>Entre no painel para acompanhar DVRs, câmeras, eventos críticos e backups em uma única operação.</p>
          </div>

          <div className="login-side-list">
            <div className="login-side-item">
              <ShieldCheck size={18} />
              <span>Autenticação com sessão protegida</span>
            </div>
            <div className="login-side-item">
              <MonitorDot size={18} />
              <span>Painel em tempo real para unidades, DVRs e câmeras</span>
            </div>
            <div className="login-side-item">
              <Sparkles size={18} />
              <span>Inicialização com um clique pelo atalho do projeto</span>
            </div>
          </div>

          <div className="login-hints">
            <div className="info-block">
              <MonitorDot size={18} />
              <div>
                <strong>Admin inicial</strong>
                <span>admin@spygym.local</span>
              </div>
            </div>
            <div className="info-block">
              <LockKeyhole size={18} />
              <div>
                <strong>Senha inicial</strong>
                <span>Admin@123</span>
              </div>
            </div>
          </div>
        </section>

        <section className="login-panel">
          <div className="login-panel-head">
            <span className="eyebrow">Acesso Seguro</span>
            <strong>{booting ? 'Preparando ambiente' : 'Entrar no painel'}</strong>
            <p>{booting ? 'Validando a sessão atual e conectando ao backend.' : 'Use suas credenciais para abrir o centro de operações do SPYGYM.'}</p>
          </div>

          <form className="login-form" onSubmit={submit}>
            <label className="login-field">
              <span>E-mail</span>
              <input
                type="email"
                placeholder="admin@spygym.local"
                value={form.email}
                disabled={loading || booting}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
            <label className="login-field">
              <span>Senha</span>
              <input
                type="password"
                placeholder="Sua senha"
                value={form.password}
                disabled={loading || booting}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              />
            </label>

            {error ? <div className="alert-banner error">{error}</div> : null}

            <div className="login-actions">
              <button type="button" className="button ghost login-ghost" onClick={fillDefaultAccess} disabled={loading || booting}>
                <KeyRound size={16} />
                Usar acesso padrão
              </button>
              <button type="submit" className="button primary wide login-submit" disabled={loading || booting}>
                {booting ? 'Conectando...' : loading ? 'Entrando...' : 'Entrar no SPYGYM'}
                {!booting && !loading ? <ArrowRight size={16} /> : null}
              </button>
            </div>

            <div className="login-note">
              <LockKeyhole size={16} />
              <span>Login inicial disponível com o usuário administrador padrão.</span>
            </div>
          </form>
        </section>
      </div>
    </div>
  )
}
