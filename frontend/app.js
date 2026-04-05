const { useState, useEffect, useRef, useCallback, createContext, useContext } = React

// ── Utilities ─────────────────────────────────────────────────────────────────
function cn(...c) { return c.filter(Boolean).join(' ') }
function parseOwnershipPct(label) {
  const m = (label || '').match(/^(\d+)%/)
  return m ? parseInt(m[1], 10) : 0
}

// ── Brand tokens ──────────────────────────────────────────────────────────────
const BRAND_GRAD   = 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)'
const BRAND_GLOW   = '0 2px 16px rgba(99,102,241,0.32)'
const BRAND_ACCENT = '#4f46e5'

// ── Semantic color maps ────────────────────────────────────────────────────────
const SEV = {
  critical: { fg: '#991b1b', bg: '#fff1f2', border: '#fecdd3', dot: '#ef4444', strip: 'linear-gradient(90deg,#ef4444,#f87171)' },
  high:     { fg: '#9a3412', bg: '#fff7ed', border: '#fed7aa', dot: '#f97316', strip: 'linear-gradient(90deg,#f97316,#fb923c)' },
  medium:   { fg: '#78350f', bg: '#fffbeb', border: '#fde68a', dot: '#f59e0b', strip: 'linear-gradient(90deg,#f59e0b,#fbbf24)' },
  low:      { fg: '#064e3b', bg: '#f0fdf4', border: '#bbf7d0', dot: '#10b981', strip: 'linear-gradient(90deg,#10b981,#34d399)' },
}

const DOC = {
  asic_extract:         { label: 'ASIC',  fg: '#3730a3', bg: '#eef2ff', border: '#c7d2fe' },
  constitution:         { label: 'CONST', fg: '#5b21b6', bg: '#f5f3ff', border: '#ddd6fe' },
  shareholder_register: { label: 'REG',   fg: '#065f46', bg: '#ecfdf5', border: '#a7f3d0' },
}

