import React from 'react'

export function StatusPill({ value }: { value: string }) {
  const key = value.toUpperCase()
  const cls = key === 'READY' || key === 'COMPLETE' ? 'status good' : key.includes('PROGRESS') ? 'status active' : 'status muted'
  return <span className={cls}>{value}</span>
}
