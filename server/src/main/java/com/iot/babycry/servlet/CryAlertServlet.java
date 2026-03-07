package com.iot.babycry.servlet;

import com.iot.babycry.bot.BabyCryTelegramBot;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.MultipartConfig;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.Part;
import java.io.IOException;

@WebServlet(name = "CryAlertServlet", urlPatterns = "/api/cry")
@MultipartConfig
public class CryAlertServlet extends HttpServlet {

    private BabyCryTelegramBot telegramBot;

    @Override
    public void init() throws ServletException {
        telegramBot = (BabyCryTelegramBot) getServletContext().getAttribute("telegramBot");
    }

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        try {
            Part filePart = req.getPart("image");
            if (filePart != null) {
                byte[] bytes = filePart.getInputStream().readAllBytes();
                if (telegramBot != null) {
                    telegramBot.sendAlertWithPhoto(bytes);
                    resp.setStatus(HttpServletResponse.SC_OK);
                    resp.getWriter().write("Alert received and forwarded to Telegram via Standard Servlet");
                } else {
                    resp.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
                    resp.getWriter().write("Telegram Bot not initialized");
                }
            } else {
                resp.setStatus(HttpServletResponse.SC_BAD_REQUEST);
                resp.getWriter().write("Missing image parameter");
            }
        } catch (Exception e) {
            resp.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            resp.getWriter().write("Failed to process image: " + e.getMessage());
        }
    }
}
