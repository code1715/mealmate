from fastapi import FastAPI

app = FastAPI(title="order-service")


@app.get("/health")
def health():
    return {"status": "ok"}
