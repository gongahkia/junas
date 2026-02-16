import { useEffect, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export default function LiveView() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [running, setRunning] = useState(false);
  const [useLocalDetection, setUseLocalDetection] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [detections, setDetections] = useState([]);
  const [avgByLabel, setAvgByLabel] = useState({});
  const [trackGrams, setTrackGrams] = useState([]);
  const [macros, setMacros] = useState(null);
  const [narrative, setNarrative] = useState('');
  const [macrosLoading, setMacrosLoading] = useState(false);
  const [macrosError, setMacrosError] = useState('');
  const [frameIntervalMs, setFrameIntervalMs] = useState(150);
  const [history, setHistory] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  const [fps, setFps] = useState(0);
  const fpsRef = useRef({ frames: 0, lastTime: Date.now() });
  const rollingWindow = useRef({});
  const tracksRef = useRef([]);

  const iou = (a, b) => {
    const x1 = Math.max(a.x, b.x);
    const y1 = Math.max(a.y, b.y);
    const x2 = Math.min(a.x + a.width, b.x + b.width);
    const y2 = Math.min(a.y + a.height, b.y + b.height);
    const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
    const union = a.width * a.height + b.width * b.height - inter;
    return union > 0 ? inter / union : 0;
  };

  const nonMaxSuppression = (detections, iouThreshold = 0.5) => {
    if (!detections || detections.length === 0) return [];

    // Sort by confidence (descending)
    const sorted = [...detections].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    const keep = [];

    for (let i = 0; i < sorted.length; i++) {
      const current = sorted[i];
      if (!current.box) {
        keep.push(current);
        continue;
      }

      let shouldKeep = true;
      for (let j = 0; j < keep.length; j++) {
        const kept = keep[j];
        if (!kept.box) continue;

        // Only suppress if same category/label
        const currentLabel = (current.label || current.category || '').toLowerCase();
        const keptLabel = (kept.label || kept.category || '').toLowerCase();
        if (currentLabel !== keptLabel) continue;

        const overlap = iou(current.box, kept.box);
        if (overlap > iouThreshold) {
          shouldKeep = false;
          break;
        }
      }

      if (shouldKeep) {
        keep.push(current);
      }
    }

    return keep;
  };

  const updateTracks = (newDets) => {
    const tracks = tracksRef.current.slice();
    const used = new Array(newDets.length).fill(false);

    // Match existing tracks to new detections
    tracks.forEach(t => {
      let bestIdx = -1;
      let bestScore = 0;
      newDets.forEach((d, i) => {
        if (used[i]) return;
        if (t.label !== (d.label || d.category)) return;
        const score = iou(t.box, d.box || { x:0,y:0,width:0,height:0 });
        if (score > bestScore) {
          bestScore = score;
          bestIdx = i;
        }
      });
      if (bestIdx >= 0 && bestScore > 0.2) {
        // Update track
        const d = newDets[bestIdx];
        t.box = d.box;
  t.avg = (t.avg * t.hits + (d.confidence || 0)) / (t.hits + 1);
  t.lastConf = d.confidence || t.lastConf || 0;
        t.hits += 1;
        t.misses = 0;
        used[bestIdx] = true;
      } else {
        t.misses += 1;
      }
    });

    // Create new tracks for unmatched detections
    newDets.forEach((d, i) => {
      if (used[i]) return;
      const id = Math.random().toString(36).slice(2, 9);
  tracks.push({ id, label: d.label || d.category || 'unknown', box: d.box, avg: d.confidence || 0, hits: 1, misses: 0, lastConf: d.confidence || 0 });
    });

    // Prune stale tracks
    const next = tracks.filter(t => t.misses <= 8);
    tracksRef.current = next;
    return next;
  };

  const analyzeLocal = (ctx, w, h) => {
    // Simple quadrant analysis: infer category by color dominance
    const regions = [
      { x: 0, y: 0, width: Math.floor(w/2), height: Math.floor(h/2) },
      { x: Math.floor(w/2), y: 0, width: Math.ceil(w/2), height: Math.floor(h/2) },
      { x: 0, y: Math.floor(h/2), width: Math.floor(w/2), height: Math.ceil(h/2) },
      { x: Math.floor(w/2), y: Math.floor(h/2), width: Math.ceil(w/2), height: Math.ceil(h/2) },
    ];
    const dets = [];
    regions.forEach(r => {
      const sampleStep = 8;
      let rs=0, gs=0, bs=0, c=0;
      for (let y = r.y; y < r.y + r.height; y += sampleStep) {
        for (let x = r.x; x < r.x + r.width; x += sampleStep) {
          const data = ctx.getImageData(x, y, 1, 1).data;
          rs += data[0]; gs += data[1]; bs += data[2]; c++;
        }
      }
      if (c === 0) return;
      const rmean = rs/c, gmean = gs/c, bmean = bs/c;
      const brightness = (rmean+gmean+bmean)/3;
      let label = 'protein';
      let conf = 0.4;
      if (gmean > rmean && gmean > bmean) { label = 'vegetable'; conf = 0.6 + (gmean - Math.max(rmean,bmean))/255; }
      else if (brightness > 180) { label = 'starch'; conf = 0.6 + (brightness-180)/75; }
      else if (Math.abs(rmean-gmean) < 15 && rmean > bmean) { label = 'protein'; conf = 0.5; }
      conf = Math.max(0.2, Math.min(0.95, conf));
      dets.push({ label, confidence: conf, box: r, category: label });
    });
    return dets;
  };

  const initCamera = async () => {
    setCameraError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        await videoRef.current.play();
      }
      return s;
    } catch (e) {
      console.error('getUserMedia error', e);
      setCameraError(e.name === 'NotAllowedError' ? 'Camera permission denied.' : `Camera error: ${e.message}`);
      return null;
    }
  };

  useEffect(() => {
    let stream;
    (async () => {
      stream = await initCamera();
    })();
    return () => {
      if (stream) stream.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    if (!running) return;
    rollingWindow.current = {};
    let timer;

    const tick = async () => {
      try {
        fpsRef.current.frames += 1;
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video || !canvas || video.readyState < 2) {
          timer = setTimeout(tick, frameIntervalMs);
          return;
        }

        // Draw current frame to canvas
        const w = video.videoWidth;
        const h = video.videoHeight;
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, w, h);

        // Get base64
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);

        let dets = [];
        if (useLocalDetection) {
          dets = analyzeLocal(ctx, w, h);
        } else {
          // Send to backend for analysis
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 5000);
          try {
            const resp = await fetch(`${API_URL}/live/analyze`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ imageBase64: dataUrl }),
              signal: controller.signal
            });
            var json = await resp.json();
          } finally {
            clearTimeout(timeoutId);
          }
          if (json?.success) {
            dets = json.detections || [];
          }
        }
        if (dets.length >= 0) {
          // Apply non-max suppression to remove overlapping boxes
          dets = nonMaxSuppression(dets, 0.5);

          setDetections(dets);

          // Update rolling averages by label
          dets.forEach(d => {
            const key = d.label || d.category || 'unknown';
            if (!rollingWindow.current[key]) rollingWindow.current[key] = { sum: 0, count: 0 };
            rollingWindow.current[key].sum += d.confidence;
            rollingWindow.current[key].count += 1;
          });

          const nextAvg = {};
          Object.entries(rollingWindow.current).forEach(([label, v]) => {
            nextAvg[label] = v.sum / Math.max(1, v.count);
          });
          setAvgByLabel(nextAvg);

          // Update tracks and use their averages for per-box overlays
          let tracks = updateTracks(dets);
          // Sort tracks by avg confidence desc and limit to maxItems
          const maxItems = 10;
          tracks = tracks
            .filter(t => t.box)
            .sort((a,b) => (b.avg||0) - (a.avg||0))
            .slice(0, maxItems);

          // Calculate grams for each track
          const plateGrams = 500; // heuristic: full-frame ~500g of food
          const gramsData = tracks.map(t => {
            const area = (t.box?.width || 0) * (t.box?.height || 0);
            const ratio = area / (w * h);
            const grams = Math.round(Math.max(0, Math.min(plateGrams * ratio, plateGrams)));
            return {
              label: t.label,
              grams,
              areaRatio: ratio,
              confidence: t.avg
            };
          });
          setTrackGrams(gramsData);

          // Draw boxes
          ctx.lineWidth = 2;
          ctx.font = '14px sans-serif';
          const colorFor = (label) => {
            const l = (label||'').toLowerCase();
            if (l.includes('veg')) return '#22c55e';     // green
            if (l.includes('protein')) return '#f97316'; // orange
            if (l.includes('starch') || l.includes('rice') || l.includes('noodle')) return '#3b82f6'; // blue
            return '#a3a3a3'; // gray
          };
          tracks.forEach(t => {
            if (!t.box || (t.avg || 0) < 0.4) return;
            const { x, y, width, height } = t.box;
            ctx.strokeStyle = colorFor(t.label);
            ctx.strokeRect(x, y, width, height);
            const label = t.label || 'unknown';
            const avg = t.avg || 0;
            const labelAvg = nextAvg[label] || avg || 0;
            // Compose value block to the right of the box
            const lines = [
              `${label}`,
              `conf ${(t.lastConf*100||0).toFixed(0)}%`,
              `avg ${(labelAvg*100).toFixed(0)}%`,
            ];
            const pad = 6;
            const lineH = 18;
            const blockW = Math.max(...lines.map(l => ctx.measureText(l).width)) + pad*2;
            const blockH = lines.length * lineH + pad*2;
            const rx = Math.min(w - blockW - 2, x + width + 6); // prefer right side
            const ry = Math.max(2, Math.min(h - blockH - 2, y));
            // Block background
            ctx.fillStyle = 'rgba(0,0,0,0.55)';
            ctx.fillRect(rx, ry, blockW, blockH);
            // Text
            ctx.fillStyle = '#fff';
            lines.forEach((ln, i) => ctx.fillText(ln, rx + pad, ry + pad + lineH*(i+0.7)));
          });
        }
      } catch (e) {
        console.error('analyze tick error', e);
      } finally {
        if (running) timer = setTimeout(tick, frameIntervalMs);
      }
    };

    timer = setTimeout(tick, frameIntervalMs);
    return () => clearTimeout(timer);
  }, [running]);

  const buildDerivedText = () => {
    const video = videoRef.current;
    const w = video?.videoWidth || 1;
    const h = video?.videoHeight || 1;
    const tracks = tracksRef.current || [];
    const plateGrams = 500; // heuristic: full-frame ~500g of food

    const lines = tracks.map(t => {
      const area = (t.box?.width || 0) * (t.box?.height || 0);
      const ratio = area / (w * h);
      const grams = Math.round(Math.max(0, Math.min(plateGrams * ratio, plateGrams)));
      return `${t.label}: avg=${(t.avg*100).toFixed(0)}%, areaRatio=${(ratio*100).toFixed(1)}%, estGrams=${grams}`;
    });

    const summary = Object.entries(avgByLabel)
      .sort((a,b)=>b[1]-a[1])
      .map(([label, avg]) => `${label} avg=${(avg*100).toFixed(0)}%`)
      .join(', ');

    return `Tracks:\n${lines.join('\n')}\nSummary: ${summary}\nAssumptions: total plate ~${plateGrams}g; categories inferred by color.`;
  };

  const estimateMacros = async () => {
    const derivedText = buildDerivedText();
    setMacrosLoading(true);
    setMacrosError('');
    try {
      const resp = await fetch(`${API_URL}/live/macros`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ derivedText })
      });
      const json = await resp.json();
      if (json?.success) {
        const newMacros = json.macros || null;
        setMacros(newMacros);
        setNarrative(json.narrative || '');
        
        // Add to history
        if (newMacros && trackGrams.length > 0) {
          const historyEntry = {
            timestamp: new Date().toLocaleTimeString(),
            macros: newMacros,
            foods: trackGrams.map(t => ({ label: t.label, grams: t.grams }))
          };
          setHistory(prev => [historyEntry, ...prev].slice(0, 5));
        }
      } else {
        setMacrosError(json?.message || 'Failed to estimate macros');
      }
    } catch (e) {
      console.error('macros error', e);
      setMacrosError('Network error estimating macros');
    } finally {
      setMacrosLoading(false);
    }
  };

  // FPS counter
  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - fpsRef.current.lastTime) / 1000;
      setFps((fpsRef.current.frames / elapsed).toFixed(1));
      fpsRef.current.frames = 0;
      fpsRef.current.lastTime = now;
    }, 1000);
    return () => clearInterval(interval);
  }, [running]);

  return (
    <div className="live-view-container">
      {/* Settings Panel */}
      {showSettings && (
        <div className="settings-panel card">
          <h3 className="settings-title">⚙️ Settings</h3>
          <div className="settings-grid">
            <div className="setting-item">
              <label>Frame Rate</label>
              <select 
                value={frameIntervalMs} 
                onChange={e => setFrameIntervalMs(Number(e.target.value))}
                className="setting-select"
              >
                <option value={250}>~4 FPS (Slower)</option>
                <option value={150}>~6-7 FPS (Balanced)</option>
                <option value={100}>~10 FPS (Faster)</option>
              </select>
            </div>
            <div className="setting-item">
              <label className="checkbox-label">
                <input 
                  type="checkbox" 
                  checked={useLocalDetection} 
                  onChange={e => setUseLocalDetection(e.target.checked)} 
                />
                <span>Use Local Detection (Offline Mode)</span>
              </label>
              <p className="setting-hint">Local mode uses color analysis instead of ML</p>
            </div>
          </div>
        </div>
      )}

      {/* Control Bar */}
      <div className="control-bar">
        <div className="control-group">
          <button 
            className={`btn btn-control ${running ? 'btn-stop' : 'btn-start'}`}
            onClick={() => setRunning(v => !v)}
          >
            <span className="btn-icon">{running ? '⏸️' : '▶️'}</span>
            {running ? 'Pause Detection' : 'Start Detection'}
          </button>
          <button 
            className="btn btn-control btn-secondary"
            onClick={estimateMacros} 
            disabled={macrosLoading || (!running && Object.keys(avgByLabel).length === 0)}
          >
            <span className="btn-icon">{macrosLoading ? '⏳' : '🍽️'}</span>
            {macrosLoading ? 'Analyzing...' : 'Estimate Nutrition'}
          </button>
        </div>
        <div className="control-group">
          <div className="fps-badge" title="Frames per second">
            {running ? `${fps} FPS` : '—'}
          </div>
          <button 
            className="btn btn-icon-only"
            onClick={() => setShowSettings(!showSettings)}
            title="Settings"
          >
            ⚙️
          </button>
        </div>
      </div>

      {/* Error Display */}
      {macrosError && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          {macrosError}
        </div>
      )}

      {/* Main Content Grid */}
      <div className="content-grid">
        {/* Video Feed */}
        <div className="video-section card">
          <div className="card-header">
            <h3 className="card-title">📹 Live Feed</h3>
            <div className="legend-compact">
              <span className="legend-item" style={{ '--color': '#22c55e' }}>🥬 Veg</span>
              <span className="legend-item" style={{ '--color': '#f97316' }}>🍗 Protein</span>
              <span className="legend-item" style={{ '--color': '#3b82f6' }}>🍚 Starch</span>
              <span className="legend-item" style={{ '--color': '#a3a3a3' }}>❓ Other</span>
            </div>
          </div>
          {cameraError ? (
            <div className="camera-error">
              <span className="error-icon">📷</span>
              <p className="error-message">{cameraError}</p>
              <button className="btn btn-retry" onClick={initCamera}>
                🔄 Retry Camera
              </button>
            </div>
          ) : (
            <div className="video-wrapper">
              <video ref={videoRef} className="video-element" muted playsInline />
              <canvas ref={canvasRef} className="canvas-overlay" />
              {!running && (
                <div className="video-overlay-message">
                  <p className="overlay-text">Press "Start Detection" to begin</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Detection Stats */}
        <div className="stats-section">
          {trackGrams.length > 0 && (
            <div className="card stats-card">
              <h3 className="card-title">📊 Detected Foods</h3>
              <div className="food-list">
                {trackGrams.map((item, idx) => (
                  <div key={idx} className="food-item">
                    <div className="food-info">
                      <span className="food-emoji">
                        {item.label.toLowerCase().includes('veg') ? '🥬' : 
                         item.label.toLowerCase().includes('protein') ? '🍗' : 
                         item.label.toLowerCase().includes('starch') || item.label.toLowerCase().includes('rice') ? '🍚' : '🍽️'}
                      </span>
                      <div className="food-details">
                        <strong className="food-label">{item.label}</strong>
                        <span className="food-weight">{item.grams}g</span>
                      </div>
                    </div>
                    <div className="confidence-bar-container">
                      <div 
                        className="confidence-bar" 
                        style={{ width: `${(item.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="confidence-text">{(item.confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Macros Display */}
          {macros && (
            <div className="card macros-card">
              <h3 className="card-title">🍱 Nutrition Estimate</h3>
              <div className="macros-grid">
                <div className="macro-item">
                  <div className="macro-icon">🔥</div>
                  <div className="macro-details">
                    <span className="macro-label">Calories</span>
                    <span className="macro-value">{macros.calories || 0}</span>
                    <span className="macro-unit">kcal</span>
                  </div>
                </div>
                <div className="macro-item">
                  <div className="macro-icon">💪</div>
                  <div className="macro-details">
                    <span className="macro-label">Protein</span>
                    <span className="macro-value">{macros.protein || 0}</span>
                    <span className="macro-unit">g</span>
                  </div>
                </div>
                <div className="macro-item">
                  <div className="macro-icon">🌾</div>
                  <div className="macro-details">
                    <span className="macro-label">Carbs</span>
                    <span className="macro-value">{macros.carbs || 0}</span>
                    <span className="macro-unit">g</span>
                  </div>
                </div>
                <div className="macro-item">
                  <div className="macro-icon">🥑</div>
                  <div className="macro-details">
                    <span className="macro-label">Fat</span>
                    <span className="macro-value">{macros.fat || 0}</span>
                    <span className="macro-unit">g</span>
                  </div>
                </div>
              </div>
              {narrative && (
                <div className="narrative-section">
                  <p className="narrative-text">{narrative}</p>
                </div>
              )}
            </div>
          )}

          {/* History */}
          {history.length > 0 && (
            <div className="card history-card">
              <h3 className="card-title">📜 Recent Analyses</h3>
              <div className="history-list">
                {history.map((entry, idx) => (
                  <div key={idx} className="history-entry">
                    <div className="history-time">{entry.timestamp}</div>
                    <div className="history-summary">
                      <span className="history-stat">{entry.macros.calories} kcal</span>
                      <span className="history-separator">•</span>
                      <span className="history-foods">{entry.foods.map(f => f.label).join(', ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
