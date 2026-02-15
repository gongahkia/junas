import { useEffect, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export default function LiveView() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [running, setRunning] = useState(false);
  const [useLocalDetection, setUseLocalDetection] = useState(false);
  const [detections, setDetections] = useState([]);
  const [avgByLabel, setAvgByLabel] = useState({});
  const [trackGrams, setTrackGrams] = useState([]); // Store grams data per track
  const [macros, setMacros] = useState(null);
  const [narrative, setNarrative] = useState('');
  const [macrosLoading, setMacrosLoading] = useState(false);
  const [macrosError, setMacrosError] = useState('');
  const frameIntervalMs = 150; // ~6-7 fps target; adjustable up to ~100ms for ~10 fps
  const rollingWindow = useRef({}); // { label: { sum, count } }
  const tracksRef = useRef([]); // IoU tracker: [{ id, label, box, avg, hits, misses, lastConf }]

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

  useEffect(() => {
    let stream;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
      } catch (e) {
        console.error('getUserMedia error', e);
      }
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
            if (!t.box) return;
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
        setMacros(json.macros || null);
        setNarrative(json.narrative || '');
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

  return (
    <div>
      {/* Color Legend */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12, padding: '8px 12px', background: '#f9fafb', borderRadius: 6, border: '1px solid #e5e7eb' }}>
        <strong style={{ fontSize: 13, color: '#6b7280' }}>Legend:</strong>
        <div style={{ display: 'flex', gap: 12, fontSize: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 16, background: '#22c55e', borderRadius: 3 }} />
            <span>Vegetables</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 16, background: '#f97316', borderRadius: 3 }} />
            <span>Protein</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 16, background: '#3b82f6', borderRadius: 3 }} />
            <span>Starch/Rice</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 16, background: '#a3a3a3', borderRadius: 3 }} />
            <span>Unknown</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
        <button onClick={() => setRunning((v) => !v)}>{running ? 'Stop' : 'Start'} Live</button>
        <label style={{ display:'inline-flex', alignItems:'center', gap:6 }}>
          <input type="checkbox" checked={useLocalDetection} onChange={e=>setUseLocalDetection(e.target.checked)} />
          Use local detection
        </label>
        <button onClick={estimateMacros} disabled={macrosLoading || (!running && Object.keys(avgByLabel).length === 0)}>
          {macrosLoading ? '⏳ Estimating...' : 'Estimate Macros'}
        </button>
      </div>

      {macrosError && (
        <div style={{ background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca', borderRadius: 6, padding: '8px 12px', marginBottom: 8 }}>
          {macrosError}
        </div>
      )}

      <div style={{ position: 'relative', width: '100%', maxWidth: 900 }}>
        <video ref={videoRef} style={{ width: '100%', border: '1px solid #ccc' }} muted playsInline />
        <canvas ref={canvasRef} style={{ position: 'absolute', left: 0, top: 0 }} />
      </div>

      <div style={{ marginTop: 12 }}>
        <strong>Rolling averages:</strong>
        <pre style={{ background: '#f5f5f5', padding: 8 }}>
{JSON.stringify(avgByLabel, null, 2)}
        </pre>
      </div>

      {trackGrams.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <strong>Estimated grams per item:</strong>
          <div style={{ background: '#f5f5f5', padding: 8, marginTop: 4 }}>
            {trackGrams.map((item, idx) => (
              <div key={idx} style={{ marginBottom: 6, fontSize: 13 }}>
                <strong>{item.label}</strong>: {item.grams}g
                <span style={{ color: '#6b7280', marginLeft: 8 }}>
                  (area: {(item.areaRatio * 100).toFixed(1)}%, conf: {(item.confidence * 100).toFixed(0)}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {macros && (
        <div style={{ marginTop: 12 }}>
          <strong>Estimated Macros:</strong>
          <pre style={{ background: '#f5f5f5', padding: 8 }}>
{JSON.stringify(macros, null, 2)}
          </pre>
          {narrative && <p style={{ marginTop: 8 }}>{narrative}</p>}
        </div>
      )}
    </div>
  );
}
