import uvicorn

if __name__ == "__main__":
    print("=======================================================")
    print("  Korean Vocab Extractor Web App Starting...")
    print("  URL: http://localhost:8000")
    print("=======================================================")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
