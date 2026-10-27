/**
 * clyffy — live face renderer (drive contract v1, adapter #1)
 *
 * WHAT THIS IS
 *   A RENDERER ADAPTER, not the owner of the face. The drive contract
 *   (control_surface.schema.json, authored in Clyffy_Avatar) is the seam.
 *   three-vrm is adapter #1; Unreal is expected to become adapter #2. Neither
 *   may re-define the contract — same law as /infra swapping vLLM · llama.cpp ·
 *   candle behind the brain port.
 *
 * WHAT DRIVES IT  (operator decision 2026-07-27 — the SPLIT)
 *   * viseme_weights   → derived LOCALLY here, from the audio actually playing,
 *                        so lipsync cannot drift from playback.
 *   * expression_state / gaze_target / rest_loop / goggle_state
 *                      → owned by clyffyd, streamed from GET /avatar/state (SSE).
 *                        Degrades to the idle stand-in when no daemon is reachable:
 *                        a presentation surface must never freeze on a dead socket.
 *
 * LAYERING is the contract's, applied in this exact order (contract v1):
 *   expression_state base → viseme_weights max-merge → rest_loop zeros all
 *
 * THE CONSTANTS ARE NOT COPIED
 *   VISEMES and ENVELOPE are read at runtime from control_surface.schema.json,
 *   which `tools/control_surface.py` emits. Two hand-written copies of this
 *   mapping would drift silently — the offline mp4 and this window would
 *   lipsync differently on identical audio. One definition, two readers.
 *
 * ⚠️ ONE HONEST DEVIATION FROM THE OFFLINE PATH
 *   avatar_drive.py normalises the envelope by the WHOLE-CLIP maximum. A live
 *   surface cannot: it has not heard the rest of the utterance yet. This uses a
 *   rolling peak with decay instead (`peak`, PEAK_DECAY). Steady speech tracks
 *   the offline result closely; the first ~200ms of a clip and abrupt loudness
 *   jumps will differ. That is inherent to live, not a bug to be tuned away —
 *   it is recorded here so nobody "fixes" the offline path to match.
 *
 * jawOpen is ALWAYS the jaw BONE, never a shape key (contract v1).
 */
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm'

const $ = (id) => document.getElementById(id)
const setTxt = (id, v) => { const e = $(id); if (e) e.textContent = v }

// ── contract ────────────────────────────────────────────────────────────────
const contract = await fetch('/control_surface.schema.json').then((r) => r.json())
const VISEMES = contract.visemes
const PRESETS = contract.presets || {}
const ENV = contract.envelope
const IDLE = contract.idle || null
if (!VISEMES || !ENV) throw new Error('control_surface.schema.json missing visemes/envelope')
if (!IDLE) console.warn('contract has no `idle` block — head/body will not move (pre-A10 schema)')

const JAW_MAX = THREE.MathUtils.degToRad(ENV.jaw.max_deg)
const PEAK_DECAY = 0.9985   // rolling-peak decay per audio frame (see deviation note)

// ── scene ───────────────────────────────────────────────────────────────────
// ?transparent=1 — the desktop shell composites the face directly onto the desktop, so the
// canvas must carry alpha and the scene must NOT paint a background. Browser/dev use keeps
// the DPN dark studio backdrop so the face is readable on its own.
const TRANSPARENT = new URLSearchParams(location.search).has('transparent')
const stage = $('stage')
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: TRANSPARENT })
if (TRANSPARENT) {
  renderer.setClearColor(0x000000, 0)
  document.documentElement.style.background = 'transparent'
  document.body.style.background = 'transparent'
  document.body.classList.add('transparent')
}
renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
renderer.setSize(innerWidth, innerHeight)
renderer.outputColorSpace = THREE.SRGBColorSpace
stage.appendChild(renderer.domElement)

const scene = new THREE.Scene()
scene.background = TRANSPARENT ? null : new THREE.Color(0x06090b)   // DPN dark studio (canon palette)
const camera = new THREE.PerspectiveCamera(30, innerWidth / innerHeight, 0.01, 50)

// canon light palette: warm key, steel-blue fill, amber rim, teal bounce
const mk = (c, i, pos) => { const l = new THREE.DirectionalLight(c, i); l.position.set(...pos); scene.add(l); return l }
mk(0xfff7ec, 2.1, [0.6, 1.1, 1.4])     // key
mk(0x80aef2, 0.7, [-1.2, 0.3, 0.9])    // steel fill
mk(0xff8c2e, 0.9, [-0.4, 0.7, -1.4])   // amber rim
mk(0x1f7378, 0.5, [0.3, -1.0, 0.6])    // teal bounce
scene.add(new THREE.AmbientLight(0x24333a, 1.0))

