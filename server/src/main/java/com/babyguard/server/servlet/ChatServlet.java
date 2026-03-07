package com.babyguard.server.servlet;

import com.babyguard.server.service.LogService;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;

@WebServlet("/chat")
public class ChatServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        request.setAttribute("chatLogs", LogService.getAiChatLogs());
        request.getRequestDispatcher("/WEB-INF/jsp/chat.jsp").forward(request, response);
    }
}
