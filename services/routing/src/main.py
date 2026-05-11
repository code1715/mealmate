from fastapi import FastAPI

app = FastAPI(title="routing-service")


@app.get("/health")
def health():
    return {"status": "ok"}
