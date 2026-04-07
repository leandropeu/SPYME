import {
  Download,
  Eye,
  FileDown,
  FileText,
  ImagePlus,
  MonitorPlay,
  Printer,
  RotateCcw,
  Save,
  Upload,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import Modal from '../components/Modal'
import Topbar from '../components/Topbar'
import { api } from '../utils/api'

const STORAGE_KEY = 'spygym-report-draft-v1'

const EMPTY_REPORT = {
  title: 'Relatorio de Monitoramento da Recepcao',
  documentCode: '',
  unit_id: '',
  receptionName: '',
  requestedBy: '',
  author: '',
  reviewedBy: '',
  reportDate: new Date().toISOString().slice(0, 10),
  periodStart: '',
  periodEnd: '',
  requestedPeriods: '',
  objective: '',
  summary: '',
  introduction: '',
  methodology: '',
  currentScenario: '',
  findingsByPeriod: '',
  serviceRisks: '',
  mediaContext: '',
  decisions: '',
  actionPlan: '',
  recommendations: '',
  conclusion: '',
  attachments: [],
}

function sanitizeText(value) {
  return (value || '').replace(/\r\n/g, '\n').trim()
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

function paragraphize(value) {
  return sanitizeText(value)
    .split('\n')
    .filter(Boolean)
    .map((line) => `<p>${escapeHtml(line)}</p>`)
    .join('')
}

function buildPowerPointOutline(report, unitName) {
  return [
    report.title || 'Relatorio de Monitoramento',
    `Unidade: ${unitName || 'Nao informada'}`,
    `Recepcao: ${report.receptionName || 'Nao informada'}`,
    `Periodo: ${report.periodStart || '—'} a ${report.periodEnd || '—'}`,
    '',
    'Resumo Executivo',
    sanitizeText(report.summary) || 'Sem conteudo',
    '',
    'Objetivo',
    sanitizeText(report.objective) || 'Sem conteudo',
    '',
    'Metodologia',
    sanitizeText(report.methodology) || 'Sem conteudo',
    '',
    'Achados por Periodo',
    sanitizeText(report.findingsByPeriod) || 'Sem conteudo',
    '',
    'Tomadas de Decisao',
    sanitizeText(report.decisions) || 'Sem conteudo',
    '',
    'Plano de Acao',
    sanitizeText(report.actionPlan) || 'Sem conteudo',
    '',
    'Recomendacoes',
    sanitizeText(report.recommendations) || 'Sem conteudo',
    '',
    'Conclusao',
    sanitizeText(report.conclusion) || 'Sem conteudo',
  ].join('\n')
}

function buildPlainTextReport(report, unitName) {
  return [
    report.title || 'Relatorio de Monitoramento',
    '',
    `Codigo: ${report.documentCode || 'Nao informado'}`,
    `Data: ${report.reportDate || 'Nao informada'}`,
    `Unidade: ${unitName || 'Nao informada'}`,
    `Recepcao: ${report.receptionName || 'Nao informada'}`,
    `Periodo: ${report.periodStart || '—'} a ${report.periodEnd || '—'}`,
    `Solicitante: ${report.requestedBy || 'Nao informado'}`,
    `Responsavel: ${report.author || 'Nao informado'}`,
    `Aprovacao: ${report.reviewedBy || 'Nao informado'}`,
    '',
    `Periodos solicitados: ${sanitizeText(report.requestedPeriods) || 'Sem conteudo.'}`,
    '',
    '1. Resumo Executivo',
    sanitizeText(report.summary) || 'Sem conteudo.',
    '',
    '2. Objetivo',
    sanitizeText(report.objective) || 'Sem conteudo.',
    '',
    '3. Introducao',
    sanitizeText(report.introduction) || 'Sem conteudo.',
    '',
    '4. Metodologia',
    sanitizeText(report.methodology) || 'Sem conteudo.',
    '',
    '5. Cenario Atual da Recepcao',
    sanitizeText(report.currentScenario) || 'Sem conteudo.',
    '',
    '6. Achados por Periodo Monitorado',
    sanitizeText(report.findingsByPeriod) || 'Sem conteudo.',
    '',
    '7. Riscos e Impactos no Atendimento',
    sanitizeText(report.serviceRisks) || 'Sem conteudo.',
    '',
    '8. Contexto dos Registros Visuais',
    sanitizeText(report.mediaContext) || 'Sem conteudo.',
    '',
    '9. Tomadas de Decisao',
    sanitizeText(report.decisions) || 'Sem conteudo.',
    '',
    '10. Medidas para Melhoria do Processo',
    sanitizeText(report.actionPlan) || 'Sem conteudo.',
    '',
    '11. Recomendacoes Complementares',
    sanitizeText(report.recommendations) || 'Sem conteudo.',
    '',
    '12. Conclusao',
    sanitizeText(report.conclusion) || 'Sem conteudo.',
    '',
    '13. Anexos Visuais',
    report.attachments.length
      ? report.attachments.map((attachment, index) => `${index + 1}. ${attachment.name}${attachment.caption ? ` - ${attachment.caption}` : ''}`).join('\n')
      : 'Sem anexos.',
  ].join('\n')
}

function buildReportHtml(report, unitName) {
  const attachments = report.attachments
    .map((attachment, index) => {
      const caption = attachment.caption ? `<figcaption>${escapeHtml(attachment.caption)}</figcaption>` : ''
      if (attachment.kind === 'video') {
        return `
          <figure class="media-item">
            <video controls preload="metadata" src="${attachment.dataUrl}"></video>
            ${caption || `<figcaption>Video ${index + 1}</figcaption>`}
          </figure>
        `
      }
      return `
        <figure class="media-item">
          <img src="${attachment.dataUrl}" alt="${escapeHtml(attachment.name || `Imagem ${index + 1}`)}" />
          ${caption || `<figcaption>Imagem ${index + 1}</figcaption>`}
        </figure>
      `
    })
    .join('')

  return `<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(report.title || 'Relatorio')}</title>
    <style>
      body { font-family: "Times New Roman", serif; color: #111; margin: 0; background: #fff; }
      .document { width: 210mm; min-height: 297mm; margin: 0 auto; padding: 25mm 20mm 25mm 30mm; box-sizing: border-box; }
      h1, h2 { margin: 0 0 12px; font-weight: 700; }
      h1 { font-size: 18pt; text-align: center; margin-bottom: 26px; text-transform: uppercase; }
      h2 { font-size: 12pt; margin-top: 22px; text-transform: uppercase; }
      p { font-size: 12pt; line-height: 1.5; text-align: justify; margin: 0 0 10px; }
      .meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 22px; margin-bottom: 24px; }
      .meta-item { border-bottom: 1px solid #999; padding-bottom: 6px; }
      .meta-item strong { display: block; font-size: 10pt; text-transform: uppercase; margin-bottom: 3px; }
      .media-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 12px; }
      .media-item { margin: 0; border: 1px solid #ccc; padding: 10px; }
      .media-item img, .media-item video { width: 100%; display: block; }
      .media-item figcaption { font-size: 10pt; margin-top: 8px; text-align: center; }
      .signature-row { display: grid; grid-template-columns: 1fr 1fr; gap: 36px; margin-top: 36px; }
      .signature-box { padding-top: 24px; border-top: 1px solid #333; text-align: center; }
    </style>
  </head>
  <body>
    <main class="document">
      <h1>${escapeHtml(report.title || 'Relatorio de Monitoramento')}</h1>
      <section class="meta-grid">
        <div class="meta-item"><strong>Codigo do Documento</strong>${escapeHtml(report.documentCode || 'Nao informado')}</div>
        <div class="meta-item"><strong>Data do Relatorio</strong>${escapeHtml(report.reportDate || 'Nao informada')}</div>
        <div class="meta-item"><strong>Unidade</strong>${escapeHtml(unitName || 'Nao informada')}</div>
        <div class="meta-item"><strong>Recepcao Monitorada</strong>${escapeHtml(report.receptionName || 'Nao informada')}</div>
        <div class="meta-item"><strong>Periodo Avaliado</strong>${escapeHtml(report.periodStart || '—')} a ${escapeHtml(report.periodEnd || '—')}</div>
        <div class="meta-item"><strong>Periodos Solicitados</strong>${escapeHtml(report.requestedPeriods || 'Nao informados')}</div>
        <div class="meta-item"><strong>Solicitante</strong>${escapeHtml(report.requestedBy || 'Nao informado')}</div>
        <div class="meta-item"><strong>Responsavel</strong>${escapeHtml(report.author || 'Nao informado')}</div>
      </section>
      ${[
        ['1. Resumo Executivo', report.summary],
        ['2. Objetivo', report.objective],
        ['3. Introducao', report.introduction],
        ['4. Metodologia', report.methodology],
        ['5. Cenario Atual da Recepcao', report.currentScenario],
        ['6. Achados por Periodo Monitorado', report.findingsByPeriod],
        ['7. Riscos e Impactos no Atendimento', report.serviceRisks],
        ['8. Contexto dos Registros Visuais', report.mediaContext],
        ['9. Tomadas de Decisao', report.decisions],
        ['10. Medidas para Melhoria do Processo', report.actionPlan],
        ['11. Recomendacoes Complementares', report.recommendations],
        ['12. Conclusao', report.conclusion],
      ].map(([title, value]) => `<section><h2>${title}</h2>${paragraphize(value)}</section>`).join('')}
      <section>
        <h2>13. Anexos Visuais</h2>
        ${attachments ? `<div class="media-grid">${attachments}</div>` : '<p>Sem anexos visuais.</p>'}
      </section>
      <section class="signature-row">
        <div class="signature-box">${escapeHtml(report.author || 'Responsavel pela elaboracao')}</div>
        <div class="signature-box">${escapeHtml(report.reviewedBy || 'Responsavel pela aprovacao')}</div>
      </section>
    </main>
  </body>
</html>`
}

function ReportPreview({ report, unitName }) {
  const sections = [
    ['1. Resumo Executivo', report.summary],
    ['2. Objetivo', report.objective],
    ['3. Introducao', report.introduction],
    ['4. Metodologia', report.methodology],
    ['5. Cenario Atual da Recepcao', report.currentScenario],
    ['6. Achados por Periodo Monitorado', report.findingsByPeriod],
    ['7. Riscos e Impactos no Atendimento', report.serviceRisks],
    ['8. Contexto dos Registros Visuais', report.mediaContext],
    ['9. Tomadas de Decisao', report.decisions],
    ['10. Medidas para Melhoria do Processo', report.actionPlan],
    ['11. Recomendacoes Complementares', report.recommendations],
    ['12. Conclusao', report.conclusion],
  ]

  return (
    <div className="report-preview">
      <div className="report-sheet">
        <header className="report-cover">
          <span className="eyebrow">Relatorio formal</span>
          <h1>{report.title || 'Relatorio de Monitoramento'}</h1>
          <div className="report-meta-grid">
            <div className="report-meta-item"><strong>Codigo</strong><span>{report.documentCode || 'Nao informado'}</span></div>
            <div className="report-meta-item"><strong>Data</strong><span>{report.reportDate || 'Nao informada'}</span></div>
            <div className="report-meta-item"><strong>Unidade</strong><span>{unitName || 'Nao informada'}</span></div>
            <div className="report-meta-item"><strong>Recepcao</strong><span>{report.receptionName || 'Nao informada'}</span></div>
            <div className="report-meta-item"><strong>Periodo</strong><span>{report.periodStart || '—'} a {report.periodEnd || '—'}</span></div>
            <div className="report-meta-item"><strong>Solicitante</strong><span>{report.requestedBy || 'Nao informado'}</span></div>
          </div>
        </header>

        {sections.map(([title, value]) => (
          <section key={title} className="report-section">
            <h2>{title}</h2>
            {sanitizeText(value).split('\n').filter(Boolean).length ? sanitizeText(value).split('\n').filter(Boolean).map((line, index) => (
              <p key={`${title}-${index}`}>{line}</p>
            )) : <p className="report-empty">Sem conteudo preenchido.</p>}
          </section>
        ))}

        <section className="report-section">
          <h2>13. Anexos Visuais</h2>
          {report.attachments.length ? (
            <div className="report-media-grid">
              {report.attachments.map((attachment) => (
                <figure key={attachment.id} className="report-media-card">
                  {attachment.kind === 'video' ? (
                    <video controls preload="metadata" src={attachment.dataUrl} />
                  ) : (
                    <img src={attachment.dataUrl} alt={attachment.name} />
                  )}
                  <figcaption>
                    <strong>{attachment.name}</strong>
                    <span>{attachment.caption || 'Sem legenda'}</span>
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <p className="report-empty">Nenhum anexo inserido.</p>
          )}
        </section>

        <section className="report-signatures">
          <div className="report-signature-box"><span>{report.author || 'Responsavel pela elaboracao'}</span></div>
          <div className="report-signature-box"><span>{report.reviewedBy || 'Responsavel pela aprovacao'}</span></div>
        </section>
      </div>
    </div>
  )
}

export default function ReportsPage({ connected, currentUser, onLogout }) {
  const [units, setUnits] = useState([])
  const [report, setReport] = useState(EMPTY_REPORT)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const importRef = useRef(null)

  useEffect(() => {
    const bootstrap = async () => {
      try {
        setUnits(await api.listUnits())
      } catch (err) {
        setError(err.message)
      }

      const saved = window.localStorage.getItem(STORAGE_KEY)
      if (saved) {
        try {
          const parsed = JSON.parse(saved)
          setReport((current) => ({ ...current, ...parsed, attachments: parsed.attachments || [] }))
        } catch {
          window.localStorage.removeItem(STORAGE_KEY)
        }
      }
    }

    bootstrap()
  }, [])

  useEffect(() => {
    const { attachments, ...persistable } = report
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable))
  }, [report])

  const selectedUnit = useMemo(
    () => units.find((unit) => String(unit.id) === String(report.unit_id)),
    [report.unit_id, units],
  )

  const fileBaseName = useMemo(() => {
    const unitChunk = (selectedUnit?.name || 'unidade').toLowerCase().replace(/[^a-z0-9]+/gi, '-')
    const receptionChunk = (report.receptionName || 'recepcao').toLowerCase().replace(/[^a-z0-9]+/gi, '-')
    const dateChunk = report.reportDate || 'relatorio'
    return `relatorio-${unitChunk}-${receptionChunk}-${dateChunk}`.replace(/-+/g, '-')
  }, [report.receptionName, report.reportDate, selectedUnit?.name])

  const setField = (name, value) => {
    setReport((current) => ({ ...current, [name]: value }))
  }

  const saveBlob = (content, fileName, mimeType = 'text/plain;charset=utf-8') => {
    const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = fileName
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const exportJson = () => {
    saveBlob(JSON.stringify(report, null, 2), `${fileBaseName}.json`, 'application/json;charset=utf-8')
    setNotice('Rascunho exportado em JSON.')
  }

  const exportMarkdown = () => {
    const content = [
      `# ${report.title || 'Relatorio de Monitoramento'}`,
      '',
      `- Unidade: ${selectedUnit?.name || 'Nao informada'}`,
      `- Recepcao: ${report.receptionName || 'Nao informada'}`,
      `- Data: ${report.reportDate || 'Nao informada'}`,
      `- Periodo: ${report.periodStart || '—'} a ${report.periodEnd || '—'}`,
      '',
      '## Resumo Executivo',
      sanitizeText(report.summary) || 'Sem conteudo.',
      '',
      '## Objetivo',
      sanitizeText(report.objective) || 'Sem conteudo.',
      '',
      '## Introducao',
      sanitizeText(report.introduction) || 'Sem conteudo.',
      '',
      '## Metodologia',
      sanitizeText(report.methodology) || 'Sem conteudo.',
      '',
      '## Achados por Periodo Monitorado',
      sanitizeText(report.findingsByPeriod) || 'Sem conteudo.',
      '',
      '## Tomadas de Decisao',
      sanitizeText(report.decisions) || 'Sem conteudo.',
      '',
      '## Plano de Acao',
      sanitizeText(report.actionPlan) || 'Sem conteudo.',
      '',
      '## Conclusao',
      sanitizeText(report.conclusion) || 'Sem conteudo.',
    ].join('\n')
    saveBlob(content, `${fileBaseName}.md`, 'text/markdown;charset=utf-8')
    setNotice('Versao Markdown exportada.')
  }

  const exportText = () => {
    saveBlob(buildPlainTextReport(report, selectedUnit?.name), `${fileBaseName}.txt`, 'text/plain;charset=utf-8')
    setNotice('Versao em texto exportada.')
  }

  const exportHtml = () => {
    saveBlob(buildReportHtml(report, selectedUnit?.name), `${fileBaseName}.html`, 'text/html;charset=utf-8')
    setNotice('Versao HTML exportada.')
  }

  const exportWord = () => {
    saveBlob(buildReportHtml(report, selectedUnit?.name), `${fileBaseName}.doc`, 'application/msword;charset=utf-8')
    setNotice('Documento Word exportado.')
  }

  const exportPowerPointOutline = () => {
    saveBlob(buildPowerPointOutline(report, selectedUnit?.name), `${fileBaseName}-outline.txt`, 'text/plain;charset=utf-8')
    setNotice('Outline para PowerPoint exportado.')
  }

  const printReport = () => {
    const html = buildReportHtml(report, selectedUnit?.name)
    const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=1200,height=900')
    if (!printWindow) {
      setError('Nao foi possivel abrir a janela de impressao.')
      return
    }
    printWindow.document.open()
    printWindow.document.write(html)
    printWindow.document.close()
    printWindow.onload = () => {
      printWindow.focus()
      printWindow.print()
    }
  }

  const clearDraft = () => {
    if (!window.confirm('Limpar todo o rascunho atual?')) return
    window.localStorage.removeItem(STORAGE_KEY)
    setReport(EMPTY_REPORT)
    setNotice('Rascunho limpo.')
  }

  const handleImportFile = async (event) => {
    const [file] = Array.from(event.target.files || [])
    if (!file) return
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      setReport({ ...EMPTY_REPORT, ...parsed, attachments: parsed.attachments || [] })
      setNotice('Rascunho importado com sucesso.')
      setError('')
    } catch {
      setError('Arquivo invalido. Importe um JSON gerado por esta aba.')
    } finally {
      event.target.value = ''
    }
  }

  const handleAttachments = async (event) => {
    const files = Array.from(event.target.files || [])
    if (!files.length) return

    const attachments = await Promise.all(files.map((file) => new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve({
        id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        kind: file.type.startsWith('video/') ? 'video' : 'image',
        type: file.type,
        dataUrl: reader.result,
        caption: '',
      })
      reader.onerror = () => reject(new Error('Falha ao ler o arquivo selecionado.'))
      reader.readAsDataURL(file)
    })))

    setReport((current) => ({ ...current, attachments: [...current.attachments, ...attachments] }))
    setNotice(`${attachments.length} anexo(s) carregado(s).`)
    event.target.value = ''
  }

  const updateAttachmentCaption = (id, caption) => {
    setReport((current) => ({
      ...current,
      attachments: current.attachments.map((attachment) => (
        attachment.id === id ? { ...attachment, caption } : attachment
      )),
    }))
  }

  const removeAttachment = (id) => {
    setReport((current) => ({
      ...current,
      attachments: current.attachments.filter((attachment) => attachment.id !== id),
    }))
  }

  const sections = [
    ['summary', '1. Resumo Executivo', 'Sintese objetiva do que foi observado, dos impactos e da principal conclusao.'],
    ['objective', '2. Objetivo', 'Qual foi a demanda da gestao e o foco do monitoramento solicitado.'],
    ['introduction', '3. Introducao', 'Contexto da unidade, da recepcao e da necessidade de observacao.'],
    ['methodology', '4. Metodologia', 'Como o monitoramento foi conduzido, criterios, horarios, quantidade de registros e forma de analise.'],
    ['currentScenario', '5. Cenario Atual da Recepcao', 'Descreva fluxo, comportamento da equipe, gargalos, filas, postura, padroes e desvios.'],
    ['findingsByPeriod', '6. Achados por Periodo Monitorado', 'Separe por manha, tarde, noite, pico, datas ou recortes solicitados pela gestao.'],
    ['serviceRisks', '7. Riscos e Impactos no Atendimento', 'Aponte reflexos em experiencia do cliente, conversao, acolhimento, espera, retrabalho e clima operacional.'],
    ['mediaContext', '8. Contexto dos Registros Visuais', 'Explique o que cada foto ou video evidencia e por que foi anexado.'],
    ['decisions', '9. Tomadas de Decisao', 'Campo livre para decisoes aprovadas, ajustes imediatos e encaminhamentos gerenciais.'],
    ['actionPlan', '10. Medidas para Melhoria do Processo', 'Plano pratico com medidas de curto, medio e longo prazo para melhorar o atendimento nas recepcoes.'],
    ['recommendations', '11. Recomendacoes Complementares', 'Treinamento, escala, roteiro de atendimento, reposicionamento, auditoria, indicadores e controles.'],
    ['conclusion', '12. Conclusao', 'Fechamento final do documento e mensagem executiva para a gestao.'],
  ]

  return (
    <section className="page-shell">
      <Topbar
        title="Relatorios de monitoramento"
        subtitle="Editor estruturado em padrao formal para recepcoes, com texto livre, anexos, tomada de decisao e saidas para Word, PDF e apresentacao."
        connected={connected}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      {error ? <div className="alert-banner error">{error}</div> : null}
      {notice ? <div className="alert-banner success">{notice}</div> : null}

      <div className="report-toolbar">
        <button type="button" className="button primary" onClick={() => setPreviewOpen(true)}><Eye size={16} />Visualizar</button>
        <button type="button" className="button ghost" onClick={printReport}><Printer size={16} />Imprimir / PDF</button>
        <button type="button" className="button ghost" onClick={exportWord}><FileDown size={16} />Exportar Word</button>
        <button type="button" className="button ghost" onClick={exportHtml}><FileText size={16} />Exportar HTML</button>
        <button type="button" className="button ghost" onClick={exportMarkdown}><Download size={16} />Exportar Markdown</button>
        <button type="button" className="button ghost" onClick={exportText}><Download size={16} />Exportar TXT</button>
        <button type="button" className="button ghost" onClick={exportPowerPointOutline}><MonitorPlay size={16} />Outline PowerPoint</button>
        <button type="button" className="button ghost" onClick={exportJson}><Save size={16} />Exportar rascunho</button>
        <button type="button" className="button warning" onClick={() => importRef.current?.click()}><Upload size={16} />Importar rascunho</button>
        <button type="button" className="button danger" onClick={clearDraft}><RotateCcw size={16} />Limpar</button>
        <input ref={importRef} type="file" accept=".json,application/json" hidden onChange={handleImportFile} />
      </div>

      <div className="empty-state">
        Fluxo recomendado: edite o documento diretamente nesta aba, mantenha a versao de trabalho em JSON para continuar depois e gere Word, PDF ou outline para PowerPoint apenas na etapa final.
      </div>

      <div className="panel-grid two-columns report-layout">
        <section className="panel report-editor-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Estrutura ABNT</span>
              <h3>Dados de identificacao</h3>
            </div>
          </div>

          <div className="form-grid report-form-grid">
            <label className="full"><span>Titulo do relatorio</span><input value={report.title} onChange={(event) => setField('title', event.target.value)} /></label>
            <label><span>Codigo do documento</span><input value={report.documentCode} onChange={(event) => setField('documentCode', event.target.value)} /></label>
            <label><span>Data do relatorio</span><input type="date" value={report.reportDate} onChange={(event) => setField('reportDate', event.target.value)} /></label>
            <label>
              <span>Unidade</span>
              <select value={report.unit_id} onChange={(event) => setField('unit_id', event.target.value)}>
                <option value="">Selecione</option>
                {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
              </select>
            </label>
            <label><span>Recepcao monitorada</span><input value={report.receptionName} onChange={(event) => setField('receptionName', event.target.value)} /></label>
            <label><span>Solicitante / gestao</span><input value={report.requestedBy} onChange={(event) => setField('requestedBy', event.target.value)} /></label>
            <label><span>Responsavel pela elaboracao</span><input value={report.author} onChange={(event) => setField('author', event.target.value)} /></label>
            <label><span>Responsavel pela aprovacao</span><input value={report.reviewedBy} onChange={(event) => setField('reviewedBy', event.target.value)} /></label>
            <label><span>Inicio do periodo</span><input type="date" value={report.periodStart} onChange={(event) => setField('periodStart', event.target.value)} /></label>
            <label><span>Fim do periodo</span><input type="date" value={report.periodEnd} onChange={(event) => setField('periodEnd', event.target.value)} /></label>
            <label className="full"><span>Periodos solicitados pela gestao</span><textarea rows={3} value={report.requestedPeriods} onChange={(event) => setField('requestedPeriods', event.target.value)} /></label>
          </div>
        </section>

        <section className="panel report-editor-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Orientacao</span>
              <h3>Melhor forma de editar</h3>
            </div>
          </div>
          <div className="stack-list">
            <article className="info-block"><div><strong>1. Trabalhe por secoes</strong><span>Preencha primeiro identificacao, resumo, metodologia e achados. Isso acelera a revisao final.</span></div></article>
            <article className="info-block"><div><strong>2. Use o rascunho JSON para continuidade</strong><span>Exportar e importar JSON e a forma mais segura de continuar o documento depois, inclusive com anexos.</span></div></article>
            <article className="info-block"><div><strong>3. Feche em Word ou PDF na conclusao</strong><span>Word e melhor para circulacao interna; impressao/PDF e melhor para protocolo, assinatura e envio final.</span></div></article>
            <article className="info-block"><div><strong>4. Para PowerPoint</strong><span>Use o arquivo “Outline PowerPoint” para transformar o relatorio em apresentacao executiva por topicos.</span></div></article>
          </div>
        </section>
      </div>

      <div className="report-sections-grid">
        {sections.map(([field, title, hint]) => (
          <section key={field} className="panel report-editor-panel">
            <div className="panel-header">
              <div>
                <span className="eyebrow">Secao</span>
                <h3>{title}</h3>
              </div>
            </div>
            <span className="report-hint">{hint}</span>
            <textarea className="report-textarea" rows={8} value={report[field]} onChange={(event) => setField(field, event.target.value)} />
          </section>
        ))}
      </div>

      <section className="panel report-editor-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">Anexos</span>
            <h3>Fotos e videos</h3>
          </div>
          <label className="button primary report-upload-button">
            <ImagePlus size={16} />
            Inserir fotos / videos
            <input type="file" accept="image/*,video/*" multiple hidden onChange={handleAttachments} />
          </label>
        </div>

        {report.attachments.length ? (
          <div className="report-media-grid editor-media-grid">
            {report.attachments.map((attachment) => (
              <article key={attachment.id} className="report-media-card">
                {attachment.kind === 'video' ? (
                  <video controls preload="metadata" src={attachment.dataUrl} />
                ) : (
                  <img src={attachment.dataUrl} alt={attachment.name} />
                )}
                <div className="report-media-meta">
                  <strong>{attachment.name}</strong>
                  <textarea rows={3} placeholder="Legenda / contexto do anexo" value={attachment.caption} onChange={(event) => updateAttachmentCaption(attachment.id, event.target.value)} />
                  <button type="button" className="button danger" onClick={() => removeAttachment(attachment.id)}>Remover</button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            Nenhum anexo inserido ainda. Use fotos e videos quando forem importantes para demonstrar fluxo, fila, atendimento, postura operacional ou ponto de melhoria.
          </div>
        )}
      </section>

      <Modal open={previewOpen} title="Visualizacao final do relatorio" onClose={() => setPreviewOpen(false)} className="wide-modal report-preview-modal">
        <div className="report-preview-actions">
          <button type="button" className="button primary" onClick={printReport}><Printer size={16} />Imprimir / Salvar em PDF</button>
          <button type="button" className="button ghost" onClick={exportWord}><FileDown size={16} />Exportar Word</button>
          <button type="button" className="button ghost" onClick={exportHtml}><FileText size={16} />Exportar HTML</button>
          <button type="button" className="button ghost" onClick={exportPowerPointOutline}><MonitorPlay size={16} />Outline PowerPoint</button>
        </div>
        <ReportPreview report={report} unitName={selectedUnit?.name} />
      </Modal>
    </section>
  )
}
