export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { code } = req.body || {};
  const valid = process.env.ACCESS_CODE;

  if (!valid) {
    return res.status(500).json({ error: 'ACCESS_CODE not configured' });
  }

  if (code === valid) {
    return res.status(200).json({ ok: true });
  }

  return res.status(401).json({ ok: false });
}
