from fastapi import FastAPI

app = FastAPI(title="auth-service")


@app.get("/health")
def health():
    return {"status": "ok"}