// ── Cytoscape style ───────────────────────────────────────────────────────────
const CY_STYLE = [
  { selector: 'node', style: {
    label: 'data(label)', 'text-wrap': 'wrap', 'text-max-width': '116px',
    'font-family': 'Inter, system-ui, sans-serif', 'font-size': '10px', 'font-weight': '500',
    'text-valign': 'center', 'text-halign': 'center', 'border-width': 1.5, color: '#ffffff',
  }},
  { selector: 'node[type="Company"]', style: {
    shape: 'round-rectangle',
    'background-color': '#1e293b',
    'border-color': '#334155', 'border-width': 2,
    width: 172, height: 68,
    'font-size': '11px', 'font-weight': '700', 'text-max-width': '150px',
  }},
  { selector: 'node[type="Director"]', style: {
    shape: 'ellipse',
    'background-color': '#4f46e5',
    'border-color': '#3730a3', 'border-width': 2, width: 128, height: 58,
  }},
  { selector: 'node[type="Shareholder"]', style: {
    shape: 'ellipse',
    'background-color': '#059669',
    'border-color': '#047857', 'border-width': 2, width: 136, height: 58,
  }},
  { selector: 'node[type="ShareClass"]', style: {
    shape: 'diamond',
    'background-color': '#b45309',
    'border-color': '#92400e', 'border-width': 2, width: 150, height: 86,
    'font-size': '9.5px', color: '#fef3c7',
  }},
  { selector: 'node[type="UltimateHoldingCompany"]', style: {
    shape: 'round-rectangle',
    'background-color': '#7c3aed',
    'border-color': '#5b21b6', 'border-width': 2, width: 172, height: 68, 'font-weight': '700',
  }},
  { selector: 'edge', style: {
    width: 1.5, 'curve-style': 'bezier',
    'target-arrow-shape': 'triangle', 'target-arrow-color': '#94a3b8', 'line-color': '#cbd5e1',
    label: 'data(label)', 'font-size': '9px', 'font-family': 'Inter, system-ui, sans-serif',
    color: '#64748b', 'text-background-color': '#fafafa', 'text-background-opacity': 0.95,
    'text-background-padding': '2px',
  }},
  { selector: 'edge[type="CONTROLS"]', style: {
    'line-color': '#818cf8', 'target-arrow-color': '#818cf8', width: 1.5,
    'font-size': '10px', 'font-weight': '600', color: '#3730a3',
    'text-background-color': '#e0e7ff', 'text-background-opacity': 1, 'text-background-padding': '3px',
    'text-border-width': 1, 'text-border-color': '#a5b4fc', 'text-border-opacity': 1,
    'text-background-shape': 'roundrectangle',
  }},
  { selector: 'edge[type="OWNS"]', style: {
    'line-color': '#34d399', 'target-arrow-color': '#34d399',
    width: 'mapData(ownershipPct, 0, 100, 1.5, 5)',
    'font-size': '11px', 'font-weight': '700', color: '#065f46',
    'text-background-color': '#d1fae5', 'text-background-opacity': 1, 'text-background-padding': '4px',
    'text-border-width': 1, 'text-border-color': '#6ee7b7', 'text-border-opacity': 1,
    'text-background-shape': 'roundrectangle',
  }},
  { selector: 'edge[type="ISSUED_UNDER"]', style: {
    'line-color': '#fbbf24', 'target-arrow-color': '#fbbf24', 'line-style': 'dashed', 'line-dash-pattern': [5, 3],
  }},
  { selector: 'edge[type="CONTRADICTION"]', style: {
    'line-color': '#f87171', 'target-arrow-color': '#f87171',
    'target-arrow-shape': 'tee', 'line-style': 'dashed', 'line-dash-pattern': [6, 3],
    width: 3.5, label: '', 'z-index': 999,
  }},
  { selector: '.highlighted', style: { opacity: 1, 'z-index': 999 }},
  { selector: '.dimmed',      style: { opacity: 0.07 }},
  { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#7c3aed' }},
]

// ─────────────────────────────────────────────────────────────────────────────
// shadcn-style component primitives
// ─────────────────────────────────────────────────────────────────────────────

// ── Button ────────────────────────────────────────────────────────────────────
function Button({ children, className, variant = 'default', size = 'default', onClick, disabled, style, ...rest }) {
  const base = 'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 cursor-pointer select-none'
  const variants = {
    default:   'bg-slate-900 text-white hover:bg-slate-800 active:bg-slate-950 shadow-sm',
    outline:   'border border-slate-200 bg-white hover:bg-slate-50 active:bg-slate-100 text-slate-700 shadow-sm',
    ghost:     'hover:bg-slate-100 active:bg-slate-200 text-slate-600',
    secondary: 'bg-slate-100 text-slate-700 hover:bg-slate-200 active:bg-slate-300',
    destructive: 'bg-red-50 border border-red-200 text-red-700 hover:bg-red-100',
    success:   'bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100',
    brand:     'text-white shadow-sm hover:opacity-90 active:opacity-80',
  }
  const sizes = {
    default: 'h-9 px-4 text-sm',
    sm:      'h-8 px-3 text-xs',
    lg:      'h-10 px-6 text-sm',
    icon:    'h-9 w-9',
    xs:      'h-7 px-2.5 text-[11px] rounded-md',
  }
  const brandStyle = variant === 'brand'
    ? { background: BRAND_GRAD, boxShadow: BRAND_GLOW, ...style }
    : style
  return (
    <button
      className={cn(base, variants[variant] ?? variants.default, sizes[size] ?? sizes.default, className)}
      style={brandStyle}
      onClick={onClick}
      disabled={disabled}
      {...rest}
    >{children}</button>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────────────
function Badge({ children, variant = 'default', className, style }) {
  const variants = {
    default:     'bg-slate-900 text-white border-transparent',
    secondary:   'bg-slate-100 text-slate-600 border-slate-200',
    outline:     'bg-transparent text-slate-600 border-slate-300',
    destructive: 'bg-red-50 text-red-700 border-red-200',
    success:     'bg-emerald-50 text-emerald-700 border-emerald-200',
    warning:     'bg-amber-50 text-amber-700 border-amber-200',
    indigo:      'bg-indigo-50 text-indigo-700 border-indigo-200',
    violet:      'bg-violet-50 text-violet-700 border-violet-200',
  }
  return (
    <span
      className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold transition-colors', variants[variant] ?? variants.default, className)}
      style={style}
    >{children}</span>
  )
}

// ── Card ──────────────────────────────────────────────────────────────────────
function Card({ children, className, style, onClick }) {
  return (
    <div
      className={cn('rounded-xl border border-slate-200 bg-white overflow-hidden', onClick && 'cursor-pointer select-none', className)}
      style={style}
      onClick={onClick}
    >{children}</div>
  )
}
function CardHeader({ children, className, style }) {
  return <div className={cn('flex flex-col gap-1 px-4 pt-4 pb-2', className)} style={style}>{children}</div>
}
function CardTitle({ children, className }) {
  return <h3 className={cn('font-semibold leading-snug tracking-tight text-slate-900', className)}>{children}</h3>
}
function CardDescription({ children, className }) {
  return <p className={cn('text-xs text-slate-500 leading-relaxed', className)}>{children}</p>
}
function CardContent({ children, className, style }) {
  return <div className={cn('px-4 pb-4', className)} style={style}>{children}</div>
}
function CardFooter({ children, className, style }) {
  return <div className={cn('flex items-center px-4 pb-4', className)} style={style}>{children}</div>
}

// ── Progress ──────────────────────────────────────────────────────────────────
function Progress({ value = 0, className, barClassName, barStyle }) {
  return (
    <div className={cn('h-1.5 bg-slate-100 rounded-full overflow-hidden', className)}>
      <div
        className={cn('h-full rounded-full transition-all duration-700 ease-out', barClassName)}
        style={{ width: `${Math.min(100, Math.max(0, value))}%`, ...barStyle }}
      />
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function Skeleton({ className, style }) {
  return <div className={cn('animate-pulse rounded-md bg-slate-100', className)} style={style} />
}

// ── Separator ─────────────────────────────────────────────────────────────────
function Separator({ className, style }) {
  return <div className={cn('h-px bg-slate-100 w-full', className)} style={style} />
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
function Tooltip({ children, content, side = 'top' }) {
  const [show, setShow] = useState(false)
  if (!content) return children
  const pos = {
    top:    'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left:   'right-full top-1/2 -translate-y-1/2 mr-2',
    right:  'left-full top-1/2 -translate-y-1/2 ml-2',
  }
  return (
    <div className="relative inline-flex" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div className={cn(
          'absolute z-50 px-2.5 py-1.5 text-xs rounded-lg whitespace-nowrap pointer-events-none',
          'bg-slate-900 text-slate-100 shadow-xl',
          pos[side] ?? pos.top
        )}>
          {content}
        </div>
      )}
    </div>
  )
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function TabsGroup({ tabs, value, onChange, className }) {
  return (
    <div className={cn('inline-flex items-center gap-0.5 bg-slate-100 rounded-lg p-0.5', className)} role="tablist">
      {tabs.map(t => (
        <button
          key={t.value}
          role="tab"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-[7px] text-xs font-medium transition-all select-none cursor-pointer',
            value === t.value
              ? 'bg-white text-slate-900 shadow-sm ring-1 ring-black/5'
              : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/60',
          )}
        >
          {t.icon && <span className="opacity-75">{t.icon}</span>}
          {t.label}
        </button>
      ))}
    </div>
  )
}

// ── Callout ───────────────────────────────────────────────────────────────────
function Callout({ children, title, variant = 'default' }) {
  const v = {
    default: { bg: '#f8fafc', border: '#e8ecf0', title: '#475569', accent: '#6366f1' },
    warning: { bg: 'linear-gradient(135deg,#fffbeb,#fefce8)', border: '#fde68a', title: '#92400e', accent: '#f59e0b' },
    brand:   { bg: 'linear-gradient(135deg,#f9f7ff,#f5f0ff)', border: '#ddd6fe', title: '#5b21b6', accent: BRAND_ACCENT },
  }[variant] ?? {}
  return (
    <div style={{
      borderRadius: 10, border: `1px solid ${v.border}`, borderLeftWidth: 3, borderLeftColor: v.accent,
      background: v.bg, padding: '12px 14px',
    }}>
      {title && (
        <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: v.title, marginBottom: 7 }}>
          {title}
        </div>
      )}
      <div style={{ fontSize: 11.5, color: '#4b5563', lineHeight: 1.65 }}>{children}</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// App-specific components
// ─────────────────────────────────────────────────────────────────────────────

// ── Node Popover ──────────────────────────────────────────────────────────────
function NodePopover({ data, x, y, graphData, onClose }) {
  if (!data) return null

  const allNodes = (graphData.nodes || []).map(n => n.data || n)
  const allEdges = (graphData.edges || []).map(e => e.data || e)
  const type = data.type
  const lines = []
  const warnings = []

  if (type === 'Company') {
    const directors = allNodes.filter(n => n.type === 'Director')
    const shareholders = allNodes.filter(n => n.type === 'Shareholder')
    const totalShares = shareholders.reduce((s, n) => s + parseInt(n.shares || 0, 10), 0)
    lines.push(`${directors.length} director${directors.length !== 1 ? 's' : ''}`)
    lines.push(`${shareholders.length} shareholder${shareholders.length !== 1 ? 's' : ''}`)
    if (totalShares > 0) lines.push(`${totalShares.toLocaleString()} total shares`)
    if (data.acn) lines.push(`ACN ${data.acn}`)
  } else if (type === 'Director') {
    if (data.appointment_date) lines.push(`Appointed ${data.appointment_date}`)
    const edge = allEdges.find(e => e.source === data.id && e.type === 'CONTROLS')
    if (edge) lines.push(edge.label)
    if (data.sole_signatory) warnings.push('SOLE SIGNATORY AUTHORITY')
  } else if (type === 'Shareholder') {
    const shares = parseInt(data.shares || 0, 10)
    const cls = data.share_class || 'Unknown'
    lines.push(`${shares.toLocaleString()} ${cls} Shares`)
    const classNode = allNodes.find(n => n.type === 'ShareClass' && n.name === cls)
    if (classNode && parseInt(classNode.quantity, 10) > 0) {
      const pct = Math.round((shares / parseInt(classNode.quantity, 10)) * 100)
      lines.push(`${pct}% of ${cls} class`)
    }
    if (/Pty\s+Ltd/i.test(data.name)) warnings.push('Corporate shareholder (potential nominee)')
  } else if (type === 'ShareClass') {
    if (data.quantity) lines.push(`${parseInt(data.quantity, 10).toLocaleString()} issued`)
    if (data.undisclosed) warnings.push('NOT IN CONSTITUTION')
  } else if (type === 'UltimateHoldingCompany') {
    lines.push('Ultimate Holding Company')
  }

  const typeColors = {
    Company: '#1e293b', Director: '#4f46e5', Shareholder: '#059669',
    ShareClass: '#b45309', UltimateHoldingCompany: '#7c3aed',
  }
  const typeColor = typeColors[type] || '#64748b'
  const displayType = type === 'ShareClass' ? 'Share Class'
    : type === 'UltimateHoldingCompany' ? 'Holding Co.' : type

  return (
    <div
      className="panel-slide"
      style={{
        position: 'absolute',
        left: Math.min(x + 12, 700),
        top: Math.max(y - 30, 8),
        zIndex: 60,
        width: 230,
        background: '#fff',
        border: '1px solid #e8ecf0',
        borderRadius: 12,
        boxShadow: '0 8px 32px rgba(15,23,42,0.12), 0 2px 8px rgba(15,23,42,0.08)',
        padding: '10px 12px',
        pointerEvents: 'auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: type === 'ShareClass' ? 0 : '50%',
          transform: type === 'ShareClass' ? 'rotate(45deg)' : 'none',
          background: typeColor, flexShrink: 0,
        }} />
        <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: typeColor }}>
          {displayType}
        </span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', marginBottom: 6, lineHeight: 1.3 }}>
        {data.name}
      </div>
      {lines.map((line, i) => (
        <div key={i} style={{ fontSize: 11, color: '#64748b', lineHeight: 1.5 }}>{line}</div>
      ))}
      {warnings.map((w, i) => (
        <div key={`w${i}`} style={{
          marginTop: 6, fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em',
          background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c',
          padding: '3px 7px', borderRadius: 6,
        }}>
          {w}
        </div>
      ))}
    </div>
  )
}

function SevBadge({ severity, sm }) {
  const s = SEV[severity] ?? SEV.medium
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: sm ? 4 : 5,
      background: s.bg, border: `1px solid ${s.border}`, color: s.fg,
      padding: sm ? '1px 7px' : '2px 9px', borderRadius: 999,
      fontSize: sm ? 9 : 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', flexShrink: 0,
    }}>
      <span style={{ width: sm ? 4 : 5, height: sm ? 4 : 5, borderRadius: '50%', background: s.dot, flexShrink: 0 }} />
      {severity}
    </span>
  )
}

