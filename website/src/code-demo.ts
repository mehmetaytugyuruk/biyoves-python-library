interface CodeLine {
  plain: string
  html: string
}

interface CodeExample {
  description: string
  result: string
  spec: string
  lines: CodeLine[]
}

const importLine: CodeLine = {
  plain: 'from biyoves import BiyoVes',
  html: '<span class="code-keyword">from</span> biyoves <span class="code-keyword">import</span> BiyoVes',
}

const blankLine: CodeLine = { plain: '', html: '&nbsp;' }

const portraitLine: CodeLine = {
  plain: 'photo = BiyoVes("portrait.jpg")',
  html: 'photo = <span class="code-function">BiyoVes</span>(<span class="code-string">"portrait.jpg"</span>)',
}

const examples: CodeExample[] = [
  {
    description: 'A Python example showing how to create a four-photo biometric print sheet with BiyoVes.',
    result: 'sheet.jpg',
    spec: '4 photos · 300 DPI',
    lines: [
      importLine,
      blankLine,
      portraitLine,
      { plain: 'photo.create_image(', html: 'photo.<span class="code-function">create_image</span>(' },
      { plain: '    photo_type="biyometrik",', html: '    photo_type=<span class="code-string">"biyometrik"</span>,' },
      { plain: '    layout_type="4lu",', html: '    layout_type=<span class="code-string">"4lu"</span>,' },
      { plain: '    output_path="sheet.jpg",', html: '    output_path=<span class="code-string">"sheet.jpg"</span>,' },
      { plain: ')', html: ')' },
    ],
  },
  {
    description: 'A Python example showing how to process an entire portrait folder with BiyoVes.',
    result: 'results/',
    spec: 'Folder complete · 300 DPI',
    lines: [
      importLine,
      blankLine,
      { plain: 'results = BiyoVes.batch_process(', html: 'results = BiyoVes.<span class="code-function">batch_process</span>(' },
      { plain: '    input_dir="portraits/",', html: '    input_dir=<span class="code-string">"portraits/"</span>,' },
      { plain: '    output_dir="results/",', html: '    output_dir=<span class="code-string">"results/"</span>,' },
      { plain: '    photo_type="biyometrik",', html: '    photo_type=<span class="code-string">"biyometrik"</span>,' },
      { plain: '    layout_type="4lu",', html: '    layout_type=<span class="code-string">"4lu"</span>,' },
      { plain: ')', html: ')' },
    ],
  },
  {
    description: 'A Python example showing how to inspect portrait sharpness, eye state and frontal angle.',
    result: 'acceptable: True',
    spec: '3 checks passed',
    lines: [
      importLine,
      blankLine,
      portraitLine,
      { plain: 'report = photo.check_quality()', html: 'report = photo.<span class="code-function">check_quality</span>()' },
      blankLine,
      { plain: '# sharpness · eyes · face angle', html: '<span class="code-comment"># sharpness · eyes · face angle</span>' },
      { plain: 'print(report["is_acceptable"])', html: '<span class="code-function">print</span>(report[<span class="code-string">"is_acceptable"</span>])' },
    ],
  },
]

const wait = (milliseconds: number): Promise<void> => new Promise(
  (resolve) => window.setTimeout(resolve, milliseconds),
)

