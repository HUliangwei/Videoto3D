import React, { useRef, useState } from 'react'

type Point = { x: number; y: number }
function clamp(v: number) { return Math.max(0, Math.min(1, v)) }

export function RoiSelector({ src, onConfirm, disabled = false }: { src: string; onConfirm: (box: [number,number,number,number]) => void; disabled?: boolean }) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [start, setStart] = useState<Point | null>(null)
  const [end, setEnd] = useState<Point | null>(null)
  const point = (e: React.PointerEvent) => {
    const rect = imgRef.current!.getBoundingClientRect()
    return { x: clamp((e.clientX - rect.left) / rect.width), y: clamp((e.clientY - rect.top) / rect.height) }
  }
  const boxStyle = start && end ? {
    left: `${Math.min(start.x,end.x)*100}%`, top: `${Math.min(start.y,end.y)*100}%`,
    width: `${Math.abs(end.x-start.x)*100}%`, height: `${Math.abs(end.y-start.y)*100}%`,
  } : undefined
  const confirm = () => {
    const img = imgRef.current
    if (!img || !start || !end) return
    const x0 = Math.round(Math.min(start.x,end.x) * img.naturalWidth), y0 = Math.round(Math.min(start.y,end.y) * img.naturalHeight)
    const x1 = Math.round(Math.max(start.x,end.x) * img.naturalWidth), y1 = Math.round(Math.max(start.y,end.y) * img.naturalHeight)
    if (x1 > x0 && y1 > y0) onConfirm([x0,y0,x1,y1])
  }
  return <div className="roi-panel panel">
    <div className="roi-copy"><div><div className="eyebrow">SAM2 TARGET</div><h3>Drag a box around the subject</h3></div><button className="primary-button" disabled={disabled || !boxStyle} onClick={confirm}>{disabled ? 'Generating Masks…' : 'Generate Masks'}</button></div>
    <div className="roi-stage" onPointerDown={(e) => { if(disabled) return; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); const p=point(e); setStart(p); setEnd(p) }} onPointerMove={(e) => { if(start && (e.buttons & 1)) setEnd(point(e)) }} onPointerUp={(e) => { if(start) setEnd(point(e)) }}>
      <img ref={imgRef} src={src} draggable={false} />
      {boxStyle && <div className="roi-box" style={boxStyle} />}
    </div>
    <p className="form-help">只需要框主体一次；坐标会转换回原始首帧像素并交给现有 SAM2 pipeline。</p>
  </div>
}
