import { useCallback, useEffect, useRef } from 'react'

type Fn = (...args: any[]) => any

export function useDebouncedCallback<T extends Fn>(
  callback: T,
  deps: React.DependencyList,
  delay: number = 250
): (...args: Parameters<T>) => void {
  const callbackRef = useRef(callback)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    callbackRef.current = callback
  })

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
      }
    }
  }, [...deps, delay])

  return useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
      }
      timerRef.current = setTimeout(() => {
        callbackRef.current(...args)
      }, delay)
    },
    [delay, ...deps]
  )
}
