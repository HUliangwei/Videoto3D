import React, { useState } from 'react'
import type { RuntimePaths } from '../types'

function CopyRow({ label, value, meta }: { label: string; value: string; meta?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 900)
    } catch {}
  }
  return <div className="path-row"><div className="path-label"><span>{label}</span>{meta ? <small>{meta}</small> : null}</div><code title={value}>{value || '—'}</code><button className="copy-path" disabled={!value} onClick={copy}>{copied ? 'Copied' : 'Copy Path'}</button></div>
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="path-group"><div className="eyebrow">{title}</div>{children}</section>
}

export function PathInspector({ paths }: { paths?: RuntimePaths }) {
  if (!paths) return null
  return <section className="paths-section"><div className="section-title"><div className="eyebrow">PROJECT INSPECTOR</div><h2>Paths & Runtime</h2><p>只读查看当前项目、环境、工具和 Run 路径；本版不在网页中修改工具配置。</p></div><div className="panel path-panel">
    <Group title="PROJECT">
      <CopyRow label="Root" value={paths.project.root} /><CopyRow label="Workspace" value={paths.project.workspace} /><CopyRow label="Runtime" value={paths.project.runtime} />
    </Group>
    <Group title="ENVIRONMENTS">
      <CopyRow label="Core Python" value={paths.environments.core} /><CopyRow label="SEG Python" value={paths.environments.seg} /><CopyRow label="GUI Python" value={paths.environments.gui} />
    </Group>
    <Group title="TOOLS">
      {Object.entries(paths.tools).map(([name, entry]) => <CopyRow key={name} label={name.toUpperCase()} value={entry.path} meta={entry.source || undefined} />)}
    </Group>
    <Group title="CURRENT RUN">
      {Object.entries(paths.run).map(([name, value]) => <CopyRow key={name} label={name.toUpperCase()} value={value} />)}
    </Group>
  </div></section>
}
