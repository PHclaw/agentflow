/* 演示应用：同页两个实例，验证并行互不干扰 */
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { PixelToggle } from './PixelToggle';

function App() {
  const [a, setA] = useState(false);
  const [b, setB] = useState(true);

  return (
    <div className="list">
      <div className="row">
        <span>夜间模式（默认夜间）</span>
        <PixelToggle checked={a} onCheckedChange={setA} />
      </div>
      <div className="row">
        <span>日间模式（默认日间）</span>
        <PixelToggle checked={b} onCheckedChange={setB} sound={false} />
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
