import '@fontsource-variable/instrument-sans/wght.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import './style.css'

import {
  isServiceConfigured,
  processPhoto,
  type ProcessProgress,
  type ProcessResult,
  type QualitySummary,
} from './api'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const MAX_PIXELS = 12_000_000
const ACCEPTED_TYPES = new Set(['image/jpeg', 'image/png'])

const photoStandards = [
  { value: 'biyometrik', label: 'Biometric', dimensions: '50 × 60 mm', detail: 'Standard biometric portrait' },
  { value: 'vesikalik', label: 'ID Photo', dimensions: '45 × 60 mm', detail: 'Turkish ID portrait format' },
  { value: 'abd_vizesi', label: 'US Visa', dimensions: '50 × 50 mm', detail: 'Square visa photo format' },
  { value: 'schengen', label: 'Schengen Visa', dimensions: '35 × 45 mm', detail: 'European visa photo format' },
] as const

const layouts = [
  { value: '2li', label: '2 photos', grid: '2 × 1' },
  { value: '4lu', label: '4 photos', grid: '2 × 2' },
  { value: '6li', label: '6 photos', grid: '3 × 2' },
  { value: '8li', label: '8 photos', grid: '4 × 2' },
] as const

type Screen = 'upload' | 'configure' | 'processing' | 'result' | 'error'

interface AppState {
  screen: Screen
  file?: File
  previewUrl?: string
  photoType: string
  layoutType: string
  background: string
  progress?: ProcessProgress
  result?: ProcessResult
  error?: string
}

