from fastapi import FastAPI

app = FastAPI(title="Containerized Help Desk Platform")


@app.get("/")
def root():
    return {
        "message": "Containerized Help Desk Platform API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
