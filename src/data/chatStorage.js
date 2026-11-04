let connection

function openChatStorage() {
  connection ||= new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) return reject(new Error('IndexedDB unavailable'))
    const request = indexedDB.open('science-workbench-chat', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('workspace')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
  return connection
}

export async function loadChatState(scope) {
  const db = await openChatStorage()
  return new Promise((resolve, reject) => {
    const request = db.transaction('workspace').objectStore('workspace').get(scope)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function saveChatState(scope, state) {
  const db = await openChatStorage()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('workspace', 'readwrite')
    transaction.oncomplete = resolve
    transaction.onabort = () => reject(transaction.error)
    transaction.objectStore('workspace').put(state, scope)
  })
}