// ── load the VRM ────────────────────────────────────────────────────────────
// A failed load must be VISIBLE. Without this the top-level await rejects and the
// HUD sits on "loading vrm…" forever, which reads identical to a slow load.
addEventListener('error', (ev) => setTxt('s-state', `err: ${ev.message}`))
addEventListener('unhandledrejection', (ev) => setTxt('s-state', `err: ${ev.reason?.message ?? ev.reason}`))

setTxt('s-state', 'loading vrm…')
const loader = new GLTFLoader()
loader.register((parser) => new VRMLoaderPlugin(parser))
let gltf
try {
  gltf = await loader.loadAsync('/clyffy.vrm', (p) => {
    if (p.lengthComputable) setTxt('s-state', `vrm ${Math.round((p.loaded / p.total) * 100)}%`)
  })
} catch (err) {
  setTxt('s-state', `vrm load failed: ${err?.message ?? err}`)
  console.error('[clyffy-avatar] VRM load failed', err)
  throw err
}
const vrm = gltf.userData.vrm
if (!vrm) { setTxt('s-state', 'no VRMC_vrm in file'); throw new Error('gltf.userData.vrm missing') }
// ⚠️ VRMUtils.removeUnnecessaryVertices / combineSkeletons are DELIBERATELY NOT RUN.
// This mesh is 4 primitives sharing one skin (body · mouth_interior · teeth · tongue)
// with 43 morph targets. Those optimisers rewrite vertex and joint indices; with the
// teeth on their own primitive, a joint remap detaches them from the jaw and they
// punch through the muzzle the moment jawOpen > 0 — while the body still deforms
// correctly, which is exactly how the bug presented. Blender renders the same
// jawOpen=0.85 cleanly, so the rig is not at fault.
// Re-enable only with a jaw-open frame checked against tools/control_surface.py apply.
const OPTIMISE_SCENE = false
if (OPTIMISE_SCENE) {
  for (const fn of ['removeUnnecessaryVertices', 'combineSkeletons']) {
    try { VRMUtils[fn]?.(gltf.scene) } catch (e) { console.warn(`[clyffy-avatar] VRMUtils.${fn} skipped:`, e.message) }
  }
}
vrm.scene.traverse((o) => { o.frustumCulled = false })
scene.add(vrm.scene)

// VRM 1.0 models face +Z and the camera sits at +Z looking back, so the model already
// faces us — NO corrective rotation here.
//
// Until 2026-07-27 this line was `vrm.scene.rotation.y = Math.PI`, compensating for an
// export that was 55.1° off spec. That hack was wrong twice over: it only ever produced
// a 3/4 view, and rotating the scene does NOT fix the bone axes — so `jawBone.rotation.x`
// was rotating about an axis 55° from the true lateral, giving a pitch/yaw mix that
// swung the teeth sideways through the lip. Fixed at the source in
// Clyffy_Avatar/tools/vrm_export.py; verify with tools/vrm_check.py.

// ── morph-target index: ARKit name -> [{mesh, index}] ───────────────────────
// The pack's VISEMES table addresses ARKit blendshapes BY NAME. The mesh has 4
// primitives, so a single name can live on several three.js meshes.
const morphIndex = new Map()
vrm.scene.traverse((o) => {
  if (!o.isMesh || !o.morphTargetDictionary) return
  for (const [name, idx] of Object.entries(o.morphTargetDictionary)) {
    if (!morphIndex.has(name)) morphIndex.set(name, [])
    morphIndex.get(name).push({ mesh: o, index: idx })
  }
})

// every non-jawOpen key the contract can ask for
// every morph the contract can ask for, from BOTH layers — clearMorphs must reset all of
// them or an expression would smear into the next frame.
const drivenKeys = new Set()
for (const w of Object.values(VISEMES)) for (const k of Object.keys(w)) if (k !== 'jawOpen') drivenKeys.add(k)
for (const p of Object.values(PRESETS)) {
  if (p && typeof p === 'object') for (const k of Object.keys(p)) if (k !== 'jawOpen') drivenKeys.add(k)
}
const missing = [...drivenKeys].filter((k) => !morphIndex.has(k))

