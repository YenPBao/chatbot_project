// Placeholder chat JS
console.log('chat.js loaded');

async function sendEcho(message) {
  try {
    const token = localStorage.getItem('access_token');
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
      },
      body: JSON.stringify({ message }),
    });
    return await res.json();
  } catch (err) {
    return { error: String(err) };
  }
}
