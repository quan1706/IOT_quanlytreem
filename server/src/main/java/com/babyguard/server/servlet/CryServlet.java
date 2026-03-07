package com.babyguard.server.servlet;

import com.babyguard.server.service.LogService;
import com.babyguard.server.service.TelegramService;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.MultipartConfig;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.Part;

import java.io.IOException;
import java.io.InputStream;

@WebServlet("/api/cry")
@MultipartConfig(fileSizeThreshold = 1024 * 1024 * 1, // 1 MB
        maxFileSize = 1024 * 1024 * 10, // 10 MB
        maxRequestSize = 1024 * 1024 * 15 // 15 MB
)
public class CryServlet extends HttpServlet {
    private final TelegramService telegramService = new TelegramService();

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        Part imagePart = request.getPart("image");
        String label = request.getParameter("label");
        if (label == null)
            label = "baby_cry"; // Ensure label is not null for caption

        LogService.addFormattedLog("ESP32", "Gửi cảnh báo (" + label + ")", "Đã nhận & xử lý");
        LogService.addLog("[CryServlet] - Kích thước ảnh: " + (imagePart != null ? imagePart.getSize() : 0) + " bytes");

        if (imagePart == null) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST, "Missing image part");
            return;
        }

        try (InputStream inputStream = imagePart.getInputStream()) {
            byte[] imageBytes = inputStream.readAllBytes();

            // 3. Gui thong bao kem anh len Telegram
            String caption = "⚠️ *PHAT HIEN TRE DANG KHOC!*\nLabel: `" + label + "`\nHay chon hanh dong ben duoi:";
            telegramService.sendPhotoWithButtons(imageBytes, caption);

            response.setStatus(HttpServletResponse.SC_OK);
            response.getWriter().println("Alert processed");
        } catch (Exception e) {
            LogService.addLog("[CryServlet] LỖI: " + e.getMessage());
            response.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR, e.getMessage());
        }
    }
}
