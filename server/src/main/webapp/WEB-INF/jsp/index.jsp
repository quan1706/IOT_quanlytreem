<%@ page language="java" contentType="text/html; charset=UTF-8" pageEncoding="UTF-8"%>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .status-online { color: #28a745; font-weight: bold; }
        .header-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem 0; margin-bottom: 2rem; }
    </style>
</head>
<body>
    <div class="header-section text-center">
        <h1>👶 Baby Cry Monitor</h1>
        <p>Hệ thống giám sát và chăm sóc trẻ em thông minh</p>
    </div>

    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card p-4">
                    <h3 class="card-title border-bottom pb-2">Trạng thái hệ thống</h3>
                    <div class="mt-3">
                        <p>Tình trạng: <span class="status-online">${status}</span></p>
                        <p>Cảm biến AI: <span class="badge bg-success">Đang hoạt động</span></p>
                        <p>Camera: <span class="badge bg-success">Sẵn sàng</span></p>
                    </div>
                    <hr>
                    <h4>Điều khiển nhanh</h4>
                    <div class="d-flex gap-2">
                        <button class="btn btn-primary">🎵 Phát nhạc</button>
                        <button class="btn btn-warning">🔄 Ru võng</button>
                        <button class="btn btn-danger">⏹ Dừng</button>
                        <button class="btn btn-info">📷 Kiểm tra</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="text-center mt-5 text-muted">
        <p>&copy; 2026 IoT Baby Cry Detector Project</p>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
