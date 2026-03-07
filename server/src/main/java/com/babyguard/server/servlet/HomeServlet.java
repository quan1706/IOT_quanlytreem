package com.babyguard.server.servlet;

import com.babyguard.server.config.Config;
import com.babyguard.server.service.LogService;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;

@WebServlet(name = "HomeServlet", urlPatterns = "/")
public class HomeServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        System.out.println("[HomeServlet] Request received at root context path");
        request.setAttribute("title", "Baby Guard Dashboard");
        request.setAttribute("systemStatus", "OPERATIONAL");
        request.setAttribute("time",
                java.time.format.DateTimeFormatter.ofPattern("HH:mm:ss").format(java.time.LocalDateTime.now()));
        request.setAttribute("botName", Config.BOT_USERNAME);
        request.setAttribute("logs", LogService.getLogs());

        request.getRequestDispatcher("/WEB-INF/jsp/index.jsp").forward(request, response);
    }
}
