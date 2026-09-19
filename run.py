import uvicorn
import webbrowser
import threading

def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("=======================================================")
    print("  Korean Vocab Extractor Web App Starting...")
    print("  URL: http://127.0.0.1:8000")
    print("=======================================================")
    # サーバー起動とほぼ同時にブラウザを自動で開く
    threading.Timer(1.5, open_browser).start()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

