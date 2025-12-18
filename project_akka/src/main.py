"""
Project Akka - FastAPI Entrypoint
Board Game Assistant for NVIDIA Jetson Orin Nano
"""

from fastapi import FastAPI

app = FastAPI(
    title="Project Akka",
    description="Tablet-First Board Game Assistant",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Project Akka is running"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "service": "Project Akka",
        "version": "0.1.0"
    }

＠app.post("/chat")
async def chat():
print("Chat endpoint hit")
# TODO: Add routes for:
# - /chat (main conversation endpoint)
# - /games (list available games)
# - /rules/{game_id} (get game rules)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
