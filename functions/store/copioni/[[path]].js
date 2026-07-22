export function onRequest() {
  return new Response('Not Found', {
    status: 404,
    headers: { 'Cache-Control': 'no-store' },
  })
}
