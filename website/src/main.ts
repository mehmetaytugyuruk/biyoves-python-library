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
      <a href="#how-it-works">How it works</a>
      <a href="#standards">Standards</a>
      <a href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">GitHub</a>
    </nav>

    <a class="header-action" href="#studio-section">Open studio <span aria-hidden="true">&#8595;</span></a>
  </header>

  <main id="top">
    <section class="hero section-shell" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow"><span class="eyebrow-dot"></span> Open-source biometric photo studio</p>
        <h1 id="hero-title">Create print-ready biometric photos.</h1>
        <p class="hero-description">Upload a portrait and get a properly sized, background-corrected, 300 DPI photo ready to download and print.</p>

        <div class="hero-actions">
          <a class="hero-primary" href="#studio-section">Open the studio <span aria-hidden="true">&#8595;</span></a>
          <a class="hero-secondary" href="#transformation">See a real result <span aria-hidden="true">&#8599;</span></a>
        </div>

        <div class="trust-row" aria-label="Product highlights">
          <span>No sign-up</span>
          <span>300 DPI output</span>
          <span>JPG &amp; PDF</span>
        </div>
      </div>

      <figure class="hero-output">
        <div class="hero-output-frame">
          <img src="./demo/biyoves-print-sheet.webp" alt="A four-photo biometric print sheet created by BiyoVes" />
        </div>
        <figcaption><span>Real BiyoVes output</span><b>50 × 60 mm · 300 DPI</b></figcaption>
      </figure>
    </section>

    <section class="studio-stage" id="studio-section" aria-labelledby="studio-title">
      <div class="studio-stage-heading section-shell">
        <div>
          <p class="section-index">BiyoVes Studio / Live workspace</p>
          <h2 id="studio-title">Everything you need, in one focused workspace.</h2>
        </div>
        <p>Upload, configure, inspect and download without leaving the page.</p>
      </div>
      <div class="studio-frame section-shell">
        <div class="studio-frame-bar">
          <span>BiyoVes Studio</span>
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
          </div>
          <figcaption>
            <div><span>Everyday portrait</span><b>Mixed background · casual framing</b></div>
            <span>01</span>
          </figcaption>
        </figure>

        <div class="proof-connector" aria-hidden="true"><span></span><b>&#8594;</b></div>

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

    <section class="standards-section" id="standards" aria-labelledby="standards-title">
      <div class="section-shell">
        <div class="section-intro section-intro--row">
          <div>
            <p class="section-index">02 / STANDARDS</p>
            <h2 id="standards-title">Built for official photo formats.</h2>
          </div>
          <p>Choose an existing standard. BiyoVes handles the exact physical dimensions and exports at 300 DPI.</p>
        </div>

        <div class="standards-table">
          ${photoStandards.map((standard, index) => `
            <article class="standard-row">
              <span class="standard-number">0${index + 1}</span>
              <h3>${standard.label}</h3>
              <span class="standard-detail">${standard.detail}</span>
              <strong>${standard.dimensions}</strong>
            </article>
          `).join('')}
        </div>
      </div>
    </section>

    <section class="how-section section-shell" id="how-it-works" aria-labelledby="how-title">
      <div class="section-intro">
        <p class="section-index">03 / HOW IT WORKS</p>
        <h2 id="how-title">One photo. Three simple steps.</h2>
      </div>

      <div class="steps-grid">
        <article>
          <span class="step-number">01</span>
          <div class="step-rule"></div>
          <h3>Upload a portrait</h3>
          <p>Choose a clear JPG or PNG photo taken from the front.</p>
        </article>
        <article>
          <span class="step-number">02</span>
          <div class="step-rule"></div>
          <h3>Select the format</h3>
          <p>Pick the official size, print layout and background.</p>
        </article>
        <article>
          <span class="step-number">03</span>
          <div class="step-rule"></div>
          <h3>Download and print</h3>
          <p>Save a high-quality JPG or a print-ready PDF.</p>
        </article>
      </div>
    </section>

    <section class="principles-section">
      <div class="section-shell principles-grid">
        <article class="principle principle--privacy">
          <p class="section-index">PRIVACY</p>
          <h2>Your photo stays yours.</h2>
          <p>Files are used only to create your result. No account, profile or photo library is created.</p>
          <span class="principle-mark" aria-hidden="true">&#9675;</span>
        </article>

        <article class="principle principle--source">
          <p class="section-index">OPEN SOURCE</p>
          <h2>Built in public.</h2>
          <p>The processing library is free to inspect, use and improve.</p>
          <a href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">Explore the project <span aria-hidden="true">&#8599;</span></a>
        </article>
      </div>
    </section>

    <section class="closing-cta section-shell">
      <p class="section-index">READY WHEN YOU ARE</p>
      <h2>Create your biometric photo.</h2>
      <a href="#studio-section">Open the studio <span aria-hidden="true">&#8593;</span></a>
    </section>
  </main>

  <footer class="site-footer section-shell">
    <a class="brand" href="#top" aria-label="BiyoVes home">
      <span>BiyoVes</span>
    </a>
    <p>Open-source biometric photo studio.</p>
    <div class="footer-links">
      <a href="https://pypi.org/project/biyoves/" target="_blank" rel="noreferrer">PyPI</a>
      <a href="https://github.com/mehmetaytugyuruk/biyoves-python-library" target="_blank" rel="noreferrer">GitHub</a>
    </div>
    <span class="footer-origin">Made in Türkiye</span>
  </footer>
`

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
