# Clipmarket web UI

Next.js 15 app for the CLIP marketing library. Talks to `../server.py`.

```bash
# from repo root
python server.py
cd web && npm install && npm run dev
```

Open http://localhost:3000. The Next.js rewrite `/backend/*` proxies to FastAPI on port 8000.