const state: AppState = {
  screen: 'upload',
  photoType: 'biyometrik',
  layoutType: '4lu',
  background: 'white',
}

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <header class="site-header">
    <a class="brand" href="#top" aria-label="BiyoVes home">
      <span>BiyoVes</span>
    </a>

    <nav class="main-nav" aria-label="Main navigation">
      <a href="#studio-section">Live studio</a>
      <a href="#transformation">Result</a>
      <a href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">GitHub</a>
    </nav>

    <a class="header-action" href="https://pypi.org/project/biyoves/" target="_blank" rel="noreferrer">View on PyPI</a>
  </header>

  <main id="top">
    <section class="hero section-shell" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow"><span class="eyebrow-dot"></span> Open-source Python library · MIT code</p>
        <h1 id="hero-title">Build print-ready biometric photos with Python.</h1>
        <p class="hero-description">Detect, align, crop and prepare official photo formats with a free Python library—or run the same pipeline directly in your browser.</p>

        <div class="hero-actions">
          <a class="hero-primary" href="#studio-section">Try the live studio <span aria-hidden="true">&#8595;</span></a>
          <a class="hero-secondary" href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">View on GitHub</a>
        </div>

        <div class="install-command" aria-label="Package installation command">
          <span aria-hidden="true">$</span>
          <code>pip install biyoves</code>
          <button type="button" data-copy-install>Copy</button>
        </div>

        <div class="trust-row" aria-label="Product highlights">
          <span>Free &amp; open source</span>
          <span>Python 3.8+</span>
          <span>300 DPI output</span>
        </div>
      </div>

      <section class="code-canvas" aria-label="Interactive BiyoVes Python examples" aria-describedby="code-example-description">
        <header class="code-canvas-header">
          <div class="code-package">
            <span class="code-package-mark" aria-hidden="true">Py</span>
            <div><strong>BiyoVes</strong><small>Open-source package</small></div>
          </div>
          <div class="code-badges" aria-label="Package metadata">
            <span>v1.4.1</span><span>MIT</span><span>PyPI</span>
          </div>
        </header>

        <div class="code-tabs" role="tablist" aria-label="Python usage examples">
          <button class="code-tab is-active" type="button" role="tab" data-code-tab="create" aria-controls="code-example-panel" aria-selected="true">
            <span>01</span><strong>Single photo</strong><i aria-hidden="true"></i>
          </button>
          <button class="code-tab" type="button" role="tab" data-code-tab="batch" aria-controls="code-example-panel" aria-selected="false">
            <span>02</span><strong>Batch</strong><i aria-hidden="true"></i>
          </button>
          <button class="code-tab" type="button" role="tab" data-code-tab="quality" aria-controls="code-example-panel" aria-selected="false">
            <span>03</span><strong>Quality</strong><i aria-hidden="true"></i>
          </button>
        </div>

        <div class="code-editor" id="code-example-panel" role="tabpanel">
          <div class="code-editor-bar"><span>quickstart.py</span><span>Python 3.13</span></div>
          <pre class="live-code" aria-hidden="true"><code id="live-code"></code></pre>
          <p class="sr-only" id="code-example-description">A Python example showing how to create a biometric print sheet with BiyoVes.</p>
        </div>

        <footer class="code-runner" aria-hidden="true">
          <div class="runner-state"><i></i><span><strong id="runner-title">Ready</strong><small id="runner-detail">Waiting to run quickstart.py</small></span></div>
          <div class="runner-result"><span id="runner-result">sheet.jpg</span><strong id="runner-spec">4 photos · 300 DPI</strong></div>
        </footer>
      </section>
    </section>

    <section class="studio-stage" id="studio-section" aria-labelledby="studio-title">
      <div class="studio-stage-heading section-shell">
        <div>
          <p class="section-index">Live library demo / No installation</p>
          <h2 id="studio-title">Run BiyoVes before you install it.</h2>
        </div>
        <p>This interface runs the same open-source processing pipeline available through the Python package.</p>
      </div>
      <div class="studio-frame section-shell">
        <div class="studio-frame-bar">
          <span>BiyoVes / Web interface</span>
          <span class="studio-online ${isServiceConfigured() ? '' : 'is-offline'}"><i></i> ${isServiceConfigured() ? 'Processing service online' : 'Service configuration required'}</span>
          <span>Private session</span>
        </div>
        <div class="studio-workspace" id="studio" aria-live="polite"></div>
      </div>
    </section>

    <section class="transformation section-shell" id="transformation" aria-labelledby="transformation-title">
      <div class="section-intro">
        <p class="section-index">01 / THE RESULT</p>
        <h2 id="transformation-title">From everyday portrait to precise print sheet.</h2>
        <p>BiyoVes detects, aligns and sizes your portrait, cleans the background, then arranges the result for printing.</p>
      </div>

      <div class="proof-flow">
        <figure class="proof-card proof-card--source">
          <div class="proof-image">
            <img src="./demo/synthetic-source.webp" alt="Synthetic source portrait in a busy home interior" loading="lazy" />
            <span class="proof-badge">Before</span>
            <span class="face-guide" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
          </div>
          <figcaption>
            <div><span>Everyday portrait</span><b>Mixed background · casual framing</b></div>
            <span>01</span>
          </figcaption>
        </figure>

        <div class="proof-pipeline" aria-label="BiyoVes processing stages">
          <span class="pipeline-track" aria-hidden="true"><i></i></span>
          <ol>
            <li><span>01</span><strong>Detect</strong></li>
            <li><span>02</span><strong>Align</strong></li>
            <li><span>03</span><strong>Isolate</strong></li>
            <li><span>04</span><strong>Arrange</strong></li>
          </ol>
        </div>

        <figure class="proof-card proof-card--output">
          <div class="proof-image">
            <img src="./demo/biyoves-print-sheet.webp" alt="Four-up biometric print sheet created from the synthetic portrait" loading="lazy" />
            <span class="proof-badge">After</span>
          </div>
          <figcaption>
            <div><span>BiyoVes output</span><b>50 × 60 mm · four-up · 300 DPI</b></div>
            <span>02</span>
          </figcaption>
        </figure>
      </div>

      <p class="proof-disclosure"><span>Synthetic demo subject</span> The source portrait depicts no real person. The output was produced by the public BiyoVes processing service using the same workflow available above.</p>
    </section>

    <section class="closing-cta section-shell" id="install" aria-labelledby="closing-title">
      <div class="closing-copy">
        <p class="section-index">OPEN SOURCE / TWO WAYS TO USE</p>
        <h2 id="closing-title">Use BiyoVes your way.</h2>
        <p>Install the Python package for your own workflow, or process a portrait in the live studio without creating an account.</p>
      </div>

      <div class="closing-options">
        <div class="closing-install" aria-label="Package installation command">
          <span aria-hidden="true">$</span>
          <code>pip install biyoves</code>
          <button type="button" data-copy-install>Copy</button>
        </div>
        <div class="closing-actions">
          <a class="hero-primary" href="#studio-section">Open live studio</a>
          <a class="hero-secondary" href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">View source</a>
        </div>
      </div>
    </section>
  </main>

  <footer class="site-footer section-shell">
    <a class="brand" href="#top" aria-label="BiyoVes home">
      <span>BiyoVes</span>
    </a>
    <p>Open-source biometric photo processing for Python.</p>
    <div class="footer-links">
      <a href="https://pypi.org/project/biyoves/" target="_blank" rel="noreferrer">PyPI</a>
      <a href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">GitHub</a>
    </div>
    <span class="footer-origin">Made in Türkiye</span>
  </footer>
