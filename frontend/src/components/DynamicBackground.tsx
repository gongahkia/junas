import { useEffect, useRef } from "react"

interface Point { x: number; y: number }

const CLIMB_EMOJIS = ["🧗", "🧗‍♀️", "🧗‍♂️", "💪", "🔥", "🙌", "👏", "🎯", "⛰️", "🪨", "✨", "🏆", "🫡", "😤", "🥳", "👀", "🤝", "💯"]

const TARGET_FPS = 45 // cap below 60 to save CPU; still visually smooth
const FRAME_INTERVAL = 1000 / TARGET_FPS
const MAX_DPR = 1.5

// viewport-tier density: keep mobile light + appropriately scaled
const densityFor = (w: number) => {
  if (w < 480) return { lines: 12, sils: 10, scale: 0.55, font: 16 }
  if (w < 768) return { lines: 18, sils: 16, scale: 0.7, font: 18 }
  if (w < 1280) return { lines: 24, sils: 22, scale: 0.85, font: 20 }
  return { lines: 30, sils: 30, scale: 1, font: 22 }
}

export default function DynamicBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d", { alpha: true })
    if (!ctx) return

    const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR)
    let width = window.innerWidth
    let height = window.innerHeight
    let tier = densityFor(width)

    const applySize = () => {
      width = window.innerWidth
      height = window.innerHeight
      tier = densityFor(width)
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    applySize()

    // actors — defined as plain objects (no class overhead, fewer prop lookups)
    type Line = { points: Point[]; color: string; speed: number; dir: Point; curve: number }
    type Sil = { x: number; y: number; speed: number; size: number; dir: number }
    type Em = { x: number; y: number; emoji: string; opacity: number; speed: number }

    const randDir = (): Point => { const a = Math.random() * Math.PI * 2; return { x: Math.cos(a), y: Math.sin(a) } }

    const mkLine = (): Line => {
      const hues = [20, 28, 36, 200, 160]
      return {
        points: [{ x: Math.random() * width, y: Math.random() * height }],
        color: `hsl(${hues[Math.floor(Math.random() * hues.length)]}, 70%, 55%)`,
        speed: Math.random() * 0.5 + 0.1,
        dir: randDir(),
        curve: 0.1,
      }
    }

    const mkSil = (): Sil => {
      const dir = Math.random() < 0.5 ? -1 : 1
      return {
        dir,
        x: dir === 1 ? -50 : width + 50,
        y: height - Math.random() * (height / 2),
        speed: (Math.random() * 0.5 + 0.5) * dir,
        size: (Math.random() * 15 + 25) * tier.scale,
      }
    }

    let lines: Line[] = Array.from({ length: tier.lines }, mkLine)
    let silhouettes: Sil[] = Array.from({ length: tier.sils }, mkSil)
    const emojis: Em[] = []
    const collisionPairs = new Set<string>()

    const reseed = () => {
      lines = Array.from({ length: tier.lines }, mkLine)
      silhouettes = Array.from({ length: tier.sils }, mkSil)
      collisionPairs.clear()
    }

    const drawLine = (l: Line) => {
      const pts = l.points
      ctx.beginPath()
      ctx.moveTo(pts[0].x, pts[0].y)
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y)
      ctx.strokeStyle = l.color
      ctx.lineWidth = 2
      ctx.stroke()
    }

    const updateLine = (l: Line) => {
      const last = l.points[l.points.length - 1]
      const nx = last.x + l.dir.x * l.speed
      const ny = last.y + l.dir.y * l.speed
      if (Math.random() < l.curve) l.dir = randDir()
      if (nx < 0 || nx > width || ny < 0 || ny > height) {
        l.points = [{ x: Math.random() * width, y: Math.random() * height }]
        l.dir = randDir()
      } else {
        l.points.push({ x: nx, y: ny })
        if (l.points.length > 50) l.points.shift()
      }
    }

    const drawSil = (s: Sil, legPhase: number) => {
      ctx.fillStyle = "rgba(30, 35, 42, 0.75)"
      ctx.strokeStyle = "rgba(30, 35, 42, 0.75)"
      ctx.beginPath()
      ctx.arc(s.x, s.y - s.size / 2, s.size / 8, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillRect(s.x - s.size / 6, s.y - s.size / 3, s.size / 3, s.size / 2)
      const legLen = s.size / 3
      const hip = s.size / 4
      const swing = Math.PI / 6
      ctx.lineWidth = 4
      ctx.beginPath()
      ctx.moveTo(s.x - hip / 2, s.y + s.size / 6)
      ctx.lineTo(
        s.x - hip / 2 + Math.sin(legPhase) * legLen * Math.sin(swing),
        s.y + s.size / 6 + Math.abs(Math.cos(legPhase)) * legLen,
      )
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(s.x + hip / 2, s.y + s.size / 6)
      ctx.lineTo(
        s.x + hip / 2 + Math.sin(legPhase + Math.PI) * legLen * Math.sin(swing),
        s.y + s.size / 6 + Math.abs(Math.cos(legPhase + Math.PI)) * legLen,
      )
      ctx.stroke()
    }

    const updateSil = (s: Sil) => {
      s.x += s.speed
      if (s.dir === 1 && s.x > width + 50) {
        s.x = -50; s.y = height - Math.random() * (height / 2)
      } else if (s.dir === -1 && s.x < -50) {
        s.x = width + 50; s.y = height - Math.random() * (height / 2)
      }
    }

    const checkInteractions = () => {
      for (let i = 0; i < silhouettes.length; i++) {
        const s1 = silhouettes[i]
        for (let j = i + 1; j < silhouettes.length; j++) {
          const s2 = silhouettes[j]
          if (s1.dir === s2.dir) continue
          const d = Math.abs(s1.x - s2.x)
          if (d < 10) {
            const pid = `${i}-${j}`
            if (!collisionPairs.has(pid) && Math.random() < 0.5) {
              emojis.push({
                x: (s1.x + s2.x) / 2,
                y: Math.min(s1.y, s2.y) - 20,
                emoji: CLIMB_EMOJIS[Math.floor(Math.random() * CLIMB_EMOJIS.length)],
                opacity: 1,
                speed: Math.random() * 0.5 + 0.5,
              })
              collisionPairs.add(pid)
            }
          } else if (d > 20) {
            collisionPairs.delete(`${i}-${j}`)
          }
        }
      }
    }

    let rafId = 0
    let lastFrame = 0
    let running = true

    // dev FPS probe
    let fpsFrames = 0
    let fpsStart = performance.now()
    const devProbe = import.meta.env?.DEV

    const tick = (now: number) => {
      if (!running) return
      rafId = requestAnimationFrame(tick)
      const elapsed = now - lastFrame
      if (elapsed < FRAME_INTERVAL) return
      lastFrame = now - (elapsed % FRAME_INTERVAL)

      ctx.clearRect(0, 0, width, height)
      for (let i = 0; i < lines.length; i++) { updateLine(lines[i]); drawLine(lines[i]) }
      const legPhase = (now / 200) % (Math.PI * 2)
      for (let i = 0; i < silhouettes.length; i++) { updateSil(silhouettes[i]); drawSil(silhouettes[i], legPhase) }
      checkInteractions()
      ctx.font = `${tier.font}px Arial`
      // iterate backward so splice doesn't skip
      for (let i = emojis.length - 1; i >= 0; i--) {
        const e = emojis[i]
        e.y -= e.speed
        e.opacity -= 0.02
        if (e.opacity <= 0) { emojis.splice(i, 1); continue }
        ctx.globalAlpha = e.opacity
        ctx.fillText(e.emoji, e.x, e.y)
      }
      ctx.globalAlpha = 1

      if (devProbe) {
        fpsFrames++
        if (now - fpsStart >= 2000) {
          // eslint-disable-next-line no-console
          console.log(`[DynamicBackground] fps≈${(fpsFrames * 1000 / (now - fpsStart)).toFixed(1)} (target ${TARGET_FPS})`)
          fpsFrames = 0; fpsStart = now
        }
      }
    }

    const drawStaticFrame = () => {
      ctx.clearRect(0, 0, width, height)
      for (let i = 0; i < lines.length; i++) drawLine(lines[i])
      for (let i = 0; i < silhouettes.length; i++) drawSil(silhouettes[i], 0)
    }

    const start = () => {
      if (reduced) { drawStaticFrame(); return }
      if (rafId) return
      lastFrame = 0
      fpsStart = performance.now(); fpsFrames = 0
      rafId = requestAnimationFrame(tick)
    }

    const stop = () => {
      running = false
      if (rafId) { cancelAnimationFrame(rafId); rafId = 0 }
      running = true // allow restart
    }

    const onVisibility = () => {
      if (document.hidden) stop(); else start()
    }

    let resizeTimer: number | undefined
    let lastW = width
    const onResize = () => {
      if (resizeTimer) window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => {
        const prevTier = tier
        applySize()
        if (tier !== prevTier || Math.abs(width - lastW) > 80) reseed() // viewport class changed or major width swing
        lastW = width
        if (reduced) drawStaticFrame()
      }, 150)
    }

    document.addEventListener("visibilitychange", onVisibility)
    window.addEventListener("resize", onResize)
    start()

    return () => {
      stop()
      document.removeEventListener("visibilitychange", onVisibility)
      window.removeEventListener("resize", onResize)
      if (resizeTimer) window.clearTimeout(resizeTimer)
    }
  }, [])

  return <canvas ref={canvasRef} className="absolute top-0 left-0 w-full h-full" />
}
