import React from 'react'
import ReactDOM from 'react-dom/client'
import { AssetViewer } from '../../src'

const params = new URLSearchParams(location.search)
const type = params.get('type') === 'splat' ? 'splat' : 'glb'
const src = params.get('src') || ''

ReactDOM.createRoot(document.getElementById('root')!).render(
  <div style={{position:'fixed', inset:0, background:'#07090d'}}>
    {src ? <AssetViewer type={type} src={src} /> : <div style={{color:'white', padding:32, fontFamily:'system-ui'}}>Use ?type=glb|splat&src=/path/to/asset</div>}
  </div>
)
