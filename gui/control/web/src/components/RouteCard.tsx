import React from 'react'
import { StatusPill } from './StatusPill'

export function RouteCard({ title, subtitle, status, accent }: { title: string; subtitle: string; status: string; accent: 'mesh' | 'splat' | 'shared' }) {
  return (
    <div className={`route-card ${accent}`}>
      <div>
        <div className="eyebrow">{subtitle}</div>
        <h3>{title}</h3>
      </div>
      <StatusPill value={status} />
    </div>
  )
}
