import { useCallback, useEffect, useRef } from 'react'

export function useAbortController() {
  const controllerRef = useRef<AbortController>(new AbortController())

  useEffect(() => {
    return () => {
      controllerRef.current.abort('hook cleanup')
    }
  }, [])

  const abort = useCallback((reason?: string) => {
    controllerRef.current.abort(reason)
  }, [])

  const renew = useCallback(() => {
    if (!controllerRef.current.signal.aborted) {
      controllerRef.current.abort('renewed')
    }
    controllerRef.current = new AbortController()
  }, [])

  return {
    signal: controllerRef.current.signal as AbortSignal,
    abort,
    renew,
    controller: controllerRef,
  }
}
