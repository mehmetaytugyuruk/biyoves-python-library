import { Client, handle_file, type SpaceStatus } from '@gradio/client'

const spaceId = import.meta.env.VITE_GRADIO_SPACE?.trim() ?? ''
const PROCESS_ENDPOINT = '/process'
const REQUEST_TIMEOUT_MS = 180_000

export type ProcessStage = 'waking' | 'queued' | 'processing'

export interface ProcessProgress {
  stage: ProcessStage
  message: string
  position?: number
  queueSize?: number
}

export interface QualitySummary {
  acceptable: boolean
  blurPassed: boolean
  blurScore?: number
  eyesOpen: boolean
  anglePassed: boolean
  angleDegrees?: number
}

export interface ProcessResult {
  jpgUrl: string
  pdfUrl?: string
  quality?: QualitySummary
}

export interface ProcessOptions {
  file: File
  photoType: string
  layoutType: string
  background: string
  onProgress: (progress: ProcessProgress) => void
}

let clientPromise: ReturnType<typeof Client.connect> | undefined

export function isServiceConfigured(): boolean {
  return Boolean(spaceId)
}

function describeSpaceStatus(status: SpaceStatus): string | undefined {
  if (status.status === 'sleeping' || status.status === 'starting') {
    return 'Starting the processing service. This may take a moment.'
  }

  if (status.status === 'building') {
    return 'The processing service is updating. Please keep this page open.'
  }

  if (status.status === 'space_error' || status.status === 'paused' || status.status === 'error') {
    return status.message || 'The processing service is temporarily unavailable.'
  }

  return undefined
}

function getClient(onProgress: ProcessOptions['onProgress']) {
  if (!clientPromise) {
    clientPromise = Client.connect(spaceId, {
      events: ['data', 'status'],
      record_history: false,
      status_callback: (status) => {
        const message = describeSpaceStatus(status)
        if (message) onProgress({ stage: 'waking', message })
      },
    })
  }

  return clientPromise
}

function extractFileUrl(value: unknown): string | undefined {
  if (typeof value === 'string') return value
  if (!value || typeof value !== 'object') return undefined

  const file = value as { url?: string; data?: string; path?: string }
  return file.url ?? file.data ?? file.path
}

function parseQuality(value: unknown): QualitySummary | undefined {
  if (!value || typeof value !== 'object') return undefined

  const quality = value as Record<string, unknown>
  const blurScore = typeof quality.blur_score === 'number' ? quality.blur_score : undefined
  const angleDegrees = typeof quality.face_angle_degrees === 'number'
    ? quality.face_angle_degrees
    : undefined

  return {
    acceptable: Boolean(quality.is_acceptable ?? quality.acceptable),
    blurPassed: typeof quality.blur_ok === 'boolean'
      ? quality.blur_ok
      : blurScore === undefined || blurScore >= 80,
    blurScore,
    eyesOpen: quality.eyes_open !== false,
    anglePassed: typeof quality.angle_ok === 'boolean'
      ? quality.angle_ok
      : angleDegrees === undefined || Math.abs(angleDegrees) <= 15,
    angleDegrees,
  }
}

function parseResult(data: unknown): ProcessResult {
  const values = Array.isArray(data) ? data : [data]
  const jpgUrl = extractFileUrl(values[0])

  if (!jpgUrl) {
    throw new Error('The processing service returned an invalid result.')
  }

  return {
    jpgUrl,
    pdfUrl: extractFileUrl(values[1]),
    quality: parseQuality(values[2]),
  }
}

export async function processPhoto(options: ProcessOptions): Promise<ProcessResult> {
  if (!spaceId) {
    throw new Error('The processing service has not been connected yet.')
  }

  const client = await getClient(options.onProgress)
  const submission = client.submit(PROCESS_ENDPOINT, {
    image: handle_file(options.file),
    photo_type: options.photoType,
    layout_type: options.layoutType,
    background: options.background,
  })

  const timeout = window.setTimeout(() => void submission.cancel(), REQUEST_TIMEOUT_MS)
  let result: ProcessResult | undefined

  try {
    for await (const event of submission) {
      if (event.type === 'status') {
        if (event.stage === 'pending') {
          options.onProgress({
            stage: 'queued',
            message: 'Your photo is waiting in the queue.',
            position: event.position,
            queueSize: event.size,
          })
        } else if (event.stage === 'generating' || event.stage === 'streaming') {
          options.onProgress({
            stage: 'processing',
            message: event.progress_data?.[0]?.desc || 'Preparing your biometric photo.',
          })
        } else if (event.stage === 'error') {
          throw new Error('The photo could not be processed. Please try another image.')
        }
      }

      if (event.type === 'data') {
        result = parseResult(event.data)
      }
    }
  } finally {
    window.clearTimeout(timeout)
  }

  if (!result) {
    throw new Error('The processing service did not return a result.')
  }

  return result
}
