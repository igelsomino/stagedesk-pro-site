export async function onRequestGet({ env }) {
  return Response.json(
    {
      url: env.SUPABASE_URL || '',
      publishableKey: env.SUPABASE_PUBLISHABLE_KEY || '',
    },
    {
      headers: {
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',
      },
    },
  )
}
