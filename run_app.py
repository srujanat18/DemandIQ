"""
DemandIQ Web Application Server Runner
"""
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"==================================================")
    print(f" DemandIQ Dashboard running at http://127.0.0.1:{port}")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=port, debug=True)