const jawBone = vrm.humanoid?.getNormalizedBoneNode('jaw')
// ── A10/B1: the bones the idle drives. Without these the head never moves, which is both why
// the face reads robotic AND why the ears never wobble — the spring chains are authored and
// simulated every frame by vrm.update(dt), they simply had zero excitation.
const headBone  = vrm.humanoid?.getNormalizedBoneNode('head')
const spineBone = vrm.humanoid?.getNormalizedBoneNode('spine')
const chestBone = vrm.humanoid?.getNormalizedBoneNode('chest')
const hipsBone  = vrm.humanoid?.getNormalizedBoneNode('hips')
const hipsRest  = hipsBone ? hipsBone.position.clone() : null
const D2R = Math.PI / 180
const eyeL = vrm.humanoid?.getNormalizedBoneNode('leftEye')
const eyeR = vrm.humanoid?.getNormalizedBoneNode('rightEye')

console.log(`[clyffy-avatar] morph targets: ${morphIndex.size} · driven keys: ${drivenKeys.size}` +
            ` · jaw bone: ${jawBone ? 'yes' : 'NO'}`)
if (missing.length) console.warn('[clyffy-avatar] contract keys with no morph target:', missing)
$('s-warn').innerHTML = missing.length
  ? `<span class="warn">missing morphs: ${missing.length}</span>`
  : (jawBone ? '' : '<span class="warn">no jaw bone — jawOpen inert</span>')

function setMorph (name, value) {
  const hits = morphIndex.get(name)
  if (!hits) return
  for (const h of hits) h.mesh.morphTargetInfluences[h.index] = value
}
function clearMorphs () { for (const k of drivenKeys) setMorph(k, 0) }

// ── framing (mirrors the pack: waist-up default, full-body optional) ────────
const box = new THREE.Box3().setFromObject(vrm.scene)
// A10/B1: figure height scales the idle's vertical bob, which the contract specifies in
// body-heights. Declared HERE and not up with the bones, because `box` is initialised on this
// line — referencing it earlier threw "can't access lexical declaration 'box' before
// initialization" and blanked the page.
const figureH = box.max.y - box.min.y
const H = box.max.y - box.min.y
const headY = vrm.humanoid?.getNormalizedBoneNode('head')?.getWorldPosition(new THREE.Vector3())?.y ?? box.max.y * 0.9
let full = false
function frame () {
  if (full) {
    camera.position.set(0, box.min.y + H * 0.5, H * 2.55)
    camera.lookAt(0, box.min.y + H * 0.5, 0)
  } else {
    camera.position.set(0, headY - H * 0.06, H * 1.45)
    camera.lookAt(0, headY - H * 0.06, 0)
  }
}
frame()
$('framing').onclick = () => {
  full = !full; frame()
  $('framing').textContent = `framing: ${full ? 'full-body' : 'waist-up'}`
}

// ── audio → viseme (the LOCAL half of the split) ────────────────────────────
let actx = null, analyser = null, tdata = null, playing = false
let peak = 1e-6, envSmoothed = 0, currentViseme = 'sil'

function classify (e) {
  for (const c of ENV.classes) if (e < c.max) return c.viseme
  return ENV.classes[ENV.classes.length - 1].viseme
}

async function speak (url) {
  actx ||= new AudioContext()
  await actx.resume()
  const buf = await actx.decodeAudioData(await (await fetch(url)).arrayBuffer())
  const src = actx.createBufferSource()
  src.buffer = buf
  analyser = actx.createAnalyser()
  analyser.fftSize = 1024
  tdata = new Float32Array(analyser.fftSize)
  src.connect(analyser); analyser.connect(actx.destination)
  // rest-state law: the tail returns to rest and holds
  src.onended = () => { playing = false; peak = 1e-6; setTxt('s-state', 'rest') }
  playing = true
  setTxt('s-state', 'speaking')
  src.start()
}
$('play').onclick = () => speak('/voice_sample.wav').catch((e) => {
  console.error(e); setTxt('s-state', 'audio failed')
})

// ?autoplay=1 — speak as soon as the VRM is up. Exists so the lipsync path can be
// verified without depending on click timing (headless/offscreen capture); needs
// chromium --autoplay-policy=no-user-gesture-required.
if (new URLSearchParams(location.search).has('autoplay')) {
  speak('/voice_sample.wav').catch((e) => { console.error(e); setTxt('s-state', `audio failed: ${e.message}`) })
}

// peak witnesses — numeric proof the drive actually moved, not just that it rendered
let peakEnv = 0, peakJaw = 0
const seenVisemes = new Set()

