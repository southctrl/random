"use client"

import { useState, useEffect, useCallback } from "react"

export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const [storedValue, setStoredValue] = useState<T>(initialValue)
  const [isInitialized, setIsInitialized] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") return

    try {
      const item = window.localStorage.getItem(key)
      if (item) {
        if (item === 'null') {
          setStoredValue(null as T)
        } else if (item === 'true') {
          setStoredValue(true as T)
        } else if (item === 'false') {
          setStoredValue(false as T)
        } else if (!isNaN(Number(item)) && item.trim() !== '') {
          setStoredValue(Number(item) as T)
        } else if ((item.startsWith('{') && item.endsWith('}')) || 
                   (item.startsWith('[') && item.endsWith(']'))) {
          try {
            setStoredValue(JSON.parse(item))
          } catch (parseError) {
            console.error(`Error parsing localStorage key "${key}", clearing corrupted data:`, parseError)
            window.localStorage.removeItem(key)
          }
        } else if (item.startsWith('"') && item.endsWith('"')) {
          try {
            setStoredValue(JSON.parse(item))
          } catch (parseError) {
            console.error(`Error parsing quoted string for localStorage key "${key}", clearing corrupted data:`, parseError)
            window.localStorage.removeItem(key)
          }
        } else {
          setStoredValue(item as T)
        }
      }
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error)
    }
    setIsInitialized(true)
  }, [key])

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        const valueToStore =
          value instanceof Function ? value(storedValue) : value
        
        setStoredValue(valueToStore)
        
        if (typeof window !== "undefined") {
          let serializedValue: string
          if (typeof valueToStore === 'string') {
            serializedValue = valueToStore
          } else {
            serializedValue = JSON.stringify(valueToStore)
          }
          
          window.localStorage.setItem(key, serializedValue)
          
          window.dispatchEvent(
            new CustomEvent("local-storage-change", {
              detail: { key, value: valueToStore },
            })
          )
        }
      } catch (error) {
        console.error(`Error setting localStorage key "${key}":`, error)
      }
    },
    [key, storedValue]
  )

  const removeValue = useCallback(() => {
    try {
      setStoredValue(initialValue)
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(key)
      }
    } catch (error) {
      console.error(`Error removing localStorage key "${key}":`, error)
    }
  }, [key, initialValue])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        try {
          if (e.newValue === 'null') {
            setStoredValue(null as T)
          } else if (e.newValue === 'true') {
            setStoredValue(true as T)
          } else if (e.newValue === 'false') {
            setStoredValue(false as T)
          } else if (!isNaN(Number(e.newValue)) && e.newValue.trim() !== '') {
            setStoredValue(Number(e.newValue) as T)
          } else if ((e.newValue.startsWith('{') && e.newValue.endsWith('}')) || 
                     (e.newValue.startsWith('[') && e.newValue.endsWith(']'))) {
            setStoredValue(JSON.parse(e.newValue))
          } else if (e.newValue.startsWith('"') && e.newValue.endsWith('"')) {
            setStoredValue(JSON.parse(e.newValue))
          } else {
            setStoredValue(e.newValue as T)
          }
        } catch (parseError) {
          console.error(`Error parsing storage change for key "${key}":`, parseError)
        }
      }
    }

    window.addEventListener("storage", handleStorageChange)
    return () => window.removeEventListener("storage", handleStorageChange)
  }, [key])

  return [storedValue, setValue, removeValue]
}

export function useDiscordToken(): [string, (value: string) => void] {
  const [token, setToken] = useLocalStorage<string>("discord_token", "")
  return [token, setToken]
}