`

document.querySelectorAll<HTMLButtonElement>('[data-copy-install]').forEach((button) => {
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText('pip install biyoves')
      button.textContent = 'Copied'
      window.setTimeout(() => { button.textContent = 'Copy' }, 1600)
    } catch {
      button.textContent = 'pip install biyoves'
    }
  })
})

interface CodeLine {
  plain: string
  html: string
}

interface CodeExample {
  key: string
  description: string
  result: string
  spec: string
  lines: CodeLine[]
}

const codeExamples: CodeExample[] = [
  {
    key: 'create',
    description: 'A Python example showing how to create a four-photo biometric print sheet with BiyoVes.',
    result: 'sheet.jpg',
    spec: '4 photos · 300 DPI',
    lines: [
      { plain: 'from biyoves import BiyoVes', html: '<span class="code-keyword">from</span> biyoves <span class="code-keyword">import</span> BiyoVes' },
      { plain: '', html: '&nbsp;' },
      { plain: 'photo = BiyoVes("portrait.jpg")', html: 'photo = <span class="code-function">BiyoVes</span>(<span class="code-string">"portrait.jpg"</span>)' },
      { plain: 'photo.create_image(', html: 'photo.<span class="code-function">create_image</span>(' },
      { plain: '    photo_type="biyometrik",', html: '    photo_type=<span class="code-string">"biyometrik"</span>,' },
      { plain: '    layout_type="4lu",', html: '    layout_type=<span class="code-string">"4lu"</span>,' },
      { plain: '    output_path="sheet.jpg",', html: '    output_path=<span class="code-string">"sheet.jpg"</span>,' },
      { plain: ')', html: ')' },
    ],
  },
  {
    key: 'batch',
    description: 'A Python example showing how to process an entire portrait folder with BiyoVes.',
    result: 'results/',
    spec: 'Folder complete · 300 DPI',
    lines: [
      { plain: 'from biyoves import BiyoVes', html: '<span class="code-keyword">from</span> biyoves <span class="code-keyword">import</span> BiyoVes' },
      { plain: '', html: '&nbsp;' },
      { plain: 'results = BiyoVes.batch_process(', html: 'results = BiyoVes.<span class="code-function">batch_process</span>(' },
      { plain: '    input_dir="portraits/",', html: '    input_dir=<span class="code-string">"portraits/"</span>,' },
      { plain: '    output_dir="results/",', html: '    output_dir=<span class="code-string">"results/"</span>,' },
      { plain: '    photo_type="biyometrik",', html: '    photo_type=<span class="code-string">"biyometrik"</span>,' },
      { plain: '    layout_type="4lu",', html: '    layout_type=<span class="code-string">"4lu"</span>,' },
      { plain: ')', html: ')' },
    ],
  },
  {
    key: 'quality',
    description: 'A Python example showing how to inspect portrait sharpness, eye state and frontal angle.',
    result: 'acceptable: True',
    spec: '3 checks passed',
    lines: [
      { plain: 'from biyoves import BiyoVes', html: '<span class="code-keyword">from</span> biyoves <span class="code-keyword">import</span> BiyoVes' },
      { plain: '', html: '&nbsp;' },
      { plain: 'photo = BiyoVes("portrait.jpg")', html: 'photo = <span class="code-function">BiyoVes</span>(<span class="code-string">"portrait.jpg"</span>)' },
      { plain: 'report = photo.check_quality()', html: 'report = photo.<span class="code-function">check_quality</span>()' },
      { plain: '', html: '&nbsp;' },
      { plain: '# sharpness · eyes · face angle', html: '<span class="code-comment"># sharpness · eyes · face angle</span>' },
      { plain: 'print(report["is_acceptable"])', html: '<span class="code-function">print</span>(report[<span class="code-string">"is_acceptable"</span>])' },
    ],
  },
]

const codeCanvas = document.querySelector<HTMLElement>('.code-canvas')!
const codeTabs = [...document.querySelectorAll<HTMLButtonElement>('[data-code-tab]')]
const liveCode = document.querySelector<HTMLElement>('#live-code')!
const codeDescription = document.querySelector<HTMLElement>('#code-example-description')!
const runnerTitle = document.querySelector<HTMLElement>('#runner-title')!
const runnerDetail = document.querySelector<HTMLElement>('#runner-detail')!
const runnerResult = document.querySelector<HTMLElement>('#runner-result')!
const runnerSpec = document.querySelector<HTMLElement>('#runner-spec')!
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
let codeAnimationId = 0
let activeCodeIndex = 0

function waitForCodeAnimation(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

function selectCodeTab(index: number): void {
  activeCodeIndex = index
  codeTabs.forEach((tab, tabIndex) => {
    const isSelected = tabIndex === index
    tab.classList.toggle('is-active', isSelected)
    tab.setAttribute('aria-selected', String(isSelected))
    tab.tabIndex = isSelected ? 0 : -1
  })
}

function renderCompleteCode(example: CodeExample): void {
  liveCode.replaceChildren(...example.lines.map((line, index) => {
    const row = document.createElement('span')
    row.className = 'code-line'
    row.innerHTML = `<span class="line-number">${String(index + 1).padStart(2, '0')}</span><span class="line-content">${line.html}</span>`
    return row
  }))
}

function updateRunner(state: 'typing' | 'running' | 'success', example: CodeExample): void {
  codeCanvas.dataset.runner = state
  runnerResult.textContent = example.result
  runnerSpec.textContent = example.spec

  if (state === 'typing') {
    runnerTitle.textContent = 'Writing example'
    runnerDetail.textContent = 'Building quickstart.py'
  } else if (state === 'running') {
    runnerTitle.textContent = 'Running BiyoVes'
    runnerDetail.textContent = 'Executing the open-source pipeline'
  } else {
    runnerTitle.textContent = 'Output created'
    runnerDetail.textContent = 'The pipeline completed successfully'
  }
}

async function typeCode(example: CodeExample, animationId: number): Promise<boolean> {
  liveCode.replaceChildren()

  for (const [index, line] of example.lines.entries()) {
    if (animationId !== codeAnimationId) return false

    const row = document.createElement('span')
    const number = document.createElement('span')
    const content = document.createElement('span')
    row.className = 'code-line'
    number.className = 'line-number'
    content.className = 'line-content is-typing'
    number.textContent = String(index + 1).padStart(2, '0')
    row.append(number, content)
    liveCode.append(row)

    if (!line.plain) {
      content.innerHTML = '&nbsp;'
      content.classList.remove('is-typing')
      await waitForCodeAnimation(45)
      continue
    }

    for (const character of line.plain) {
      if (animationId !== codeAnimationId) return false
      content.textContent += character
      await waitForCodeAnimation(character === ',' || character === '(' ? 20 : 12)
    }

    content.innerHTML = line.html
    content.classList.remove('is-typing')
    await waitForCodeAnimation(55)
  }

  return animationId === codeAnimationId
}

async function playCodeExample(index: number, holdAfterSelection = false): Promise<void> {
  const animationId = ++codeAnimationId
  const example = codeExamples[index]
  if (!example) return

  selectCodeTab(index)
  codeDescription.textContent = example.description
  codeCanvas.classList.remove('is-playing')
  void codeCanvas.offsetWidth
  codeCanvas.classList.add('is-playing')

  if (reducedMotion.matches) {
    renderCompleteCode(example)
    updateRunner('success', example)
    return
  }

  updateRunner('typing', example)
  if (!await typeCode(example, animationId)) return

  updateRunner('running', example)
  await waitForCodeAnimation(820)
  if (animationId !== codeAnimationId) return

  updateRunner('success', example)
  await waitForCodeAnimation(holdAfterSelection ? 7000 : 2300)
  if (animationId !== codeAnimationId) return

  void playCodeExample((index + 1) % codeExamples.length)
}

codeTabs.forEach((tab, index) => {
  tab.addEventListener('click', () => void playCodeExample(index, true))
  tab.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const direction = event.key === 'ArrowRight' ? 1 : -1
    const nextIndex = (index + direction + codeTabs.length) % codeTabs.length
    codeTabs[nextIndex]?.focus()
    void playCodeExample(nextIndex, true)
  })
})

reducedMotion.addEventListener('change', () => void playCodeExample(activeCodeIndex))
void playCodeExample(0)

const transformation = document.querySelector<HTMLElement>('#transformation')

if (transformation && 'IntersectionObserver' in window) {
  const transformationObserver = new IntersectionObserver(([entry], observer) => {
    if (!entry?.isIntersecting) return
    transformation.classList.add('is-revealed')
    observer.disconnect()
  }, { threshold: 0.28 })

  transformationObserver.observe(transformation)
} else {
  transformation?.classList.add('is-revealed')
}

const studio = document.querySelector<HTMLDivElement>('#studio')!

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  })[character] ?? character)
}

function getSelectedStandard() {
  return photoStandards.find((standard) => standard.value === state.photoType) ?? photoStandards[0]
}

function getSelectedLayout() {
  return layouts.find((layout) => layout.value === state.layoutType) ?? layouts[1]
}

function renderCropCorners(): string {
  return `
    <span class="crop-corner crop-corner--tl"></span>
    <span class="crop-corner crop-corner--tr"></span>
    <span class="crop-corner crop-corner--bl"></span>
    <span class="crop-corner crop-corner--br"></span>
  `
}

function renderWorkflow(activeStep: number): string {
  const steps = [
    { number: '01', label: 'Input', detail: 'Choose a portrait' },
    { number: '02', label: 'Format', detail: 'Set size and layout' },
    { number: '03', label: 'Output', detail: 'Inspect and download' },
  ]

  return `
    <aside class='workflow-rail' aria-label='Studio progress'>
      <span class='rail-label'>Workflow</span>
      <ol>
        ${steps.map((step, index) => {
          const stepNumber = index + 1
          const className = stepNumber === activeStep ? 'is-active' : stepNumber < activeStep ? 'is-complete' : ''
          return `
            <li class='${className}'>
              <span>${step.number}</span>
              <div><strong>${step.label}</strong><small>${step.detail}</small></div>
            </li>
          `
        }).join('')}
      </ol>
      <p>No account required.<br />Files are temporary.</p>
    </aside>
  `
}

function renderUpload(): string {
  return `
    <div class='workspace-layout'>
      ${renderWorkflow(1)}

      <section class='workspace-canvas workspace-canvas--upload' aria-labelledby='upload-title'>
        <div class='canvas-toolbar'><span>Input canvas</span><span>JPG or PNG</span></div>
        <label class='upload-zone' id='upload-zone' for='photo-input'>
          <input id='photo-input' type='file' accept='image/jpeg,image/png' />
          ${renderCropCorners()}
          <span class='upload-symbol' aria-hidden='true'>&#8593;</span>
          <span class='step-label'>Step 01 / Input</span>
          <strong id='upload-title'>Drop a portrait into the workspace</strong>
          <span>or select one from your device</span>
          <span class='choose-file'>Choose a photo</span>
        </label>
      </section>

      <aside class='workspace-inspector'>
        <span class='inspector-kicker'>Start here</span>
        <h3>Choose a clear portrait.</h3>
        <p>An eye-level photo with visible shoulders gives the studio the best source material. Quality notes will never block your result.</p>
        <dl class='input-specs'>
          <div><dt>File size</dt><dd>Up to 10 MB</dd></div>
          <div><dt>Resolution</dt><dd>Up to 12 MP</dd></div>
          <div><dt>Formats</dt><dd>JPG or PNG</dd></div>
        </dl>
        <span class='inspector-note'>Your file is used only to create the output and is not added to a photo library.</span>
      </aside>
    </div>
  `
}

function renderSettings(): string {
  const standard = getSelectedStandard()
  const layout = getSelectedLayout()
  const serviceNote = isServiceConfigured()
    ? 'Quality notes never block your result.'
    : 'The public processing service is not connected in this build yet.'

  return `
    <div class='workspace-layout'>
      ${renderWorkflow(2)}

      <section class='workspace-canvas' aria-label='Selected portrait preview'>
        <div class='canvas-toolbar'>
          <span>Source portrait</span>
          <button class='text-button' id='replace-photo' type='button'>Replace photo</button>
        </div>
        <div class='original-preview'>
          ${renderCropCorners()}
          <img src='${escapeHtml(state.previewUrl ?? '')}' alt='Selected portrait preview' />
          <span>${escapeHtml(state.file?.name ?? '')}</span>
        </div>
      </section>

      <aside class='workspace-inspector'>
        <span class='inspector-kicker'>Step 02 / Format</span>
        <h3>Prepare the output.</h3>

        <label class='field-label' for='photo-standard'>Photo standard</label>
        <div class='select-wrap'>
          <select id='photo-standard'>
            ${photoStandards.map((item) => `
              <option value='${item.value}' ${item.value === state.photoType ? 'selected' : ''}>${item.label} — ${item.dimensions}</option>
            `).join('')}
          </select>
        </div>
        <p class='field-help'>${standard.detail}</p>

        <label class='field-label' for='sheet-layout'>Sheet layout</label>
        <div class='select-wrap'>
          <select id='sheet-layout'>
            ${layouts.map((item) => `
              <option value='${item.value}' ${item.value === state.layoutType ? 'selected' : ''}>${item.label} — ${item.grid}</option>
            `).join('')}
          </select>
        </div>
        <p class='field-help'>${layout.label} arranged in a ${layout.grid} print grid.</p>

        <fieldset class='background-field'>
          <legend class='field-label'>Background</legend>
          <div class='swatch-options'>
            <label class='swatch-option'>
              <input type='radio' name='background' value='white' ${state.background === 'white' ? 'checked' : ''} />
              <span class='swatch swatch--white'></span>
              <span>White</span>
            </label>
            <label class='swatch-option'>
              <input type='radio' name='background' value='light_gray' ${state.background === 'light_gray' ? 'checked' : ''} />
              <span class='swatch swatch--gray'></span>
              <span>Light gray</span>
            </label>
          </div>
        </fieldset>

        <div class='inspector-summary'>
          <span>${standard.dimensions}</span><span>${layout.grid}</span><span>300 DPI</span>
        </div>
        <button class='primary-action' id='process-photo' type='button' ${isServiceConfigured() ? '' : 'disabled'}>
          Create biometric photo <span aria-hidden='true'>&#8594;</span>
        </button>
        <p class='service-note ${isServiceConfigured() ? '' : 'service-note--pending'}'>${serviceNote}</p>
      </aside>
    </div>
  `
}

function renderProcessing(): string {
  const progress = state.progress ?? {
    stage: 'waking',
    message: 'Connecting to the processing service.',
  }
  const queueText = progress.stage === 'queued' && progress.position !== undefined
    ? ` Position ${Math.max(1, progress.position + 1)}${progress.queueSize ? ` of ${progress.queueSize}` : ''}.`
    : ''

  return `
    <div class='workspace-layout'>
      ${renderWorkflow(3)}

      <section class='workspace-canvas processing-state'>
        <span class='step-label'>Processing live</span>
        <div class='processing-gauge' aria-hidden='true'><span></span></div>
        <h2>${escapeHtml(progress.message)}</h2>
        <p>${queueText || 'Keep this page open while your print-ready photo is prepared.'}</p>
      </section>

      <aside class='workspace-inspector'>
        <span class='inspector-kicker'>Step 03 / Output</span>
        <h3>Building the print sheet.</h3>
        <ol class='processing-steps'>
          <li class='is-active'><span>01</span>Detect face</li>
          <li><span>02</span>Align portrait</li>
          <li><span>03</span>Clean background</li>
          <li><span>04</span>Create print sheet</li>
        </ol>
        <span class='inspector-note'>The free processing service may briefly queue requests during busy periods.</span>
      </aside>
    </div>
  `
}

function qualityItems(quality: QualitySummary): string {
  const items = [
    { passed: quality.blurPassed, label: 'Sharpness', detail: quality.blurScore === undefined ? '' : `Score ${quality.blurScore.toFixed(1)}` },
    { passed: quality.eyesOpen, label: 'Eyes open', detail: '' },
    { passed: quality.anglePassed, label: 'Frontal angle', detail: quality.angleDegrees === undefined ? '' : `${Math.abs(quality.angleDegrees).toFixed(1)}°` },
  ]

  return items.map((item) => `
    <li class='${item.passed ? 'is-passed' : 'has-warning'}'>
      <span aria-hidden='true'>${item.passed ? '&#10003;' : '!'}</span>
      <div><strong>${item.label}</strong>${item.detail ? `<small>${item.detail}</small>` : ''}</div>
    </li>
  `).join('')
}

function renderResult(): string {
  const result = state.result!
  const standard = getSelectedStandard()

  return `
    <div class='workspace-layout'>
      ${renderWorkflow(3)}

      <section class='workspace-canvas result-preview'>
        <div class='canvas-toolbar'><span>Final print sheet</span><span>${standard.label}</span></div>
        <div class='result-image-stage'>
          <img src='${escapeHtml(result.jpgUrl)}' alt='Completed ${escapeHtml(standard.label)} print sheet' />
        </div>
      </section>

      <aside class='workspace-inspector result-inspector'>
        <div class='result-heading'>
          <span class='inspector-kicker'>Complete</span>
          <button class='text-button' id='start-over' type='button'>Start over</button>
        </div>
        <h3>Your photo is ready.</h3>
        <p>The selected layout is prepared at the correct physical dimensions.</p>

        <dl class='result-specs'>
          <div><dt>Standard</dt><dd>${standard.label}</dd></div>
          <div><dt>Photo size</dt><dd>${standard.dimensions}</dd></div>
          <div><dt>Output</dt><dd>300 DPI</dd></div>
        </dl>

        ${result.quality ? `
          <div class='quality-panel'>
            <div>
              <span class='step-label'>Quality inspector</span>
              <p>${result.quality.acceptable ? 'All three checks passed.' : 'Output created with quality notes.'}</p>
            </div>
            <ul>${qualityItems(result.quality)}</ul>
          </div>
        ` : ''}

        <div class='download-actions'>
          <a class='primary-action' href='${escapeHtml(result.jpgUrl)}' download target='_blank' rel='noreferrer'>Download JPG <span aria-hidden='true'>&#8595;</span></a>
          ${result.pdfUrl ? `<a class='secondary-action' href='${escapeHtml(result.pdfUrl)}' download target='_blank' rel='noreferrer'>Download PDF <span aria-hidden='true'>&#8595;</span></a>` : ''}
        </div>
      </aside>
    </div>
  `
}

function renderError(): string {
  return `
    <div class='workspace-layout'>
      ${renderWorkflow(state.file ? 2 : 1)}
      <section class='workspace-canvas error-state' role='alert'>
        <span class='error-symbol' aria-hidden='true'>!</span>
        <span class='step-label'>Something went wrong</span>
        <h2>We could not create this photo.</h2>
        <p>${escapeHtml(state.error ?? 'Please try again with another photo.')}</p>
      </section>
      <aside class='workspace-inspector'>
        <span class='inspector-kicker'>Recovery</span>
        <h3>Try another source or adjust the format.</h3>
        <div class='error-actions'>
          ${state.file ? '<button class="primary-action" id="retry-settings" type="button">Back to settings</button>' : ''}
          <button class='secondary-action' id='start-over' type='button'>Choose another photo</button>
        </div>
      </aside>
    </div>
  `
}

function renderStudio(): void {
  if (state.screen === 'upload') studio.innerHTML = renderUpload()
  if (state.screen === 'configure') studio.innerHTML = renderSettings()
  if (state.screen === 'processing') studio.innerHTML = renderProcessing()
  if (state.screen === 'result') studio.innerHTML = renderResult()
  if (state.screen === 'error') studio.innerHTML = renderError()
  bindStudioInteractions()
}

async function getImagePixelCount(file: File): Promise<number> {
  if ('createImageBitmap' in window) {
    const bitmap = await createImageBitmap(file)
    const pixels = bitmap.width * bitmap.height
    bitmap.close()
    return pixels
  }

  return new Promise((resolve, reject) => {
    const image = new Image()
    const url = URL.createObjectURL(file)
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image.naturalWidth * image.naturalHeight)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('The selected file could not be read as an image.'))
    }
    image.src = url
  })
}

async function acceptFile(file?: File): Promise<void> {
  if (!file) return

  try {
    if (!ACCEPTED_TYPES.has(file.type)) {
      throw new Error('Please choose a JPG or PNG image.')
    }
    if (file.size > MAX_FILE_SIZE) {
      throw new Error('The photo is larger than 10 MB.')
    }

    const pixels = await getImagePixelCount(file)
    if (pixels > MAX_PIXELS) {
      throw new Error('The photo is larger than 12 megapixels. Please resize it and try again.')
    }

    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl)
    state.file = file
    state.previewUrl = URL.createObjectURL(file)
    state.error = undefined
    state.result = undefined
    state.screen = 'configure'
  } catch (error) {
    state.file = undefined
    state.error = error instanceof Error ? error.message : 'The selected photo could not be read.'
    state.screen = 'error'
  }

  renderStudio()
}

async function startProcessing(): Promise<void> {
  if (!state.file) return

  state.screen = 'processing'
  state.progress = { stage: 'waking', message: 'Connecting to the processing service.' }
  renderStudio()

  try {
    state.result = await processPhoto({
      file: state.file,
      photoType: state.photoType,
      layoutType: state.layoutType,
      background: state.background,
      onProgress: (progress) => {
        state.progress = progress
        renderStudio()
      },
    })
    state.screen = 'result'
  } catch (error) {
    state.error = error instanceof Error ? error.message : 'The photo could not be processed.'
    state.screen = 'error'
  }

  renderStudio()
}

function startOver(): void {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl)
  state.file = undefined
  state.previewUrl = undefined
  state.result = undefined
  state.error = undefined
  state.progress = undefined
  state.screen = 'upload'
  renderStudio()
}

function bindStudioInteractions(): void {
  const input = studio.querySelector<HTMLInputElement>('#photo-input')
  const uploadZone = studio.querySelector<HTMLLabelElement>('#upload-zone')

  input?.addEventListener('change', () => void acceptFile(input.files?.[0]))

  for (const eventName of ['dragenter', 'dragover']) {
    uploadZone?.addEventListener(eventName, (event) => {
      event.preventDefault()
      uploadZone.classList.add('is-dragging')
    })
  }

  for (const eventName of ['dragleave', 'drop']) {
    uploadZone?.addEventListener(eventName, (event) => {
      event.preventDefault()
      uploadZone.classList.remove('is-dragging')
    })
  }

  uploadZone?.addEventListener('drop', (event) => void acceptFile(event.dataTransfer?.files[0]))

  studio.querySelector<HTMLSelectElement>('#photo-standard')?.addEventListener('change', (event) => {
    state.photoType = (event.target as HTMLSelectElement).value
    renderStudio()
  })

  studio.querySelector<HTMLSelectElement>('#sheet-layout')?.addEventListener('change', (event) => {
    state.layoutType = (event.target as HTMLSelectElement).value
    renderStudio()
  })

  for (const radio of studio.querySelectorAll<HTMLInputElement>('input[name="background"]')) {
    radio.addEventListener('change', () => {
      state.background = radio.value
      renderStudio()
    })
  }

  studio.querySelector('#replace-photo')?.addEventListener('click', startOver)
  studio.querySelector('#process-photo')?.addEventListener('click', () => void startProcessing())
  studio.querySelector('#retry-settings')?.addEventListener('click', () => {
    state.screen = 'configure'
    state.error = undefined
    renderStudio()
  })
  studio.querySelector('#start-over')?.addEventListener('click', startOver)
}

renderStudio()
