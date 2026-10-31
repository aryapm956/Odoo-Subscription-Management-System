import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'

export function useApi(path, params, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)

  const paramsKey = useMemo(() => JSON.stringify(params || {}), [params])
  const depsKey = useMemo(() => JSON.stringify(deps), [deps])

  useEffect(() => {
    if (!path) {
      setLoading(false)
      setData(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError('')
    api(path, { params })
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, paramsKey, depsKey, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, loading, error, reload }
}

export function useRoute() {
  const [hash, setHash] = useState(() => window.location.hash || '#/')

  useEffect(() => {
    const onChange = () => setHash(window.location.hash || '#/')
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return useMemo(() => {
    const raw = hash.replace(/^#/, '') || '/'
    const [path, queryString] = raw.split('?')
    const params = new URLSearchParams(queryString || '')
    return {
      path: path || '/',
      params,
      navigate: (to) => {
        window.location.hash = to.startsWith('#') ? to : `#${to}`
      },
    }
  }, [hash])
}

export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
