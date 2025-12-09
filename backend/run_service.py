import uvicorn

from backend.redirect_state import RedirectState


def main():
    state = RedirectState()
    port = state.get_port()
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
