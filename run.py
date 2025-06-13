import uvicorn
import os


def dev():
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", reload=True, port=port)
