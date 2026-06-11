# import os
# import sys

# # Ensure root folder is in sys.path
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# from config.ports import HOST, PORT, DEBUG

# if __name__ == "__main__":
#     import uvicorn
    
#     print("======================================================================")
#     print("      LAUNCHING COMPENSATION CALCULATOR & OCR ASSISTANT")
#     print(f"      Server running at: http://{HOST}:{PORT}/")
#     print(f"      To change ports/hosts, edit config/ports.py")
#     print("======================================================================")
    
#     # Run the Uvicorn server
#     # We disable reload on Windows to prevent recursive folder watching of .venv (which leaks file handles and causes WinError 10055)
#     uvicorn.run(
#         "backend.main:app",
#         host=HOST,
#         port=PORT,
#         reload=False
#     )


import os
import sys

# Force unbuffered stdout/stderr — critical for seeing OCR progress in terminal
# Without this, print() output can be held in a buffer and never appear
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Ensure root folder is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.ports import HOST, PORT, DEBUG

if __name__ == "__main__":
    import uvicorn

    print("======================================================================")
    print("      LAUNCHING COMPENSATION CALCULATOR & OCR ASSISTANT")
    print(f"      Server running at: http://{HOST}:{PORT}/")
    print(f"      To change ports/hosts, edit config/ports.py")
    print("======================================================================")

    # Run the Uvicorn server with explicit log_level so OCR logs are never filtered
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )