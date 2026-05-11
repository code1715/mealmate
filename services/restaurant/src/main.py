from fastapi import FastAPI

app = FastAPI(title="restaurant-service")


@app.get("/health")
def health():
    return {"status": "ok"}
