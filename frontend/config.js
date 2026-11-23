// Where the backend API lives (default: Flask on port 5000).
// If port 5000 is already in use on your machine, start the API with FLASK_PORT=5001 and tell the browser once:
//   localStorage.setItem("unispace_api_base", "http://127.0.0.1:5001")   (run it in the browser console)
window.UNISPACE_API_BASE = localStorage.getItem("unispace_api_base") || "http://127.0.0.1:5000";
