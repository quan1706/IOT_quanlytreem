package com.babyguard.server.servlet;

import com.babyguard.server.service.LogService;
import com.google.gson.Gson;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.List;

@WebServlet({ "/api/logs", "/api/test-log" })
public class LogApiServlet extends HttpServlet {
    private final Gson gson = new Gson();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String path = request.getRequestURI();
        if (path.endsWith("/test-log")) {
            LogService.addFormattedLog("ManualTest", "Bấm nút Test Log", "Thành công");
            response.setStatus(HttpServletResponse.SC_OK);
            return;
        }

        List<String> logs = LogService.getLogs();
        String json = gson.toJson(logs);

        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");

        try (PrintWriter out = response.getWriter()) {
            out.print(json);
            out.flush();
        }
    }
}