/** RMS → contract envelope. Mirrors avatar_drive.py except for the rolling peak. */
function sampleEnvelope () {
  if (!analyser || !playing) return 0
  analyser.getFloatTimeDomainData(tdata)
  let sum = 0
  for (let i = 0; i < tdata.length; i++) sum += tdata[i] * tdata[i]
  const rms = Math.sqrt(sum / tdata.length)
  peak = Math.max(rms, peak * PEAK_DECAY)          // ← live substitute for clip max
  const norm = Math.min(rms / Math.max(peak, 1e-9), 1)
  return Math.pow(norm, ENV.rms_gamma)
}

// ── state channel — clyffyd GET /avatar/state (SSE) ─────────────────────────
// The daemon owns expression_state / gaze_target / rest_loop / goggle_state; this page
// owns viseme_weights. Frames arriving here are the SAME shape the offline path writes to
// drive_frames.jsonl — contract v1 says "same keys as live".
//
// The face must work with NO daemon: this is a presentation surface, and a dead socket
// must degrade to the idle stand-in rather than freeze. EventSource reconnects on its own.
const DAEMON = new URLSearchParams(location.search).get('daemon') || 'http://127.0.0.1:8787'
let state = { rest_loop: true, expression_state: null, gaze_target: { yaw_deg: 0, pitch_deg: 0 }, goggle_state: 'on-face' }
let stateLinked = false

function applyState (frame) {
  if (!frame || typeof frame !== 'object') return
  state = frame
  stateLinked = true
  setTxt('s-goggles', frame.goggle_state ?? '—')
  setTxt('s-expr', frame.expression_state ?? 'none')
}

function connectState () {
  let es
  try { es = new EventSource(`${DAEMON}/avatar/state`) } catch { return }
  es.addEventListener('state', (e) => {
    try { applyState(JSON.parse(e.data)) } catch (err) { console.warn('[clyffy-avatar] bad state frame', err) }
  })
  es.onopen = () => { setTxt('s-link', 'linked') }
  es.onerror = () => {
    // EventSource retries by itself; just stop claiming we are linked.
    stateLinked = false
    setTxt('s-link', 'no daemon')
    setTxt('s-goggles', '—'); setTxt('s-expr', '—')
  }
}
connectState()

let blinkT = 0, nextBlink = 2 + Math.random() * 3
// Evaluate the contract's IDLE at time t. Mirrors control_surface.idle_pose() exactly — the
// spec is the SSOT so this renderer and the Blender path cannot drift apart, the same reason
// VISEMES and ENVELOPE are read from the schema rather than duplicated here.
function idlePose (t) {
  const sum = (terms) => terms.reduce((acc, [a, f, ph]) => acc + a * Math.sin(2 * Math.PI * f * t + ph), 0)
  const br = IDLE.breath
  return {
    spine_roll:  sum(IDLE.sway.spine_roll_deg),
    spine_pitch: sum(IDLE.sway.spine_pitch_deg),
    hips_roll:   sum(IDLE.sway.hips_roll_deg),
    head_yaw:    sum(IDLE.head.yaw_deg),
    head_pitch:  sum(IDLE.head.pitch_deg),
    head_roll:   sum(IDLE.head.roll_deg),
    chest_pitch: br.chest_pitch_deg * Math.sin(2 * Math.PI * br.hz * t + br.phase),
    hips_rise:   sum(IDLE.bob.hips_rise_bodyheights),
  }
}

// Applied to the VRM's NORMALIZED bones, whose axes are canonical (+X right, +Y up, +Z fwd),
// so roll = Z, pitch = X, yaw = Y. Amplitudes were tuned against the measured reference by
// tools/idle_check.py and verified GREEN: crown X rms 0.0166 vs 0.0168, Y 0.0110 vs 0.0101.
function applyIdlePose (t) {
  if (!IDLE) return
  const p = idlePose(t)
  if (spineBone) { spineBone.rotation.z = p.spine_roll * D2R; spineBone.rotation.x = p.spine_pitch * D2R }
  if (chestBone) { chestBone.rotation.x = p.chest_pitch * D2R }
  if (headBone)  { headBone.rotation.z = p.head_roll * D2R; headBone.rotation.x = p.head_pitch * D2R; headBone.rotation.y = p.head_yaw * D2R }
  if (hipsBone && hipsRest) {
    hipsBone.rotation.z = p.hips_roll * D2R
    hipsBone.position.y = hipsRest.y + p.hips_rise * figureH
  }
}