function DocChip({ docType }) {
  const d = DOC[docType] ?? { label: (docType || 'DOC').split('_')[0].toUpperCase(), fg: '#475569', bg: '#f1f5f9', border: '#e2e8f0' }
  return (
    <span style={{
      display: 'inline-block', background: d.bg, color: d.fg,
      border: `1px solid ${d.border}`, padding: '1.5px 6px', borderRadius: 5,
      fontSize: 10, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace',
      letterSpacing: '0.03em', flexShrink: 0,
    }}>{d.label}</span>
  )
}

function SectionLabel({ children, action }) {
  return (
    <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8' }}>
        {children}
      </span>
      {action}
    </div>
  )
}

// Sidebar skeleton while loading
function SidebarSkeleton() {
  return (
    <>
      <div className="p-4 space-y-3 border-b border-slate-100">
        <div className="flex gap-3 items-start">
          <Skeleton className="w-9 h-9 rounded-lg flex-shrink-0" />
          <div className="flex-1 space-y-2 pt-0.5">
            <Skeleton className="h-3.5 w-4/5" />
            <Skeleton className="h-2.5 w-1/2" />
          </div>
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-14 rounded-full" />
        </div>
      </div>
      <div className="px-4 pt-3.5 pb-2"><Skeleton className="h-2 w-16" /></div>
      <div className="px-3 space-y-0.5">
        {[1,2,3].map(i => (
          <div key={i} className="flex items-center gap-2 px-2 py-1.5">
            <Skeleton className="h-4 w-10 rounded" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-3 w-4" />
          </div>
        ))}
      </div>
      <Separator className="my-2" />
      <div className="px-4 pt-1 pb-2"><Skeleton className="h-2 w-12" /></div>
      <div className="px-3 space-y-2">
        {[1,2,3].map(i => (
          <div key={i} className="rounded-xl border border-slate-100 overflow-hidden">
            <Skeleton className="h-1 rounded-none w-full" />
            <div className="p-3 space-y-2">
              <div className="flex justify-between">
                <Skeleton className="h-4 w-16 rounded-full" />
                <Skeleton className="h-3 w-3" />
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
              <div className="flex justify-between items-center">
                <div className="flex gap-1.5">
                  <Skeleton className="h-4 w-10 rounded" />
                  <Skeleton className="h-3 w-3" />
                  <Skeleton className="h-4 w-12 rounded" />
                </div>
                <Skeleton className="h-3 w-12" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ── Icons ─────────────────────────────────────────────────────────────────────
const Icon = {
  Brand: () => (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="1" y="2.5"  width="16" height="3"   rx="1.5" fill="white"/>
      <rect x="1" y="7.5"  width="16" height="3"   rx="1.5" fill="white" fillOpacity="0.75"/>
      <rect x="1" y="12.5" width="16" height="3"   rx="1.5" fill="white" fillOpacity="0.45"/>
    </svg>
  ),
  Building: ({ size = 14 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  ),
  Download: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
    </svg>
  ),
  X: () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  ),
  ChevronRight: () => (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6"/>
    </svg>
  ),
  AlertCircle: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <circle cx="12" cy="16" r="0.5" fill="currentColor"/>
    </svg>
  ),
  FileSearch: ({ size = 28 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" fill="none" stroke="#c7d2fe" strokeWidth="1.5"/>
      <polyline points="14 2 14 8 20 8" stroke="#c7d2fe" strokeWidth="1.5"/>
      <circle cx="10.5" cy="14.5" r="2.5" stroke="#818cf8" strokeWidth="1.5"/>
      <line x1="12.5" y1="16.5" x2="15" y2="19" stroke="#818cf8" strokeWidth="1.5"/>
    </svg>
  ),
  Check: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M20 6L9 17l-5-5" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  FileText: () => (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  ),
  ZoomIn: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
    </svg>
  ),
  ZoomOut: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      <line x1="8" y1="11" x2="14" y2="11"/>
    </svg>
  ),
  Maximize: () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
    </svg>
  ),
  Evidence: () => (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/>
    </svg>
  ),
  Analysis: () => (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  Typology: () => (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
}

// ─────────────────────────────────────────────────────────────────────────────
// App
// ─────────────────────────────────────────────────────────────────────────────
function App() {
  const [matterId, setMatterId]             = useState(null)
  const [matter, setMatter]                 = useState(null)
  const [graphData, setGraphData]           = useState({ nodes: [], edges: [] })
  const [contradictions, setContradictions] = useState([])
  const [status, setStatus]                 = useState({ phase: 'idle', message: '', progress: 0 })
  const [wsConnected, setWsConnected]       = useState(false)
  const [selected, setSelected]             = useState(null)
  const [loading, setLoading]               = useState(false)
  const [detailTab, setDetailTab]           = useState('evidence')
  const [viewingDoc, setViewingDoc]         = useState(null)
  const [nodePopover, setNodePopover]       = useState(null)
  const [hiddenTypes, setHiddenTypes]       = useState(new Set())

  const wsRef        = useRef(null)
  const cyRef        = useRef(null)
  const cyElRef      = useRef(null)
  const panelBodyRef = useRef(null)

  // Reset tab + scroll when selection changes
  useEffect(() => {
    setDetailTab('evidence')
    if (panelBodyRef.current) panelBodyRef.current.scrollTop = 0
  }, [selected?.contradiction_id])

  // ── WebSocket ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!matterId) return
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/ws/${matterId}`)
    wsRef.current = ws
    ws.onopen    = () => setWsConnected(true)
    ws.onclose   = () => setWsConnected(false)
    ws.onerror   = () => setWsConnected(false)
    ws.onmessage = ({ data }) => {
      const m = JSON.parse(data)
      if (m.type === 'status') setStatus({ phase: m.phase, message: m.message, progress: m.progress || 0 })
      else if (m.type === 'graph_update') {
        if (m.action === 'add_node') setGraphData(p => ({ ...p, nodes: [...p.nodes, m.data] }))
        if (m.action === 'add_edge') setGraphData(p => ({ ...p, edges: [...p.edges, m.data] }))
      } else if (m.type === 'contradiction_found') setContradictions(p => [...p, m.contradiction])
      else if (m.type === 'graph_full') setGraphData(m.data)
    }
    return () => ws.close()
  }, [matterId])

  // ── Cytoscape init ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!cyElRef.current) return
    if (graphData.nodes.length === 0) {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
      return
    }
    if (cyRef.current) cyRef.current.destroy()
    const elements = [
      ...graphData.nodes.map(n => ({ group: 'nodes', data: n.data || n })),
      ...graphData.edges.map(e => {
        const d = { ...(e.data || e) }
        if (d.type === 'OWNS') d.ownershipPct = parseOwnershipPct(d.label)
        return { group: 'edges', data: d }
      }),
    ]
    const cy = cytoscape({
      container: cyElRef.current, elements, style: CY_STYLE,
      layout: { name: 'dagre', rankDir: 'BT', nodeSep: 50, rankSep: 120, padding: 48 },
      pixelRatio: window.devicePixelRatio || 1,
      minZoom: 0.12, maxZoom: 3,
    })
    cy.one('layoutstop', () => cy.fit(undefined, 48))
    cy.on('tap', 'edge[type="CONTRADICTION"]', evt => {
      const cid = evt.target.data('contradiction_id')
      const c = contradictions.find(x => x.contradiction_id === cid)
      if (c) {
        setSelected(c)
        setNodePopover(null)
      }
    })
    cy.on('tap', 'node', evt => {
      const node = evt.target
      const pos = node.renderedPosition()
      setNodePopover({ data: node.data(), x: pos.x, y: pos.y })
      setSelected(null)
    })
    cy.on('tap', evt => {
      if (evt.target === cy) {
        setSelected(null)
        setNodePopover(null)
      }
    })
    cy.on('pan', () => setNodePopover(null))
    cyRef.current = cy
  }, [graphData, contradictions])

  // ── Highlight selected ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!cyRef.current) return
    cyRef.current.elements().removeClass('highlighted dimmed')
    if (selected) {
      const edge = cyRef.current.edges().filter(e => e.data('contradiction_id') === selected.contradiction_id)
      if (edge.length > 0) {
        cyRef.current.elements().addClass('dimmed')
        edge.addClass('highlighted').removeClass('dimmed')
        edge.connectedNodes().addClass('highlighted').removeClass('dimmed')
      }
    }
  }, [selected])

  // ── Filter by node type ────────────────────────────────────────────────────
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current
    cy.nodes().forEach(node => {
      const type = node.data('type')
      if (hiddenTypes.has(type)) {
        node.hide()
      } else {
        node.show()
      }
    })
    cy.edges().forEach(edge => {
      const srcType = edge.source().data('type')
      const tgtType = edge.target().data('type')
      if (hiddenTypes.has(srcType) || hiddenTypes.has(tgtType)) {
        edge.hide()
      } else {
        edge.show()
      }
    })
  }, [hiddenTypes, graphData])

  const fit = () => cyRef.current?.fit(undefined, 48)

  // ── Load fixture ───────────────────────────────────────────────────────────
  const loadFixture = useCallback(async (fixture) => {
    setLoading(true)
    setGraphData({ nodes: [], edges: [] })
    setContradictions([])
    setSelected(null)
    setMatter(null)
    setNodePopover(null)
    setViewingDoc(null)
    setHiddenTypes(new Set())
    setStatus({ phase: 'loading', message: `Analysing Fixture ${fixture}...`, progress: 0.05 })
    try {
      const data = await fetch(`/demo?fixture=${fixture}`).then(r => r.json())
      setMatterId(data.matter_id)
      const [mRes, gRes, cRes] = await Promise.all([
        fetch(`/matters/${data.matter_id}`),
        fetch(`/matters/${data.matter_id}/graph`),
        fetch(`/matters/${data.matter_id}/contradictions`),
      ])
      setMatter(await mRes.json())
      setGraphData(await gRes.json())
      const cons = await cRes.json()
      setContradictions(cons)
      setStatus({
        phase: 'complete',
        message: cons.length ? `${cons.length} flag${cons.length > 1 ? 's' : ''} detected` : 'No contradictions found',
        progress: 1,
      })
    } catch (err) {
      setStatus({ phase: 'error', message: err.message, progress: 0 })
    } finally {
      setLoading(false)
    }
  }, [])

  const downloadCDD = useCallback(async () => {
    if (!matterId) return
    const res  = await fetch(`/matters/${matterId}/generate-cdd`, { method: 'POST' })
    const blob = await res.blob()
    const url  = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), {
      href: url,
      download: `CDD_${(matter?.entity_name || 'Report').replace(/\s+/g, '_')}.pdf`,
    }).click()
    URL.revokeObjectURL(url)
  }, [matterId, matter])

  const confirmFlag = useCallback(async (cid) => {
    if (!matterId) return
    await fetch(`/matters/${matterId}/contradictions/${cid}/confirm`, { method: 'POST' })
    setContradictions(p => p.map(c => c.contradiction_id === cid ? { ...c, confirmed: true } : c))
    setSelected(p => p?.contradiction_id === cid ? { ...p, confirmed: true } : p)
  }, [matterId])

  // ── Derived ────────────────────────────────────────────────────────────────
  const hasGraph       = graphData.nodes.length > 0
  const confirmedCount = contradictions.filter(c => c.confirmed).length
  const sim            = selected?.cosine_similarity ?? 0
  const simPct         = Math.round(sim * 100)
  const simColor       = sim > 0.8 ? '#dc2626' : sim > 0.7 ? '#c2410c' : '#b45309'
  const statusDot      = { complete: '#10b981', error: '#ef4444' }[status.phase] ?? '#6366f1'
  const statusIsError  = status.phase === 'error'

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: '#f8fafc' }}>

      {loading && <div className="loading-bar" />}

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <header
        className="flex items-center px-5 gap-4 flex-shrink-0"
        style={{
          height: 56, zIndex: 20,
          background: 'rgba(255,255,255,0.98)',
          borderBottom: '1px solid rgba(0,0,0,0.06)',
          backdropFilter: 'blur(8px)',
          boxShadow: '0 1px 0 rgba(0,0,0,0.04)',
        }}
      >
        {/* Brand */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center justify-center flex-shrink-0"
               style={{ width: 36, height: 36, borderRadius: 10, background: BRAND_GRAD, boxShadow: BRAND_GLOW }}>
            <Icon.Brand />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 900, letterSpacing: '-0.04em', color: '#0f172a', lineHeight: 1 }}>STRATUM</div>
            <div style={{ fontSize: 8, fontWeight: 600, letterSpacing: '0.1em', color: '#94a3b8', marginTop: 2, textTransform: 'uppercase' }}>
              Beneficial Ownership Intelligence
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 22, background: '#e8ecf0', flexShrink: 0 }} />

        {/* Status pill */}
        {status.message && (
          <div className="flex items-center gap-2 min-w-0 overflow-hidden" style={{
            background: statusIsError ? '#fff1f2' : '#f8fafc',
            border: `1px solid ${statusIsError ? '#fecdd3' : '#e8ecf0'}`,
            borderRadius: 20, padding: '3px 10px 3px 8px', maxWidth: 380,
          }}>
            <div className="relative flex-shrink-0" style={{ width: 8, height: 8 }}>
              <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: statusDot,
                             opacity: status.phase === 'complete' ? 0.3 : 0 }}
                    className={status.phase === 'complete' ? 'ws-ping' : ''} />
              <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: statusDot }} />
            </div>
            <span className="truncate" style={{ fontSize: 11.5, color: '#64748b' }}>
              {matter && <span style={{ fontWeight: 600, color: '#1e293b' }}>{matter.entity_name} · </span>}
              {status.message}
            </span>
          </div>
        )}

        <div className="flex-1" />

        {/* Fixture buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button variant="outline" size="sm" onClick={() => loadFixture('A')} disabled={loading}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
            Fixture A
          </Button>
          <Button variant="outline" size="sm" onClick={() => loadFixture('B')} disabled={loading}
                  style={{ borderColor: '#fecdd3', background: '#fff8f8', color: '#c53030' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
            Fixture B | 3 Flags
          </Button>

          {/* WS indicator */}
          {matterId && (
            <div className="flex items-center gap-1.5 pl-1">
              <div className="relative" style={{ width: 8, height: 8 }}>
                {wsConnected && (
                  <span className="ws-ping"
                        style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: '#10b981', opacity: 0.3 }} />
                )}
                <span style={{ position: 'absolute', inset: 0, borderRadius: '50%',
                               background: wsConnected ? '#10b981' : '#cbd5e1', transition: 'background 0.3s' }} />
              </div>
              <span style={{ fontSize: 10, color: '#94a3b8', fontWeight: 500 }}>
                {wsConnected ? 'Live' : 'Offline'}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Sidebar ─────────────────────────────────────────────────────── */}
        <aside className="flex flex-col flex-shrink-0 overflow-hidden"
               style={{ width: 288, background: '#fff', borderRight: '1px solid #e8ecf0' }}>

          {loading ? <SidebarSkeleton /> : (
            <>
              {/* Entity card */}
              <div style={{ padding: '14px 16px', borderBottom: '1px solid #f1f5f9', flexShrink: 0 }}>
                {matter ? (
                  <>
                    <div className="flex items-start gap-3">
                      <div className="flex items-center justify-center flex-shrink-0"
                           style={{ width: 38, height: 38, borderRadius: 10,
                                    background: 'linear-gradient(135deg,#f1f5f9,#e8ecf0)',
                                    border: '1px solid #e2e8f0' }}>
                        <span style={{ color: '#64748b' }}><Icon.Building /></span>
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13.5, fontWeight: 700, color: '#0f172a', lineHeight: 1.3, letterSpacing: '-0.01em' }}>
                          {matter.entity_name}
                        </div>
                        <div style={{ fontSize: 10, color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace', marginTop: 3 }}>
                          ACN {matter.acn}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Badge variant="secondary">
                        <Icon.FileText />
                        {matter.documents?.length ?? 0} docs
                      </Badge>
                      {contradictions.length > 0 ? (
                        <Badge variant="destructive">
                          <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
                          {contradictions.length} flags
                        </Badge>
                      ) : (
                        <Badge variant="success">
                          <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                          Clean
                        </Badge>
                      )}
                      {confirmedCount > 0 && (
                        <Badge variant="violet">{confirmedCount} CDD</Badge>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center flex-shrink-0"
                         style={{ width: 38, height: 38, borderRadius: 10, background: '#f8fafc', border: '1px solid #f1f5f9', color: '#d1d5db' }}>
                      <Icon.Building />
                    </div>
                    <div>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: '#94a3b8' }}>No entity loaded</div>
                      <div style={{ fontSize: 10.5, color: '#d1d5db', marginTop: 2 }}>Select a fixture to begin</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Documents */}
              {matter?.documents && (
                <>
                  <SectionLabel>Source Documents</SectionLabel>
                  <div style={{ padding: '0 10px 6px', flexShrink: 0 }}>
                    {matter.documents.map((doc, i) => {
                      const isViewing = viewingDoc?.document_id === doc.document_id
                      return (
                        <div
                          key={i}
                          onClick={() => setViewingDoc(isViewing ? null : doc)}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            padding: '6px 8px', borderRadius: 8, cursor: 'pointer',
                            background: isViewing ? '#f0f0ff' : 'transparent',
                            border: isViewing ? '1px solid #c7d2fe' : '1px solid transparent',
                            transition: 'all 0.12s',
                          }}
                        >
                          <DocChip docType={doc.doc_type} />
                          <span style={{ fontSize: 11.5, color: isViewing ? '#3730a3' : '#4b5563', fontWeight: isViewing ? 600 : 400, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={doc.filename}>
                            {doc.filename}
                          </span>
                          <Tooltip content="View source document" side="left">
                            <span style={{ fontSize: 9, color: isViewing ? '#4f46e5' : '#cbd5e1', flexShrink: 0 }}>
                              <Icon.Evidence />
                            </span>
                          </Tooltip>
                        </div>
                      )
                    })}
                  </div>
                  <Separator />
                </>
              )}

              {/* Flags */}
              <SectionLabel
                action={contradictions.length > 0 && (
                  <Badge variant={contradictions.length > 0 ? 'destructive' : 'success'}>
                    {contradictions.length}
                  </Badge>
                )}
              >
                Flags
              </SectionLabel>

              <div style={{ flex: 1, overflowY: 'auto', padding: '0 10px 10px' }}>
                {contradictions.length === 0 && matter && !loading && (
                  <Card style={{ overflow: 'hidden' }}>
                    <div style={{ height: 3, background: 'linear-gradient(90deg,#10b981,#34d399)' }} />
                    <CardContent style={{ padding: '16px 12px', textAlign: 'center' }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: '50%',
                        background: '#f0fdf4', border: '1px solid #bbf7d0',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        margin: '0 auto 10px',
                      }}><Icon.Check /></div>
                      <div style={{ fontSize: 12.5, fontWeight: 700, color: '#065f46', marginBottom: 3 }}>All Clear</div>
                      <div style={{ fontSize: 10.5, color: '#059669' }}>No contradictions detected</div>
                    </CardContent>
                  </Card>
                )}

                {/* Flag cards */}
                {contradictions.map((c, i) => {
                  const sev  = SEV[c.severity] ?? SEV.medium
                  const isOn = selected?.contradiction_id === c.contradiction_id
                  return (
                    <div
                      key={c.contradiction_id ?? i}
                      className={cn('flag-card rounded-xl border overflow-hidden mb-1.5', isOn && 'flag-card-active')}
                      onClick={() => setSelected(isOn ? null : c)}
                      style={{
                        borderColor: isOn ? '#8b5cf6' : '#f1f5f9',
                        background: isOn ? 'linear-gradient(135deg,#faf7ff,#f5f0ff)' : '#fff',
                        boxShadow: isOn ? '0 0 0 1px rgba(139,92,246,0.15), 0 4px 20px rgba(124,58,237,0.1)' : '0 1px 3px rgba(15,23,42,0.04)',
                        cursor: 'pointer', userSelect: 'none',
                      }}
                    >
                      {/* Gradient severity strip */}
                      <div style={{ height: 3, background: sev.strip }} />

                      <div style={{ padding: '9px 11px 11px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                          <SevBadge severity={c.severity} sm />
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                            {c.confirmed && (
                              <Badge variant="violet" className="text-[9px]">CDD</Badge>
                            )}
                            <span style={{ color: isOn ? '#8b5cf6' : '#d1d5db' }}><Icon.ChevronRight /></span>
                          </div>
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#1e293b', lineHeight: 1.4, marginBottom: 9 }}>
                          {c.typology_label}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                            <DocChip docType={c.source_doc_type} />
                            <span style={{ color: '#d1d5db', fontSize: 9 }}>→</span>
                            <DocChip docType={c.target_doc_type} />
                          </div>
                          <Tooltip content="Cosine similarity score" side="left">
                            <span style={{ fontSize: 9.5, fontFamily: 'JetBrains Mono, monospace', color: '#94a3b8', cursor: 'default' }}>
                              {c.cosine_similarity?.toFixed(4)}
                            </span>
                          </Tooltip>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* CDD Download */}
              {matter && (
                <div style={{ padding: '10px 10px 12px', borderTop: '1px solid #f1f5f9', flexShrink: 0 }}>
                  <Button variant="brand" className="w-full h-9 hover-lift" onClick={downloadCDD}>
                    <Icon.Download />
                    Download CDD Report
                  </Button>
                </div>
              )}
            </>
          )}
        </aside>

        {/* ── Graph canvas ─────────────────────────────────────────────────── */}
        <div className="graph-bg flex-1 relative overflow-hidden">

          {!hasGraph ? (
            /* Empty state */
            <div className="absolute inset-0 flex items-center justify-center">
              <div style={{ textAlign: 'center', maxWidth: 380, padding: '0 32px' }}>
                <div className="hover-lift" style={{
                  width: 72, height: 72, borderRadius: 20,
                  background: '#fff', border: '1px solid #e8ecf0',
                  boxShadow: '0 4px 24px rgba(15,23,42,0.06)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 20px',
                }}>
                  <Icon.FileSearch size={34} />
                </div>
                <div style={{ fontSize: 17, fontWeight: 800, color: '#1e293b', letterSpacing: '-0.025em', marginBottom: 8 }}>
                  Beneficial Ownership Graph
                </div>
                <div style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.65, marginBottom: 28 }}>
                  Load a fixture to detect cross-document contradictions and visualise the corporate ownership structure.
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
                  <Button variant="outline" size="sm" className="hover-lift" onClick={() => loadFixture('A')}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#10b981' }} />
                    Fixture A
                    <span style={{ fontSize: 10.5, color: '#94a3b8', fontWeight: 400 }}>Clean</span>
                  </Button>
                  <Button variant="outline" size="sm" className="hover-lift" onClick={() => loadFixture('B')}
                          style={{ borderColor: '#fecdd3', background: '#fff8f8', color: '#c53030' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#ef4444' }} />
                    Fixture B
                    <span style={{ fontSize: 10.5, color: '#fca5a5', fontWeight: 400 }}>3 flags</span>
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div ref={cyElRef} id="cy" className="absolute inset-0" />
          )}

          {/* Zoom controls */}
          {hasGraph && (
            <div style={{ position: 'absolute', top: 14, right: 14, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[
                { icon: <Icon.ZoomIn />,  fn: () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25), tip: 'Zoom in' },
                { icon: <Icon.ZoomOut />, fn: () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8),  tip: 'Zoom out' },
                { icon: <Icon.Maximize />, fn: fit, tip: 'Fit to screen' },
              ].map((b, i) => (
                <Tooltip key={i} content={b.tip} side="left">
                  <button
                    className="btn-icon"
                    onClick={b.fn}
                    style={{
                      width: 32, height: 32, borderRadius: 8,
                      background: 'rgba(255,255,255,0.95)', border: '1px solid #e2e8f0',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: '#64748b', cursor: 'pointer',
                      boxShadow: '0 1px 4px rgba(15,23,42,0.06)', backdropFilter: 'blur(4px)',
                    }}
                  >{b.icon}</button>
                </Tooltip>
              ))}
            </div>
          )}

          {/* Legend */}
          {hasGraph && (
            <div style={{
              position: 'absolute', bottom: 16, left: 16,
              background: 'rgba(255,255,255,0.97)', border: '1px solid #e8ecf0',
              borderRadius: 12, padding: '11px 13px',
              boxShadow: '0 2px 16px rgba(15,23,42,0.07)',
              backdropFilter: 'blur(8px)', minWidth: 126,
            }}>
              <div style={{ marginBottom: 9 }}>
                <div style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8' }}>
                  Legend
                </div>
                <div style={{ fontSize: 7.5, color: '#cbd5e1', marginTop: 1 }}>Click to filter</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {[
                  { color: '#1e293b', shape: 'r', label: 'Company',     type: 'Company' },
                  { color: '#4f46e5', shape: 'c', label: 'Director',    type: 'Director' },
                  { color: '#059669', shape: 'c', label: 'Shareholder', type: 'Shareholder' },
                  { color: '#b45309', shape: 'd', label: 'Share Class', type: 'ShareClass' },
                ].map(n => {
                  const isHidden = hiddenTypes.has(n.type)
                  return (
                    <div
                      key={n.label}
                      onClick={() => {
                        setHiddenTypes(prev => {
                          const next = new Set(prev)
                          if (next.has(n.type)) next.delete(n.type)
                          else next.add(n.type)
                          return next
                        })
                      }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        fontSize: 11, color: isHidden ? '#cbd5e1' : '#475569',
                        cursor: 'pointer', userSelect: 'none',
                        opacity: isHidden ? 0.45 : 1,
                        transition: 'opacity 0.15s, color 0.15s',
                      }}
                    >
                      {n.shape === 'r' && <div style={{ width: 13, height: 8,  background: isHidden ? '#e2e8f0' : n.color, borderRadius: 2, flexShrink: 0, transition: 'background 0.15s' }} />}
                      {n.shape === 'c' && <div style={{ width: 9,  height: 9,  background: isHidden ? '#e2e8f0' : n.color, borderRadius: '50%', flexShrink: 0, transition: 'background 0.15s' }} />}
                      {n.shape === 'd' && <div style={{ width: 8,  height: 8,  background: isHidden ? '#e2e8f0' : n.color, transform: 'rotate(45deg)', flexShrink: 0, transition: 'background 0.15s' }} />}
                      <span style={{ textDecoration: isHidden ? 'line-through' : 'none', transition: 'text-decoration 0.15s' }}>{n.label}</span>
                    </div>
                  )
                })}
              </div>
              <Separator className="my-2.5" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {[
                  { color: '#f87171', dash: true,  label: 'Contradiction' },
                  { color: '#34d399', dash: false, label: 'Ownership' },
                  { color: '#818cf8', dash: false, label: 'Control' },
                ].map(e => (
                  <div key={e.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#475569' }}>
                    <div style={{ width: 16, height: 0, border: `1.5px ${e.dash ? 'dashed' : 'solid'} ${e.color}`, flexShrink: 0 }} />
                    {e.label}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Node Popover ──────────────────────────────────────────────── */}
          {nodePopover && !selected && !viewingDoc && (
            <NodePopover
              data={nodePopover.data}
              x={nodePopover.x}
              y={nodePopover.y}
              graphData={graphData}
              onClose={() => setNodePopover(null)}
            />
          )}

          {/* ── Document Viewer Panel ────────────────────────────────────── */}
          {viewingDoc && !selected && (
            <div
              className="panel-slide absolute top-0 right-0 bottom-0"
              style={{
                width: 520, background: '#fff',
                borderLeft: '1px solid #e8ecf0',
                boxShadow: '-8px 0 48px rgba(15,23,42,0.1)',
                zIndex: 50, display: 'flex', flexDirection: 'column',
              }}
            >
              {/* Header */}
              <div style={{
                padding: '0 18px', height: 54, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                borderBottom: '1px solid #f1f5f9',
                background: 'linear-gradient(to right, #f0f0ff, #ffffff)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <DocChip docType={viewingDoc.doc_type} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>
                    Source Document
                  </span>
                </div>
                <Button variant="ghost" size="icon" className="btn-icon h-8 w-8 rounded-lg" onClick={() => setViewingDoc(null)}>
                  <Icon.X />
                </Button>
              </div>

              {/* Document metadata */}
              <div style={{ padding: '12px 18px', borderBottom: '1px solid #f1f5f9', flexShrink: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>
                  {viewingDoc.filename}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Badge variant="secondary">
                    {viewingDoc.doc_type?.replace(/_/g, ' ')}
                  </Badge>
                  <Badge variant="outline">
                    {viewingDoc.chunks?.length || 0} embedded chunks
                  </Badge>
                  {viewingDoc.sha256_hash && (
                    <Tooltip content={viewingDoc.sha256_hash} side="bottom">
                      <Badge variant="outline" style={{ fontFamily: 'JetBrains Mono, monospace', cursor: 'default' }}>
                        SHA-256: {viewingDoc.sha256_hash?.slice(0, 12)}...
                      </Badge>
                    </Tooltip>
                  )}
                </div>
              </div>

              {/* Raw document text */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '16px 18px' }}>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: 10 }}>
                  Full Document Text
                </div>
                <div style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 11, lineHeight: 1.7, color: '#374151',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  background: '#f8fafc', border: '1px solid #e8ecf0',
                  borderRadius: 10, padding: '14px 16px',
                }}>
                  {viewingDoc.raw_text || '(No text content available)'}
                </div>

                {/* Chunks breakdown */}
                {viewingDoc.chunks && viewingDoc.chunks.length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: 10 }}>
                      Embedded Chunks ({viewingDoc.chunks.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {viewingDoc.chunks.map((chunk, ci) => (
                        <Card key={ci}>
                          <div style={{ padding: '10px 12px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                              <Badge variant="indigo" style={{ fontSize: 9 }}>
                                {chunk.section_type?.replace(/_/g, ' ')}
                              </Badge>
                              <span style={{ fontSize: 9, color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace' }}>
                                chunk {ci + 1}
                              </span>
                            </div>
                            <div style={{
                              fontSize: 10.5, lineHeight: 1.6, color: '#4b5563',
                              maxHeight: 80, overflowY: 'auto',
                            }}>
                              {chunk.text_snippet}
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Detail Panel ──────────────────────────────────────────────── */}
          {selected && (
            <div
              className="panel-slide absolute top-0 right-0 bottom-0"
              style={{
                width: 500, background: '#fff',
                borderLeft: '1px solid #e8ecf0',
                boxShadow: '-8px 0 48px rgba(15,23,42,0.1)',
                zIndex: 50, display: 'flex', flexDirection: 'column',
              }}
            >
              {/* Panel header */}
              <div style={{
                padding: '0 18px', height: 54, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                borderBottom: '1px solid #f1f5f9',
                background: 'linear-gradient(to right, #fafbff, #ffffff)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#94a3b8' }}><Icon.AlertCircle /></span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', letterSpacing: '-0.01em' }}>
                    Contradiction Detail
                  </span>
                  <SevBadge severity={selected.severity} />
                </div>
                <Button variant="ghost" size="icon" className="btn-icon h-8 w-8 rounded-lg" onClick={() => setSelected(null)}>
                  <Icon.X />
                </Button>
              </div>

              {/* Similarity bar under header */}
              <div style={{ height: 3, background: '#f1f5f9', flexShrink: 0 }}>
                <div style={{
                  height: '100%',
                  width: `${simPct}%`,
                  background: 'linear-gradient(90deg,#fbbf24,#f97316,#ef4444)',
                  transition: 'width 0.8s cubic-bezier(0.16,1,0.3,1)',
                }} />
              </div>

              {/* Typology title + similarity hero */}
              <div style={{ padding: '16px 18px 0', flexShrink: 0 }}>
                <h2 style={{ fontSize: 15, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: 6, lineHeight: 1.3 }}>
                  {selected.typology_label}
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14 }}>
                  <Tooltip content="Cross-document cosine similarity score (higher = more similar, counter-intuitive for contradictions)" side="bottom">
                    <div style={{ cursor: 'default' }}>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, fontSize: 34, lineHeight: 1, color: simColor, letterSpacing: '-0.03em' }}>
                        {selected.cosine_similarity?.toFixed(4)}
                      </span>
                    </div>
                  </Tooltip>
                  <div style={{ flex: 1 }}>
                    <Progress
                      value={simPct}
                      className="mb-1.5"
                      barStyle={{ background: 'linear-gradient(90deg,#fbbf24,#f97316,#ef4444)' }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5, color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace' }}>
                      <span>0.00</span>
                      <span>threshold 0.65</span>
                      <span>1.00</span>
                    </div>
                  </div>
                </div>

                {/* Tabs */}
                <TabsGroup
                  value={detailTab}
                  onChange={setDetailTab}
                  className="w-full"
                  tabs={[
                    { value: 'evidence',  label: 'Evidence',  icon: <Icon.Evidence /> },
                    { value: 'analysis',  label: 'Analysis',  icon: <Icon.Analysis /> },
                    { value: 'typology',  label: 'Typology',  icon: <Icon.Typology /> },
                  ]}
                />
              </div>

              <Separator className="mt-3" />

              {/* Scrollable tab content */}
              <div ref={panelBodyRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 18px' }}>

                {/* ─ Evidence tab ─ */}
                {detailTab === 'evidence' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: 10 }}>
                        Conflicting Passages
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        {[
                          {
                            label: selected.source_doc_type?.replace(/_/g, ' '),
                            docType: selected.source_doc_type,
                            text: selected.source_text,
                            file: selected.source_document,
                            bg: '#f0f0ff', border: '#c7d2fe', fg: '#4f46e5',
                          },
                          {
                            label: selected.target_doc_type?.replace(/_/g, ' '),
                            docType: selected.target_doc_type,
                            text: selected.target_text,
                            file: selected.target_document,
                            bg: '#fef8f8', border: '#fecdd3', fg: '#dc2626',
                          },
                        ].map((p, i) => (
                          <div key={i}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 7 }}>
                              <DocChip docType={p.docType} />
                              <span style={{ fontSize: 10, fontWeight: 600, color: p.fg, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                {p.label}
                              </span>
                            </div>
                            <div style={{
                              borderRadius: 9, background: p.bg, border: `1px solid ${p.border}`,
                              padding: '9px 10px', fontSize: 10.5, color: '#374151', lineHeight: 1.6,
                              maxHeight: 160, overflowY: 'auto',
                            }}>
                              {p.text}
                            </div>
                            <div style={{ fontSize: 9, color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace', marginTop: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {p.file}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <Callout title="Typology description" variant="default">
                      {selected.typology_description}
                    </Callout>
                  </div>
                )}

                {/* ─ Analysis tab ─ */}
                {detailTab === 'analysis' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <Callout title="AML/CTF Assessment" variant="warning">
                      {selected.explanation}
                    </Callout>
                    <Card>
                      <CardHeader>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <CardTitle style={{ fontSize: 12 }}>Similarity Metrics</CardTitle>
                          <Badge variant="outline">
                            <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 700, color: simColor }}>
                              {selected.cosine_similarity?.toFixed(4)}
                            </span>
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11.5 }}>
                          {[
                            { label: 'Cosine Similarity',  value: selected.cosine_similarity?.toFixed(6) },
                            { label: 'Cosine Distance',    value: selected.cosine_distance?.toFixed(6) },
                            { label: 'Typology Match',     value: (selected.typology_similarity * 100).toFixed(1) + '%' },
                            { label: 'Threshold',          value: '0.65 (configurable)' },
                          ].map(row => (
                            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid #f8fafc' }}>
                              <span style={{ color: '#64748b' }}>{row.label}</span>
                              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: '#1e293b', fontSize: 11 }}>
                                {row.value}
                              </span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* ─ Typology tab ─ */}
                {detailTab === 'typology' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <Callout title="AUSTRAC / FATF Typology" variant="brand">
                      <div style={{ marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                          <div style={{
                            width: 32, height: 32, borderRadius: 8,
                            background: BRAND_GRAD, boxShadow: BRAND_GLOW,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                          }}><Icon.Brand /></div>
                          <div>
                            <div style={{ fontSize: 13.5, fontWeight: 800, color: '#4c1d95', letterSpacing: '-0.01em', marginBottom: 2 }}>
                              {selected.typology_label}
                            </div>
                            <div style={{ fontSize: 9.5, fontFamily: 'JetBrains Mono, monospace', color: '#8b5cf6' }}>
                              {selected.typology_id}
                            </div>
                          </div>
                        </div>
                      </div>
                      {selected.typology_description}
                    </Callout>

                    <Card>
                      <CardHeader>
                        <CardTitle style={{ fontSize: 12 }}>Source Documents</CardTitle>
                        <CardDescription>Documents contributing to this contradiction flag</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {[
                            { label: 'Source', docType: selected.source_doc_type, file: selected.source_document, section: selected.source_section },
                            { label: 'Target', docType: selected.target_doc_type, file: selected.target_document, section: selected.target_section },
                          ].map((d, i) => (
                            <div key={i} style={{
                              display: 'flex', alignItems: 'flex-start', gap: 10,
                              padding: '9px 10px', borderRadius: 8, background: '#f8fafc', border: '1px solid #f1f5f9',
                            }}>
                              <DocChip docType={d.docType} />
                              <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {d.file}
                                </div>
                                <div style={{ fontSize: 9.5, color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>
                                  §{d.section?.replace(/_/g, ' ')}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <Card style={{ flex: 1 }}>
                        <CardHeader style={{ padding: '10px 12px 4px' }}>
                          <CardDescription>Severity</CardDescription>
                        </CardHeader>
                        <CardContent style={{ padding: '4px 12px 10px' }}>
                          <SevBadge severity={selected.severity} />
                        </CardContent>
                      </Card>
                      <Card style={{ flex: 1 }}>
                        <CardHeader style={{ padding: '10px 12px 4px' }}>
                          <CardDescription>CDD Status</CardDescription>
                        </CardHeader>
                        <CardContent style={{ padding: '4px 12px 10px' }}>
                          {selected.confirmed
                            ? <Badge variant="success">Added to CDD</Badge>
                            : <Badge variant="secondary">Pending review</Badge>
                          }
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                )}

                {/* Confirm CTA */}
                <div style={{ marginTop: 16 }}>
                  <Button
                    variant={selected.confirmed ? 'success' : 'brand'}
                    className={cn('w-full hover-lift', !selected.confirmed && '')}
                    onClick={() => !selected.confirmed && confirmFlag(selected.contradiction_id)}
                    disabled={selected.confirmed}
                  >
                    {selected.confirmed ? 'Added to CDD Record' : 'Add to CDD Record'}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const root = ReactDOM.createRoot(document.getElementById('root'))
root.render(React.createElement(App))