export function initCodeDemo(): void {
  const canvas = document.querySelector<HTMLElement>('.code-canvas')
  const tabs = [...document.querySelectorAll<HTMLButtonElement>('[data-code-tab]')]
  const code = document.querySelector<HTMLElement>('#live-code')
  const description = document.querySelector<HTMLElement>('#code-example-description')
  const runnerTitle = document.querySelector<HTMLElement>('#runner-title')
  const runnerDetail = document.querySelector<HTMLElement>('#runner-detail')
  const runnerResult = document.querySelector<HTMLElement>('#runner-result')
  const runnerSpec = document.querySelector<HTMLElement>('#runner-spec')

  if (!canvas || !code || !description || !runnerTitle || !runnerDetail || !runnerResult || !runnerSpec) return

  const elements = { canvas, code, description, runnerTitle, runnerDetail, runnerResult, runnerSpec }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
  let animationId = 0
  let activeIndex = 0
  let canvasVisible = true

  function selectTab(index: number): void {
    activeIndex = index
    tabs.forEach((tab, tabIndex) => {
      const selected = tabIndex === index
      tab.classList.toggle('is-active', selected)
      tab.setAttribute('aria-selected', String(selected))
      tab.tabIndex = selected ? 0 : -1
    })
  }

  function renderComplete(example: CodeExample): void {
    elements.code.replaceChildren(...example.lines.map((line, index) => {
      const row = document.createElement('span')
      row.className = 'code-line'
      row.innerHTML = `<span class="line-number">${String(index + 1).padStart(2, '0')}</span><span class="line-content">${line.html}</span>`
      return row
    }))
  }

  function updateRunner(status: 'typing' | 'running' | 'success', example: CodeExample): void {
    elements.canvas.dataset.runner = status
    elements.runnerResult.textContent = example.result
    elements.runnerSpec.textContent = example.spec

    const copy = {
      typing: ['Writing example', 'Building quickstart.py'],
      running: ['Running BiyoVes', 'Executing the open-source pipeline'],
      success: ['Output created', 'The pipeline completed successfully'],
    } as const

    elements.runnerTitle.textContent = copy[status][0]
    elements.runnerDetail.textContent = copy[status][1]
  }

  async function typeCode(example: CodeExample, currentAnimationId: number): Promise<boolean> {
    elements.code.replaceChildren()

    for (const [index, line] of example.lines.entries()) {
      if (currentAnimationId !== animationId) return false

      const row = document.createElement('span')
      const number = document.createElement('span')
      const content = document.createElement('span')
      row.className = 'code-line'
      number.className = 'line-number'
      content.className = 'line-content is-typing'
      number.textContent = String(index + 1).padStart(2, '0')
      row.append(number, content)
      elements.code.append(row)

      if (!line.plain) {
        content.innerHTML = '&nbsp;'
        content.classList.remove('is-typing')
        await wait(45)
        continue
      }

      for (const character of line.plain) {
        if (currentAnimationId !== animationId) return false
        content.textContent += character
        await wait(character === ',' || character === '(' ? 20 : 12)
      }

      content.innerHTML = line.html
      content.classList.remove('is-typing')
      await wait(55)
    }

    return currentAnimationId === animationId
  }

  async function play(index: number, holdAfterSelection = false): Promise<void> {
    const currentAnimationId = ++animationId
    const example = examples[index]
    if (!example) return

    selectTab(index)
    elements.description.textContent = example.description

    if (reducedMotion.matches || !canvasVisible || document.hidden) {
      renderComplete(example)
      updateRunner('success', example)
      return
    }

    elements.canvas.classList.remove('is-playing')
    void elements.canvas.offsetWidth
    elements.canvas.classList.add('is-playing')
    updateRunner('typing', example)
    if (!await typeCode(example, currentAnimationId)) return

    updateRunner('running', example)
    await wait(820)
    if (currentAnimationId !== animationId) return

    updateRunner('success', example)
    await wait(holdAfterSelection ? 7000 : 2300)
    if (currentAnimationId !== animationId || !canvasVisible || document.hidden) return

    void play((index + 1) % examples.length)
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => void play(index, true))
    tab.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      event.preventDefault()
      const direction = event.key === 'ArrowRight' ? 1 : -1
      const nextIndex = (index + direction + tabs.length) % tabs.length
      tabs[nextIndex]?.focus()
      void play(nextIndex, true)
    })
  })

  const restart = (): void => { void play(activeIndex) }
  reducedMotion.addEventListener('change', restart)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      animationId += 1
    } else if (canvasVisible) {
      restart()
    }
  })

  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      const visible = Boolean(entry?.isIntersecting)
      if (visible === canvasVisible) return
      canvasVisible = visible
      if (visible && !document.hidden) restart()
      else animationId += 1
    }, { threshold: 0.1 }).observe(elements.canvas)
  }

  void play(0)
}