function idle (dt, t) {
  // Head and body FIRST, so the spring bones downstream of them get their excitation this frame.
  applyIdlePose(t)
  // gaze drift + blink so the face is not a statue while state is unwired
  // Daemon-owned gaze target when linked; drift is layered ON TOP so the face still lives.
  const baseYaw = stateLinked ? (state.gaze_target?.yaw_deg ?? 0) : 0
  const basePitch = stateLinked ? (state.gaze_target?.pitch_deg ?? 0) : 0
  const yaw = THREE.MathUtils.degToRad(baseYaw + 8 * Math.sin(t / 2.5))
  const pitch = THREE.MathUtils.degToRad(basePitch + 3 * Math.sin(t / 3.1 + 0.4))
  if (eyeL) { eyeL.rotation.y = yaw; eyeL.rotation.x = pitch }
  if (eyeR) { eyeR.rotation.y = yaw; eyeR.rotation.x = pitch }
  blinkT += dt
  let blink = 0
  if (blinkT > nextBlink) {
    const p = (blinkT - nextBlink) / 0.12
    if (p >= 1) { blinkT = 0; nextBlink = 2 + Math.random() * 3 } else blink = Math.sin(p * Math.PI)
  }
  setMorph('eyeBlinkLeft', blink); setMorph('eyeBlinkRight', blink)
}

// ── frame loop ──────────────────────────────────────────────────────────────
const clock = new THREE.Clock()
let fpsT = 0, fpsN = 0
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.1)
  const t = clock.elapsedTime

  const raw = sampleEnvelope()
  // 3-tap smoothing collapsed to a 1-pole with the contract's centre weight
  envSmoothed += (raw - envSmoothed) * (playing ? ENV.smooth_kernel[1] : 0.25)
  const e = playing ? envSmoothed : 0

  // ── contract v1 LAYERING ──────────────────────────────────────────────────
  //   expression_state base -> viseme_weights max-merge -> rest_loop zeros all
  // Implemented in that exact order; do not reorder without changing the contract.
  clearMorphs()
  const acc = {}
  let jaw = 0

  // rest_loop zeros the drives, but LOCAL audio wins: if this page is speaking, it is by
  // definition not at rest, whatever the daemon last said.
  const resting = !!state.rest_loop && !playing

  // 1. expression base (daemon-owned)
  if (!resting && state.expression_state && PRESETS[state.expression_state]) {
    for (const [k, v] of Object.entries(PRESETS[state.expression_state])) {
      if (k === 'jawOpen') jaw = Math.max(jaw, v)
      else acc[k] = v
    }
  }

  // 2. viseme_weights max-merged over it (renderer-owned)
  if (playing) {
    currentViseme = classify(e)
    const w = { ...(VISEMES[currentViseme] || {}) }
    const vj = w.jawOpen || 0; delete w.jawOpen
    jaw = Math.max(jaw, vj * (ENV.jaw.scale_base + ENV.jaw.scale_env * e), ENV.jaw.env_floor * e)
    for (const [k, v] of Object.entries(w)) {
      const scaled = v * (ENV.weight_scale.base + ENV.weight_scale.env * e)
      acc[k] = Math.max(acc[k] ?? 0, scaled)
    }
  } else {
    currentViseme = 'sil'
  }

  // 3. rest_loop zeros all
  if (resting) { for (const k of Object.keys(acc)) delete acc[k]; jaw = 0 }

  for (const [k, v] of Object.entries(acc)) setMorph(k, v)
  if (jawBone) jawBone.rotation.x = JAW_MAX * jaw   // +X pitches the chin down
  if (playing) { peakEnv = Math.max(peakEnv, e); peakJaw = Math.max(peakJaw, jaw); seenVisemes.add(currentViseme) }

  idle(dt, t)
  vrm.update(dt)          // spring bones: ears + tail
  renderer.render(scene, camera)

  fpsN++; fpsT += dt
  if (fpsT >= 0.5) {
    setTxt('s-fps', (fpsN / fpsT).toFixed(0)); fpsN = 0; fpsT = 0
    setTxt('s-vis', currentViseme); setTxt('s-env', e.toFixed(2)); setTxt('s-jaw', jaw.toFixed(2))
    // witnesses are read back by the capture harness to prove the drive moved
    document.title = `clyffy — live face | peakEnv=${peakEnv.toFixed(2)} peakJaw=${peakJaw.toFixed(2)} ` +
                     `visemes=${[...seenVisemes].join(',') || 'none'}`
    $('env').style.width = `${Math.round(e * 100)}%`
  }
})

setTxt('s-state', 'rest')
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix()
  renderer.setSize(innerWidth, innerHeight)
})
